"""Durable conversation state in the existing versioned records store.

Only YES creates a complaint. State, dedup marker, complaint and reply outbox
commit in the worker's single transaction. Conflicting state versions retry.
"""
import hashlib
import re
import time
from sqlalchemy import select
from services.api.db import Record, ProviderMessage, Complaint, Event, Village
from services.api.main import latest, enqueue
from services.api.schemas import ComplaintInput
from services.api.complaints import create_complaint


def phone_key(phone):
    return hashlib.sha256(phone.encode()).hexdigest()


def owned(db, complaint, phone):
    link = latest(db, 'whatsapp_link', phone_key(phone))
    return complaint and (complaint.reporter_id == 'whatsapp:'+phone or
                          bool(link and complaint.reporter_id == link.payload['user_id']))


def intake(db, payload):
    msg = db.get(ProviderMessage, payload['message_id'])
    if latest(db, 'whatsapp_processed', msg.id):
        return {'status': 'already_processed'}
    # Serialize this sender on PostgreSQL; SQLite write conflicts retry as jobs.
    if db.bind.dialect.name == 'postgresql':
        from sqlalchemy import text as sql_text
        lock = int.from_bytes(hashlib.sha256(msg.sender.encode()).digest()[:8], 'big', signed=True)
        db.execute(sql_text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
        if latest(db, 'whatsapp_processed', msg.id):
            return {'status': 'already_processed'}
    earlier = db.scalar(select(ProviderMessage.id).outerjoin(
        Record, (Record.kind == 'whatsapp_processed') & (Record.key == ProviderMessage.id)
    ).where(ProviderMessage.sender == msg.sender, ProviderMessage.received_at < msg.received_at,
            Record.id.is_(None)).limit(1))
    if earlier:
        raise ValueError('Earlier sender message must complete first')
    text = msg.payload.get('text', {}).get('body', '').strip()
    command = text.upper()
    key = phone_key(msg.sender)
    old = latest(db, 'whatsapp_conversation', key)
    state = dict(old.payload) if old else {}
    if re.search('[\u0900-\u097f]', text):
        state['language'] = 'mr'
    if command in ('ENGLISH', 'MARATHI'):
        state['language'] = 'mr' if command == 'MARATHI' else 'en'
    mr = state.get('language') == 'mr'

    def say(en, marathi):
        return marathi if mr else en

    def save():
        db.add(Record(kind='whatsapp_conversation', key=key, version=old.version+1 if old else 1, payload=state))

    def reply(message):
        enqueue(db, 'reply:'+msg.id, 'whatsapp_reply', {'to': msg.sender, 'text': message,
                'inbound_timestamp': msg.payload.get('timestamp')})
        db.add(Record(kind='whatsapp_processed', key=msg.id, payload={'processed': True}))
        save()
        return {'status': state.get('step', 'idle')}

    if len(text) > 10000:
        return reply(say('Please shorten your message to 10,000 characters.', 'कृपया संदेश १०,००० अक्षरांपेक्षा लहान ठेवा.'))
    if command in ('SUBSCRIBE', 'UNSUBSCRIBE'):
        consent = latest(db, 'whatsapp_consent', key)
        db.add(Record(kind='whatsapp_consent', key=key, version=consent.version+1 if consent else 1,
                      payload={'opt_in': command == 'SUBSCRIBE', 'provider_message_id': msg.id,
                               'purpose': 'complaint_status_updates'}))
        return reply(say('Status notifications enabled.' if command == 'SUBSCRIBE' else 'Optional notifications stopped.',
                         'स्थिती सूचना सुरू केल्या.' if command == 'SUBSCRIBE' else 'ऐच्छिक सूचना बंद केल्या.'))
    if command.startswith('LINK '):
        code = latest(db, 'whatsapp_link_code', phone_key(text.split(maxsplit=1)[1]))
        if not code or code.payload.get('used') or code.payload['expires_at'] < time.time():
            return reply('Link code invalid or expired. Generate a new code in the farmer app.')
        user_id = code.payload['user_id']
        link = latest(db, 'whatsapp_link', key)
        if link and link.payload['user_id'] != user_id:
            return reply('This WhatsApp account is already linked. Contact support to change it.')
        db.add(Record(kind='whatsapp_link_code', key=code.key, version=code.version+1,
                      payload={**code.payload, 'used': True}))
        if not link:
            db.add(Record(kind='whatsapp_link', key=key, payload={'user_id': user_id}))
        for c in db.scalars(select(Complaint).where(Complaint.reporter_id == 'whatsapp:'+msg.sender)):
            c.reporter_id = user_id
        return reply(say('Linked. Refresh Tickets in the farmer app.', 'जोडणी झाली. अॅपमध्ये तक्रारी रीफ्रेश करा.'))
    if command.startswith('STATUS'):
        parts = text.split(maxsplit=1)
        c = db.get(Complaint, parts[1]) if len(parts) == 2 and len(parts[1]) <= 100 else None
        return reply(f'Reference ID: {c.id}\nReview: {c.review_status}\nService (demo): {c.service_status}\n{c.admin_note}'
                     if owned(db, c, msg.sender) else say('Complaint unavailable. Use STATUS <your reference ID>.', 'तक्रार उपलब्ध नाही. STATUS <तुमचा संदर्भ क्रमांक> पाठवा.'))
    if command == 'CANCEL':
        state = {'language': state.get('language', 'en')}
        return reply(say('Unfinished complaint cancelled. Send NEW to start again.', 'अपूर्ण तक्रार रद्द केली. नवीन तक्रारीसाठी NEW पाठवा.'))
    if command.startswith('REPLY '):
        parts = text.split(maxsplit=2)
        c = db.get(Complaint, parts[1]) if len(parts) == 3 else None
        if not owned(db, c, msg.sender) or len(parts[2]) > 4000:
            return reply('Use REPLY <your reference ID> <clarification up to 4000 characters>.')
        db.add(Event(complaint_id=c.id, actor_id='whatsapp:'+msg.sender, kind='message', note=parts[2]))
        if c.review_status == 'needs_information':
            c.review_status = 'submitted'
        c.version += 1
        return reply('Clarification saved. Reference ID: '+c.id)
    if command in ('HELP', 'ENGLISH', 'MARATHI'):
        return reply(say('NEW: new complaint; CANCEL: discard draft; STATUS <ID>: track; REPLY <ID> <text>: clarification; SUBSCRIBE / UNSUBSCRIBE: notifications; LINK <code>: connect farmer app; MARATHI / ENGLISH: language. Location: village, taluka, district (or LGD:<code>).',
                         'NEW: नवीन तक्रार; CANCEL: रद्द; STATUS <ID>: स्थिती; REPLY <ID> <माहिती>: अधिक माहिती; SUBSCRIBE / UNSUBSCRIBE: सूचना; LINK <code>: अॅप जोडणी; ENGLISH / MARATHI: भाषा. ठिकाण: गाव, तालुका, जिल्हा.'))
    if command == 'NEW':
        if state.get('step'):
            return reply('A draft is in progress. Continue it or send CANCEL before NEW.')
        state['step'] = 'issue'
        return reply(say('Welcome to JalSathi. What problem are you facing? Include crop and growth stage if relevant.', 'नमस्कार! JalSathi मध्ये स्वागत आहे. आपली समस्या सांगा. संबंधित पीक व वाढीची अवस्था असल्यास सांगा.'))
    if command in ('HI', 'HELLO', 'HEY', 'नमस्कार') and not state.get('step'):
        state['step'] = 'issue'
        return reply(say('Welcome to JalSathi. Describe your farming or water problem.', 'नमस्कार! JalSathi मध्ये स्वागत आहे. शेती किंवा पाण्याची समस्या सांगा.'))
    if msg.payload.get('type') == 'location':
        loc = msg.payload.get('location', {})
        try:
            lat, lon = float(loc['latitude']), float(loc['longitude'])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError()
            state['gps'] = {'latitude': lat, 'longitude': lon}
        except (ValueError, TypeError, KeyError):
            return reply('Invalid GPS location. Please send village, taluka, district.')
        return reply(say('GPS saved. Please also send village, taluka, district.', 'GPS जतन केले. कृपया गाव, तालुका, जिल्हा पाठवा.'))
    if msg.payload.get('type') == 'image':
        image = msg.payload.get('image', {})
        if image.get('mime_type') not in ('image/jpeg', 'image/png') or not re.fullmatch(r'[0-9]{1,100}', image.get('id', '')):
            return reply('Please send a JPEG or PNG photo, or continue with text.')
        images = list(state.get('images', []))
        if len(images) >= 3:
            return reply('Up to three photos per complaint. Continue with text or YES if the summary is correct.')
        state['images'] = list(dict.fromkeys(images+[image['id']]))
        caption = image.get('caption', '').strip()
        if not state.get('issue') and 10 <= len(caption) <= 10000:
            state['issue'] = caption
            state['step'] = 'location'
        return reply(say('Photo queued for inspection after registration. '+('Send YES if the summary is correct.' if state.get('step') == 'confirm' else 'Send village, taluka, district.' if state.get('issue') else 'Please describe the problem.'), 'नोंदणीनंतर फोटो तपासला जाईल. समस्या व गाव, तालुका, जिल्हा पाठवा किंवा सारांश योग्य असल्यास YES पाठवा.'))
    if msg.payload.get('type') != 'text':
        return reply(say('Please send text, a JPEG/PNG photo, or a GPS location.', 'कृपया मजकूर, JPEG/PNG फोटो किंवा GPS ठिकाण पाठवा.'))
    if command.startswith('EDIT '):
        field, _, value = text[5:].partition(' ')
        if field.lower() == 'issue' and len(value) >= 10:
            state['issue'] = value
        elif field.lower() == 'location':
            state.pop('village_id', None)
            state['step'] = 'location'
            text = value
        else:
            return reply('Use EDIT ISSUE <description> or EDIT LOCATION <village, taluka, district>.')
    elif state.get('step') == 'confirm' and command in ('YES', 'हो', 'होय'):
        v = db.get(Village, state['village_id'])
        if not v:
            state.pop('village_id', None)
            state['step'] = 'location'
            return reply('Village unavailable. Please send village, taluka, district again.')
        link = latest(db, 'whatsapp_link', key)
        reporter = link.payload['user_id'] if link else 'whatsapp:'+msg.sender
        issue = state['issue']
        category = 'irrigation' if re.search(r'irrigat|crop|soybean|पीक|शेती|सिंचन', issue, re.I) else ('shortage' if re.search(r'drought|shortage|dry|दुष्काळ|टंचाई', issue, re.I) else 'other')
        c = create_complaint(db, reporter, msg.id, ComplaintInput(village_id=v.id, description=issue, category=category, consent=True), v, 'whatsapp')
        db.flush()
        db.add(Record(kind='whatsapp_complaint', key=c.id, payload={'phone': msg.sender, 'language': state.get('language', 'en'), 'gps': state.get('gps')}))
        for media_id in state.get('images', []):
            enqueue(db, 'media:'+c.id+':'+media_id, 'whatsapp_media', {'complaint_id': c.id, 'media_id': media_id})
        state = {'language': state.get('language', 'en')}
        result = reply(say(f'Complaint registered in JalSathi. Reference ID: {c.id}\nStatus: submitted\nUse STATUS {c.id} or link your farmer app with LINK <code>. Send SUBSCRIBE for optional status updates.',
                           f'तक्रार JalSathi मध्ये नोंदवली. संदर्भ क्रमांक: {c.id}\nस्थिती: submitted\nSTATUS {c.id} पाठवा किंवा LINK <code> वापरून अॅप जोडा. सूचनांसाठी SUBSCRIBE पाठवा.'))
        return {**result, 'complaint_id': c.id}
    elif not state.get('issue'):
        if len(text) < 10:
            state['step'] = 'issue'
            return reply(say('Please describe the problem in a little more detail.', 'कृपया समस्येचे थोडे अधिक वर्णन करा.'))
        state['issue'] = text
        state['step'] = 'location'
        # Accept an explicit directory ID supplied alongside the issue.
        if 'LGD:' not in text:
            return reply(say('Where is the problem? Send village, taluka, district. You may include crop and growth stage in your description using EDIT ISSUE.', 'समस्या कुठे आहे? गाव, तालुका, जिल्हा पाठवा. EDIT ISSUE वापरून पीक व वाढीची अवस्था वर्णनात जोडा.'))

    if not state.get('village_id'):
        match = re.search(r'LGD:([^\s,]+)', text, re.I)
        if match:
            v = db.get(Village, match[1])
        else:
            parts = [p.strip() for p in text.split(',')]
            v = None
            if len(parts) == 3:
                from sqlalchemy import func
                found = list(db.scalars(select(Village).where(func.lower(Village.name) == parts[0].lower(), func.lower(Village.taluka) == parts[1].lower(), func.lower(Village.district) == parts[2].lower()).limit(2)))
                v = found[0] if len(found) == 1 else None
        if not v:
            state['step'] = 'location'
            return reply(say('Location could not be matched uniquely. Send village, taluka, district using directory spelling, or LGD:<official village code>.', 'ठिकाण निश्चित झाले नाही. निर्देशिकेतील नावानुसार गाव, तालुका, जिल्हा किंवा LGD:<गावाचा अधिकृत कोड> पाठवा.'))
        state['village_id'] = v.id
    v = db.get(Village, state['village_id'])
    state['step'] = 'confirm'
    # Keep Meta text bodies below its 4096-character limit.
    summary_issue = state['issue'][:2400] + ('…' if len(state['issue']) > 2400 else '')
    return reply(say(f'Please confirm:\nIssue: {summary_issue}\nVillage: {v.name}\nTaluka: {v.taluka}\nDistrict: {v.district}\nSend YES to register with consent to store these details, EDIT ISSUE <text>, EDIT LOCATION <village, taluka, district>, or CANCEL.',
                     f'कृपया तपशील तपासा:\nसमस्या: {summary_issue}\nगाव: {v.name}\nतालुका: {v.taluka}\nजिल्हा: {v.district}\nतपशील जतन करण्यास संमती देऊन नोंदणीसाठी YES पाठवा. दुरुस्ती: EDIT ISSUE <मजकूर>, EDIT LOCATION <गाव, तालुका, जिल्हा>. रद्द: CANCEL.'))

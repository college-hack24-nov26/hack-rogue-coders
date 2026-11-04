"""Import Meta images through the same private image inspection/storage path."""
import hashlib
from urllib.parse import urlparse
import httpx
from services.api.config import settings
from services.api.db import Complaint, Record
from services.api.main import latest
from services.api.attachments import MAX_BYTES, inspect_image, put_bytes


def import_media(db, payload):
    key = payload['complaint_id']+':'+payload['media_id']
    if latest(db, 'attachment', key):
        return {'status': 'already_imported'}
    if not settings.whatsapp_access_token or not settings.whatsapp_api_version:
        return {'status': 'blocked', 'reason': 'Meta media credentials unavailable'}
    headers = {'Authorization': 'Bearer '+settings.whatsapp_access_token}
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.get(f'https://graph.facebook.com/{settings.whatsapp_api_version}/{payload["media_id"]}', headers=headers)
        response.raise_for_status()
        media = response.json()
        url = urlparse(media['url'])
        host = url.hostname or ''
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443) or not any(host == d or host.endswith('.'+d) for d in ('facebook.com', 'fbcdn.net', 'fbsbx.com')):
            raise ValueError('Untrusted media host')
        if media.get('mime_type') not in ('image/jpeg', 'image/png') or not 0 < int(media['file_size']) <= MAX_BYTES:
            raise ValueError('Unsupported image')
        data = bytearray()
        with client.stream('GET', media['url'], headers=headers) as download:
            download.raise_for_status()
            for chunk in download.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError('Image too large')
        if len(data) != int(media['file_size']):
            raise ValueError('Image size mismatch')
    clean = inspect_image(bytes(data), media['sha256'], media['mime_type'])
    object_key = 'inspected/whatsapp-'+hashlib.sha256(key.encode()).hexdigest()+'.jpg'
    put_bytes(object_key, clean, 'image/jpeg')
    c = db.get(Complaint, payload['complaint_id'])
    db.add(Record(kind='attachment', key=key, payload={'complaint_id': c.id, 'owner_id': c.reporter_id,
                  'object_key': object_key, 'content_type': 'image/jpeg', 'source_sha256': media['sha256'],
                  'sha256': hashlib.sha256(clean).hexdigest(), 'inspection': 'decoded_reencoded_metadata_removed', 'size': len(clean)}))
    return {'status': 'inspected_private'}

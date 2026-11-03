import re
from sqlalchemy import select
from .db import Record

def retrieve_documents(db,question,limit=5):
    tokens={t for t in re.findall(r'[\w\u0900-\u097F]+',question.casefold()) if len(t)>2}
    ranked=[]
    for r in db.scalars(select(Record).where(Record.kind=='document')):
        passage=str(r.payload.get('passage',''));text=passage.casefold();matches=[(text.find(t),t) for t in tokens if t in text]
        if not matches:continue
        offset=max(0,min(p for p,_ in matches)-200);ranked.append((len(matches),r,passage[offset:offset+2000]))
    ranked.sort(key=lambda x:(x[0],x[1].created_at),reverse=True)
    return [{'record_id':r.id,'source':r.payload.get('source'),'source_date':r.payload.get('source_date'),'publication_date':r.payload.get('publication_date'),'passage':passage,'retrieval_method':'lexical_evidence_match'} for _,r,passage in ranked[:limit]]

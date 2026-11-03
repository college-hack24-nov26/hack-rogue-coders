from services.api.db import Record
from services.api.retrieval import retrieve_documents
def test_retrieval_excludes_unrelated_documents(setup):
    _,factory,_=setup
    with factory() as db:
        db.add(Record(kind='document',key='TEST-a',payload={'source':'https://example.test/a','source_date':'2026-10-30','passage':'TEST drip irrigation subsidy reviewed source passage'}))
        db.add(Record(kind='document',key='TEST-b',payload={'source':'https://example.test/b','source_date':'2026-10-30','passage':'TEST completely unrelated historical administration evidence'}));db.commit()
        result=retrieve_documents(db,'drip irrigation subsidy');assert len(result)==1;assert result[0]['source']=='https://example.test/a';assert retrieve_documents(db,'groundwater telemetry unavailable')==[]

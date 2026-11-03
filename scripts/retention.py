"""Preview expired transient records. Never delete reports, audit, forecasts or model lineage."""
import argparse
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from services.api.db import Session,Record
from services.api.config import settings
def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');args=p.parse_args()
    before=(datetime.now(timezone.utc)-timedelta(days=settings.retention_days)).isoformat()
    with Session() as db:
        eligible=list(db.scalars(select(Record).where(Record.kind.in_(['auth_session','ai_trace','source_fetch']),Record.created_at<before)))
        print({'eligible_transient_records':len(eligible),'cutoff':before,'executed':args.execute})
        if args.execute:
            for r in eligible:db.delete(r)
            db.commit()
if __name__=='__main__':main()

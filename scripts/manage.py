"""Operator-only CLI. Never expose role provisioning or source imports as public registration."""
import argparse
import csv
import getpass
import json
from sqlalchemy import select
from services.api.db import Session, User, Village, Record, uid
from services.api.auth import hash_password

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    user=sub.add_parser('create-user');user.add_argument('--email',required=True);user.add_argument('--role',choices=['farmer','admin','official','system_admin'],required=True);user.add_argument('--jurisdictions',default='');user.add_argument('--auth-subject')
    villages=sub.add_parser('import-villages');villages.add_argument('file');villages.add_argument('--source',required=True);villages.add_argument('--version',required=True)
    data=sub.add_parser('import-evidence');data.add_argument('file');data.add_argument('--kind',choices=['market','document','source_fetch','agronomy'],required=True)
    features=sub.add_parser('import-features');features.add_argument('file')
    model=sub.add_parser('register-model');model.add_argument('manifest')
    weather=sub.add_parser('queue-weather');weather.add_argument('--village',required=True)
    args=p.parse_args()
    with Session() as db:
        if args.command=='create-user':
            email=args.email.lower()
            if db.scalar(select(User).where(User.email==email)): raise ValueError('Account already exists')
            password='' if args.auth_subject else getpass.getpass('Local account password (minimum 10 characters): ')
            if not args.auth_subject and len(password)<10: raise ValueError('Password too short')
            db.add(User(id=args.auth_subject or uid(),email=email,password_hash=hash_password(password) if password else '',role=args.role,jurisdictions=[x for x in args.jurisdictions.split(',') if x]))
        elif args.command=='import-villages':
            with open(args.file,encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    if db.get(Village,row['id']): raise ValueError('Existing village: use a reviewed migration for changed geography')
                    db.add(Village(id=row['id'],name=row['name'],district=row['district'],taluka=row['taluka'],jurisdiction=row['jurisdiction'],latitude=float(row['latitude']) if row.get('latitude') else None,longitude=float(row['longitude']) if row.get('longitude') else None,provenance={'source':args.source,'directory_version':args.version}))
        elif args.command=='queue-weather':
            from services.api.planning import weather_grid
            from services.api.main import enqueue
            from datetime import datetime
            from zoneinfo import ZoneInfo
            v=db.get(Village,args.village)
            if not v:raise ValueError('Unknown village')
            grid=weather_grid(v.latitude,v.longitude)
            if not grid:raise ValueError('Coordinates unavailable')
            lat,lon=map(float,grid.split(':'));day=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
            enqueue(db,'weather:'+grid+':'+day,'weather_ingest',{'grid_id':grid,'latitude':lat,'longitude':lon})
        elif args.command=='import-features':
            with open(args.file,encoding='utf-8-sig') as f:items=json.load(f)
            from services.api.main import latest
            for item in items:
                if not db.get(Village,item['village_id']):raise ValueError('Unknown village')
                if not {'values','feature_names','station_id','grid_id','observed_at','issue_time','mapping_verified'}.issubset(item):raise ValueError('Missing feature lineage')
                old=latest(db,'features',item['village_id'])
                db.add(Record(kind='features',key=item['village_id'],version=old.version+1 if old else 1,payload=item))
        elif args.command=='register-model':
            from pathlib import Path
            from services.api.config import settings
            from services.worker.model import ApprovedModel
            with open(args.manifest,encoding='utf-8-sig') as f:manifest=json.load(f)
            root=Path(settings.model_artifact_root).resolve();artifact=(root/manifest['artifact']).resolve()
            if not artifact.is_relative_to(root):raise ValueError('Invalid artifact path')
            ApprovedModel(artifact,manifest)
            db.add(Record(kind='model',key=uid(),payload=manifest))
        else:
            with open(args.file,encoding='utf-8-sig') as f: evidence=json.load(f)
            for item in evidence:
                required={'source','source_date','units','market','variety','price'} if args.kind=='market' else {'source','source_date'}
                if not required.issubset(item): raise ValueError('Evidence missing source/date/units fields')
                record_key=uid();version=1
                if args.kind=='agronomy':
                    if not {'crop','stages','efficiencies','effective_rain_factor','reviewed','reviewer'}.issubset(item) or item['reviewed'] is not True:raise ValueError('Reviewed agronomy definition required')
                    from services.api.main import latest
                    record_key=item['crop'].strip().lower();old=latest(db,'agronomy',record_key);version=old.version+1 if old else 1
                db.add(Record(kind=args.kind,key=record_key,version=version,payload=item))
        db.commit()
    print('Completed')
if __name__=='__main__':main()

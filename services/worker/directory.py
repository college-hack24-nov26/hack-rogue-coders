"""Identity validation shared by operator and worker directory imports."""
SOURCE='https://mahavillages.mahabhumi.gov.in/all_list.php'
ENDPOINT='https://mahavillages.mahabhumi.gov.in/API/GetVillagesOfDistrict'

def normalized_rows(rows, district):
    if not isinstance(rows,list):raise ValueError('Invalid directory response')
    normalized=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid village row')
        if 'villagecode' in row:
            if str(row.get('districtcode','')).strip()!=str(district):raise ValueError('API district mismatch')
            normalized.append({'tlgdVillage':row['villagecode'],'tlgdnameenglish':row.get('villagenameenglish'),'tlgddistrict':row['districtcode'],'tlgdTaluka':row.get('subdistrictcode'),'tlgdstate':'27','source_api_raw':row})
        else:normalized.append(row)
    return normalized

def validate_rows(rows, district, expected=None):
    rows=normalized_rows(rows,district)
    if not rows and expected!=0:raise ValueError('Unexpected empty district response')
    unique={}
    for row in rows:
        key=str(row.get('tlgdVillage','')).strip()
        if not key.isdigit() or not isinstance(row.get('tlgdnameenglish'),str) or not row['tlgdnameenglish'].strip() or str(row.get('tlgdstate','')).strip()!='27' or str(row.get('tlgddistrict','')).strip()!=str(district) or not str(row.get('tlgdTaluka','')).strip().isdigit():
            raise ValueError('Invalid village or district/state mismatch')
        if key in unique:
            for field in ('tlgdnameenglish','tlgddistrict','tlgdTaluka'):
                if str(unique[key].get(field,'')).strip()!=str(row.get(field,'')).strip():raise ValueError('Conflicting duplicate village identity')
        unique[key]=row
    if expected is not None and len(unique)!=expected:raise ValueError('Unique village count does not match official catalogue')
    return unique

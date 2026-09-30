"""Private Supabase Storage, accessed only after Flask permission checks."""
import os
from pathlib import Path
from urllib.parse import quote
import requests

def enabled(): return bool(os.environ.get('DATABASE_URL'))
def config():
    url=os.environ['SUPABASE_URL'].rstrip('/')
    if not url.startswith('https://'): raise RuntimeError('Supabase requires HTTPS')
    return url,os.environ['SUPABASE_SECRET_KEY'],os.environ.get('SUPABASE_BUCKET','inventory-private')
def call(method,path,**kwargs):
    url,key,_=config()
    response=requests.request(method,url+'/storage/v1/'+path,headers={'apikey':key,'Authorization':'Bearer '+key,**kwargs.pop('headers',{})},timeout=60,**kwargs)
    if not response.ok: raise RuntimeError('Private cloud storage request failed (HTTP '+str(response.status_code)+')')
    return response

def upload(root,relative):
    if os.environ.get('TURSO_DATABASE_URL'):
        from app import db
        from turso_files import put
        put(db(),relative,(Path(root)/relative).read_bytes())
        return
    if not enabled(): return
    _,_,bucket=config()
    mime='image/webp' if relative.endswith('.webp') else 'application/octet-stream'
    call('POST','object/'+quote(bucket,safe='')+'/'+quote(relative,safe='/'),data=(Path(root)/relative).read_bytes(),headers={'Content-Type':mime,'x-upsert':'true'})

def local(root,relative):
    path=Path(root)/relative
    if os.environ.get('TURSO_DATABASE_URL'):
        from app import db
        from turso_files import get
        # Fetch source of truth even when a previous failed write left a local file.
        content=get(db(),relative)
        path.parent.mkdir(parents=True,exist_ok=True)
        import tempfile
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
            f.write(content); temp=Path(f.name)
        temp.replace(path)
        return path
    if enabled() and not path.exists():
        _,_,bucket=config()
        payload=call('GET','object/authenticated/'+quote(bucket,safe='')+'/'+quote(relative,safe='/')).content
        path.parent.mkdir(parents=True,exist_ok=True)
        import tempfile
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
            f.write(payload); temp=Path(f.name)
        temp.replace(path)
    return path

def objects(folder):
    _,_,bucket=config(); offset=0
    while True:
        page=call('POST','object/list/'+quote(bucket,safe=''),json={'prefix':folder,'limit':100,'offset':offset,'sortBy':{'column':'name','order':'asc'}}).json()
        for obj in page:
            if obj.get('id'): yield folder+'/'+obj['name']
        if len(page)<100: break
        offset+=100

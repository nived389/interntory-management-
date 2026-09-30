"""Resume-safe upload of a private prepared snapshot to an empty Turso database."""
import hashlib,json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from turso_database import Database
from turso_files import put,get
source_path=Path(sys.argv[1]);source=sqlite3.connect(source_path);source.row_factory=sqlite3.Row
config=json.loads(Path('data/turso-connection.json').read_text())
db=Database(config['TURSO_DATABASE_URL'],config['TURSO_AUTH_TOKEN'])
digest=hashlib.sha256(source_path.read_bytes()).hexdigest()
names={r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
if names:
    state=db.execute("SELECT value FROM settings WHERE key='turso_migration_source'").fetchone() if 'settings' in names else None
    if not state or state['value']!=digest:raise SystemExit('Target is not this migration; refusing overwrite')
else:
    statements=[s for s in source.iterdump() if not s.startswith('INSERT INTO "stored_files"') and not s.startswith('INSERT INTO "stored_file_chunks"')]
    statements.insert(0,'PRAGMA foreign_keys=OFF;')
    # Add state within the initial transaction, before final COMMIT.
    statements.insert(-1,"INSERT INTO settings(key,value) VALUES('turso_migration_source','"+digest+"');")
    statements.insert(-1,"INSERT INTO settings(key,value) VALUES('turso_migration_ready','false');")
    import requests
    endpoint=config['TURSO_DATABASE_URL'].replace('libsql://','https://')+'/v2/pipeline'
    headers={'Authorization':'Bearer '+config['TURSO_AUTH_TOKEN']}
    reply=requests.post(endpoint,headers=headers,json={'requests':[{'type':'execute','stmt':{'sql':sql,'want_rows':False}} for sql in statements[:-1]]},timeout=30)
    reply.raise_for_status();body=reply.json()
    failed=any(result['type']!='ok' for result in body['results'])
    if failed: print('Schema errors:',[(n,r.get('error',{})) for n,r in enumerate(body['results']) if r['type']!='ok'][:3],flush=True)
    finish=requests.post(endpoint,headers=headers,json={'baton':body['baton'],'requests':[{'type':'execute','stmt':{'sql':'ROLLBACK' if failed else 'COMMIT'}},{'type':'close'}]},timeout=30)
    finish.raise_for_status()
    if failed or any(result['type']!='ok' for result in finish.json()['results']):raise RuntimeError('Initial schema transfer failed; rolled back')
    print('Records copied.',flush=True)
files=source.execute('SELECT path FROM stored_files ORDER BY path').fetchall()
for n,row in enumerate(files,1):
    payload=get(source,row['path'])
    db.execute('BEGIN IMMEDIATE')
    try:
        put(db,row['path'],payload)
        if get(db,row['path'])!=payload:raise RuntimeError('File differs after upload')
        db.commit()
    except BaseException:
        db.rollback();raise
    if n%30==0:print(f'Files verified: {n}/{len(files)}',flush=True)
for row in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
    name=row['name'];quoted='"'+name.replace('"','""')+'"'
    local_count=source.execute('SELECT count(*) FROM '+quoted).fetchone()[0]
    remote_count=db.execute('SELECT count(*) AS n FROM '+quoted).fetchone()['n']
    if name=='settings':local_count+=2
    if local_count!=remote_count:raise RuntimeError('Row count mismatch: '+name)
if db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Foreign key verification failed')
db.execute("UPDATE settings SET value='true' WHERE key='turso_migration_ready'");db.commit();db.close()
print('Migration complete. All row counts and file contents verified.',flush=True)

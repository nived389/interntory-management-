"""Small private files stored in bounded BLOB chunks in the same database."""
import hashlib
from pathlib import PurePosixPath

CHUNK_SIZE=128*1024
DDL=(
    'CREATE TABLE IF NOT EXISTS stored_files(path TEXT PRIMARY KEY,size INTEGER NOT NULL,sha256 TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS stored_file_chunks(path TEXT NOT NULL REFERENCES stored_files(path) ON DELETE CASCADE,part INTEGER NOT NULL,content BLOB NOT NULL,PRIMARY KEY(path,part))',
)
def check(path):
    p=PurePosixPath(path)
    if len(p.parts)!=2 or p.parts[0] not in ('photos','reports') or p.parts[1] in ('.','..'):
        raise ValueError('Invalid private file path')
def put(db,path,content):
    check(path)
    digest=hashlib.sha256(content).hexdigest()
    old=db.execute('SELECT sha256 FROM stored_files WHERE path=?',(path,)).fetchone()
    if old:
        if old['sha256']!=digest:raise ValueError('Refusing to overwrite a different stored file')
        return
    db.execute('INSERT INTO stored_files(path,size,sha256) VALUES(?,?,?)',(path,len(content),digest))
    for part,start in enumerate(range(0,len(content),CHUNK_SIZE)):
        db.execute('INSERT INTO stored_file_chunks(path,part,content) VALUES(?,?,?)',(path,part,content[start:start+CHUNK_SIZE]))
def get(db,path):
    check(path)
    info=db.execute('SELECT size,sha256 FROM stored_files WHERE path=?',(path,)).fetchone()
    if info is None:raise FileNotFoundError('Private file unavailable')
    chunks=db.execute('SELECT content FROM stored_file_chunks WHERE path=? ORDER BY part',(path,)).fetchall()
    content=b''.join(bytes(row['content']) for row in chunks)
    if len(content)!=info['size'] or hashlib.sha256(content).hexdigest()!=info['sha256']:
        raise RuntimeError('Private file integrity check failed')
    return content

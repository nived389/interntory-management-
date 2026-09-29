"""Validate a trusted backup without changing live data."""
import argparse,zipfile,tempfile,sqlite3,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('backup');a=p.parse_args()
with zipfile.ZipFile(a.backup) as z,tempfile.TemporaryDirectory() as tmp:
    if 'inventory.db' not in z.namelist():raise SystemExit('Missing database')
    dbpath=Path(tmp)/'inventory.db';dbpath.write_bytes(z.read('inventory.db'))
    c=sqlite3.connect(dbpath)
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity failure'
    assert not c.execute('PRAGMA foreign_key_check').fetchall(),'Foreign key failure'
    photos={r[0] for r in c.execute('SELECT photo FROM items WHERE photo IS NOT NULL UNION SELECT photo FROM movements WHERE photo IS NOT NULL')}
    for photo in photos:
        assert 'photos/'+photo in z.namelist(),'Missing photo '+photo
        assert 'photos/thumb-'+photo in z.namelist(),'Missing thumbnail '+photo
    for path,checksum in c.execute('SELECT path,sha256 FROM archives'):
        import hashlib
        assert hashlib.sha256(z.read('reports/'+path)).hexdigest()==checksum,'Archive checksum mismatch'
    print(json.dumps({'integrity':'ok','photos':len(photos),'archives':c.execute('SELECT count(*) FROM archives').fetchone()[0]}))

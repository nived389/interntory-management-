"""Restore-compatible SQLite ZIP from a consistent libSQL read transaction."""
import sqlite3,tempfile,zipfile
from pathlib import Path
import turso_files

def archive(db,buffer):
    db.execute('BEGIN')
    try:
        definitions=db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.db';target=sqlite3.connect(path)
            try:
                for row in definitions:
                    if row['type']=='table':target.execute(row['sql'])
                for row in definitions:
                    if row['type']!='table':continue
                    name=row['name'];quoted='"'+name.replace('"','""')+'"'
                    for record in db.execute('SELECT * FROM '+quoted).fetchall():
                        target.execute('INSERT INTO '+quoted+' VALUES('+','.join('?' for _ in record)+')',tuple(record.values()))
                for row in definitions:
                    if row['type']!='table':target.execute(row['sql'])
                target.commit()
                if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or target.execute('PRAGMA foreign_key_check').fetchall():
                    raise RuntimeError('Backup integrity check failed')
                with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
                    z.write(path,'inventory.db')
                    for row in db.execute('SELECT path FROM stored_files ORDER BY path').fetchall():
                        z.writestr(row['path'],turso_files.get(db,row['path']))
            finally:target.close()
    finally:db.rollback()

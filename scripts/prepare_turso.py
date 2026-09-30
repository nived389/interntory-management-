"""Build a private SQLite migration copy, including compressed photos and reports."""
import argparse,os,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from turso_files import DDL,put,get

def prepare(data,output):
    data=Path(data);output=Path(output)
    if output.exists():raise ValueError('Output already exists; choose a new filename')
    output.parent.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
    source=sqlite3.connect('file:'+str((data/'inventory.db').resolve())+'?mode=ro',uri=True)
    dest=sqlite3.connect(output);dest.row_factory=sqlite3.Row
    try:
        source.backup(dest)
        for sql in DDL:dest.execute(sql)
        count=0
        for folder in ('photos','reports'):
            for file in sorted((data/folder).glob('*')):
                if file.is_file():
                    payload=file.read_bytes();put(dest,folder+'/'+file.name,payload)
                    if get(dest,folder+'/'+file.name)!=payload:raise RuntimeError('File verification failed')
                    count+=1
        dest.execute("INSERT INTO settings(key,value) VALUES('retention_years','4') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        dest.execute("INSERT INTO settings(key,value) VALUES('retention_delete_enabled','false') ON CONFLICT(key) DO NOTHING")
        dest.commit()
        if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or dest.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Snapshot integrity check failed')
        return count
    finally:source.close();dest.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data',default='data');parser.add_argument('--output',required=True);args=parser.parse_args()
    count=prepare(args.data,args.output)
    print('Private migration copy prepared; files verified:',count)
    print('Regenerate after pausing writes before final cloud cutover. No data uploaded.')

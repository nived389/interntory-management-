"""Consistent full backup. Run nightly using the deployment scheduler."""
import argparse,sqlite3,zipfile,tempfile,hashlib
from pathlib import Path
from datetime import datetime
p=argparse.ArgumentParser();p.add_argument('--data',default='data');p.add_argument('--destination',required=True);a=p.parse_args()
data=Path(a.data);target=Path(a.destination);target.mkdir(parents=True,exist_ok=True)
if not (data/'inventory.db').exists(): raise SystemExit('Database not found')
name=target/f'inventory-{datetime.now():%Y-%m-%d-%H%M%S}.zip'
with tempfile.TemporaryDirectory() as tmp:
    source=sqlite3.connect(data/'inventory.db');dest=sqlite3.connect(Path(tmp)/'inventory.db');source.backup(dest);dest.close();source.close()
    with zipfile.ZipFile(name,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(Path(tmp)/'inventory.db','inventory.db')
        for folder in ('photos','reports'):
            for f in (data/folder).glob('*'):z.write(f,str(f.relative_to(data)))
print(name)
print('SHA256',hashlib.sha256(name.read_bytes()).hexdigest())

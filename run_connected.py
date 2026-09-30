"""Local launcher using a privately saved, verified Turso connection."""
import json,os
from pathlib import Path
root=Path(__file__).parent
config=json.loads((root/'data/turso-connection.json').read_text())
if config.get('verified') is not True:raise RuntimeError('Verify cloud migration before activating this launcher')
for name in ('TURSO_DATABASE_URL','TURSO_AUTH_TOKEN'):os.environ[name]=config[name]
os.environ.pop('DATABASE_URL',None)
os.environ['INVENTORY_DATA']=str(root/'data')
os.environ['SESSION_SECRET']=(root/'data/session.key').read_text().strip()
os.environ['PASSWORD_VAULT_KEY']=(root/'data/password-vault.key').read_text().strip()
from app import app
if __name__=='__main__':app.run(host='127.0.0.1',port=5055,debug=False)

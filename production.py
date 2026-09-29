"""Production entry point: require restored business data before serving traffic."""
import os
from pathlib import Path

storage = Path(os.environ.get('INVENTORY_DATA', '/var/lib/travelicious'))
cloud=bool(os.environ.get('DATABASE_URL'))
if cloud:
    for key in ('SESSION_SECRET','PASSWORD_VAULT_KEY','SUPABASE_URL','SUPABASE_SECRET_KEY'):
        if not os.environ.get(key): raise RuntimeError('Missing production setting: '+key)
if not cloud and not (storage / 'inventory.db').is_file():
    raise RuntimeError('Restore the existing inventory database into INVENTORY_DATA before starting production.')
if not cloud and not (storage / 'session.key').is_file():
    raise RuntimeError('Restore session.key with the data directory before starting production.')
if os.environ.get('HTTPS') != '1':
    raise RuntimeError('Production requires HTTPS=1 and an HTTPS reverse proxy.')
os.environ['INVENTORY_DATA'] = str(storage)
os.environ.pop('INVENTORY_SKIP_OWNER_SEED', None)
from app import app

"""Owner-requested credential reveal, encrypted separately from authentication hashes."""
import os
from pathlib import Path
from cryptography.fernet import Fernet,InvalidToken

def cipher(data):
    if os.environ.get('PASSWORD_VAULT_KEY'): return Fernet(os.environ['PASSWORD_VAULT_KEY'].encode())
    if os.environ.get('DATABASE_URL') or os.environ.get('TURSO_DATABASE_URL'): raise RuntimeError('Cloud mode requires the existing PASSWORD_VAULT_KEY')
    path=Path(data)/'password-vault.key'
    if not path.exists():
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
        except FileExistsError:pass
    return Fernet(path.read_bytes())

def seal(data,password):return cipher(data).encrypt(password.encode()).decode()
def reveal(data,encrypted):
    if not encrypted:return None
    try:return cipher(data).decrypt(encrypted.encode()).decode()
    except InvalidToken:return None

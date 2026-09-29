"""Owner-requested credential reveal, encrypted separately from authentication hashes."""
import os
from pathlib import Path
from cryptography.fernet import Fernet,InvalidToken

def cipher(data):
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

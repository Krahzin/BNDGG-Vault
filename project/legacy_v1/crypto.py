# crypto.py
import json
import base64
from cryptography.fernet import Fernet
from argon2 import low_level

def derive_key_argon2(master_password: str, salt: bytes) -> bytes:
    key = low_level.hash_secret_raw(
        secret=master_password.encode(),
        salt=salt,
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        type=low_level.Type.ID
    )
    return base64.urlsafe_b64encode(key)

def encrypt_vault(key: bytes, data_dict: dict) -> str:
    f = Fernet(key)
    json_data = json.dumps(data_dict).encode()
    return f.encrypt(json_data).decode()

def decrypt_vault(key: bytes, encrypted_blob: str) -> dict:
    if not encrypted_blob:
        return {}
    f = Fernet(key)
    decrypted_data = f.decrypt(encrypted_blob.encode())
    return json.loads(decrypted_data.decode())

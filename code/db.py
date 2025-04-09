import asyncio
import psycopg2
from datetime import datetime
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import hashlib


load_dotenv()
DB_PARAMS = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


# Загрузка секретного ключа
def load_key():
    with open("useless/secret.key", "rb") as key_file:
        return key_file.read()


# Шифрование user_id
def encrypt_user_id(user_id: int) -> bytes:
    key = load_key()
    f = Fernet(key)
    encrypted = f.encrypt(str(user_id).encode())
    return encrypted


# Дешифрование
def decrypt_user_id(encrypted_id: bytes) -> int:
    key = load_key()
    f = Fernet(key)
    return int(f.decrypt(encrypted_id).decode())


def hash_user_id(user_id: int) -> bytes:
    return hashlib.sha256(str(user_id).encode()).digest()

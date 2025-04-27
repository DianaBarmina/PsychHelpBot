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


def hash_user_id(user_id: int) -> bytes:
    return hashlib.sha256(str(user_id).encode()).digest()

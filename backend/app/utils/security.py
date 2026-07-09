from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"],deprecated='auto')

def hash_password(password:str):
    return pwd_context.hash(password)

def verify_password(plain_password:str, hashed_password:str):
    return pwd_context.verify(plain_password,hashed_password)

from jose import jwt
from datetime import datetime, timedelta
from app.config import SECRET_KEY, ALGORITHM

def create_access_token(data: dict):
    to_encode=data.copy()
    expire = datetime.utcnow() + timedelta(minutes=60)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt
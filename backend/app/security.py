from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from app.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"
def hash_password(password: str) -> str: return password_hash.hash(password)
def verify_password(password: str, hashed: str) -> bool:
    try: return password_hash.verify(password, hashed)
    except Exception: return False

def create_access_token(user_id: str, role: str) -> str:
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":user_id,"role":role,"iat":now,"exp":now+timedelta(minutes=settings.access_token_minutes)},settings.secret_key,algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token,settings.secret_key,algorithms=[ALGORITHM])

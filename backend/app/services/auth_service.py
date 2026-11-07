from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from pydantic import ValidationError

from app import config
from app.schemas.auth import CurrentUser
from app.services.db_service import get_db_connection

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'shop')),
    shop_id VARCHAR(20) CHECK (shop_id IN ('hellfish', 'hooligans')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CHECK ((role = 'admin' AND shop_id IS NULL) OR (role = 'shop' AND shop_id IS NOT NULL))
);
"""

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        return False
    try:
        return bcrypt.checkpw(pwd_bytes, password_hash.encode("utf-8"))
    except (ValueError, Exception):
        return False

_DUMMY_HASH: str = hash_password("dummy-password-for-timing")

def fetch_user(username: str) -> Optional[dict]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT username, password_hash, role, shop_id FROM users WHERE username = %s;",
                (username,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "username": row[0],
                "password_hash": row[1],
                "role": row[2],
                "shop_id": row[3],
            }
        finally:
            cur.close()
    finally:
        conn.close()

def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = fetch_user(username)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "username": user["username"],
        "role": user["role"],
        "shop_id": user["shop_id"],
    }

def create_access_token(username: str, role: str, shop_id: Optional[str]) -> str:
    now_utc = datetime.now(timezone.utc)
    claims = {
        "sub": username,
        "role": role,
        "shop_id": shop_id,
        "iat": now_utc,
        "exp": now_utc + timedelta(minutes=config.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

def decode_access_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        sub = payload.get("sub")
        role = payload.get("role")
        shop_id = payload.get("shop_id")
        if role == "shop" and shop_id is None:
            raise ValueError("Token inválido")
        if role == "admin" and shop_id is not None:
            raise ValueError("Token inválido")
        return CurrentUser(username=sub, role=role, shop_id=shop_id)
    except (jwt.InvalidTokenError, ValidationError, ValueError) as exc:
        raise ValueError("Token inválido") from exc

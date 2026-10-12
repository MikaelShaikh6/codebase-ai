from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.core.database import engine
from app.models.user import User

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-secret-change-me")
TOKEN_TTL_HOURS = 24
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(expected.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _encode_segment(value: object) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def create_access_token(user_id: str) -> str:
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = _encode_segment({
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    })
    unsigned = f"{header}.{payload}"
    signature = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _decode_segment(value: str) -> dict[str, object]:
    padded = value + "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(padded)
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise ValueError("Invalid token payload.")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    if credentials is None:
        if AUTH_REQUIRED:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
        return None
    try:
        header, payload, signature = credentials.credentials.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        claims = _decode_segment(payload)
        if not hmac.compare_digest(expected, actual) or int(claims["exp"]) < datetime.now(timezone.utc).timestamp():
            raise ValueError("Expired or invalid token.")
        user_id = str(claims["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")
    with Session(engine) as session:
        user = session.exec(select(User).where(User.id == user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user

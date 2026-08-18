import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db

_bearer = HTTPBearer(auto_error=False)
SESSION_HOURS = 8
INACTIVITY_MINUTES = 30


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_session(db: Session, user_id: str, user_agent: str | None = None) -> str:
    return db.execute(text("""INSERT INTO auth_sessions (user_id, expires_at, user_agent)
        VALUES (:user_id, :expires_at, :user_agent) RETURNING id::text"""), {
        "user_id": user_id,
        "expires_at": datetime.now(UTC) + timedelta(hours=SESSION_HOURS),
        "user_agent": user_agent,
    }).scalar_one()


def create_token(user_id: str, role: str, session_id: str) -> str:
    payload = {"sub": user_id, "role": role, "sid": session_id,
               "exp": int(time.time()) + SESSION_HOURS * 3600}
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(get_settings().auth_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _decode_token(token: str) -> dict:
    body, signature = token.split(".", 1)
    expected = hmac.new(get_settings().auth_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if int(payload["exp"]) < int(time.time()):
        raise ValueError
    return payload


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = _decode_token(credentials.credentials)
        row = db.execute(text("""SELECT u.id::text, u.full_name, u.email, u.role, u.active,
            a.id::text AS session_id FROM app_users u JOIN auth_sessions a ON a.user_id=u.id
            WHERE u.id=:user_id AND a.id=:session_id AND a.revoked_at IS NULL
              AND a.expires_at>NOW()
              AND a.last_activity_at > NOW() - INTERVAL '30 minutes'"""),
            {"user_id": payload["sub"], "session_id": payload["sid"]},
        ).mappings().one_or_none()
        if not row or not row["active"]:
            raise ValueError
        db.execute(text("UPDATE auth_sessions SET last_activity_at=NOW() WHERE id=:id"),
                   {"id": row["session_id"]})
        db.commit()
        return dict(row)
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid, expired, or inactive session") from None


def optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict | None:
    if credentials is None:
        return None
    return current_user(credentials, db)


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user

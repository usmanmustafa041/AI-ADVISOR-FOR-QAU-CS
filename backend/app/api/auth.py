import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import create_session, create_token, current_user, hash_password, verify_password
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.auth import (
    AuthResponse, ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _auth_response(db: Session, row: dict, request: Request) -> dict:
    session_id = create_session(db, row["id"], request.headers.get("user-agent"))
    db.execute(text("UPDATE app_users SET last_login_at=NOW() WHERE id=:id"), {"id": row["id"]})
    db.commit()
    user = {key: row[key] for key in ("id", "full_name", "email", "role", "active")}
    return {"access_token": create_token(row["id"], row["role"], session_id), "user": user}


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    try:
        row = db.execute(text("""INSERT INTO app_users (full_name, email, password_hash, role)
            VALUES (:full_name, :email, :password_hash, 'student')
            RETURNING id::text, full_name, email, role, active"""), {
            "full_name": data.full_name.strip(), "email": data.email.lower().strip(),
            "password_hash": hash_password(data.password),
        }).mappings().one()
        return _auth_response(db, dict(row), request)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from None


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    row = db.execute(text("""SELECT id::text, full_name, email, role, active, password_hash
        FROM app_users WHERE lower(email)=:email"""),
        {"email": data.email.lower().strip()}).mappings().one_or_none()
    if not row or not row["active"] or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _auth_response(db, dict(row), request)


@router.post("/logout")
def logout(user: dict = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    db.execute(text("UPDATE auth_sessions SET revoked_at=NOW() WHERE id=:id"),
               {"id": user["session_id"]})
    db.commit()
    return {"logged_out": True}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    row = db.execute(text("SELECT id::text FROM app_users WHERE lower(email)=:email AND active"),
                     {"email": payload.email.lower().strip()}).mappings().one_or_none()
    response = {"message": "If the account exists, a reset instruction has been created."}
    if not row:
        return response
    token = secrets.token_urlsafe(32)
    db.execute(text("""INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
        VALUES (:user_id, :token_hash, :expires_at)"""), {
        "user_id": row["id"], "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "expires_at": datetime.now(UTC) + timedelta(minutes=20),
    })
    db.commit()
    # Local/demo delivery. Replace this with approved email delivery before public deployment.
    if get_settings().app_env in {"development", "production"}:
        response["demo_reset_token"] = token
    return response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    row = db.execute(text("""SELECT id::text, user_id::text FROM password_reset_tokens
        WHERE token_hash=:token_hash AND used_at IS NULL AND expires_at>NOW()"""),
        {"token_hash": token_hash}).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=422, detail="Reset token is invalid or expired")
    db.execute(text("UPDATE app_users SET password_hash=:password, updated_at=NOW() WHERE id=:id"),
               {"password": hash_password(payload.password), "id": row["user_id"]})
    db.execute(text("UPDATE password_reset_tokens SET used_at=NOW() WHERE id=:id"), {"id": row["id"]})
    db.execute(text("UPDATE auth_sessions SET revoked_at=NOW() WHERE user_id=:id AND revoked_at IS NULL"),
               {"id": row["user_id"]})
    db.commit()
    return {"password_reset": True, "message": "Password reset successfully. Sign in with your new password."}


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {key: value for key, value in user.items() if key != "session_id"}

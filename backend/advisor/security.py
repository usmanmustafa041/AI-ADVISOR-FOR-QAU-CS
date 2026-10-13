"""Password hashing, secret encryption and admin session tokens (stdlib + cryptography)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SecretBox:
    """Encrypts values at rest (API keys). The master key comes from the environment or a
    0600 key file next to the database; it never lives in the database itself."""

    def __init__(self, data_dir: Path, configured_key: str = ""):
        key_file = Path(data_dir) / "secret.key"
        if configured_key:
            raw = hashlib.sha256(configured_key.encode()).digest()
            key = base64.urlsafe_b64encode(raw)
        elif key_file.exists():
            key = key_file.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str | None:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            return None


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"

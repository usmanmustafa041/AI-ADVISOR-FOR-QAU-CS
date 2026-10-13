"""Run real browser checks with temporary accounts; remove only this run's fixtures."""

import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.auth import create_session, create_token, hash_password
from app.core.database import get_session_factory
from app.rag.corpus import PROJECT_ROOT


def main():
    SessionLocal = get_session_factory()
    identifiers = []
    fixtures = {}
    with tempfile.TemporaryDirectory(prefix="qau-browser-") as folder:
        try:
            with SessionLocal() as db:
                for name, role in (
                    ("student", "student"),
                    ("other", "student"),
                    ("admin", "admin"),
                ):
                    identifier = str(uuid4())
                    password = secrets.token_urlsafe(24)
                    email = f"browser-{identifier}@example.invalid"
                    db.execute(
                        text("""INSERT INTO app_users(id, full_name, email, password_hash, role)
                        VALUES (:id, 'Synthetic browser check', :email, :password, :role)"""),
                        {
                            "id": identifier,
                            "email": email,
                            "password": hash_password(password),
                            "role": role,
                        },
                    )
                    session = create_session(db, identifier, "QAU pipeline browser checks")
                    fixtures[name] = {
                        "access_token": create_token(identifier, role, session),
                        "user": {"id": identifier, "email": email, "role": role},
                        "password": password,
                    }
                    identifiers.append(identifier)
                db.commit()
            registration_id = str(uuid4())
            identifiers.append(registration_id)
            fixtures["registration"] = {
                "email": f"browser-{registration_id}@example.invalid",
                "password": secrets.token_urlsafe(24),
            }
            path = Path(folder) / "accounts.json"
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump(fixtures, stream)
            result = subprocess.run(
                ["npm", "run", "test:e2e", "--", "--workers=1"],
                cwd=PROJECT_ROOT / "frontend",
                env={**os.environ, "QAU_E2E_AUTH_FILE": str(path)},
                timeout=600,
                check=False,
            )
            return result.returncode
        finally:
            if identifiers:
                with SessionLocal() as db:
                    for identifier in identifiers:
                        db.execute(
                            text("DELETE FROM app_users WHERE email=:email"),
                            {"email": f"browser-{identifier}@example.invalid"},
                        )
                    db.commit()


if __name__ == "__main__":
    raise SystemExit(main())

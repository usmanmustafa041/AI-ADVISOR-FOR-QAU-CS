"""Optional single sign-on with the existing portal.

The student portal already has accounts. Rather than duplicate them, the assistant can ask the
portal "who is this?" by forwarding the caller's bearer token to a configured endpoint. Nothing is
trusted unless that endpoint confirms it, results are cached briefly, and with no URL configured the
feature is off (everyone is an anonymous guest).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

import httpx
from fastapi import Request

log = logging.getLogger("advisor.identity")

POSITIVE_TTL = 60.0
NEGATIVE_TTL = 10.0


@dataclass(frozen=True)
class User:
    id: str
    email: str
    role: str
    name: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


_cache: dict[str, tuple[float, User | None]] = {}


def _clear_cache() -> None:
    _cache.clear()


async def resolve_user(request: Request) -> User | None:
    ctx = request.app.state.ctx
    url = ctx.settings.auth_verify_url
    header = request.headers.get("authorization", "")
    if not url or not header.lower().startswith("bearer ") or len(header) < 16:
        return None
    key = hashlib.sha256(header.encode()).hexdigest()
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    user: User | None = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url, headers={"Authorization": header})
        if resp.status_code == 200:
            data = resp.json()
            uid = data.get("id") or data.get("user_id") or data.get("email")
            if uid:
                user = User(
                    id=str(uid), email=str(data.get("email", "")), role=str(data.get("role", "student")),
                    name=str(data.get("full_name") or data.get("name") or ""),
                )
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("identity check failed: %s", exc)
        return None  # a flaky portal must not turn into silent guest/identity confusion; don't cache
    _cache[key] = (now + (POSITIVE_TTL if user else NEGATIVE_TTL), user)
    if len(_cache) > 5000:
        _cache.clear()
    return user

"""Shared FastAPI dependencies: context access, client identity, rate limiting, admin auth."""

from __future__ import annotations

import time
from collections import OrderedDict, deque

from fastapi import Depends, Header, HTTPException, Request

from advisor.context import Context
from advisor.security import token_hash


def get_ctx(request: Request) -> Context:
    return request.app.state.ctx


def client_ip(request: Request) -> str:
    ctx: Context = request.app.state.ctx
    if ctx.settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Sliding-window limiter with a short burst allowance, keyed by client IP."""

    def __init__(self, per_minute: int, burst: int, max_keys: int = 20000):
        self.per_minute = per_minute
        self.burst = burst
        self.hits: OrderedDict[str, deque[float]] = OrderedDict()
        self.max_keys = max_keys

    def check(self, key: str) -> float | None:
        """Return seconds to wait if limited, else None."""
        now = time.monotonic()
        q = self.hits.setdefault(key, deque())
        self.hits.move_to_end(key)
        while q and now - q[0] > 60:
            q.popleft()
        recent = sum(1 for t in q if now - t < 10)
        if len(q) >= self.per_minute:
            return max(1.0, 60 - (now - q[0]))
        if recent >= self.burst:
            return max(1.0, 10 - (now - q[-self.burst]))
        q.append(now)
        while len(self.hits) > self.max_keys:
            self.hits.popitem(last=False)
        return None


def rate_limited(request: Request, ctx: Context = Depends(get_ctx)) -> None:
    limiter: RateLimiter = request.app.state.limiter
    wait = limiter.check(client_ip(request))
    if wait is not None:
        raise HTTPException(
            status_code=429,
            detail="You're sending questions too quickly. Please wait a moment and try again.",
            headers={"Retry-After": str(int(wait) + 1)},
        )


async def admin_required(
    request: Request,
    authorization: str | None = Header(default=None),
    ctx: Context = Depends(get_ctx),
) -> dict:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required", headers={"WWW-Authenticate": "Bearer"})
    row = ctx.db.one(
        "SELECT a.id, a.username, s.expires_at FROM admin_sessions s JOIN admins a ON a.id=s.admin_id "
        "WHERE s.token_hash=?",
        (token_hash(token),),
    )
    if row and row["expires_at"] >= time.time():
        return {"id": row["id"], "username": row["username"]}
    # Optional single sign-on: an administrator of the student portal (verified by the portal itself).
    from advisor.api.identity import resolve_user

    user = await resolve_user(request)
    if user is not None and user.is_admin:
        return {"id": 0, "username": user.email or user.id, "sso": True}
    raise HTTPException(status_code=401, detail="Session expired — please sign in again")

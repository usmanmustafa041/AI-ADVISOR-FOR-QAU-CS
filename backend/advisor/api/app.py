"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from advisor import __version__
from advisor.api import admin, public
from advisor.api.deps import RateLimiter
from advisor.config import Settings, get_settings
from advisor.context import Context, build_context
from advisor.security import hash_password

log = logging.getLogger("advisor.app")


def bootstrap_admin(ctx: Context) -> None:
    s = ctx.settings
    if ctx.db.scalar("SELECT COUNT(*) FROM admins", default=0):
        return
    if s.bootstrap_admin_user and s.bootstrap_admin_password:
        ctx.db.execute(
            "INSERT INTO admins(username, password_hash) VALUES(?,?)",
            (s.bootstrap_admin_user, hash_password(s.bootstrap_admin_password)),
        )
        log.info("created initial administrator %r from environment", s.bootstrap_admin_user)
    else:
        log.warning("No administrator exists. Create one with: python -m advisor.cli create-admin")


async def retention_loop(ctx: Context) -> None:
    """Delete old conversations and logs once a day (privacy by default)."""
    while True:
        try:
            days = ctx.settings.history_retention_days
            cutoff = f"-{days} days"
            ctx.db.execute("DELETE FROM messages WHERE created_at < datetime('now', ?)", (cutoff,))
            ctx.db.execute(
                "DELETE FROM conversations WHERE id NOT IN (SELECT DISTINCT conversation_id FROM messages)"
            )
            ctx.db.execute("DELETE FROM query_log WHERE created_at < datetime('now', ?)", (cutoff,))
            ctx.db.execute(
                "DELETE FROM feedback WHERE message_id NOT IN (SELECT id FROM messages)"
            )
        except Exception:
            log.exception("retention cleanup failed")
        await asyncio.sleep(24 * 3600)


def create_app(ctx: Context | None = None, settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        context = ctx or build_context(settings or get_settings(), load_kb=False)
        app.state.ctx = context
        app.state.limiter = RateLimiter(
            context.settings.rate_limit_per_minute, context.settings.rate_limit_burst
        )
        bootstrap_admin(context)
        if not context.kb.ready:
            await asyncio.to_thread(context.kb.load)  # model load takes a few seconds
        task = asyncio.create_task(retention_loop(context))
        try:
            yield
        finally:
            task.cancel()

    app = FastAPI(
        title="QAU CS Advisor API", version=__version__, lifespan=lifespan,
        docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
    )
    s = (ctx.settings if ctx else (settings or get_settings()))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; frame-ancestors 'none'",
        )
        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/docs"):
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers["Server-Timing"] = f"app;dur={(time.monotonic() - started) * 1000:.0f}"
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    app.include_router(public.router)
    app.include_router(admin.router)

    web_dir = s.serve_frontend_dir
    if web_dir and Path(web_dir).exists():
        web_dir = Path(web_dir)
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            candidate = (web_dir / path).resolve()
            if path and candidate.is_file() and web_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(web_dir / "index.html")

    return app


app = None


def get_app() -> FastAPI:  # uvicorn --factory advisor.api.app:get_app
    return create_app()

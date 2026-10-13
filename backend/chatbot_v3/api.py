"""Independent loopback preview. Shared imports are limited to existing authentication."""

import asyncio
import hmac
import json
import secrets
import time
from collections import OrderedDict
from contextlib import aclosing, asynccontextmanager
from typing import Annotated, Literal

from app.core.auth import optional_current_user
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from chatbot_v3.contracts import ChatRequest, ChatResponse
from chatbot_v3.embeddings import Encoder, Reranker
from chatbot_v3.index import Index
from chatbot_v3.model import ModelUnavailable, Ollama
from chatbot_v3.service import CapacityError, Service
from chatbot_v3.settings import settings
from chatbot_v3.store import Store
from chatbot_v3.timetable import api as timetable_api


def create_app(service=None):
    @asynccontextmanager
    async def lifespan(app):
        if service is not None:
            app.state.service = service
        else:
            store = Store()
            config = settings()
            encoder = reranker = None
            try:
                encoder = await asyncio.to_thread(
                    Encoder,
                    config.embedding_model,
                    config.embedding_device,
                    config.local_files_only,
                )
            except Exception:
                pass
            if config.reranker_model:
                try:
                    reranker = await asyncio.to_thread(
                        Reranker,
                        config.reranker_model,
                        config.embedding_device,
                        config.local_files_only,
                    )
                except Exception:
                    pass
            app.state.service = Service(store, Ollama(), Index(store, encoder, reranker))
            store.prune()
        await timetable_api.start(app)
        app.state.service.timetables = app.state.timetables
        try:
            yield
        finally:
            await app.state.timetable_jobs.close()

    app = FastAPI(title="QAU CS replacement preview", version="3.0.0-preview", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings().cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Developer-Token",
            "X-Timetable-Metadata",
            "X-Filename",
        ],
    )
    rate = OrderedDict()
    timetable_api.install(app)

    @app.exception_handler(KeyError)
    async def not_found(request, error):
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def conflict(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.middleware("http")
    async def guard(request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in settings().cors_origins:
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
        if request.method == "POST":
            # Bound even chunked transfer bodies before JSON parsing.
            body = bytearray()
            async for part in request.stream():
                body.extend(part)
                limit = (
                    20 * 1024 * 1024
                    if request.url.path == "/api/v3/admin/timetables/versions"
                    else 65536
                )
                if len(body) > limit:
                    return JSONResponse({"detail": "Request is too large"}, status_code=413)
            request._body = bytes(body)
        if request.url.path.endswith(("/chat", "/chat/stream")):
            key = request.client.host if request.client else "unknown"
            now = time.monotonic()
            bucket = [t for t in rate.get(key, []) if now - t < 60]
            if len(bucket) >= 20:
                return JSONResponse(
                    {"detail": "Please slow down and retry shortly"},
                    status_code=429,
                    headers={"Retry-After": "10"},
                )
            rate[key] = bucket + [now]
            rate.move_to_end(key)
            while len(rate) > 5000:
                rate.popitem(last=False)
        return await call_next(request)

    def get_service(request: Request):
        return request.app.state.service

    def identity(request: Request, user=Depends(optional_current_user)):
        if user:
            return str(user["id"]), True
        cookie = request.cookies.get("qau_v3_guest")
        if not cookie or len(cookie) != 64 or any(c not in "0123456789abcdef" for c in cookie):
            cookie = secrets.token_hex(32)
        return cookie, False

    def developer(x_developer_token: Annotated[str | None, Header()] = None):
        expected = settings().developer_token
        if (
            not expected
            or not x_developer_token
            or not hmac.compare_digest(expected, x_developer_token)
        ):
            raise HTTPException(403, "Developer access required")

    def cookie(response, owner, authenticated):
        if not authenticated:
            response.set_cookie(
                "qau_v3_guest",
                owner,
                httponly=True,
                samesite="lax",
                max_age=settings().guest_ttl_seconds,
                path="/api/v3",
            )

    @app.get("/health/live")
    @app.get("/api/v3/health/live")
    async def live():
        return {"status": "ok", "service": "qau-chatbot-v3-preview"}

    @app.get("/health/ready")
    @app.get("/api/v3/health/ready")
    async def ready(s=Depends(get_service)):
        model = await s.model.available()
        complete = (
            model
            and bool(s.index.chunks)
            and s.index.vectors is not None
            and s.index.encoder is not None
        )
        return JSONResponse(
            {
                "status": "ready" if complete else "degraded",
                "model_available": model,
                "model": settings().model,
                "semantic_index": s.index.vectors is not None,
                "semantic_encoder": s.index.encoder is not None,
                "evidence_chunks": len(s.index.chunks),
                "preview_only": True,
            },
            status_code=200 if complete else 503,
        )

    @app.post("/api/v3/chat", response_model=ChatResponse)
    async def chat(
        body: ChatRequest, response: Response, who=Depends(identity), s=Depends(get_service)
    ):
        owner, authenticated = who
        try:
            s.conversation(body, owner, authenticated)
            async with aclosing(s.events(body, owner, authenticated)) as events:
                async for event, data in events:
                    if event == "done":
                        cookie(response, owner, authenticated)
                        return data
        except KeyError:
            raise HTTPException(404, "Conversation not found or expired") from None
        except ValueError as error:
            return JSONResponse(
                {
                    "detail": "The conversation or model interpretation was invalid; please retry",
                    "trace_id": getattr(error, "trace_id", None),
                },
                status_code=422,
            )
        except (ModelUnavailable, CapacityError) as e:
            return JSONResponse(
                {"detail": str(e), "trace_id": getattr(e, "trace_id", None)},
                status_code=503,
                headers={"Retry-After": "5"},
            )

    @app.post("/api/v3/chat/stream")
    async def chat_stream(
        body: ChatRequest, request: Request, who=Depends(identity), s=Depends(get_service)
    ):
        owner, authenticated = who
        try:
            s.conversation(body, owner, authenticated)
        except KeyError:
            raise HTTPException(404, "Conversation not found or expired") from None
        except ValueError as e:
            raise HTTPException(422, str(e)) from None

        async def stream():
            try:
                async with aclosing(s.events(body, owner, authenticated)) as events:
                    async for event, data in events:
                        if await request.is_disconnected():
                            return
                        yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except (ModelUnavailable, CapacityError) as e:
                yield f"event: error\ndata: {json.dumps({'message': str(e), 'retry_after': 5, 'trace_id': getattr(e, 'trace_id', None)})}\n\n"
            except asyncio.CancelledError:
                raise
            except Exception:
                yield 'event: error\ndata: {"message":"The answer could not be completed. Please retry.","retry_after":5}\n\n'

        response = StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )
        cookie(response, owner, authenticated)
        return response

    @app.get("/api/v3/sources/{source_id}")
    def source(
        source_id: str, request: Request, version: str | None = None, s=Depends(get_service)
    ):
        if source_id.startswith("tt-"):
            v = request.app.state.timetables.version(source_id[3:])
            if v["status"] not in {"published", "archived"} or (version and version != v["id"]):
                raise HTTPException(404, "Published source not found")
            detail = request.app.state.timetables.detail(v["id"])
            return {
                "id": v["id"],
                "title": v["filename"],
                "checksum": v["sha256"],
                "effective_term": v["metadata"]["academic_term"],
                "passages": [
                    {
                        "id": m["id"],
                        "page": m["page"],
                        "content": m["raw"],
                        "coordinates": m["bbox"],
                        "continuations": m["provenance"],
                    }
                    for m in detail["meetings"]
                ],
            }
        with s.store.connect() as c:
            params = [source_id]
            sql = "SELECT v.*,d.uri,d.origin FROM document_version v JOIN document d ON d.id=v.document_id WHERE d.id=? AND d.origin IN ('official_archive','official_live')"
            if version:
                sql += " AND v.id=?"
                params.append(version)
            sql += " ORDER BY captured_at DESC LIMIT 1"
            row = c.execute(sql, params).fetchone()
            if row is None:
                raise HTTPException(404, "Source not found")
            data = dict(row)
            data.pop("raw_path", None)
            data["passages"] = [
                dict(r)
                for r in c.execute(
                    "SELECT id,page,section,content,coordinates FROM evidence_chunk WHERE version_id=?",
                    (row["id"],),
                )
            ]
            return data

    @app.get("/api/v3/knowledge/coverage")
    def coverage(s=Depends(get_service)):
        with s.store.connect() as c:
            return {
                "documents": c.execute("SELECT count(*) FROM document").fetchone()[0],
                "versions": c.execute("SELECT count(*) FROM document_version").fetchone()[0],
                "chunks": c.execute("SELECT count(*) FROM evidence_chunk").fetchone()[0],
                "review_status": {
                    r[0]: r[1]
                    for r in c.execute(
                        "SELECT review_status,count(*) FROM document_version GROUP BY review_status"
                    )
                },
                "topics": {
                    r[0]: r[1]
                    for r in c.execute("SELECT topic,count(*) FROM document_version GROUP BY topic")
                },
                "preview_only": True,
            }

    @app.get("/api/v3/knowledge/review", dependencies=[Depends(developer)])
    def review_queue(s=Depends(get_service)):
        rows = s.store.review_queue()
        for row in rows:
            row.pop("raw_path", None)
        return rows

    class Review(BaseModel):
        version_id: str = Field(min_length=64, max_length=64)
        decision: Literal["approved", "rejected", "needs_review"]
        reviewer: str = Field(min_length=2, max_length=120)
        note: str = Field(min_length=8, max_length=2000)

    @app.post("/api/v3/knowledge/review", dependencies=[Depends(developer)])
    async def review(body: Review, s=Depends(get_service)):
        try:
            await asyncio.to_thread(
                s.store.review, body.version_id, body.decision, body.reviewer, body.note
            )
        except KeyError:
            raise HTTPException(404, "Source version not found") from None
        # Review changes affect eligibility immediately, including previously published bundles.
        for chunk in s.index.chunks:
            if chunk["source_version_id"] == body.version_id:
                chunk["review_status"] = body.decision
        return {"recorded": True, "decision": body.decision}

    class Feedback(BaseModel):
        message_id: str
        helpful: bool
        reason: str | None = Field(default=None, max_length=1000)

    @app.post("/api/v3/feedback")
    def feedback(body: Feedback, who=Depends(identity), s=Depends(get_service)):
        owner, authenticated = who
        if not authenticated:
            raise HTTPException(401, "Sign in to submit saved-answer feedback")
        try:
            s.store.feedback(owner, body.message_id, body.helpful, body.reason)
        except KeyError:
            raise HTTPException(404, "Message not found") from None
        return {"saved": True}

    @app.get("/api/v3/history")
    def sessions(who=Depends(identity), s=Depends(get_service)):
        if not who[1]:
            raise HTTPException(401, "Sign in to save conversations")
        return s.store.sessions(who[0])

    @app.get("/api/v3/history/{conversation_id}")
    def saved_conversation(conversation_id: str, who=Depends(identity), s=Depends(get_service)):
        if not who[1]:
            raise HTTPException(401, "Sign in to view saved conversations")
        try:
            s.store.history(conversation_id, who[0])
        except KeyError:
            raise HTTPException(404, "Conversation not found") from None
        with s.store.connect() as c:
            return [
                {**dict(r), "metadata": json.loads(r["metadata"])}
                for r in c.execute(
                    "SELECT id,role,content,metadata FROM message WHERE conversation_id=? ORDER BY rowid",
                    (conversation_id,),
                )
            ]

    @app.delete("/api/v3/history/{conversation_id}")
    def delete_conversation(conversation_id: str, who=Depends(identity), s=Depends(get_service)):
        owner, authenticated = who
        if authenticated:
            with s.store.connect() as c:
                if not c.execute(
                    "SELECT 1 FROM conversation WHERE id=? AND owner=?", (conversation_id, owner)
                ).fetchone():
                    raise HTTPException(404, "Conversation not found")
                c.execute(
                    "DELETE FROM feedback WHERE message_id IN (SELECT id FROM message WHERE conversation_id=?)",
                    (conversation_id,),
                )
                c.execute(
                    "DELETE FROM conversation WHERE id=? AND owner=?", (conversation_id, owner)
                )
        else:
            if s.guests.pop((owner, conversation_id), None) is None:
                raise HTTPException(404, "Conversation not found")
        return {"deleted": True}

    @app.get("/api/v3/development/traces/{trace_id}", dependencies=[Depends(developer)])
    def trace(trace_id: str, s=Depends(get_service)):
        if trace_id not in s.traces:
            raise HTTPException(404, "Trace unavailable; diagnostics are opt-in and bounded")
        return s.traces[trace_id]

    @app.get("/api/v3/development/metrics", dependencies=[Depends(developer)])
    def metrics(s=Depends(get_service)):
        return {**s.metrics, "queue_depth": s.waiting}

    return app


app = create_app()

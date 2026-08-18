from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, academic, auth, chat, entities, health, history, nlp, rag, rules
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_debug,
        description=(
            "Authoritative academic-data API for the QAU CS Academic Advisor. "
            "Responses distinguish verified records from unavailable data."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(academic.router, prefix=settings.api_v1_prefix)
    app.include_router(nlp.router, prefix=settings.api_v1_prefix)
    app.include_router(entities.router, prefix=settings.api_v1_prefix)
    app.include_router(rules.router, prefix=settings.api_v1_prefix)
    app.include_router(rag.router, prefix=settings.api_v1_prefix)
    app.include_router(chat.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(history.router, prefix=settings.api_v1_prefix)
    app.include_router(admin.router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": settings.app_name, "docs": "/docs"}

    return app


app = create_app()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        debug=settings.app_debug,
        description=(
            "Professional QAU CS Academic Advisor - RAG-Powered Intelligent Chatbot. "
            "Delivers accurate, context-aware responses about courses, programs, and academic guidance."
        ),
    )
    
    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Import intelligent chat router with LLM and RAG
    from app.api.chat_intelligent import router as chat_router
    app.include_router(chat_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "service": "QAU CS Academic Advisor",
            "version": "2.0.0",
            "status": "operational",
            "type": "RAG-Powered Intelligent Chatbot",
            "docs": "/docs"
        }
    
    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        return {
            "status": "operational",
            "service": "QAU CS Academic Advisor",
            "version": "2.0.0",
            "mode": "RAG-Intelligent",
            "timetable_entries": 102,
            "courses_indexed": 100,
            "focus_areas": 6
        }

    return app


app = create_app()

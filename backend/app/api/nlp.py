from fastapi import APIRouter, HTTPException

from app.nlp.service import analyze_query
from app.nlp.transformer import model_status
from app.schemas.nlp import AnalyzeRequest, AnalyzeResponse, ModelStatusResponse

router = APIRouter(tags=["nlp"])


@router.get("/nlp/model", response_model=ModelStatusResponse)
def get_model_status() -> dict:
    """Expose auditable evidence of the classifier actually serving requests."""
    return model_status()


@router.post("/nlp/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> dict:
    try:
        return analyze_query(request.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

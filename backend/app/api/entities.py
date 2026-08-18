from fastapi import APIRouter, HTTPException

from app.nlp.entities import extract_entities
from app.schemas.entities import EntityRequest, EntityResponse

router = APIRouter(tags=["entity recognition"])


@router.post("/nlp/entities", response_model=EntityResponse)
def entities(request: EntityRequest) -> dict:
    text = " ".join(request.text.strip().split())
    if not text:
        raise HTTPException(status_code=422, detail="Query cannot be empty")
    return {"text": text, "entities": extract_entities(text)}


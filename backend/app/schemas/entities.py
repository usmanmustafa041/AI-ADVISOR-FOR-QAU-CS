from pydantic import BaseModel, Field


class EntityRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class EntityResponse(BaseModel):
    text: str
    entities: dict[str, list[str]]


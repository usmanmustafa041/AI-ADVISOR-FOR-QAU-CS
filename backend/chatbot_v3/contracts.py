from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Language = Literal["english", "roman_urdu", "urdu"]
Programme = Literal["BSCS", "MPhil", "PhD", "MS-DS", "MS-IST"]
Topic = Literal[
    "curriculum",
    "faculty",
    "admissions",
    "fees",
    "academic_policy",
    "timetable",
    "exam_schedule",
    "registration",
    "research",
    "services",
    "programme",
    "general",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Turn(Contract):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class StudentContext(Contract):
    programme: Programme | None = None
    admission_batch: str | None = None
    semester: int | None = Field(default=None, ge=1, le=12)
    preferred_language: Language | None = None


class ChatRequest(Contract):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
    history: list[Turn] = Field(default_factory=list, max_length=12)
    preferred_language: Language | None = None
    student_context: StudentContext | None = None

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Please enter a question")
        return value.strip()


class Task(Contract):
    question: str
    search_query: str
    topic: Topic
    programme: Programme | None = None
    admission_batch: str | None = None
    operational_term: str | None = None
    semester: int | None = None
    course_codes: list[str] = Field(default_factory=list)
    person_names: list[str] = Field(default_factory=list)
    high_stakes: bool = False


class QueryUnderstanding(Contract):
    original: str
    normalized: str
    language: Language = Field(
        description="Language of the ORIGINAL student message: roman_urdu for Urdu written in Latin letters; urdu for Urdu script; english for English. Do not use the English search rewrite's language."
    )
    tasks: list[Task] = Field(default_factory=list, max_length=5)
    course_codes: list[str] = Field(default_factory=list)
    person_names: list[str] = Field(default_factory=list)
    programme: Programme | None = None
    admission_batch: str | None = None
    operational_term: str | None = None
    mode: Literal["university", "tutor", "mixed", "conversation", "private_record"]
    ambiguous_fields: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None


class EvidenceReference(Contract):
    source_id: str
    source_version_id: str
    chunk_id: str
    number: int = 0
    canonical_url: str | None = None
    workspace_path: str | None = None
    document_title: str
    page: int | None = None
    section: str | None = None
    effective_term: str | None = None
    programme: str | None = None
    admission_batch: str | None = None
    quote: str | None = None
    origin_status: str
    review_status: str
    captured_at: str | None = None
    checksum: str


class ChatResponse(Contract):
    answer: str
    mode: str
    conversation_id: str | None = None
    message_id: str | None = None
    cited_sources: list[EvidenceReference] = Field(default_factory=list)
    groundedness_status: str
    scope: dict = Field(default_factory=dict)
    followup_question: str | None = None
    warnings: list[str] = Field(default_factory=list)
    trace_id: str
    latency_ms: int
    first_token_ms: int | None = None

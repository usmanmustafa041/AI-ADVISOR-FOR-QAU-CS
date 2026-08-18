from datetime import date, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceSummary(BaseModel):
    source_code: str
    title: str
    source_url: str | None = None
    last_verified_at: str | None = None
    verification_status: str


class ProgramSummary(BaseModel):
    id: UUID
    code: str
    name: str
    level: str
    study_mode: str | None
    normal_semesters: int | None
    maximum_semesters: int | None
    minimum_cgpa: Decimal | None


class CourseDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    description: str | None
    theory_credit_hours: Decimal
    lab_credit_hours: Decimal
    total_credit_hours: Decimal
    active: bool
    source: SourceSummary | None


class PrerequisiteItem(BaseModel):
    course_code: str
    course_title: str
    relation_type: str
    minimum_grade: str | None
    waiver_condition: str | None
    verified: bool
    source: SourceSummary


class PrerequisiteResponse(BaseModel):
    course_code: str
    course_title: str
    curriculum: str
    prerequisites: list[PrerequisiteItem]
    dataset_complete: bool
    notice: str


class FeeItem(BaseModel):
    program_code: str | None
    program_name: str | None
    official_fee_category: str
    shift: str
    fee_type: str
    amount: Decimal
    currency: str
    effective_from: date
    effective_to: date | None
    source: SourceSummary


class FeeResponse(BaseModel):
    as_of: date
    fees: list[FeeItem]
    notice: str | None = None
    demo_data: bool = False


class TimetableItem(BaseModel):
    course_code: str
    course_title: str
    section: str
    instructor: str | None
    session_type: str
    day_of_week: int
    starts_at: time
    ends_at: time
    room: str
    lab_group: str | None
    source: SourceSummary


class TimetableResponse(BaseModel):
    academic_year: int
    term: str
    entries: list[TimetableItem]
    verified_data_available: bool
    notice: str | None = None
    demo_data: bool = False

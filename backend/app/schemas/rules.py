from pydantic import BaseModel, Field


class PrerequisiteInput(BaseModel):
    course_code: str = Field(min_length=2, max_length=20)
    minimum_grade: str | None = None


class PrerequisiteCheckRequest(BaseModel):
    course_code: str = Field(min_length=2, max_length=20)
    completed_grades: dict[str, str] = {}
    requirements: list[PrerequisiteInput] = []
    dataset_complete: bool = False


class LoadCheckRequest(BaseModel):
    requested_credit_hours: float = Field(ge=0, le=100)
    approval_for_exception: bool = False
    remaining_credit_hours: float | None = Field(default=None, ge=0, le=100)


class ProgressionCheckRequest(BaseModel):
    cgpa: float = Field(ge=0, le=4)
    probation_chances_used: int = Field(default=0, ge=0)


class ExemptionCheckRequest(BaseModel):
    requested_credit_hours: float = Field(gt=0, le=51)
    already_exempted_credit_hours: float = Field(default=0, ge=0, le=51)
    minimum_grade_met: bool
    institution_recognized: bool


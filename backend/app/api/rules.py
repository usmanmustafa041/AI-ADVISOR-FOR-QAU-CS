from fastapi import APIRouter

from app.rules.engine import (
    PrerequisiteRequirement,
    evaluate_exemption,
    evaluate_prerequisite,
    evaluate_progression,
    evaluate_semester_load,
)
from app.schemas.rules import (
    ExemptionCheckRequest,
    LoadCheckRequest,
    PrerequisiteCheckRequest,
    ProgressionCheckRequest,
)

router = APIRouter(tags=["academic rules"])


@router.post("/rules/prerequisite-check")
def prerequisite_check(request: PrerequisiteCheckRequest) -> dict:
    requirements = [
        PrerequisiteRequirement(course_code=item.course_code, minimum_grade=item.minimum_grade)
        for item in request.requirements
    ]
    return evaluate_prerequisite(
        request.course_code,
        requirements,
        request.completed_grades,
        request.dataset_complete,
    )


@router.post("/rules/semester-load")
def semester_load(request: LoadCheckRequest) -> dict:
    return evaluate_semester_load(
        request.requested_credit_hours,
        request.approval_for_exception,
        request.remaining_credit_hours,
    )


@router.post("/rules/progression")
def progression(request: ProgressionCheckRequest) -> dict:
    return evaluate_progression(request.cgpa, request.probation_chances_used)


@router.post("/rules/exemption")
def exemption(request: ExemptionCheckRequest) -> dict:
    return evaluate_exemption(
        request.requested_credit_hours,
        request.already_exempted_credit_hours,
        request.minimum_grade_met,
        request.institution_recognized,
    )


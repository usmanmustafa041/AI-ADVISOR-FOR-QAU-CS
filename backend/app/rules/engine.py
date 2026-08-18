from dataclasses import dataclass


GRADE_POINTS = {
    "A": 4.0, "A-": 3.8, "B+": 3.5, "B": 3.0, "B-": 2.8,
    "C+": 2.5, "C": 2.0, "D": 1.0, "F": 0.0,
}


@dataclass(frozen=True)
class PrerequisiteRequirement:
    course_code: str
    minimum_grade: str | None = None


def _grade_satisfies(actual: str | None, minimum: str | None) -> bool:
    if minimum is None:
        return actual is not None
    if actual is None:
        return False
    return GRADE_POINTS.get(actual.upper(), -1) >= GRADE_POINTS.get(minimum.upper(), 99)


def evaluate_prerequisite(
    target_course_code: str,
    requirements: list[PrerequisiteRequirement],
    completed_grades: dict[str, str],
    dataset_complete: bool,
) -> dict:
    """Evaluate all known requirements without inferring missing requirements."""
    normalized_grades = {code.upper(): grade.upper() for code, grade in completed_grades.items()}
    missing = []
    for requirement in requirements:
        grade = normalized_grades.get(requirement.course_code.upper())
        if not _grade_satisfies(grade, requirement.minimum_grade):
            missing.append(
                {
                    "course_code": requirement.course_code.upper(),
                    "minimum_grade": requirement.minimum_grade,
                    "completed_grade": grade,
                }
            )

    if not dataset_complete:
        return {
            "eligible": None,
            "decision": "unverified",
            "target_course_code": target_course_code.upper(),
            "missing_requirements": missing,
            "notice": "The prerequisite matrix is incomplete; eligibility cannot be confirmed safely.",
        }
    return {
        "eligible": not missing,
        "decision": "eligible" if not missing else "ineligible",
        "target_course_code": target_course_code.upper(),
        "missing_requirements": missing,
        "notice": None,
    }


def evaluate_semester_load(
    requested_credit_hours: float,
    approval_for_exception: bool = False,
    remaining_credit_hours: float | None = None,
) -> dict:
    """Apply the published BSCS 15-18 normal / 12-21 exceptional-load rule."""
    if requested_credit_hours < 0:
        raise ValueError("Credit hours cannot be negative")
    if 15 <= requested_credit_hours <= 18:
        return {"allowed": True, "category": "normal", "notice": None}
    if approval_for_exception and requested_credit_hours <= 21:
        if requested_credit_hours >= 12 or (
            remaining_credit_hours is not None and requested_credit_hours == remaining_credit_hours
        ):
            return {"allowed": True, "category": "exceptional", "notice": "Required approvals apply."}
    return {
        "allowed": False,
        "category": "outside_limit",
        "notice": "Normal load is 15-18 credits; exceptional load requires approval and is capped at 21 credits.",
    }


def evaluate_progression(cgpa: float, probation_chances_used: int = 0) -> dict:
    if not 0 <= cgpa <= 4:
        raise ValueError("CGPA must be between 0 and 4")
    if probation_chances_used < 0:
        raise ValueError("Probation chance count cannot be negative")
    if cgpa < 1.0:
        return {"status": "dropped", "can_continue": False, "notice": "CGPA is below 1.0."}
    if cgpa < 2.0:
        return {
            "status": "probation",
            "can_continue": probation_chances_used < 3,
            "notice": "CGPA is below 2.0; probation rules apply.",
        }
    return {"status": "good_standing", "can_continue": True, "notice": None}


def evaluate_exemption(
    requested_credit_hours: float,
    already_exempted_credit_hours: float,
    minimum_grade_met: bool,
    institution_recognized: bool,
) -> dict:
    total = already_exempted_credit_hours + requested_credit_hours
    allowed = (
        requested_credit_hours > 0
        and already_exempted_credit_hours >= 0
        and total <= 51
        and minimum_grade_met
        and institution_recognized
    )
    return {
        "allowed": allowed,
        "total_exempted_credit_hours": total,
        "maximum_exempted_credit_hours": 51,
        "notice": None if allowed else "Exemption conditions or the 51-credit maximum were not satisfied.",
    }


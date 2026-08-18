from app.rules.engine import (
    PrerequisiteRequirement,
    evaluate_exemption,
    evaluate_prerequisite,
    evaluate_progression,
    evaluate_semester_load,
)


def test_verified_prerequisite_passes_grade_requirement() -> None:
    result = evaluate_prerequisite(
        "CSC-483", [PrerequisiteRequirement("CSC-322", "C")], {"CSC-322": "B"}, True
    )
    assert result["decision"] == "eligible"


def test_verified_prerequisite_reports_missing_course() -> None:
    result = evaluate_prerequisite(
        "CSC-483", [PrerequisiteRequirement("CSC-322")], {}, True
    )
    assert result["decision"] == "ineligible"
    assert result["missing_requirements"][0]["course_code"] == "CSC-322"


def test_exemption_cap_is_enforced() -> None:
    result = evaluate_exemption(3, 49, True, True)
    assert result["allowed"] is False
    assert result["total_exempted_credit_hours"] == 52


def test_progression_below_one_is_dropped() -> None:
    assert evaluate_progression(0.9)["status"] == "dropped"


def test_exceptional_load_requires_approval() -> None:
    assert evaluate_semester_load(21)["allowed"] is False
    assert evaluate_semester_load(21, approval_for_exception=True)["allowed"] is True


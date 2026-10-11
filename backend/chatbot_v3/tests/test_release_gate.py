from chatbot_v3.scripts.release_gate import evaluate


def test_pending_cases_and_automatic_pattern_success_cannot_pass_release():
    pending = {
        "cases": [
            {"id": str(i), "review_status": "pending", "reference_answer": "draft"}
            for i in range(250)
        ]
    }
    automatic = {
        "cases": [
            {
                "case_id": str(i),
                "factually_correct": True,
                "reviewer": "same model",
                "review_kind": "AI",
                "reviewed_at": "today",
            }
            for i in range(250)
        ]
    }
    report = evaluate(pending, automatic)
    assert report["quality_gate_passed"] is False
    assert report["approved_references"] == 0
    assert report["metrics"]["factual_accuracy"] is None


def test_release_requires_human_answer_grades_in_addition_to_gold_labels():
    cases = [
        {
            "id": str(i),
            "review_status": "approved",
            "approved_reference_answer": "answer",
            "critical_assertions": ["fact"],
            "reviewer": "QAU reviewer",
            "reviewed_at": "2026-10-11",
        }
        for i in range(200)
    ]
    report = evaluate({"cases": cases}, {"cases": []})
    assert report["approved_references"] == 200
    assert report["quality_gate_passed"] is False


def test_duplicate_and_incomplete_grades_do_not_count_as_independent_answers():
    reference = {
        "id": "one",
        "review_status": "approved",
        "approved_reference_answer": "answer",
        "critical_assertions": ["fact"],
        "reviewer": "human",
        "reviewed_at": "today",
        "expected_behavior": "answer",
    }
    grade = {
        "case_id": "one",
        "reviewer": "human",
        "reviewed_at": "today",
        "review_kind": "human",
        "factually_correct": True,
        "citations_valid": True,
        "complete": True,
        "appropriate_behavior": True,
        "prefer_replacement": 0.5,
    }
    report = evaluate({"cases": [reference]}, {"cases": [grade] * 200})
    assert report["human_graded_answers"] == 1
    assert any("replacement_preference" in failure for failure in report["failures"])
    del grade["complete"]
    assert evaluate({"cases": [reference]}, {"cases": [grade]})["human_graded_answers"] == 0

from chatbot_v3.calculations import credit_category_sum
from chatbot_v3.generation import validate_paragraph


def test_only_complete_unambiguous_printed_categories_support_a_sum():
    text = "\n".join(
        [
            "Computing Core (CC) 46",
            "Domain Core (DC) 18",
            "Domain Elective (DE) 21",
            "Maths and Supporting (MS) 12",
            "Elective Supporting (ES) 3",
            "General Education (GE) 30",
        ]
    )
    calculation = credit_category_sum(text)
    assert calculation["value"] == 130
    assert "not a quoted" in calculation["method"]
    assert credit_category_sum(text.split("\n", 1)[1]) is None
    assert credit_category_sum(text + "\nDomain Core (DC) 19") is None
    assert validate_paragraph(
        "The six published categories sum to 130 credits. [1]",
        [{"content": text, "effective_term": None}],
        "Total credits?",
    ) == [1]

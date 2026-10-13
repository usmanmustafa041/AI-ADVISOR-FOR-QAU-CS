"""User-supplied weighted GPA arithmetic, without assuming a university scale."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.response.grounded import GroundedAnswer

PAIR = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:credits?|credit hours?|CH|کریڈٹ)\s*"
    r"(?:at|@|:|with|par|pe|پر)\s*(\d+(?:\.\d+)?)",
    re.I,
)


def calculate_gpa(query, language="english"):
    if not re.search(r"\bgpa\b|\bcgpa\b|جی پی اے", query, re.I):
        return None
    matches = PAIR.findall(query)
    if not matches:
        return None
    try:
        pairs = [(Decimal(c), Decimal(g)) for c, g in matches]
        if len(pairs) > 40 or any(c <= 0 or c > 30 or g < 0 or g > 4 for c, g in pairs):
            raise ValueError
        credits = sum(c for c, _ in pairs)
        points = sum(c * g for c, g in pairs)
        value = (points / credits).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return GroundedAnswer(
            "Use positive credit hours and grade points between 0 and 4.", model="calculator"
        )
    labels = {
        "english": "Using the credit hours and grade points you supplied",
        "roman_urdu": "Aap ke diye hue credit hours aur grade points ke mutabiq",
        "urdu": "آپ کے فراہم کردہ کریڈٹ آورز اور گریڈ پوائنٹس کے مطابق",
    }
    answer = (
        f"{labels.get(language, labels['english'])}:\n\n"
        f"GPA = Σ(credits × grade points) / Σcredits = {points} / {credits} = **{value}**."
        "\n\nThis is a calculation from your inputs. It does not establish QAU's "
        "grade conversion, repeat-course or rounding rules."
    )
    return GroundedAnswer(answer, engine="rule", grounding_status="calculated", model="calculator")

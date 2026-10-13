"""Identify explicit requests for private records before retrieval/generation."""

import re


def private_record_request(query: str) -> bool:
    value = query.lower()
    if re.search(
        r"\b(private|personal)\b.{0,70}\b(grades?|gpa|records?|phone|mobile|address)\b", value
    ):
        return True
    if re.search(r"\b(home address|ghar ka address|private gpa|personal grades)\b", value):
        return True
    if re.search(
        r"how.{0,30}(?:calculat|improv)|\b(?:policy|minimum|required|requirement)\b", value
    ):
        return False
    record = r"grades?|gpa|cgpa|marks|attendance\s+record|transcript|student\s+record"
    possession = r"\b(my|his|her|another student'?s?|mere|mera|meri|doosre student|\w+['’]s)\b"
    access = r"\b(show|tell|give|access|download|fetch|retrieve|dikhao|batao|nikaal)\b"
    # A student asking a general policy question ("how is my GPA calculated?")
    # does not request access to their record.
    return bool(
        re.search(possession, value) and re.search(access, value) and re.search(record, value)
    )


def private_record_answer(query: str, language: str):
    if not private_record_request(query):
        return None
    from app.response.grounded import GroundedAnswer

    messages = {
        "english": (
            "I cannot access or share private student records or personal contact details. "
            "Please use the authorized university portal or contact the department."
        ),
        "roman_urdu": (
            "Main private student records ya personal contact details access ya share nahi "
            "kar sakta. Authorized university portal use karein ya department se rabta karein."
        ),
        "urdu": (
            "میں طلبہ کے نجی ریکارڈ یا ذاتی رابطے کی تفصیلات تک رسائی حاصل یا انہیں فراہم "
            "نہیں کر سکتا۔ براہِ کرم مجاز یونیورسٹی پورٹل استعمال کریں یا شعبے سے رابطہ کریں۔"
        ),
    }
    return GroundedAnswer(
        messages.get(language, messages["english"]),
        engine="fallback",
        grounding_status="private_information",
        model="privacy-guard",
    )

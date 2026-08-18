import re


URDU_SCRIPT = re.compile(r"[\u0600-\u06ff]")
ROMAN_URDU_MARKERS = {
    "kya", "hai", "hain", "kitni", "kitne", "ka", "ki", "ke", "mujhe",
    "chahiye", "tarekha", "tareekh", "dikha", "dein", "karne", "sakte", "assalam",
}


def detect_language(text: str) -> str:
    if URDU_SCRIPT.search(text):
        return "urdu"
    tokens = set(re.findall(r"[a-z']+", text.lower()))
    if len(tokens & ROMAN_URDU_MARKERS) >= 1:
        return "roman_urdu"
    return "english"

"""Fast, complete-turn conversational replies; academic questions still use RAG."""

import re
import unicodedata

from app.response.grounded import GroundedAnswer


def conversational_reply(message: str, language: str) -> GroundedAnswer | None:
    text = unicodedata.normalize("NFKC", message).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    text = " ".join(text.split())
    greeting = (
        r"hi+|he+y+|hello+|salaa?m|assalam(?:u|o)? alaikum|assalam o alaikum|"
        r"as salam al[ae]ikum|salaam alaikum|good morning|good afternoon|good evening|"
        r"السلام علیکم|اسلام علیکم|وعلیکم السلام"
    )
    kind = None
    if re.fullmatch(rf"(?:{greeting})(?:\s+(?:{greeting}|there|everyone|qau|advisor|bot))*", text):
        kind = "greeting"
    # A greeting may precede another purely conversational turn. A real
    # question still fails these complete-turn patterns and proceeds to RAG.
    text = re.sub(rf"^(?:{greeting})(?:\s+(?:{greeting}))*\s+", "", text)
    if kind is None and re.fullmatch(
        r"thanks?(?: you)?(?: so much| a lot)?|thank you(?: so much)?|shukriya|شکریہ", text
    ):
        kind = "thanks"
    elif re.fullmatch(
        r"how are you(?: doing)?|how s it going|k[ae]ise ho|aap k[ae]ise hain|آپ کیسے ہیں", text
    ):
        kind = "wellbeing"
    elif re.fullmatch(
        r"help(?: me)?|i need help|can you help(?: me)?|what can you do|"
        r"how can you help(?: me)?|who are you|what(?: s| is) your name",
        text,
    ):
        kind = "capabilities"
    elif re.fullmatch(r"ok(?:ay)?|alright|got it|acha|theek(?: hai)?|ٹھیک ہے", text):
        kind = "acknowledgement"
    elif re.fullmatch(r"bye(?: bye)?|goodbye|see you|allah hafiz|خدا حافظ|اللہ حافظ", text):
        kind = "farewell"
    if kind is None:
        return None
    replies = {
        "english": {
            "greeting": "Hi! How can I help you with QAU today?",
            "thanks": "You're welcome! Let me know if you need anything else.",
            "wellbeing": "I'm here and ready to help. What would you like to know?",
            "capabilities": (
                "I'm your QAU CS advisor. Ask me about programmes, admissions, courses, "
                "fees, faculty or university policies. I'll use the available university "
                "sources and tell you when information is missing."
            ),
            "acknowledgement": "Got it. Let me know what you'd like to check next.",
            "farewell": "Take care, and good luck with your studies!",
        },
        "roman_urdu": {
            "greeting": "Assalamu Alaikum! QAU ke bare mein kis cheez mein madad chahiye?",
            "thanks": "Khushi hui madad kar ke! Aur kuch poochna ho to batayein.",
            "wellbeing": "Main madad ke liye tayyar hoon. Aap kya janna chahte hain?",
            "capabilities": (
                "Main QAU CS advisor hoon. Programmes, admissions, courses, fees, "
                "faculty ya policies ke bare mein poochhein; main available university "
                "sources se jawab doon ga."
            ),
            "acknowledgement": "Theek hai. Agla sawal ho to batayein.",
            "farewell": "Allah Hafiz! Parhai ke liye naik khwahishat.",
        },
        "urdu": {
            "greeting": "السلام علیکم! آج QAU کے بارے میں کس چیز میں مدد چاہیے؟",
            "thanks": "خوش رہیں! مزید مدد چاہیے تو بتائیں۔",
            "wellbeing": "میں مدد کے لیے تیار ہوں۔ آپ کیا جاننا چاہتے ہیں؟",
            "capabilities": (
                "میں QAU CS کا معاون ہوں۔ پروگرامز، داخلوں، کورسز، فیس، اساتذہ یا "
                "پالیسیوں کے بارے میں پوچھیں؛ میں دستیاب یونیورسٹی ذرائع سے جواب دوں گا۔"
            ),
            "acknowledgement": "ٹھیک ہے۔ اگلا سوال ہو تو بتائیں۔",
            "farewell": "اللہ حافظ! آپ کی تعلیم کے لیے نیک خواہشات۔",
        },
    }
    return GroundedAnswer(
        replies.get(language, replies["english"])[kind],
        engine="conversation",
        grounding_status="conversational",
        model="conversation",
    )

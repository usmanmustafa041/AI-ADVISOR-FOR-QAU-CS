"""Exact timetable lookups.

Students ask for the timetable in many shapes: *"monday ko 8th semester ki kon kon si classes hain"*,
*"Dr. Rabeeh kab parhate hain"*, *"room 201 mein 10 baje kya hai"*, *"semester 5 regular ka timetable"*.
A language model reading a few retrieved chunks gets these wrong (it mixes classes, drops rows). The
timetable PDF is a grid, so the answer is a *lookup*: this module parses the question into filters
(day, class, section, teacher, room, time, course), applies them to the structured timetable built at
ingest time, and renders a table. The same code path serves English, Roman Urdu and Urdu.

``Timetable.answer`` returns ``None`` when the message is not a timetable lookup, so everything else
keeps flowing through the normal retrieval + generation path.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

DAY_ORDER = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
DAY_ALIASES = {
    "MONDAY": r"mon(?:day)?|somwar|sumwar|peer|pir|پیر",
    "TUESDAY": r"tue(?:s|sday)?|mangal|mangl|منگل",
    "WEDNESDAY": r"wed(?:nesday)?|budh|بدھ",
    "THURSDAY": r"thu(?:r|rs|rsday)?|jumerat|jumeraat|جمعرات",
    "FRIDAY": r"fri(?:day)?|jumma|juma|jumah|جمعہ",
    "SATURDAY": r"sat(?:urday)?|sanichar",
    "SUNDAY": r"sun(?:day)?|itwar|itwaar|اتوار",
}
DAY_RE = {d: re.compile(rf"(?<![a-z])(?:{a})(?![a-z])", re.I) for d, a in DAY_ALIASES.items()}
DAY_NAME_UR = {"MONDAY": "پیر", "TUESDAY": "منگل", "WEDNESDAY": "بدھ", "THURSDAY": "جمعرات",
               "FRIDAY": "جمعہ", "SATURDAY": "ہفتہ", "SUNDAY": "اتوار"}
TODAY_RE = re.compile(r"\b(today|aaj|aj)\b|آج", re.I)
TOMORROW_RE = re.compile(r"\b(tomorrow|tmrw|tmr|kal)\b|کل", re.I)
WEEK_RE = re.compile(r"\b(week|weekly|whole week|poore hafte|pure hafte|haftawar|hafte ka)\b|ہفتہ وار", re.I)

ROMAN_UR_WORDS = re.compile(r"\b(kon|kaun|kaunsi|konsi|kon\s?si|kab|kya|ko|ki|ka|ke|hai|hain|aaj|kal|parhate|parhata|parhati|mein|me|se|wali|wala|aur|ya|kitne|baje|bje|din|bata|batao|dikhao|hota|hoti|hoga|kia|kitni|kitna|kaisi|batao|bataen|chahiye|wali|wale|mujhe|mera|meri)\b")
def looks_roman_urdu(text: str) -> bool:
    """Roman Urdu is Latin text that language detectors call English; two distinct common Urdu words give it away."""
    return len(set(ROMAN_UR_WORDS.findall(text.lower()))) >= 2


ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
            "ninth": 9, "tenth": 10, "pehla": 1, "pehle": 1, "dosra": 2, "doosra": 2, "teesra": 3, "chautha": 4,
            "panchwa": 5, "panchwan": 5, "chatha": 6, "satwa": 7, "satwan": 7, "athwa": 8, "athwan": 8,
            "پہلے": 1, "پہلا": 1, "دوسرے": 2, "دوسرا": 2, "تیسرے": 3, "تیسرا": 3, "چوتھے": 4, "چوتھا": 4,
            "پانچویں": 5, "چھٹے": 6, "چھٹا": 6, "ساتویں": 7, "آٹھویں": 8, "آٹھواں": 8, "نویں": 9, "دسویں": 10}
CARDINALS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "paanch": 5, "panch": 5, "chay": 6, "saat": 7, "aath": 8}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
ROMAN_OUT = {v: k.upper() for k, v in ROMAN.items()}
SEM_WORD = r"(?:semester|semestr|sem|smstr|samester|سمسٹر)"

CUES = re.compile(
    r"time\s?table|schedule|class(?:es)?\b|lectures?\b|\blec\b|\broom\b|\bperiods?\b|\bslot\b|\bfree\b|\bkhali\b|\bkhaali\b|\bkab\b|"
    r"kitne\s+baje|\bbaje\b|\bbje\b|kis\s+din|kis\s+room|kahan|kahaan|parh(?:a|ata|ate|ati|ayen|aenge)\b|"
    r"ٹائم\s?ٹیبل|کلاس|کب|کمرہ|\bwhen\b|\btimings?\b|\btime\b|\bwaqt\b|\bvaqt\b|lab\b|\bsession",
    re.I,
)
# Cues that are specific to timetables; "time"/"when"/"timings" alone are too common to hijack a question.
STRONG_CUES = re.compile(
    r"time\s?table|schedule|class(?:es)?\b|lectures?\b|\blec\b|\broom\b|\bperiods?\b|\bslot\b|\bfree\b|\bkhali\b|\bkhaali\b|\bkab\b|"
    r"kitne\s+baje|\bbaje\b|\bbje\b|kis\s+din|kis\s+room|parh(?:a|ata|ate|ati|ayen|aenge)\b|"
    r"ٹائم\s?ٹیبل|کلاس|کب|کمرہ|\bsession",
    re.I,
)
NOT_TIMETABLE = re.compile(
    r"\b(exam|datesheet|date\s?sheet|midterm|mid-term|final|terminal|paper|result|admission|merit|fee|deadline|"
    r"scheme|prerequisite|prereq|credit|syllabus|outline|calendar|holiday|gpa|cgpa)\b",
    re.I,
)
FREE_RE = re.compile(r"\b(free|khali|khaali|vacant|empty|available)\b|خالی", re.I)
TITLE_WORDS = {"dr", "mr", "ms", "mrs", "miss", "sir", "madam", "mam", "maam", "prof", "professor", "doctor", "engr", "ma'am"}
STOP = {"class", "classes", "the", "and", "for", "ki", "ka", "ke", "ko", "kon", "kaun", "kab", "kya", "hai", "hain", "from",
        "with", "that", "this", "what", "when", "where", "time", "table", "timetable", "schedule", "room", "show",
        "semester", "morning", "evening", "regular", "self", "support", "week", "aaj", "today", "tomorrow", "lecture"}
COURSE_ALIASES = {
    "dsa": "data structures", "ds": "data structures", "dbms": "database systems", "db": "database systems",
    "oop": "object oriented programming", "os": "operating systems", "ai": "artificial intelligence",
    "wad": "web application development", "hci": "human computer interaction", "psp": "problem solving",
    "ict": "applications of ict", "ada": "analysis and design of algorithms", "sc": "software construction",
    "stat": "probability and statistics", "dm": "discrete mathematics", "cc": "compiler construction",
    "sqa": "software quality assurance", "iis": "information security", "tbw": "technical and business writing",
    "ico": "computer organization", "mad": "mobile application development",
}

T = {
    "en": {
        "intro": "Here is the timetable for {what}:",
        "all_classes": "all classes", "on": "on {day}", "weekly": "the whole week",
        "cols": ("Time", "Course", "Teacher", "Room", "Class", "Day"),
        "sec": {"R": "Regular (morning)", "S": "Self-support (evening)", "RS": "Regular & Self-support", "Rep": "Repeaters"},
        "teacher_of": "{t}", "room_of": "room {r}", "course_of": "{c}",
        "also_other_days": "This class also meets on: {days}.",
        "no_slot": "No fixed weekly slot in the timetable: {names}.",
        "other_courses": "Other courses of this class (not on {day}): {items}.",
        "sections_note": "{cls} has separate Regular (morning) and Self-support (evening) sections; both are shown.",
        "only_section": "The timetable lists {cls} only for the {sec} section.",
        "free_title": "Free slots in room {r} ({day}):", "no_free": "no free slot — booked all day",
        "none_day": "No classes are scheduled on {day}.",
        "none_found": "I couldn't find any scheduled class for {what}.",
        "none_that_day": "There is no class for {what} on {day}.",
        "meets_on": "It meets on: {days}.",
        "no_class": "The {term} timetable doesn't list {cls}. Classes it does list: {avail}.",
        "no_teacher": "I couldn't find that teacher in the {term} timetable.",
        "help": ("I can show the timetable by **day**, **semester**, **teacher**, **room** or **course**. For example:\n\n"
                 "- *Monday classes for 8th semester*\n- *Dr. Rabeeh's timetable*\n- *What is in room 201 on Tuesday?*\n"
                 "- *Operating Systems class time*"),
        "foot": "Source: {title}{eff} [1]. R = Regular (morning), S = Self-support (evening). CS- and CSC- codes are the same courses. "
                "Please confirm with the department office if the timetable has been revised.",
        "weekend": "Today is {day}, and the department has no classes then.",
        "tomorrow_is": "(tomorrow is {day})", "today_is": "(today is {day})", "more_days": "Other days",
        "edited_note": "✎ Updated by the department on {date}; this can differ from the printed PDF.",
        "foot_manual": "Source: department timetable — {title}{eff} [1]. R = Regular (morning), S = Self-support (evening). CS- and CSC- codes are the same courses. "
                       "Please confirm with the department office if anything has changed.",
    },
    "roman-ur": {
        "intro": "Ye raha {what} ka timetable:",
        "all_classes": "tamam classes", "on": "{day} ko", "weekly": "poore hafte",
        "cols": ("Time", "Course", "Teacher", "Room", "Class", "Din"),
        "sec": {"R": "Regular (morning)", "S": "Self-support (evening)", "RS": "Regular aur Self-support", "Rep": "Repeaters"},
        "teacher_of": "{t}", "room_of": "room {r}", "course_of": "{c}",
        "also_other_days": "Ye class in dino mein bhi hoti hai: {days}.",
        "no_slot": "In courses ka timetable mein koi fixed weekly slot nahi hai: {names}.",
        "other_courses": "Is class ke baaki courses ({day} ko nahi): {items}.",
        "sections_note": "{cls} ke Regular (morning) aur Self-support (evening) dono sections alag hain; dono dikhaye gaye hain.",
        "only_section": "Timetable mein {cls} sirf {sec} section ke liye diya gaya hai.",
        "free_title": "Room {r} ({day}) ke khali slots:", "no_free": "koi khali slot nahi — poora din booked",
        "none_day": "{day} ko koi class scheduled nahi hai.",
        "none_found": "{what} ke liye koi scheduled class nahi mili.",
        "none_that_day": "{what} ki {day} ko koi class nahi hai.",
        "meets_on": "Ye in dino mein hoti hai: {days}.",
        "no_class": "{term} ke timetable mein {cls} shamil nahi hai. Jo classes shamil hain: {avail}.",
        "no_teacher": "{term} ke timetable mein ye teacher mujhe nahi mile.",
        "help": ("Main timetable **din**, **semester**, **teacher**, **room** ya **course** ke hisab se dikha sakta hoon. Misal ke taur par:\n\n"
                 "- *Monday ko 8th semester ki classes*\n- *Dr. Rabeeh kab parhate hain*\n- *Room 201 mein Tuesday ko kya hai*\n"
                 "- *Operating Systems ki class kab hoti hai*"),
        "foot": "Source: {title}{eff} [1]. R = Regular (morning), S = Self-support (evening). CS- aur CSC- codes ek hi courses hain. "
                "Timetable mein tabdeeli ho sakti hai, department office se confirm kar lein.",
        "weekend": "Aaj {day} hai, aur department mein is din classes nahi hotin.",
        "tomorrow_is": "(kal {day} hai)", "today_is": "(aaj {day} hai)", "more_days": "Dusre din",
        "edited_note": "✎ Department ne {date} ko update kiya; ye chhape huay PDF se mukhtalif ho sakta hai.",
        "foot_manual": "Source: department timetable — {title}{eff} [1]. R = Regular (morning), S = Self-support (evening). CS- aur CSC- codes ek hi courses hain. "
                       "Koi tabdeeli ho to department office se confirm kar lein.",
    },
    "ur": {
        "intro": "یہ رہا {what} کا ٹائم ٹیبل:",
        "all_classes": "تمام کلاسز", "on": "{day} کے دن", "weekly": "پورے ہفتے",
        "cols": ("وقت", "کورس", "استاد", "کمرہ", "کلاس", "دن"),
        "sec": {"R": "ریگولر (صبح)", "S": "سیلف سپورٹ (شام)", "RS": "ریگولر اور سیلف سپورٹ", "Rep": "ریپیٹرز"},
        "teacher_of": "{t}", "room_of": "کمرہ {r}", "course_of": "{c}",
        "also_other_days": "یہ کلاس ان دنوں میں بھی ہوتی ہے: {days}۔",
        "no_slot": "ٹائم ٹیبل میں ان کورسز کا کوئی مقررہ ہفتہ وار وقت نہیں: {names}۔",
        "other_courses": "اس کلاس کے باقی کورسز ({day} کے دن نہیں): {items}۔",
        "sections_note": "{cls} کے ریگولر (صبح) اور سیلف سپورٹ (شام) سیکشن الگ ہیں؛ دونوں دکھائے گئے ہیں۔",
        "only_section": "ٹائم ٹیبل میں {cls} صرف {sec} سیکشن کے لیے دیا گیا ہے۔",
        "free_title": "کمرہ {r} ({day}) کے خالی اوقات:", "no_free": "کوئی خالی وقت نہیں — پورا دن مصروف",
        "none_day": "{day} کے دن کوئی کلاس مقرر نہیں۔",
        "none_found": "{what} کے لیے کوئی کلاس نہیں ملی۔",
        "none_that_day": "{what} کی {day} کے دن کوئی کلاس نہیں۔",
        "meets_on": "یہ ان دنوں میں ہوتی ہے: {days}۔",
        "no_class": "{term} کے ٹائم ٹیبل میں {cls} شامل نہیں۔ شامل کلاسز: {avail}۔",
        "no_teacher": "{term} کے ٹائم ٹیبل میں یہ استاد نہیں ملے۔",
        "help": ("میں ٹائم ٹیبل **دن**، **سمسٹر**، **استاد**، **کمرے** یا **کورس** کے مطابق دکھا سکتا ہوں۔ مثال کے طور پر:\n\n"
                 "- *پیر کو 8th سمسٹر کی کلاسز*\n- *Dr. Rabeeh کب پڑھاتے ہیں*\n- *کمرہ 201 میں منگل کو کیا ہے*\n"
                 "- *Operating Systems کی کلاس کب ہوتی ہے*"),
        "foot": "ماخذ: {title}{eff} [1]۔ R = ریگولر (صبح)، S = سیلف سپورٹ (شام)۔ CS- اور CSC- کوڈ ایک ہی کورسز ہیں۔ "
                "ٹائم ٹیبل میں تبدیلی ممکن ہے، شعبے کے دفتر سے تصدیق کر لیں۔",
        "weekend": "آج {day} ہے اور اس دن شعبے میں کلاسز نہیں ہوتیں۔",
        "tomorrow_is": "(کل {day} ہے)", "today_is": "(آج {day} ہے)", "more_days": "دوسرے دن",
        "edited_note": "✎ شعبے نے {date} کو اپ ڈیٹ کیا؛ یہ چھپے ہوئے PDF سے مختلف ہو سکتا ہے۔",
        "foot_manual": "ماخذ: شعبے کا ٹائم ٹیبل — {title}{eff} [1]۔ R = ریگولر (صبح)، S = سیلف سپورٹ (شام)۔ CS- اور CSC- کوڈ ایک ہی کورسز ہیں۔ "
                       "کوئی تبدیلی ہو تو شعبے کے دفتر سے تصدیق کر لیں۔",
    },
}


# ---------------------------------------------------------------------------------- time helpers
def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _split(rng: str) -> tuple[int, int] | None:
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", rng or "")
    if not m:
        return None
    return int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])


def _clock(minutes: int, meridiem: bool = True) -> str:
    h, m = divmod(minutes, 60)
    suffix = " AM" if h < 12 else " PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d}" + (suffix if meridiem else "")


def fmt_range(rng: str) -> str:
    sp = _split(rng)
    if not sp:
        return rng or "time not listed"
    a, b = sp
    if (a < 720) == (b < 720) or (a >= 720) == (b >= 720):
        return f"{_clock(a, False)} – {_clock(b)}"
    return f"{_clock(a)} – {_clock(b)}"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def pretty_date(stamp: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", stamp or "")
    return f"{int(m[3])} {MONTHS[int(m[2]) - 1]} {m[1]}" if m else ""


def _name_tokens(name: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]+", name.lower()) if t not in TITLE_WORDS and len(t) > 1]


def _close(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):  # one substitution
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


# ---------------------------------------------------------------------------------- query
@dataclass
class Query:
    days: list[str] = field(default_factory=list)
    relative: str = ""  # today | tomorrow
    week: bool = False
    semester: int | None = None
    program: str = ""
    sections: set[str] = field(default_factory=set)  # {"R"}, {"S"}
    teachers: list[str] = field(default_factory=list)
    rooms: list[str] = field(default_factory=list)
    room_labels: list[str] = field(default_factory=list)
    at_minute: int | None = None
    courses: list[str] = field(default_factory=list)  # course keys
    cue: bool = False
    strong: bool = False
    free: bool = False

    @property
    def subject(self) -> bool:
        return bool(self.semester or self.teachers or self.rooms or self.courses or self.program)

    @property
    def structured(self) -> bool:
        return self.subject or bool(self.days or self.relative or self.at_minute is not None)


def _parse_semester(q: str, cue: bool) -> int | None:
    low = q.lower()
    m = re.search(rf"(\d{{1,2}})\s*(?:st|nd|rd|th)?\s*[-]?\s*{SEM_WORD}", low) or re.search(rf"{SEM_WORD}\s*[-:#]?\s*(\d{{1,2}})(?!\d)", low)
    if m and 1 <= int(m[1]) <= 12:
        return int(m[1])
    m = re.search(rf"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|pehla|pehle|dosra|doosra|teesra|chautha|panchwa|panchwan|chatha|satwa|satwan|athwa|athwan)\b\s*{SEM_WORD}", low)
    if m:
        return ORDINALS[m[1]]
    m = re.search(rf"\b(one|two|three|four|five|six|seven|eight|nine|ten|paanch|panch|chay|saat|aath)\b\s*{SEM_WORD}|{SEM_WORD}\s*[-:#]?\s*\b(one|two|three|four|five|six|seven|eight|nine|ten|paanch|panch|chay|saat|aath)\b", low)
    if m:
        return CARDINALS[m[1] or m[2]]
    for word, n in ORDINALS.items():
        if re.search(rf"{re.escape(word)}\s*{SEM_WORD}|{SEM_WORD}\s*{re.escape(word)}", q) and not word.isascii():
            return n
    m = re.search(rf"\b(viii|vii|vi|iv|ix|iii|ii|v|x|i)\b\s*{SEM_WORD}", low) or re.search(rf"{SEM_WORD}\s*[-:#]?\s*(viii|vii|vi|iv|ix|iii|ii|v|x|i)\b", low)
    if m:
        return ROMAN[m[1]]
    if cue:  # "8th ki classes"
        m = re.search(r"(?<![\w:.-])(\d{1,2})\s*(?:st|nd|rd|th)\b", low)
        if m and 1 <= int(m[1]) <= 10:
            return int(m[1])
    return None


class Timetable:
    def __init__(self, data: dict):
        self.data = data
        self.term = data.get("term") or "current term"
        self.effective = data.get("effective") or ""
        self.url = data.get("url") or ""
        self.classes: list[dict] = data.get("classes", [])
        self.sessions: list[dict] = data.get("sessions", [])
        self.teacher_index: dict[str, set[str]] = {}
        self.course_index: dict[str, dict] = {}
        for cls in self.classes:
            for c in cls["courses"]:
                if c.get("teacher"):
                    self.teacher_index.setdefault(c["teacher"], set()).update(_name_tokens(c["teacher"]))
                key = c.get("key")
                if key:
                    info = self.course_index.setdefault(key, {"title": c["title"], "code": c["code"], "abbr": set()})
                    for tok in re.findall(r"[A-Za-z]{2,}", re.sub(r"^\S+\s+", "", c["label"])):
                        if tok.upper() not in ("R", "S", "REP", "RS"):
                            info["abbr"].add(tok.lower())
        self.manual_only = bool(data.get("manual_only"))
        for sess in self.sessions:  # a visiting teacher / make-up class carries its own teacher
            if sess.get("teacher"):
                self.teacher_index.setdefault(sess["teacher"], set()).update(_name_tokens(sess["teacher"]))
        self.rooms = sorted({s["room"] for s in self.sessions})
        self.grid_slots = sorted({s["slot"] for s in self.sessions if s.get("slot") and _split(s["slot"])},
                                 key=lambda t: _split(t)[0])
        if not self.grid_slots:  # no PDF grid (manual timetable): use the times that repeat
            counts: dict[str, int] = {}
            for sess in self.sessions:
                if _split(sess.get("time", "")):
                    counts[sess["time"]] = counts.get(sess["time"], 0) + 1
            self.grid_slots = sorted((t for t, n in counts.items() if n >= 2), key=lambda t: _split(t)[0])

    @classmethod
    def from_json(cls, data: dict) -> Timetable:
        return cls(data)

    # ------------------------------------------------------------------ parsing
    def parse(self, question: str, today: dt.date | None = None) -> Query:
        q = Query()
        text = question.strip()
        low = text.lower()
        q.cue = bool(CUES.search(text))
        q.strong = bool(STRONG_CUES.search(text))
        for d, rx in DAY_RE.items():
            if rx.search(text):
                q.days.append(d)
        today = today or dt.date.today()
        if not q.days and TODAY_RE.search(text):
            q.relative, q.days = "today", [DAY_ORDER[today.weekday()]]
        elif not q.days and TOMORROW_RE.search(text):
            q.relative, q.days = "tomorrow", [DAY_ORDER[(today.weekday() + 1) % 7]]
        q.week = bool(WEEK_RE.search(text)) and not q.days
        q.semester = _parse_semester(text, q.cue)
        if re.search(r"mphil|phd", low):
            q.program = "MPhil/PhD"
        elif re.search(r"ms-?\s?ds\b|msds", low):
            q.program = "MS-DS"
        elif q.semester:
            q.program = "BS"
        if re.search(r"self[\s-]?support|\bevening\b|\bshaam\b|\bss\b|سیلف", low):
            q.sections.add("S")
        if re.search(r"\bregular\b|\bmorning\b|\bsubah\b|\bsubha\b|ریگولر|صبح", low):
            q.sections.add("R")
        q.free = bool(FREE_RE.search(text))
        self._parse_rooms(low, q)
        self._parse_time(low, q)
        self._parse_teachers(low, q)
        self._parse_courses(text, low, q)
        return q

    @staticmethod
    def _room_keys(room: str) -> set[str]:
        labs = {f"lab{n}" for n in re.findall(r"lab\s*(\d+)", room.lower())}
        return labs or {re.sub(r"[\s/]+", "", room.lower())}

    def _parse_rooms(self, low: str, q: Query) -> None:
        wanted: list[str] = []
        for m in re.finditer(r"\b(?:room|rm|kamra|kamre)\s*(?:no\.?|number|#)?\s*([a-z]?\d{1,3})\b|کمرہ\s*(\d{1,3})", low):
            wanted.append((m[1] or m[2]).replace(" ", ""))
        for m in re.finditer(r"\blab\s*(\d{1,3}|three)\b", low):
            wanted.append("lab" + ("3" if m[1] == "three" else m[1]))
        for m in re.finditer(r"\b(f6|f8)\b", low):
            wanted.append(m[1])
        for name, key in (("seminar room", "seminarroom"), ("bs lab", "bslab"), ("cs lab", "cslab"), ("online", "online")):
            if name in low:
                wanted.append(key)
        for w in wanted:
            for room in self.rooms:
                if w in self._room_keys(room) and room not in q.rooms:
                    q.rooms.append(room)
            plain = next((r for r in self.rooms if self._room_keys(r) == {w}), None)
            label = plain or (f"Lab {w[3:]}" if w.startswith("lab") else w.upper() if re.fullmatch(r"f\d", w) else w)
            if label not in q.room_labels and any(w in self._room_keys(r) for r in self.rooms):
                q.room_labels.append(label)

    def _parse_time(self, low: str, q: Query) -> None:
        m = re.search(r"(?<![\d:])(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje|bje|o'?clock)\b", low) or re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b(?!\s*(?:st|nd|rd|th))", low) or re.search(r"(?<!\d)(\d{1,2}):(\d{2})\b", low)
        if not m:
            return
        h, mi = int(m[1]), int(m[2] or 0)
        mer = (m[3] or "").lower() if m.lastindex and m.lastindex >= 3 else ""
        if h > 23 or mi > 59 or (mi == 0 and m.lastindex and not m[2] and h > 12 and not mer):
            return
        if mer == "pm" and h < 12:
            h += 12
        elif mer == "am" and h == 12:
            h = 0
        elif not mer and 1 <= h <= 7:  # classes run 8:30–20:00, so "3 baje" means 3 PM
            h += 12
        q.at_minute = h * 60 + mi

    def _parse_teachers(self, low: str, q: Query) -> None:
        words = re.findall(r"[a-z]+", low)
        have_title = any(w in TITLE_WORDS for w in words)
        found: list[str] = []
        for w in words:
            if len(w) < 4 or w in STOP or w in TITLE_WORDS or w in COURSE_ALIASES:
                continue
            hits = [t for t, toks in self.teacher_index.items() if any(_close(w, tok) for tok in toks)]
            if hits and len(hits) <= 3 and (have_title or q.cue or len(words) <= 4):
                for t in hits:
                    if t not in found:
                        found.append(t)
        # two spelling variants of one name (Umer / Umar Rashid) are the same query, not two people
        q.teachers = found

    def _parse_courses(self, text: str, low: str, q: Query) -> None:
        keys: list[str] = []
        for m in re.finditer(r"\b([A-Za-z]{2,4})\s?-?\s?(\d{3})[A-Za-z]?\b", text):
            code = f"{m[1].upper()}-{m[2]}"
            code = re.sub(r"^CS-", "CSC-", code)
            if code in self.course_index and code not in keys:
                keys.append(code)
        norm = " " + re.sub(r"[^a-z0-9&+ ]+", " ", low) + " "
        for key, info in self.course_index.items():
            if key in keys:
                continue
            title = re.sub(r"[^a-z0-9&+ ]+", " ", info["title"].lower()).strip()
            long_title = len(title) >= 7 and f" {title} " in norm
            alias_hit = any(a in norm.split() and COURSE_ALIASES[a] in info["title"].lower() for a in COURSE_ALIASES)
            abbr_hit = any(len(a) >= 3 and f" {a} " in norm and a not in STOP for a in info["abbr"])
            if long_title or alias_hit or abbr_hit:
                keys.append(key)
        q.courses = keys

    # ------------------------------------------------------------------ lookup
    @staticmethod
    def _compatible(cls_sections: list[str], sec: str) -> bool:
        if not sec:
            return True
        if sec == "RS":
            return bool(set(cls_sections) & {"R", "S"})
        return sec in cls_sections

    def _rows(self, s: dict) -> list[tuple[dict, dict]]:
        every, out = [], []
        for cls in self.classes:
            for c in cls["courses"]:
                if s["key"] and c.get("key") == s["key"]:
                    every.append((cls, c))
                    if self._compatible(cls["sections"], s["section"]):
                        out.append((cls, c))
        return out or every  # a stray section letter in the grid must not hide a course the allocation lists

    def _class_ok(self, cls: dict, q: Query) -> bool:
        if q.program and cls["program"] != q.program:
            return False
        if q.semester and q.semester not in cls["semesters"]:
            return False
        if q.sections and not (q.sections & set(cls["sections"])):
            return False
        return True

    def select(self, q: Query) -> list[dict]:
        rows_out = []
        for s in self.sessions:
            if q.days and s["day"] not in q.days:
                continue
            if q.rooms and s["room"] not in q.rooms:
                continue
            if q.at_minute is not None:
                sp = _split(s["time"])
                if not sp or not (sp[0] - 20 <= q.at_minute < sp[1]):
                    continue
            if q.courses and s["key"] not in q.courses:
                continue
            rows = self._rows(s)
            need_rows = bool(q.semester or q.program or q.sections or q.teachers)
            if need_rows:
                rows = [(cls, c) for cls, c in rows if self._class_ok(cls, q)
                        and (not q.teachers or (s.get("teacher") or c.get("teacher")) in q.teachers)]
                if not rows:
                    continue
            rows_out.append({"s": s, "rows": rows})
        return rows_out

    # ------------------------------------------------------------------ rendering helpers
    def _class_label(self, cls: dict, lang: str, with_section: bool = True) -> str:
        if cls["program"] == "BS" and cls["semesters"]:
            base = f"BS Semester {ROMAN_OUT[cls['semesters'][0]]}"
        else:
            base = cls["group"]
        secs = cls["sections"]
        key = "Rep" if secs == ["Rep"] else "".join(sorted(secs)) if len(secs) == 2 else (secs[0] if secs else "")
        if key == "RS":
            return base
        tag = T[lang]["sec"].get(key, "") if with_section else ""
        return f"{base} · {tag}" if tag else base

    def _entries(self, picked: list[dict], lang: str) -> list[dict]:
        entries = []
        for item in picked:
            s, rows = item["s"], item["rows"]
            teachers = [s["teacher"]] if s.get("teacher") else list(dict.fromkeys(c["teacher"] for _cls, c in rows if c.get("teacher")))
            title = s.get("title") or (rows[0][1]["title"] if rows else "")
            code = rows[0][1]["code"] if rows else s["code"]
            groups: dict[str, set[str]] = {}
            for cls, _c in rows:
                base = self._class_label(cls, lang, with_section=False)
                groups.setdefault(base, set()).update(cls["sections"] if cls["sections"] != ["R", "S"] else [])
            classes = []
            for base, secs in groups.items():
                key = "Rep" if secs == {"Rep"} else "RS" if secs >= {"R", "S"} else next(iter(secs), "")
                tag = T[lang]["sec"].get(key, "")
                classes.append(f"{base} · {tag}" if tag else base)
            entries.append({"day": s["day"], "time": s["time"], "room": s["room"], "code": code or s["code"],
                            "title": title or s["text"], "teachers": teachers, "classes": classes,
                            "start": (_split(s["time"]) or (9999, 0))[0], "text": s["text"],
                            "edited": s.get("src") in ("edited", "manual"), "stamp": s.get("stamp", ""), "note": s.get("note", "")})
        entries.sort(key=lambda e: (DAY_ORDER.index(e["day"]), e["start"], e["room"]))
        merged: list[dict] = []
        for e in entries:  # same course, day, time and room seen twice (R+S cells) → one line
            if merged and all(merged[-1][k] == e[k] for k in ("day", "time", "room", "code")):
                merged[-1]["classes"] = list(dict.fromkeys(merged[-1]["classes"] + e["classes"]))
                merged[-1]["teachers"] = list(dict.fromkeys(merged[-1]["teachers"] + e["teachers"]))
                merged[-1]["edited"] = merged[-1]["edited"] or e["edited"]
                merged[-1]["stamp"] = max(merged[-1]["stamp"], e["stamp"])
                continue
            merged.append(e)
        return merged

    @staticmethod
    def _md(cell: str) -> str:
        return cell.replace("|", "/").replace("\n", " ").strip()

    def _table(self, entries: list[dict], q: Query, lang: str, show_class: bool) -> str:
        c_time, c_course, c_teacher, c_room, c_class, _c_day = T[lang]["cols"]
        cols = [c_time, c_course]
        if not q.teachers:
            cols.append(c_teacher)
        if not q.rooms:
            cols.append(c_room)
        if show_class:
            cols.append(c_class)
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for e in entries:
            course = f"**{e['code']}** · {e['title']}" if e["code"] and e["title"] != e["text"] else self._md(e["title"] or e["text"])
            if e["edited"]:
                course += " ✎"
            if e.get("note"):
                course += f" _({e['note']})_"
            row = [f"`{fmt_range(e['time'])}`", self._md(course)]
            if not q.teachers:
                row.append(self._md(" / ".join(e["teachers"]) or "—"))
            if not q.rooms:
                row.append(self._md(e["room"]))
            if show_class:
                row.append(self._md(" / ".join(e["classes"]) or "—"))
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def _day_name(self, day: str, lang: str) -> str:
        return DAY_NAME_UR[day] if lang == "ur" else day.title()

    def _what(self, q: Query, lang: str, classes: list[dict], weekly: bool = True) -> str:
        t = T[lang]
        parts = []
        if q.semester and classes:
            labels = list(dict.fromkeys(self._class_label(c, lang, with_section=bool(q.sections)) for c in classes))
            parts.append(f"**{' / '.join(labels[:2])}**" if len(labels) <= 2 else f"**BS Semester {ROMAN_OUT[q.semester]}**")
        elif q.semester:
            parts.append(f"**BS Semester {ROMAN_OUT.get(q.semester, q.semester)}**")
        if q.teachers:
            parts.append("**" + " / ".join(q.teachers[:2]) + "**")
        if q.rooms:
            parts.append("**" + t["room_of"].format(r=" / ".join(q.room_labels or q.rooms)) + "**")
        if q.courses:
            names = [self.course_index[k]["title"] for k in q.courses[:2]]
            parts.append("**" + " / ".join(names) + "**")
        if q.at_minute is not None:
            parts.append("**" + _clock(q.at_minute) + "**")
        subject = " · ".join(parts) if parts else t["all_classes"]
        has_subject = bool(q.semester or q.teachers or q.rooms or q.courses)
        if q.days:
            days = " & ".join(f"**{self._day_name(d, lang)}**" for d in q.days)
            when = t["on"].format(day=days)
            return f"{subject} {when}" if lang != "roman-ur" else f"{when} {subject}"
        return f"{subject} ({t['weekly']})" if weekly and (q.week or (has_subject and not q.days and q.at_minute is None)) else subject

    # ------------------------------------------------------------------ public API
    def source_passage(self) -> dict:
        eff = f" (effective {self.effective})" if self.effective else ""
        manual = self.manual_only or not self.url
        return {
            "title": f"CS Department Timetable — {self.term}", "heading": f"CS Department Timetable — {self.term}",
            "url": self.url or "doc://department-timetable", "kind": "timetable",
            "kind_label": "department timetable" if manual else "timetable PDF",
            "text": f"Weekly timetable of the Department of Computer Sciences, {self.term}{eff}.",
            "note": "", "fetched": "", "score": 1.0, "chunk_id": "computed-timetable",
        }

    def _inherit(self, q: Query, history: list[tuple[str, str]], question: str, today: dt.date) -> Query:
        """A short follow-up ("aur Tuesday?", "what about 5th?") borrows what it leaves out from the last timetable question."""
        short = len(question.split()) <= 6
        if not short or not history:
            return q
        prev = None
        for role, text in reversed(history):
            if role != "user":
                continue
            pq = self.parse(text, today)
            if pq.structured and (pq.cue or pq.subject):
                prev = pq
                break
        if prev is None:
            return q
        if q.subject and not q.days and prev.days and not q.week:
            q.days = list(prev.days)
        elif q.days and not q.subject and prev.subject:
            q.semester, q.program, q.teachers, q.rooms, q.courses = prev.semester, prev.program, list(prev.teachers), list(prev.rooms), list(prev.courses)
            q.sections = q.sections or set(prev.sections)
        return q

    def answer(self, question: str, lang: str = "en", history: list[tuple[str, str]] | None = None,
               today: dt.date | None = None) -> dict | None:
        today = today or dt.date.today()
        if NOT_TIMETABLE.search(question) and not DAY_RE["MONDAY"].search(question):
            return None
        q = self.parse(question, today)
        if history:
            q = self._inherit(q, history, question, today)
        lang = lang if lang in T else "en"
        if lang == "en" and looks_roman_urdu(question):
            lang = "roman-ur"
        t = T[lang]
        if not q.structured:
            if re.search(r"time\s?table|ٹائم\s?ٹیبل", question, re.I) and len(question.split()) <= 7 and not NOT_TIMETABLE.search(question):
                return self._reply(t["help"], q, lang, [])
            return None
        # Is this really a timetable lookup? Be conservative: a wrong hijack is worse than a normal answer.
        lookup = (
            (q.cue and (q.subject or q.days or q.at_minute is not None) and not (q.teachers and not q.strong and not q.days))
            or (bool(q.days) and q.subject)
        )
        if q.courses and not (q.days or q.semester or q.teachers or q.rooms or q.at_minute is not None or q.strong):
            lookup = False
        if q.days and not q.subject and q.at_minute is None and not q.strong:
            lookup = False
        if not lookup:
            return None

        # ---- whole class missing from this term's timetable
        if q.semester:
            known = sorted({s for c in self.classes if c["program"] == (q.program or "BS") for s in c["semesters"]})
            if q.semester not in known and (q.program or "BS") == "BS":
                avail = ", ".join(f"Semester {ROMAN_OUT[s]}" for s in known)
                return self._reply(t["no_class"].format(term=self.term, cls=f"BS Semester {ROMAN_OUT.get(q.semester, q.semester)}", avail=avail), q, lang, [])
        picked = self.select(q)
        entries = self._entries(picked, lang)
        classes = [cls for cls in self.classes if self._class_ok(cls, q)] if q.semester else []

        if q.free and q.rooms:
            return self._free_slots(q, entries, lang)
        if not entries:
            what = self._what(Query(**{**q.__dict__, "days": []}), lang, classes, weekly=False) if q.days else self._what(q, lang, classes, weekly=False)
            if q.days and not q.subject and q.at_minute is None:
                msg = t["none_day"].format(day=self._day_name(q.days[0], lang))
            elif q.days:
                other = self.select(Query(**{**q.__dict__, "days": []}))
                days = [d for d in DAY_ORDER if d in {i["s"]["day"] for i in other}]
                msg = t["none_that_day"].format(what=what, day=" & ".join(self._day_name(d, lang) for d in q.days))
                if days:
                    msg += " " + t["meets_on"].format(days=", ".join(self._day_name(d, lang) for d in days))
            elif q.teachers and not self.select(Query(teachers=q.teachers)):
                msg = t["no_teacher"].format(term=self.term)
            else:
                msg = t["none_found"].format(what=what)
            return self._reply(msg, q, lang, [])

        days_in = list(dict.fromkeys(e["day"] for e in entries))
        multi_class = len({tuple(e["classes"]) for e in entries}) > 1 or not q.semester
        show_class = bool(multi_class)
        header = t["intro"].format(what=self._what(q, lang, classes))
        out = [header, ""]
        if len(days_in) > 1:
            for d in days_in:
                sub = [e for e in entries if e["day"] == d]
                out += [f"**{self._day_name(d, lang)}**", "", self._table(sub, q, lang, show_class), ""]
        else:
            out += [self._table(entries, q, lang, show_class), ""]

        # ---- helpful extras for a class view
        extras: list[str] = []
        if q.semester and classes:
            secs_listed = sorted({s for c in classes for s in c["sections"]})
            cls0 = self._class_label(classes[0], lang, with_section=False)
            if not q.sections and len(secs_listed) == 1 and secs_listed[0] in ("R", "S"):
                extras.append(t["only_section"].format(cls=cls0, sec=t["sec"][secs_listed[0]]))
            elif not q.sections and set(secs_listed) >= {"R", "S"} and len(classes) > 1:
                extras.append(t["sections_note"].format(cls=cls0))
            all_courses = [(c["title"], c["key"]) for cls in classes for c in cls["courses"]]
            meets: dict[str, set[str]] = {}
            for item in self.select(Query(semester=q.semester, program=q.program, sections=set(q.sections))):
                key = item["s"]["key"]
                meets.setdefault(key, set()).add(item["s"]["day"])
            shown_keys = {i["s"]["key"] for i in picked}
            no_slot = [title for title, key in dict.fromkeys(all_courses) if key not in meets]
            if no_slot:
                extras.append(t["no_slot"].format(names=", ".join(dict.fromkeys(no_slot))))
            if q.days:
                others = [f"{title} ({', '.join(self._day_name(d, lang)[:3] if lang != 'ur' else self._day_name(d, lang) for d in DAY_ORDER if d in meets[key])})"
                          for title, key in dict.fromkeys(all_courses) if key in meets and key not in shown_keys]
                if others:
                    extras.append(t["other_courses"].format(day=self._day_name(q.days[0], lang), items="; ".join(others)))
        elif q.courses and len(days_in) >= 1 and q.days:
            all_days = [d for d in DAY_ORDER if d in {i["s"]["day"] for i in self.select(Query(courses=q.courses))}]
            if len(all_days) > len(days_in):
                extras.append(t["also_other_days"].format(days=", ".join(self._day_name(d, lang) for d in all_days)))
        stamps = [e["stamp"] for e in entries if e["edited"] and e["stamp"]]
        if any(e["edited"] for e in entries):
            extras.append(t["edited_note"].format(date=pretty_date(max(stamps)) if stamps else pretty_date(self.data.get("updated", ""))))
        out += [("> - " + x) for x in extras]
        if extras:
            out.append("")
        followups = self._followups(q, picked, lang)
        return self._reply("\n".join(out).rstrip(), q, lang, followups)

    def _free_slots(self, q: Query, entries: list[dict], lang: str) -> dict:
        t = T[lang]
        spans: dict[str, list[tuple[int, int]]] = {}
        for s in self.sessions:
            if s["room"] in q.rooms and _split(s["time"]):
                spans.setdefault(s["day"], []).append(_split(s["time"]))
        days = q.days or DAY_ORDER[:5]
        lines = []
        for d in days:
            free = [fmt_range(sl) for sl in self.grid_slots
                    if not any(a < _split(sl)[1] and _split(sl)[0] < b for a, b in spans.get(d, []))]
            lines.append(f"**{self._day_name(d, lang)}**: " + (", ".join(free) if free else t["no_free"]))
        title = t["free_title"].format(r=" / ".join(q.room_labels or q.rooms), day=", ".join(self._day_name(d, lang) for d in days))
        return self._reply(title + "\n\n" + "\n\n".join(lines), q, lang, [])

    def _followups(self, q: Query, picked: list[dict], lang: str) -> list[dict]:
        if len(q.days) != 1 or not q.subject:
            return []
        base = Query(**{**q.__dict__, "days": []})
        other_days = [d for d in DAY_ORDER if d in {i["s"]["day"] for i in self.select(base)} and d != q.days[0]]
        subject = self._subject_phrase(q, lang)
        chips = []
        for d in other_days[:6]:
            name = self._day_name(d, lang)
            text = f"{name} ko {subject}" if lang == "roman-ur" else f"{name} {subject}" if lang != "ur" else f"{name} {subject}"
            chips.append({"label": name, "text": text})
        return chips

    def _subject_phrase(self, q: Query, lang: str) -> str:
        sec = " regular" if q.sections == {"R"} else " self support" if q.sections == {"S"} else ""
        if q.semester:
            return f"{ordinal(q.semester)} semester{sec} ki classes" if lang == "roman-ur" else f"classes for semester {q.semester}{sec}"
        if q.teachers:
            return f"{q.teachers[0]} ki classes" if lang == "roman-ur" else f"classes of {q.teachers[0]}"
        if q.rooms:
            r0 = (q.room_labels or q.rooms)[0]
            return f"room {r0} mein kya hai" if lang == "roman-ur" else f"schedule of room {r0}"
        if q.courses:
            return f"{q.courses[0]} ki class" if lang == "roman-ur" else f"{q.courses[0]} class"
        return "classes"

    def _reply(self, body: str, q: Query, lang: str, followups: list[dict]) -> dict:
        eff = f" (effective {self.effective})" if self.effective else ""
        key = "foot_manual" if (self.manual_only or not self.url) else "foot"
        foot = T[lang][key].format(title=f"CS Department Timetable — {self.term}" if key == "foot" else self.term, eff=eff)
        return {"text": f"{body}\n\n<sub>{foot}</sub>", "followups": followups, "followup_title": T[lang]["more_days"],
                "passage": self.source_passage()}

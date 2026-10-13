"""Exact fee lookups (BS / MPhil / PhD; morning or evening; national or foreign students).

A language model that reads loose fragments of the fee pages mixes the tables up: it once answered
"fee structure kia hai?" with the *summer per-course tuition* and attached a BS evening line to PhD. The fee
pages are three small, regular tables, so the right answer is a lookup in the structured copy that the index
build keeps (``fees.json``): this module parses the question (programme, shift, student type and what is being
asked — per-semester fee, admission fee, first-semester total, summer tuition, one-time charges) and renders
the matching rows with clear labels, the term, and the source page.

``Fees.answer`` returns ``None`` for anything that is not clearly a fee-amount question (refunds, waivers,
scholarships, how to pay …), which then goes through normal retrieval.
"""

from __future__ import annotations

import re

from advisor.ingest.fees import core_rows, one_time_rows
from advisor.rag.timetable_qa import looks_roman_urdu

FEE_CUE = re.compile(
    r"\bfees?\b|\bfee\s*structure\b|\btuition\b|\bdues\b|\bchallan\b|\bkitni\s+fee\b|\bfee\s+kitn[ai]\b|فیس|\bkharcha\b|\bkharch\b",
    re.I,
)
NOT_FEE = re.compile(
    r"refund|waiver|waive|scholarship|instal+ment|concession|hostel|late\s+fee|\bfine\b|\bbank\b|account\s+number|deposit|"
    r"how\s+(?:to|do|can)\s+(?:i\s+)?pay|payment\s+(?:method|mode)|kaise\s+(?:jama|pay|bhar)|jama\s+karwa|last\s+date|due\s+date|"
    r"deadline|financial\s+aid|stipend|transport|library|merit\s+list|calculat|formula|\bkaise\b",
    re.I,
)
LEVEL_RE = {
    "BS": re.compile(r"\b(?:bs|b\.s\.?|bscs|bs\s?cs|bachelors?|undergrad(?:uate)?|ug)\b", re.I),
    "MPhil": re.compile(r"\bm\.?\s?phil\b", re.I),
    "PhD": re.compile(r"\bph\.?\s?d\b|\bdoctorate\b|\bdoctoral\b", re.I),
    "MS": re.compile(r"\bms(?:[-\s]?(?:ds|ist|cs))?\b(?!\.)|\bm\.s\b", re.I),
}
REGULAR = re.compile(r"\bregular\b|\bmorning\b|\bsubah\b|\bday\s+program|ریگولر|صبح", re.I)
EVENING = re.compile(r"\bevening\b|\bself[\s-]?(?:finance|financed|support)\b|\bsf\b|\bshaam\b|\bnight\b|ایوننگ|شام|سیلف", re.I)
FOREIGN = re.compile(r"\bforeign(?:er|ers)?\b|\binternational\b|\boverseas\b|\babroad\b|\bdollars?\b|\busd\b|\$|non[\s-]?pakistani|غیر\s*ملکی", re.I)
SUMMER = re.compile(r"\bsummer\b|\bgarmi|سمر", re.I)
ADMISSION = re.compile(r"admission\s+fee|at\s+(?:the\s+)?time\s+of\s+admission|new\s+admission|admission\s+(?:ke|ki|k)\s|first\s+semester|pehle\s+semester|داخلہ", re.I)
PER_SEM = re.compile(r"per\s+semester|every\s+semester|each\s+semester|semester\s+fee|sem\s+fee|(?:normal|regular|ordinary)\s+sem|har\s+semester|ہر\s*سمسٹر|fee\s+per\s+sem", re.I)
ONE_TIME = re.compile(r"ڈگری|سرٹیفکیٹ|one[\s-]?time|certificates?|degree|transcript|grade\s*card|result\s*card|migration|verification|re[\s-]?exam|duplicate|folder|processing|non[\s-]?credit|repeat|improv|failure|extension|detail\s+marks?|\bdmc\b|misc", re.I)
ITEM_KEYS = [
    (r"urgent\s+degree|degree.*urgent", r"Urgent Degree Fee"),
    (r"duplicate\s+degree", r"Duplicate Degree Fee"),
    (r"degree\s+folder|folder", r"Degree Folder"),
    (r"degree", r"^Degree Fee"),
    (r"migration", r"Migration"),
    (r"grade\s*card|result\s*card|transcript", r"Grade Card"),
    (r"duplicate\s+(?:detail\s+)?marks?|duplicate\s+dmc", r"Duplicate Detail"),
    (r"detail\s+marks?|\bdmc\b", r"Detail Mark"),
    (r"verification", r"Verification"),
    (r"re[\s-]?exam", r"Re-examination"),
    (r"extension", r"Extension"),
    (r"processing", r"Processing"),
    (r"non[\s-]?credit", r"non credit"),
    (r"repeat|improv|failure", r"Repeating"),
]

T = {
    "en": {
        "intro": "Here are the **{what}** fees for **Computer Science** ({scope}):",
        "scope_nat": "national students, PKR", "scope_for": "foreign students, US dollars",
        "per_sem": "Per semester (every semester)", "adm": "Admission fee (once)",
        "first": "First semester total (admission + semester)", "summer": "Summer semester (per course)",
        "reg": "BS · Regular", "eve": "BS · Evening", "metric": "",
        "items_intro": "Here are the one-time / certificate charges for **{what}** (PKR):",
        "item": "Charge", "none_item": "I couldn't find that charge in the fee pages.",
        "evening_open": "BS evening (open merit): Rs. {v:,}.",
        "summer_rule": "A summer course runs only if at least 12 students join; otherwise the students share the teacher's remuneration equally.",
        "extras": "ℹ️ Field-work / laboratory charges (where applicable) and 5% advance tax (section 326(I)) are added on top. These are the department's national-student rates as printed on the page.",
        "ms": "I don't have the **MS** fee structure: QAU lists it on a separate page that is not among the pages I could read. The MPhil and PhD tables above are different programmes. Please confirm the MS fee with the department office: {contact}.",
        "term_note": "Terms on the page: {terms}.",
        "foot": "Source: {src}. Always confirm with the department office before paying.",
        "more": "You can also ask", "mismatch": "⚠ The page's totals do not add up exactly; the figures are shown as printed.",
        "chips": {"eve": "BS evening fee", "mphil": "MPhil fee", "phd": "PhD fee", "summer": "Summer semester fee", "items": "Degree and certificate fees", "foreign": "Fee for foreign students"},
        "foreign_title": "Foreign students (US dollars), {level}",
        "foreign_rows": ("Admission (Category A)", "Per semester (Category B)", "Total at admission"),
    },
    "roman-ur": {
        "intro": "Ye hain **Computer Science** ki **{what}** ki fees ({scope}):",
        "scope_nat": "pakistani students, PKR", "scope_for": "foreign students, US dollars",
        "per_sem": "Har semester ki fee", "adm": "Admission fee (sirf aik baar)",
        "first": "Pehle semester ka total (admission + semester)", "summer": "Summer semester (har course ki)",
        "reg": "BS · Regular", "eve": "BS · Evening", "metric": "",
        "items_intro": "Ye hain **{what}** ke one-time / certificate charges (PKR):",
        "item": "Charge", "none_item": "Ye charge mujhe fee pages mein nahi mila.",
        "evening_open": "BS evening (open merit): Rs. {v:,}.",
        "summer_rule": "Summer course tab chalta hai jab kam az kam 12 students hon; warna students teacher ka muawza barabar bant kar dete hain.",
        "extras": "ℹ️ Field-work / laboratory charges (jahan lagu hon) aur 5% advance tax (section 326(I)) ispar alag se lagte hain. Ye department ke pakistani students ke rates hain jo page par likhe hain.",
        "ms": "Mere paas **MS** ka fee structure nahi hai: QAU isay alag page par deta hai jo mere paas maujood pages mein shamil nahi. Upar MPhil aur PhD ke tables doosre programmes ke hain. MS ki fee department office se confirm karein: {contact}.",
        "term_note": "Page par terms: {terms}.",
        "foot": "Source: {src}. Payment se pehle department office se confirm kar lein.",
        "more": "Aap ye bhi pooch sakte hain", "mismatch": "⚠ Page ke totals bilkul match nahi karte; figures waisay hi dikhaye gaye hain jaisay page par hain.",
        "chips": {"eve": "BS evening ki fee", "mphil": "MPhil ki fee", "phd": "PhD ki fee", "summer": "Summer semester ki fee", "items": "Degree aur certificate ki fees", "foreign": "Foreign students ki fee"},
        "foreign_title": "Foreign students (US dollars), {level}",
        "foreign_rows": ("Admission (Category A)", "Har semester (Category B)", "Admission ke waqt total"),
    },
    "ur": {
        "intro": "یہ ہیں **کمپیوٹر سائنس** کی **{what}** کی فیسیں ({scope}):",
        "scope_nat": "پاکستانی طلبہ، روپے", "scope_for": "غیر ملکی طلبہ، امریکی ڈالر",
        "per_sem": "ہر سمسٹر کی فیس", "adm": "داخلہ فیس (صرف ایک بار)",
        "first": "پہلے سمسٹر کا کل (داخلہ + سمسٹر)", "summer": "سمر سمسٹر (فی کورس)",
        "reg": "BS · ریگولر", "eve": "BS · ایوننگ", "metric": "",
        "items_intro": "یہ ہیں **{what}** کے ایک بار والے / سرٹیفکیٹ چارجز (روپے):",
        "item": "چارج", "none_item": "یہ چارج مجھے فیس کے صفحات میں نہیں ملا۔",
        "evening_open": "BS ایوننگ (اوپن میرٹ): {v:,} روپے۔",
        "summer_rule": "سمر کورس صرف تب چلتا ہے جب کم از کم 12 طلبہ ہوں؛ ورنہ طلبہ استاد کا معاوضہ برابر بانٹ لیتے ہیں۔",
        "extras": "ℹ️ فیلڈ ورک / لیبارٹری چارجز (جہاں لاگو ہوں) اور 5% ایڈوانس ٹیکس (دفعہ 326(I)) اس کے علاوہ لگتے ہیں۔ یہ صفحے پر درج پاکستانی طلبہ کے نرخ ہیں۔",
        "ms": "میرے پاس **MS** کا فیس سٹرکچر نہیں ہے: QAU اسے الگ صفحے پر دیتی ہے جو میرے پڑھے ہوئے صفحات میں شامل نہیں۔ اوپر MPhil اور PhD کے جدول دوسرے پروگراموں کے ہیں۔ MS کی فیس شعبے کے دفتر سے تصدیق کر لیں: {contact}۔",
        "term_note": "صفحے پر درج ٹرم: {terms}۔",
        "foot": "ماخذ: {src}۔ ادائیگی سے پہلے شعبے کے دفتر سے تصدیق کر لیں۔",
        "more": "آپ یہ بھی پوچھ سکتے ہیں", "mismatch": "⚠ صفحے کے مجموعے پوری طرح نہیں ملتے؛ اعداد و شمار جیسے صفحے پر ہیں ویسے دکھائے گئے ہیں۔",
        "chips": {"eve": "BS ایوننگ کی فیس", "mphil": "MPhil کی فیس", "phd": "PhD کی فیس", "summer": "سمر سمسٹر کی فیس", "items": "ڈگری اور سرٹیفکیٹ کی فیسیں", "foreign": "غیر ملکی طلبہ کی فیس"},
        "foreign_title": "غیر ملکی طلبہ (امریکی ڈالر)، {level}",
        "foreign_rows": ("داخلہ (Category A)", "ہر سمسٹر (Category B)", "داخلے کے وقت کل"),
    },
}
LEVEL_NAME = {"BS": "BS", "MPhil": "MPhil", "PhD": "PhD"}
CONTACT = "cs@qau.edu.pk, +92 (051) 9064-2057"


def money(v, cur: str = "PKR") -> str:
    if v is None:
        return "—"
    if v == "formula":
        return "set by the department"
    return f"{v:,.0f}" if cur == "PKR" else f"${v:,.0f}"


class FeeQuery:
    def __init__(self):
        self.level: str = ""
        self.shift: str = ""  # R | S | ""
        self.foreign = False
        self.topic = "overview"  # overview | per_sem | admission | summer | items
        self.items: list[str] = []
        self.cue = False


class Fees:
    def __init__(self, data: dict):
        self.data = data
        self.pages = {p["level"]: p for p in data.get("pages", [])}

    @classmethod
    def from_json(cls, data: dict) -> Fees:
        return cls(data)

    # ------------------------------------------------------------------ parsing
    def parse(self, text: str) -> FeeQuery:
        q = FeeQuery()
        q.cue = bool(FEE_CUE.search(text))
        for level in ("MPhil", "PhD", "BS", "MS"):  # MPhil/PhD before MS: "MPhil/MS" must not read as MS
            if LEVEL_RE[level].search(text):
                q.level = level
                break
        if q.level == "MS" and re.search(r"\bm\.?\s?phil\b", text, re.I):
            q.level = "MPhil"
        q.shift = "S" if EVENING.search(text) else "R" if REGULAR.search(text) else ""
        if q.shift and not q.level:
            q.level = "BS"  # morning/evening programmes exist for BS only
        q.foreign = bool(FOREIGN.search(text))
        if SUMMER.search(text):
            q.topic = "summer"
        elif ONE_TIME.search(text):
            q.topic = "items"
            q.items = [pat for rx, pat in ITEM_KEYS if re.search(rx, text, re.I)][:3]
        elif PER_SEM.search(text) and not ADMISSION.search(text):
            q.topic = "per_sem"
        elif ADMISSION.search(text) and not PER_SEM.search(text):
            q.topic = "admission"
        return q

    # ------------------------------------------------------------------ helpers
    def _group(self, level: str, gid: str) -> dict | None:
        page = self.pages.get(level)
        return next((g for g in page["groups"] if g["id"] == gid), None) if page else None

    def _levels_for(self, q: FeeQuery) -> list[str]:
        if q.level in self.pages:
            return [q.level]
        return [lv for lv in ("BS", "MPhil", "PhD") if lv in self.pages]

    def _columns(self, levels: list[str], shift: str, lang: str) -> list[tuple[str, str, int]]:
        """(label, level, value index) per table column."""
        t = T[lang]
        cols = []
        for lv in levels:
            g = self._group(lv, "cs")
            if not g:
                continue
            if g["columns"] == ["R", "S"]:
                if shift in ("", "R"):
                    cols.append((t["reg"], lv, 0))
                if shift in ("", "S"):
                    cols.append((t["eve"], lv, 1))
            else:
                cols.append((LEVEL_NAME[lv], lv, 0))
        return cols

    def _value(self, lv: str, row: dict | None, idx: int):
        if not row:
            return None
        vals = row["values"]
        return vals[idx] if idx < len(vals) else (vals[0] if vals else None)

    @staticmethod
    def _table(header: list[str], rows: list[list[str]]) -> str:
        out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
        out += ["| " + " | ".join(r) + " |" for r in rows]
        return "\n".join(out)

    def _passages(self, levels: list[str]) -> list[dict]:
        out = []
        for lv in levels:
            p = self.pages[lv]
            g = self._group(lv, "cs")
            out.append({
                "title": p["title"], "heading": f"{lv} fee structure", "url": p["url"], "kind": "fees",
                "kind_label": "QAU fee structure page", "text": f"{lv} fee structure for Computer Science, {g['term'] if g else ''}.",
                "note": "", "fetched": p.get("fetched", ""), "score": 1.0, "chunk_id": f"computed-fees-{lv}",
            })
        return out

    def _foot(self, levels: list[str], lang: str, extra: str = "") -> str:
        srcs = " · ".join(f"[{i}] {lv} fee structure ({self._group(lv, 'cs')['term']})" for i, lv in enumerate(levels, 1))
        return f"<sub>{T[lang]['foot'].format(src=srcs)}{(' ' + extra) if extra else ''}</sub>"

    # ------------------------------------------------------------------ answer
    def answer(self, question: str, lang: str = "en", history: list[tuple[str, str]] | None = None) -> dict | None:
        if not self.pages:
            return None
        lang = lang if lang in T else "en"
        if lang == "en" and looks_roman_urdu(question):
            lang = "roman-ur"
        q = self.parse(question)
        if NOT_FEE.search(question):
            return None
        if not q.cue:
            q = self._inherit(q, question, history or [])
            if not q.cue:
                return None
        t = T[lang]
        if q.level == "MS":
            return self._ms(lang)
        if q.foreign:
            return self._foreign(q, lang)
        if q.topic == "items":
            return self._items(q, lang)
        if q.topic == "summer":
            return self._summer(q, lang)
        return self._core(q, lang, t)

    def _inherit(self, q: FeeQuery, question: str, history: list[tuple[str, str]]) -> FeeQuery:
        """A short follow-up ("aur evening ki?", "and PhD?") borrows what it leaves out from the last fee question."""
        if len(question.split()) > 6 or not (q.level or q.shift or q.foreign or q.topic != "overview"):
            return q
        for role, text in reversed(history):
            if role != "user":
                continue
            prev = self.parse(text)
            if prev.cue and not NOT_FEE.search(text):
                q.cue = True
                q.level = q.level or prev.level
                q.shift = q.shift or prev.shift
                q.foreign = q.foreign or prev.foreign
                if q.topic == "overview":
                    q.topic, q.items = prev.topic, prev.items
                return q
        return q

    def _core(self, q: FeeQuery, lang: str, t: dict) -> dict:
        levels = self._levels_for(q)
        cols = self._columns(levels, q.shift, lang)
        what = {"R": "BS regular (morning)", "S": "BS evening"}.get(q.shift) if (q.shift and q.level == "BS") else (
            LEVEL_NAME[levels[0]] if len(levels) == 1 else "BS / MPhil / PhD")
        wanted = {"per_sem": ("per_semester",), "admission": ("admission", "first_total")}.get(q.topic, ("per_semester", "admission", "first_total"))
        labels = {"per_semester": t["per_sem"], "admission": t["adm"], "first_total": t["first"]}
        rows = []
        mismatch = False
        for key in wanted:
            cells = []
            for _label, lv, idx in cols:
                g = self._group(lv, "cs")
                cells.append(money(self._value(lv, core_rows(g)[key], idx)))
            rows.append([labels[key], *cells])
        for _label, lv, idx in cols:  # sanity: admission + per semester = total, as printed
            core = core_rows(self._group(lv, "cs"))
            a, b, c = (self._value(lv, core[k], idx) for k in ("admission", "per_semester", "first_total"))
            if all(isinstance(x, (int, float)) for x in (a, b, c)) and a + b != c:
                mismatch = True
        text = [t["intro"].format(what=what, scope=t["scope_nat"]), "", self._table([""] + [c[0] for c in cols], rows), ""]
        if q.topic in ("overview",) and any(lv == "BS" for lv in levels):
            g = self._group("BS", "cs")
            sm = g["summer"]["values"] if g and g["summer"] else []
            if sm:
                text.append(f"- **{t['summer']}:** Rs. {sm[0]:,}." + (f" {t['evening_open'].format(v=sm[1])}" if len(sm) > 1 and q.shift != "R" else ""))
        notes = []
        by_term: dict[str, list[str]] = {}
        for lv in levels:
            g = self._group(lv, "cs")
            if g and g["term"]:
                by_term.setdefault(g["term"], []).append(lv)
        if by_term:
            terms = "; ".join(f"{' / '.join(lvs)} **{term}**" for term, lvs in by_term.items())
            notes.append(t["term_note"].format(terms=terms))
        if mismatch:
            notes.append(t["mismatch"])
        text += [("> " + n) for n in dict.fromkeys(notes)]
        text += ["", t["extras"]]
        if q.topic == "overview" and not q.level:
            text += ["", t["ms"].format(contact=CONTACT)]
        text += ["", self._foot(levels, lang)]
        return {"text": "\n".join(text), "followups": self._chips(q, lang), "followup_title": t["more"], "passages": self._passages(levels)}

    def _summer(self, q: FeeQuery, lang: str) -> dict:
        t = T[lang]
        levels = self._levels_for(q)
        rows, header = [], [t["summer"]]
        cols = self._columns(levels, q.shift, lang)
        cells = []
        for _label, lv, idx in cols:
            g = self._group(lv, "cs")
            sm = g["summer"]["values"] if g and g["summer"] else []
            cells.append(money(sm[idx] if idx < len(sm) else None))
        rows.append([t["summer"], *cells])
        what = {"R": "BS regular (morning)", "S": "BS evening"}.get(q.shift) if (q.shift and q.level == "BS") else (LEVEL_NAME[levels[0]] if len(levels) == 1 else "BS / MPhil / PhD")
        text = [t["intro"].format(what=what, scope=t["scope_nat"]), "", self._table([""] + [c[0] for c in cols], rows), "",
                "> " + t["summer_rule"], "", t["extras"], "", self._foot(levels, lang)]
        return {"text": "\n".join(text), "followups": self._chips(q, lang), "followup_title": t["more"], "passages": self._passages(levels)}

    def _items(self, q: FeeQuery, lang: str) -> dict:
        t = T[lang]
        levels = self._levels_for(q)
        if not q.level:
            levels = [lv for lv in levels if lv == "BS"] or levels[:1]
        cols = self._columns(levels, q.shift, lang)
        base = one_time_rows(self._group(levels[0], "cs"))
        if q.items:
            picked = [r for r in base if any(re.search(p, r["head"], re.I) for p in q.items)]
        else:
            picked = [r for r in base if r["values"] and r["values"][0] != "formula"]
        if not picked:
            return {"text": t["none_item"] + "\n\n" + self._foot(levels, lang), "followups": [], "followup_title": t["more"], "passages": self._passages(levels)}
        rows = []
        for r in picked:
            cells = []
            for _label, lv, idx in cols:
                row = next((x for x in one_time_rows(self._group(lv, "cs")) if x["head"] == r["head"]), None)
                cells.append(money(self._value(lv, row, idx)) if row and row["values"] and row["values"][0] != "formula" else "set by the department")
            rows.append([re.sub(r"\s*[\*#]+\s*", " ", r["head"]).strip(), *cells])
        what = {"R": "BS regular (morning)", "S": "BS evening"}.get(q.shift) if (q.shift and q.level == "BS") else LEVEL_NAME[levels[0]]
        text = [t["items_intro"].format(what=what), "", self._table([t["item"]] + [c[0] for c in cols], rows), "",
                "> Degree / certificate charges apply only when the student applies for them.", "", self._foot(levels, lang)]
        return {"text": "\n".join(text), "followups": self._chips(q, lang), "followup_title": t["more"], "passages": self._passages(levels)}

    def _foreign(self, q: FeeQuery, lang: str) -> dict:
        t = T[lang]
        levels = self._levels_for(q)
        blocks = []
        for lv in levels:
            g = self._group(lv, "foreign")
            if not g:
                continue
            core = core_rows(g)
            a, b, c = (core[k]["values"][0] if core[k] else None for k in ("admission", "per_semester", "first_total"))
            rows = [[t["foreign_rows"][0], money(a, "USD")], [t["foreign_rows"][1], money(b, "USD")], [t["foreign_rows"][2], money(c, "USD")]]
            sm = g["summer"]["values"] if g["summer"] else []
            if sm:
                rows.append([t["summer"], money(sm[0], "USD")])
            blocks += [f"**{t['foreign_title'].format(level=LEVEL_NAME[lv])}** ({g['term']})", "", self._table(["", "USD"], rows), ""]
        if not blocks:
            return {"text": t["none_item"], "followups": [], "followup_title": t["more"], "passages": []}
        text = blocks + ["> Foreign students pay in US dollars (or the equivalent in rupees at the time of admission); hostel fees for international students are charged double the local rate.", "", self._foot(levels, lang)]
        return {"text": "\n".join(text), "followups": self._chips(q, lang), "followup_title": t["more"], "passages": self._passages(levels)}

    def _ms(self, lang: str) -> dict:
        t = T[lang]
        return {"text": t["ms"].format(contact=CONTACT), "followups": self._chips(FeeQuery(), lang), "followup_title": t["more"], "passages": []}

    def _chips(self, q: FeeQuery, lang: str) -> list[dict]:
        c = T[lang]["chips"]
        chips = []
        if q.level in ("", "BS") and q.shift != "S":
            chips.append({"label": c["eve"], "text": c["eve"]})
        if q.level != "MPhil":
            chips.append({"label": c["mphil"], "text": c["mphil"]})
        if q.level != "PhD":
            chips.append({"label": c["phd"], "text": c["phd"]})
        if q.topic != "summer":
            chips.append({"label": c["summer"], "text": c["summer"]})
        if q.topic != "items":
            chips.append({"label": c["items"], "text": c["items"]})
        if not q.foreign:
            chips.append({"label": c["foreign"], "text": c["foreign"]})
        return chips[:6]

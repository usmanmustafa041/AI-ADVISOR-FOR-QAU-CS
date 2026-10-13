"""Course prerequisite graph: build, query and explain.

Why this exists
---------------
"Can I take Data Structures if I haven't passed PSP?" needs *multi-step* reasoning
(PSP → OOP → Data Structures). Language models — especially small local ones — get such
chains wrong. So the chain is computed here, deterministically, from two sources:

* the department's *approved prerequisite list* (a document supplied by the department and
  verified against its original, see :mod:`advisor.prereq.verify`);
* the prerequisite lines on the website's course pages.

Every edge keeps its source, so an answer can say who says what, and conflicting sources
are reported rather than silently merged. The model only phrases the computed analysis.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from advisor.retrieval.text import CODE_RE, norm_code

# Codes the department renumbered while keeping the same course (same title). Listed explicitly
# and reported to the administrator for confirmation instead of being guessed ad hoc.
# CSC-104 is the code on the timetable and current schemes; CSC-105 / CS-105 appear only in older prerequisite lines.
EQUIVALENT_CODES: list[tuple[str, ...]] = [("CSC-104", "CSC-105")]  # Problem Solving and Programming

# Student shorthand -> normalised course title(s). Anything printed in the department's own
# list (e.g. "A&DforSS") is added automatically from the data.
SHORTHAND: dict[str, list[str]] = {
    "psp": ["problem solving and programming"],
    "oop": ["object oriented programming"],
    "ds": ["data structures"],
    "dsa": ["data structures"],
    "ada": ["analysis and design of algorithms"],
    "daa": ["analysis and design of algorithms"],
    "adss": ["analysis and design for software systems"],
    "adfss": ["analysis and design for software systems"],
    "sc": ["software construction"],
    "se": ["software engineering"],
    "hci": ["human computer interaction"],
    "ico": ["introduction to computer organization"],
    "coa": ["computer organization and assembly language"],
    "coal": ["computer organization and assembly language"],
    "dbs": ["database systems"],
    "dbms": ["database systems"],
    "db": ["database systems"],
    "os": ["operating systems"],
    "ccn": ["computer communications and networks"],
    "cn": ["computer communications and networks"],
    "toa": ["theory of automata"],
    "tofa": ["theory of automata"],
    "ai": ["artificial intelligence"],
    "wad": ["web application development"],
    "cg": ["computer graphics"],
    "cc": ["compiler construction"],
    "ncp": ["net centric programming"],
    "sqa": ["software quality assurance"],
    "spm": ["software project management"],
    "fyp1": ["project i"], "fypi": ["project i"], "p1": ["project i"], "project1": ["project i"],
    "fyp2": ["project ii"], "fypii": ["project ii"], "p2": ["project ii"], "project2": ["project ii"],
    "fyp": ["project i", "project ii", "final year project"],
}

PREREQ_CUES = re.compile(
    r"pre-?\s?req|prerequisite|before (i |we |you )?(can |could |may )?(take|register|enrol|enroll|do|study|start)|"
    r"required (to|for)|need(ed)? to (pass|take|clear|complete|have)|can('| no)?t (i )?(take|register|enrol|do|study)|"
    r"cannot (take|register|do|study)|can i (take|register|enrol|do|study|start)|allowed to (take|register)|"
    r"unlock|lead(s)? to|depend|which (course|courses|subject|subjects) (need|require|come after)|"
    r"sequence|chain|roadmap|path to|order of (courses|subjects)|without (passing|clearing|completing|taking)|"
    r"(haven't|have not|hasn't|didn't|did not|not) (yet )?(passed|cleared|completed|taken|done)|"
    r"fail(ed)?( in)?|must (pass|clear|take)|has to be passed|pass(ed)? first|"
    r"\bbefore\b|\bafter\b|\bneeds?\b|\bneeded\b|\brequires?\b|\brequired\b|\bfirst\b|\bnext\b|\bcome(s)? after\b|"
    r"pehle|baghair|bagair|fail ho|pass kiye|pass kia|zaroori",
    re.I,
)
NEGATION = re.compile(
    r"(haven't|have not|hasn't|didn't|did not|not|never|yet to)\s+(yet\s+)?(passed|cleared|completed|taken|done|pass|clear|complete)|"
    r"fail(ed|ing)?( in| to pass)?|without (passing|clearing|completing|taking)|couldn't pass|can't pass|"
    r"nahi (pass|clear)|fail ho|baghair|bagair",
    re.I,
)


# ---------------------------------------------------------------------------------- helpers
def norm_title(title: str) -> str:
    t = title.lower().replace("&", " and ")
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    words = []
    for w in t.split():
        if w == "complier":  # typo present in the department's own list
            w = "compiler"
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.append(w)
    t = " ".join(words)
    t = re.sub(r"\bproject[- ]?(1|i)\b", "project i", t)
    t = re.sub(r"\bproject[- ]?(2|ii)\b", "project ii", t)
    return re.sub(r"\s+", " ", t).strip()


def canon(code: str) -> str | None:
    """'CS 103', 'CS-103', 'csc103', 'BY:201' -> canonical id ('CSC-103', 'BY-201')."""
    code = code.strip().replace(":", "-")
    m = CODE_RE.search(code)
    return norm_code(m.group(1), m.group(2)) if m else None


@dataclass
class Edge:
    course: str
    prereq: str
    source: str  # source id (see Graph.sources)
    scheme: str = ""
    quote: str = ""
    page: int | None = None

    def key(self) -> tuple[str, str]:
        return (self.course, self.prereq)


@dataclass
class Course:
    id: str
    codes: set[str] = field(default_factory=set)  # every spelling seen
    titles: set[str] = field(default_factory=set)
    abbreviations: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    schemes: dict[str, int | None] = field(default_factory=dict)  # scheme -> semester

    @property
    def title(self) -> str:
        return sorted(self.titles, key=len)[-1] if self.titles else self.id

    def label(self) -> str:
        return f"{self.id} {self.title}"


class Graph:
    def __init__(self):
        self.courses: dict[str, Course] = {}
        self.edges: dict[tuple[str, str], list[Edge]] = {}
        self.sources: dict[str, dict] = {}
        self.silent: dict[str, set[str]] = defaultdict(set)  # course -> sources that list none for it
        self._eq: dict[str, str] = {}
        for group in EQUIVALENT_CODES:
            for c in group[1:]:
                self._eq[c] = group[0]

    # ------------------------------------------------------------------ building
    def rep(self, code: str) -> str:
        return self._eq.get(code, code)

    def node(self, code: str, title: str = "", source: str = "") -> Course:
        cid = self.rep(code)
        c = self.courses.setdefault(cid, Course(cid))
        c.codes.add(code)
        if title:
            c.titles.add(title.strip())
        if source:
            c.sources.add(source)
        return c

    def add_edge(self, e: Edge) -> None:
        e.course, e.prereq = self.rep(e.course), self.rep(e.prereq)
        if e.course == e.prereq:
            return
        bucket = self.edges.setdefault(e.key(), [])
        if not any(x.source == e.source for x in bucket):
            bucket.append(e)

    # ------------------------------------------------------------------ queries
    def parents(self, cid: str) -> list[str]:
        return sorted(p for (c, p) in self.edges if c == cid)

    def children(self, cid: str) -> list[str]:
        return sorted(c for (c, p) in self.edges if p == cid)

    def ancestors(self, cid: str) -> dict[str, int]:
        """All (transitive) prerequisites with their distance (1 = direct)."""
        depth: dict[str, int] = {}
        queue = deque([(cid, 0)])
        while queue:
            cur, d = queue.popleft()
            for p in self.parents(cur):
                if p not in depth and p != cid:
                    depth[p] = d + 1
                    queue.append((p, d + 1))
        return depth

    def descendants(self, cid: str) -> dict[str, int]:
        depth: dict[str, int] = {}
        queue = deque([(cid, 0)])
        while queue:
            cur, d = queue.popleft()
            for ch in self.children(cur):
                if ch not in depth and ch != cid:
                    depth[ch] = d + 1
                    queue.append((ch, d + 1))
        return depth

    def path(self, src: str, dst: str) -> list[str] | None:
        """Shortest prerequisite path src → … → dst (src must be passed to reach dst)."""
        prev: dict[str, str | None] = {src: None}
        queue = deque([src])
        while queue:
            cur = queue.popleft()
            if cur == dst:
                out = []
                while cur is not None:
                    out.append(cur)
                    cur = prev[cur]
                return out[::-1]
            for ch in self.children(cur):
                if ch not in prev:
                    prev[ch] = cur
                    queue.append(ch)
        return None

    def edge_sources(self, course: str, prereq: str) -> list[Edge]:
        return self.edges.get((course, prereq), [])

    def has_cycle(self) -> list[str] | None:
        state: dict[str, int] = {}

        def visit(n: str, stack: list[str]) -> list[str] | None:
            state[n] = 1
            for ch in self.children(n):
                if state.get(ch) == 1:
                    return stack + [n, ch]
                if ch not in state:
                    found = visit(ch, stack + [n])
                    if found:
                        return found
            state[n] = 2
            return None

        for n in list(self.courses):
            if n not in state:
                found = visit(n, [])
                if found:
                    return found
        return None

    # ------------------------------------------------------------------ serialisation
    def to_json(self) -> dict:
        return {
            "sources": self.sources,
            "courses": {
                cid: {
                    "codes": sorted(c.codes), "titles": sorted(c.titles),
                    "abbreviations": sorted(c.abbreviations), "sources": sorted(c.sources),
                    "schemes": c.schemes,
                }
                for cid, c in sorted(self.courses.items())
            },
            "edges": [
                {"course": e.course, "prereq": e.prereq, "source": e.source, "scheme": e.scheme,
                 "quote": e.quote, "page": e.page}
                for bucket in self.edges.values() for e in bucket
            ],
            "silent": {k: sorted(v) for k, v in self.silent.items()},
        }

    @classmethod
    def from_json(cls, data: dict) -> Graph:
        g = cls()
        g.sources = data.get("sources", {})
        for cid, c in data["courses"].items():
            g.courses[cid] = Course(
                cid, set(c["codes"]), set(c["titles"]), set(c["abbreviations"]), set(c["sources"]), c.get("schemes", {})
            )
        for e in data["edges"]:
            bucket = g.edges.setdefault((e["course"], e["prereq"]), [])
            bucket.append(Edge(e["course"], e["prereq"], e["source"], e.get("scheme", ""), e.get("quote", ""), e.get("page")))
        for k, v in data.get("silent", {}).items():
            g.silent[k] = set(v)
        return g


# ---------------------------------------------------------------------------------- loading
APPROVED_SOURCE_ID = "approved-list-2021"


def add_department_list(g: Graph, path: Path, source_id: str = APPROVED_SOURCE_ID) -> None:
    """Load a prerequisite JSON in the agreed schema (see docs/ADVISOR.md)."""
    data = json.loads(Path(path).read_text())
    src = data.get("source", {})
    g.sources[source_id] = {
        "title": src.get("document_title") or "Department prerequisite list",
        "label": f"{src.get('document_title') or 'Department prerequisite list'} ({src.get('date_or_version') or 'undated'})",
        "issuer": src.get("issuing_body") or "",
        "kind": "department_document",
        "file": src.get("file_name"),
        "schemes": src.get("schemes_covered", []),
    }
    abbrs: dict[str, set[str]] = defaultdict(set)
    for c in data["courses"]:
        cid = canon(c["code"])
        if not cid:
            continue
        node = g.node(cid, c["title"], source_id)
        node.codes.add(c["code"])
        if c.get("abbreviation"):
            node.abbreviations.add(c["abbreviation"])
        if c.get("semester"):
            node.schemes[c["scheme"]] = c["semester"]
        elif c["scheme"] not in node.schemes:
            node.schemes[c["scheme"]] = None
    for p in data["prerequisites"]:
        if not p.get("prereq_code") or p["type"] not in ("must_pass", "all_of"):
            continue  # alternatives / credit-hour rules are surfaced separately, never flattened
        a, b = canon(p["course_code"]), canon(p["prereq_code"])
        if a and b:
            g.node(a, "", source_id)
            g.node(b, p.get("prereq_title") or "", source_id)
            g.add_edge(Edge(a, b, source_id, p["scheme"], p.get("source_quote", ""), p.get("source_page")))
    listed = {g.rep(canon(p["course_code"])) for p in data["prerequisites"] if canon(p["course_code"])}
    approved_scheme = [c for c in data["courses"] if c["scheme"].lower().startswith("list of")]
    for c in approved_scheme:
        cid = canon(c["code"])
        if cid and g.rep(cid) not in listed:
            g.silent[g.rep(cid)].add(source_id)
    del abbrs


def add_website_courses(g: Graph, course_docs: list, source_id: str = "website-course-pages") -> None:
    g.sources[source_id] = {
        "title": "Department website course pages", "label": "course pages on cs.qau.edu.pk",
        "issuer": "Department of Computer Sciences, QAU", "kind": "website",
    }
    for d in course_docs:
        m = d.meta
        cid = canon(m.get("course_code", ""))
        if not cid:
            continue
        node = g.node(cid, m.get("course_name", ""), source_id)
        node.codes.add(m["course_code"])
        node.sources.add(source_id)
        node.schemes.setdefault("website (current)", None)
        pres = m.get("prerequisites") or []
        for pre in pres:
            mm = re.match(r"([A-Za-z]{2,5}[-\s]?\d[0-9A-Za-z]{0,3})\s*(?:—\s*(.*))?", pre)
            pid = canon(mm.group(1)) if mm else None
            if pid:
                g.node(pid, (mm.group(2) or "").strip(), "")
                g.add_edge(Edge(cid, pid, source_id, "website (current)", f"{m['course_code']} — Prerequisites: {pre}", None))
        if not pres:
            g.silent[g.rep(cid)].add(source_id)


def build_graph(course_docs: list, department_files: list[Path]) -> Graph:
    g = Graph()
    for i, f in enumerate(department_files):
        add_department_list(g, f, APPROVED_SOURCE_ID if i == 0 else f"{APPROVED_SOURCE_ID}-{i + 1}")
    add_website_courses(g, course_docs)
    return g


# ---------------------------------------------------------------------------------- resolution
@dataclass
class Mention:
    node: str
    via: str  # how it was recognised: code | abbreviation | title


class Resolver:
    def __init__(self, g: Graph):
        self.g = g
        self.by_title: dict[str, list[str]] = defaultdict(list)
        for cid, c in g.courses.items():
            for t in c.titles:
                nt = norm_title(t)
                if cid not in self.by_title[nt]:
                    self.by_title[nt].append(cid)
        self.short: dict[str, list[str]] = {}
        for abbr, titles in SHORTHAND.items():
            nodes = [n for t in titles for n in self.by_title.get(norm_title(t), [])]
            if nodes:
                self.short[abbr] = list(dict.fromkeys(nodes))
        for cid, c in g.courses.items():  # abbreviations printed in the department's own list
            for a in c.abbreviations:
                key = re.sub(r"[^a-z0-9]", "", a.lower())
                if key and key not in SHORTHAND:
                    self.short.setdefault(key, [])
                    if cid not in self.short[key]:
                        self.short[key].append(cid)
        self.phrases = sorted(self.by_title, key=lambda p: -len(p))

    def find(self, text: str) -> list[tuple[int, Mention]]:
        """Courses mentioned in ``text`` with their character positions, in order."""
        found: list[tuple[int, Mention]] = []
        low = text.lower()
        taken: list[tuple[int, int]] = []

        def free(a, b):
            return not any(a < y and x < b for x, y in taken)

        for m in CODE_RE.finditer(text):
            cid = canon(m.group(0))
            cid = self.g.rep(cid) if cid else None
            if cid in self.g.courses and free(m.start(), m.end()):
                found.append((m.start(), Mention(cid, "code")))
                taken.append((m.start(), m.end()))
        norm_text = norm_title(text.replace("-", " "))
        for phrase in self.phrases:
            if len(phrase.split()) < 2 and len(phrase) < 8:
                continue
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", norm_text):
                # positions are approximate (normalised text); good enough for ordering mentions
                if free(m.start(), m.end()):
                    for node in self.by_title[phrase]:
                        found.append((m.start(), Mention(node, "title")))
                    taken.append((m.start(), m.end()))
        for m in re.finditer(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z&]{0,7}(?:[- ]?(?:\d|i{1,3}|1|2))?)(?![A-Za-z0-9])", text):
            key = re.sub(r"[^a-z0-9]", "", m.group(1).lower())
            if key in self.short and (len(key) >= 2) and free(m.start(), m.end()):
                # short ambiguous words (cc, sc, se, os, ai, ds, db, p1) need to look like course shorthand
                if len(key) <= 2 and not m.group(1).isupper():
                    continue
                for node in self.short[key]:
                    found.append((m.start(), Mention(node, "abbreviation")))
                taken.append((m.start(), m.end()))
        found.sort(key=lambda x: x[0])
        seen, out = set(), []
        for pos, men in found:
            if men.node not in seen:
                seen.add(men.node)
                out.append((pos, men))
        return out


# ---------------------------------------------------------------------------------- analysis
DESC_INTENT = re.compile(
    r"unlock|blocked|block\b|can('| no)?t take until|cannot take until|(which|what) (courses?|subjects?)[^?]*(need|require|depend|come after|after)|"
    r"comes? after|what (can|could|should) i (take|do) (next|after)|leads? to|depends? on",
    re.I,
)
ANC_INTENT = re.compile(
    r"prerequisite|pre-?req|need(ed)? to (pass|take|clear|complete)|must (pass|clear|take)|required|chain|sequence|roadmap|zaroori|pehle",
    re.I,
)
# "before" / "first" are everyday words ("what did I ask you first?"): they only mean a prerequisite
# question when the student actually names a course.
ANC_WEAK = re.compile(r"\bbefore\b|\bfirst\b", re.I)


@dataclass
class Analysis:
    text: str
    sources: list[dict]
    courses: list[str]
    warnings: list[str] = field(default_factory=list)  # source disagreements, always shown to the student
    ancestors: list[str] = field(default_factory=list)  # titles, earliest first (single-course analyses)
    descendants: list[str] = field(default_factory=list)  # titles
    pair_chains: list[list[str]] = field(default_factory=list)  # chains between courses the student named

    def addendum(self, question: str, answer: str, course_named: bool = True) -> str:
        """Deterministic guarantees appended after the model's answer.

        * Source disagreements are always stated, in plain words, whatever the model wrote.
        * If the student asked for a list (prerequisites, or courses blocked) and the model left
          items out, the missing ones are appended so the answer is complete.
        """
        parts: list[str] = []
        norm_answer = norm_title(answer)
        wanted: list[str] = []
        if len(self.courses) == 1:
            if DESC_INTENT.search(question):
                wanted = self.descendants
            elif ANC_INTENT.search(question) or (course_named and ANC_WEAK.search(question)):
                wanted = self.ancestors
        for chain in self.pair_chains:
            hidden = [t for t in chain[1:-1] if norm_title(t) not in norm_answer]
            if hidden:  # the middle of the chain is exactly what students need to see
                parts.append("**Prerequisite chain:** " + " → ".join(chain) + ". [1]")
        missing = [t for t in wanted if norm_title(t) not in norm_answer]
        if missing:
            parts.append("**Also, to complete the list:** " + "; ".join(missing) + ". [1]")
        if self.warnings:
            parts.append(
                "> ⚠️ **The sources differ:** " + " ".join(self.warnings)
                + " Please confirm with the department office. [1]"
            )
        return ("\n\n" + "\n\n".join(parts)) if parts else ""


class Concepts:
    """Nodes that share a normalised title are one course in different schemes (for example
    Operating Systems is CS-223 in the 2021 scheme and CSC-226 in the current one)."""

    def __init__(self, g: Graph, only: set[str] | None = None):
        self.g = g
        self.only = only  # restrict to edges asserted by these sources
        self.of: dict[str, str] = {}
        self.members: dict[str, list[str]] = defaultdict(list)
        for cid, c in g.courses.items():
            key = norm_title(c.title) or cid
            self.of[cid] = key
            self.members[key].append(cid)

    def name(self, key: str) -> str:
        """Title, the course's main code first, then other spellings seen in older lists."""
        ids = sorted(self.members[key])
        title = self.g.courses[ids[0]].title
        printed = []
        for i in ids:
            c = self.g.courses[i]
            printed += [x.replace(" ", "-").replace(":", "-") for x in sorted(c.codes)] + [i]
        main = ids[0]
        others = [x for x in dict.fromkeys(printed) if x != main]
        if len(ids) > 1:  # different scheme codes for one course (e.g. OS: CSC-223 / CSC-226)
            main = " / ".join(ids)
            others = [x for x in others if x not in ids]
        return f"{title} ({main}" + (f"; also printed {' / '.join(others[:3])}" if others else "") + ")"

    def parents(self, key: str) -> list[str]:
        out = []
        for m in self.members[key]:
            for p in self.g.parents(m):
                if self.only is not None and not any(e.source in self.only for e in self.g.edge_sources(m, p)):
                    continue
                k = self.of[p]
                if k != key and k not in out:
                    out.append(k)
        return out

    def children(self, key: str) -> list[str]:
        out = []
        for m in self.members[key]:
            for c in self.g.children(m):
                if self.only is not None and not any(e.source in self.only for e in self.g.edge_sources(c, m)):
                    continue
                k = self.of[c]
                if k != key and k not in out:
                    out.append(k)
        return out

    def closure(self, key: str, up: bool) -> dict[str, int]:
        depth: dict[str, int] = {}
        queue = deque([(key, 0)])
        while queue:
            cur, d = queue.popleft()
            for nxt in (self.parents(cur) if up else self.children(cur)):
                if nxt not in depth and nxt != key:
                    depth[nxt] = d + 1
                    queue.append((nxt, d + 1))
        return depth

    def path(self, src: str, dst: str) -> list[str] | None:
        prev: dict[str, str | None] = {src: None}
        queue = deque([src])
        while queue:
            cur = queue.popleft()
            if cur == dst:
                out = []
                while cur is not None:
                    out.append(cur)
                    cur = prev[cur]
                return out[::-1]
            for ch in self.children(cur):
                if ch not in prev:
                    prev[ch] = cur
                    queue.append(ch)
        return None

    def edge_sources(self, child: str, parent: str) -> set[str]:
        out = set()
        for c in self.members[child]:
            for p in self.members[parent]:
                out.update(e.source for e in self.g.edge_sources(c, p))
        return out


def _levels(g: Graph, concepts: Concepts, key: str, anc: dict[str, int]) -> str:
    """Prerequisites grouped by step, earliest first; branches are shown as [A; B], not as one line."""
    by_depth: dict[int, list[str]] = defaultdict(list)
    for k, d in anc.items():
        by_depth[d].append(g.courses[concepts.members[k][0]].title)
    steps = []
    for d in sorted(by_depth, reverse=True):
        names = sorted(by_depth[d])
        steps.append(names[0] if len(names) == 1 else "[" + "; ".join(names) + " — in any order]")
    return " → ".join(steps + [g.courses[concepts.members[key][0]].title])


def _list(items: list[str], limit: int) -> str:
    shown = items[:limit]
    more = len(items) - len(shown)
    return "; ".join(shown) + (f"; … and {more} more" if more > 0 else "")


def analyse(g: Graph, resolver: Resolver, question: str, max_courses: int = 3) -> Analysis | None:
    """Deterministic prerequisite analysis for the courses a question mentions."""
    if not PREREQ_CUES.search(question):
        return None
    concepts = Concepts(g)
    keys: list[str] = []
    for _pos, m in resolver.find(question):
        k = concepts.of[m.node]
        if k not in keys:
            keys.append(k)
    if not keys:
        return None
    keys = keys[:max_courses]
    used: set[str] = set()
    warnings: list[str] = []
    out: list[str] = ["COMPUTED PREREQUISITE ANALYSIS (deterministic; sources in brackets)"]

    def label(srcs: set[str]) -> str:
        used.update(srcs)
        return "[" + " & ".join(sorted(g.sources[s]["label"] for s in srcs)) + "]"

    pair_chains: list[list[str]] = []
    if len(keys) >= 2:
        out.append("\nRelationships between the courses mentioned:")
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                found = False
                for x, y in ((a, b), (b, a)):
                    p = concepts.path(x, y)
                    if p:
                        found = True
                        srcs = set()
                        for u, v in zip(p, p[1:], strict=False):
                            srcs |= concepts.edge_sources(v, u)
                        how = "directly" if len(p) == 2 else "indirectly"
                        names = " → ".join(g.courses[concepts.members[k][0]].title for k in p)
                        pair_chains.append([g.courses[concepts.members[k][0]].title for k in p])
                        out.append(
                            f"  - {g.courses[concepts.members[x][0]].title} must be passed before "
                            f"{g.courses[concepts.members[y][0]].title} ({how}). Chain: {names}. {label(srcs)}"
                        )
                if not found:
                    out.append(
                        f"  - No prerequisite link is listed between {g.courses[concepts.members[a][0]].title} "
                        f"and {g.courses[concepts.members[b][0]].title} in the available sources."
                    )

    for key in keys:
        out.append(f"\nCourse: {concepts.name(key)}")
        # What does each source say the direct prerequisites are?
        asserted: dict[str, set[str]] = defaultdict(set)
        for p in concepts.parents(key):
            for sid in concepts.edge_sources(key, p):
                asserted[sid].add(p)
        silent = set()
        for m in concepts.members[key]:
            silent |= g.silent.get(m, set())
        disagree = len({frozenset(v) for v in asserted.values()}) > 1 or bool(asserted and (silent - set(asserted)))
        if disagree:
            out.append("  THE SOURCES DISAGREE about this course — each source's rule is given separately; do not combine them:")
            bits = []
            for sid in sorted(set(asserted) | silent):
                lab = g.sources[sid]["label"]
                bits.append(
                    f"{lab} says it requires " + " and ".join(g.courses[concepts.members[p][0]].title for p in sorted(asserted[sid]))
                    if sid in asserted else f"{lab} lists no prerequisite for it"
                )
            warnings.append(f"For {g.courses[concepts.members[key][0]].title}: " + "; ".join(bits) + ".")
            for sid in sorted(set(asserted) | silent):
                lab = g.sources[sid]["label"]
                used.add(sid)
                if sid in asserted:
                    sub = Concepts(g, {sid})
                    anc = sub.closure(key, up=True)
                    out.append(
                        f"  - {lab}: requires " + "; ".join(concepts.name(p) for p in sorted(asserted[sid]))
                        + (f". Full sequence: {_levels(g, sub, key, anc)}" if anc else "")
                    )
                else:
                    out.append(f"  - {lab}: lists NO prerequisite for it.")
        else:
            parents = concepts.parents(key)
            if parents:
                parts = [f"{concepts.name(p)} {label(concepts.edge_sources(key, p))}" for p in parents]
                out.append("  Direct prerequisites: " + "; ".join(parts))
            else:
                used.update(silent)
                who = ", ".join(g.sources[s]["label"] for s in sorted(silent))
                out.append(
                    "  Direct prerequisites: none listed" + (f" in {who}" if who else "")
                    + " (nothing is published; that does not prove none exists)."
                )
            anc = concepts.closure(key, up=True)
            if anc:
                out.append("  Everything that must be passed first (earliest first): " + _levels(g, concepts, key, anc))
        direct = concepts.children(key)
        desc = concepts.closure(key, up=False)
        if desc:
            ordered = direct + sorted((c for c in desc if c not in direct), key=lambda k: (desc[k], k))
            items = [
                f"{i}) {concepts.name(c) if c in direct else g.courses[concepts.members[c][0]].title}"
                f" ({'direct' if c in direct else 'indirect'})"
                for i, c in enumerate(ordered, 1)
            ]
            out.append(
                f"  Courses that cannot be taken until this is passed — {len(ordered)} in total, list ALL of them: "
                + _list(items, 16 if len(keys) == 1 else 6)
            )
        else:
            out.append("  Not listed as a prerequisite of any other course.")
    out.append(
        "\nScope: the department's approved prerequisite list covers the BSCS Fall 2015 and Fall 2021 schemes "
        "(old CS-xxx codes). Newer schemes (CSC-xxx codes) are covered only where a website course page lists a "
        "prerequisite. Credit-hour limits, instructor consent and other conditions are not part of this analysis."
    )
    sources = [{"id": s, **g.sources[s]} for s in sorted(used) if s in g.sources]
    result = Analysis("\n".join(out), sources, [concepts.members[k][0] for k in keys], warnings)
    result.pair_chains = pair_chains
    if len(keys) == 1:
        k = keys[0]
        anc = concepts.closure(k, up=True)
        desc = concepts.closure(k, up=False)
        result.ancestors = [g.courses[concepts.members[x][0]].title for x in sorted(anc, key=lambda y: (-anc[y], y))]
        result.descendants = [g.courses[concepts.members[x][0]].title for x in sorted(desc, key=lambda y: (desc[y], y))]
    return result


# ---------------------------------------------------------------------------------- documents
def prerequisite_documents(g: Graph, source_id: str = APPROVED_SOURCE_ID):
    """Searchable text for the prerequisite data, so ordinary retrieval can also find it."""
    from advisor.ingest.model import Block, Document

    concepts = Concepts(g)
    blocks: list[Block] = []
    for key in sorted(concepts.members):
        parents = concepts.parents(key)
        if not parents:
            continue
        anc = concepts.closure(key, up=True)
        order = sorted(anc, key=lambda k: (-anc[k], k))
        sources = sorted({s for p in parents for s in concepts.edge_sources(key, p)})
        chain = " → ".join(g.courses[concepts.members[k][0]].title for k in order + [key])
        text = (
            f"Prerequisites of {concepts.name(key)}: "
            + "; ".join(concepts.name(p) for p in parents)
            + f".\nFull sequence to take it (earliest first): {chain}.\n"
            + "Source: " + ", ".join(g.sources[s]["label"] for s in sources)
        )
        children = concepts.children(key)
        if children:
            text += f"\nPassing it unlocks: {', '.join(g.courses[concepts.members[c][0]].title for c in children)}."
        blocks.append(Block(heading=f"Prerequisites › {concepts.name(key)}", text=text, atomic=True))
    if not blocks:
        return []
    return [
        Document(
            url="doc://department-prerequisite-list",
            title="Department prerequisite list (BSCS)",
            kind="prerequisites",
            blocks=blocks,
            meta={"variant": "prerequisite-graph", "note": "Compiled from the department's approved prerequisite list and the website course pages."},
            priority=10,
        )
    ]


def conflicts(g: Graph) -> list[dict]:
    """Courses where one source lists prerequisites and another is silent or lists different ones."""
    concepts = Concepts(g)
    out = []
    for key, members in sorted(concepts.members.items()):
        by_source: dict[str, set[str]] = defaultdict(set)
        for m in members:
            for p in g.parents(m):
                for e in g.edge_sources(m, p):
                    by_source[e.source].add(concepts.name(concepts.of[p]))
        silent = set()
        for m in members:
            silent |= g.silent.get(m, set())
        listing = {s for s in by_source}
        gaps = sorted(silent - listing)
        differ = len({frozenset(v) for v in by_source.values()}) > 1
        if (listing and gaps) or differ:
            out.append(
                {
                    "course": concepts.name(key),
                    "lists": {g.sources[s]["label"]: sorted(v) for s, v in by_source.items()},
                    "silent_in": [g.sources[s]["label"] for s in gaps],
                }
            )
    return out

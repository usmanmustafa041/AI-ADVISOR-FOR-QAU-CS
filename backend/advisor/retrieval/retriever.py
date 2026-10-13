"""Hybrid retrieval: BM25 + dense vectors fused with RRF, entity boosts, optional rerank."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from advisor.prereq.graph import PREREQ_CUES
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.models import Encoder, Reranker
from advisor.retrieval.text import STOPWORDS, detect_language, expand_query, extract_codes

RRF_K = 60
TITLES = {"dr", "prof", "mr", "ms", "mrs", "sir", "madam", "engr", "professor"}


@dataclass
class Hit:
    idx: int
    chunk: dict
    score: float
    parts: dict = field(default_factory=dict)

    @property
    def url(self) -> str:
        return self.chunk["url"]


@dataclass
class QueryEntities:
    codes: list[str]
    faculty: list[str]  # lower-case faculty keys
    course_name_codes: list[str]
    wants_publications: bool


INTENT_TIMETABLE = re.compile(
    r"this semester|current(ly)?|right now|today|tomorrow|timetable|time table|schedule|"
    r"\bwhich room\b|\bwhat time\b|\bwhen is\b.*\b(class|lecture|lab)\b|\bsection\b|"
    r"who (is )?teach|taught by|teacher|instructor|kaun parha|parhata",
    re.I,
)
INTENT_DIRECTORY = re.compile(
    r"\b(faculty members|professors|teachers|staff|all faculty|how many (faculty|professors|teachers)|"
    r"list of (faculty|professors)|who are the)\b",
    re.I,
)
INTENT_FEES = re.compile(r"\b(fees?|tuition|dues|challan|charges?|cost|payable|scholarship)\b", re.I)
INTENT_ADMISSION = re.compile(r"\b(admissions?|apply|applying|last date|deadline|merit|entry test|test date)\b", re.I)
GENERIC_WORDS = frozenset("course courses prerequisite prerequisites class credit hours subject".split())
INTENT_LISTING = re.compile(r"\b(list|all|which courses|what courses|every|names? of|how many)\b", re.I)


def wants_listing(query: str) -> bool:
    return bool(INTENT_LISTING.search(query))


def _plain(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


class Retriever:
    def __init__(self, bundle: Bundle, encoder: Encoder | None, reranker: Reranker | None = None):
        self.b = bundle
        self.encoder = encoder
        self.reranker = reranker
        self.rerank_top = 12  # candidates the cross-encoder scores; the dominant per-query CPU cost
        self._name_tokens: dict[str, set[str]] = {}
        token_owner: dict[str, set[str]] = {}
        for key, ent in bundle.faculty.items():
            toks = {t for t in re.findall(r"[a-z]+", key) if t not in TITLES and len(t) >= 3}
            self._name_tokens[key] = toks
            for t in toks:
                token_owner.setdefault(t, set()).add(key)
        self._token_owner = token_owner
        self._course_phrases: list[tuple[str, str]] = []
        for code, name in bundle.course_names.items():
            plain = _plain(name)
            toks = plain.split()
            if len(toks) >= 2 or (toks and len(toks[0]) >= 7):
                self._course_phrases.append((plain, code))
        # longest phrases first so "advanced operating systems" beats "operating systems"
        self._course_phrases.sort(key=lambda p: -len(p[0]))
        self._course_tokens = [
            (set(plain.split()), code) for plain, code in self._course_phrases
        ]

    # ------------------------------------------------------------------ analysis
    def entities(self, query: str) -> QueryEntities:
        codes = extract_codes(query)
        plain = " " + _plain(query) + " "
        name_codes: list[str] = []
        consumed = plain
        for phrase, code in self._course_phrases:
            if f" {phrase} " in consumed and code not in name_codes:
                name_codes.append(code)
                consumed = consumed.replace(f" {phrase} ", " ")
            if len(name_codes) >= 4:
                break
        if not name_codes:  # partial names: "computer networks" -> Computer Communications and Networks
            q_content = {
                t for t in re.findall(r"[a-z]+", query.lower())
                if t not in STOPWORDS and t not in GENERIC_WORDS and len(t) >= 4
            }
            if len(q_content) >= 2:
                fits = [code for toks, code in self._course_tokens if q_content <= toks]
                if 1 <= len(fits) <= 2:
                    name_codes.extend(fits)
        qtoks = [t for t in re.findall(r"[a-z]+", query.lower()) if t not in TITLES and len(t) >= 3]
        scores: dict[str, int] = {}
        for t in qtoks:
            for key in self._token_owner.get(t, ()):
                scores[key] = scores.get(key, 0) + (2 if len(self._token_owner[t]) == 1 else 1)
        faculty = []
        for key, sc in sorted(scores.items(), key=lambda kv: -kv[1]):
            ambiguous_only = all(len(self._token_owner[t]) > 1 for t in qtoks if t in self._name_tokens[key])
            # a lone shared token ("khan", "saeed") is too weak; a unique one or two tokens suffice
            if sc >= 2 and not (ambiguous_only and sc < 3):
                faculty.append(key)
        # common words that also happen to be name tokens must not trigger faculty lookup
        faculty = [k for k in faculty if not (self._name_tokens[k] & STOPWORDS)] or faculty
        return QueryEntities(
            codes=codes,
            faculty=faculty[:3],
            course_name_codes=name_codes,
            wants_publications=bool(re.search(r"publication|paper|journal|published|research output", query, re.I)),
        )

    # ------------------------------------------------------------------ search
    def search(self, query: str, *, k: int = 40, rerank_top: int | None = None, extra_query: str | None = None) -> list[Hit]:
        b = self.b
        ents = self.entities(query)
        lex_query = expand_query(query if not extra_query else f"{query} {extra_query}")
        bm = b.bm25.scores(lex_query)
        if self.encoder is not None:
            dv = b.vectors @ self.encoder.encode_query(query)
        else:
            dv = np.zeros(len(b.chunks), dtype=np.float32)

        def ranks(scores: np.ndarray, n: int = 80) -> dict[int, int]:
            order = np.argsort(-scores)[:n]
            return {int(i): r for r, i in enumerate(order) if scores[i] > 0}

        r_bm, r_dv = ranks(bm), ranks(dv)
        fused: dict[int, float] = {}
        for i, r in r_bm.items():
            fused[i] = fused.get(i, 0) + 1.0 / (RRF_K + r)
        for i, r in r_dv.items():
            fused[i] = fused.get(i, 0) + 1.0 / (RRF_K + r)
        parts: dict[int, dict] = {i: {"bm25_rank": r_bm.get(i), "dense_rank": r_dv.get(i)} for i in fused}

        def boost(i: int, amount: float, why: str):
            fused[i] = fused.get(i, 0) + amount
            parts.setdefault(i, {})[why] = amount

        unique_names = len(ents.course_name_codes) == 1
        wanted = [(c, 0.045) for c in ents.codes] + [
            (c, 0.045 if unique_names else 0.012) for c in ents.course_name_codes
        ]
        seen_codes: set[str] = set()
        for code, strength in wanted:
            if code in seen_codes:
                continue
            seen_codes.add(code)
            rec = b.course_record.get(code)
            if rec is not None:
                boost(rec, strength, "course_record")
            mention = 0.012 if strength >= 0.045 else 0.004
            for i in b.code_chunks.get(code, []):
                if i != rec:
                    boost(i, mention, "code_mention")
        if INTENT_TIMETABLE.search(query):
            for i, c in enumerate(b.chunks):
                if c["kind"] == "timetable" and i in fused:
                    boost(i, 0.012, "intent_timetable")
        if INTENT_DIRECTORY.search(query) and not ents.faculty:
            for i, c in enumerate(b.chunks):
                if c["kind"] == "directory" and "Faculty directory" in c["title"]:
                    boost(i, 0.03, "intent_directory")
        for key in ents.faculty:
            for i in b.faculty[key]["chunks"]:
                c = b.chunks[i]
                if c["kind"] == "publications" and not ents.wants_publications:
                    boost(i, 0.004, "faculty")
                else:
                    boost(i, 0.03, "faculty")
        if INTENT_ADMISSION.search(query):
            for i, c in enumerate(b.chunks):
                if c["kind"] in ("admissions", "external") and "admission" in c["url"].lower() and i in fused:
                    boost(i, 0.01, "intent_admission")
        if INTENT_FEES.search(query):
            for i, c in enumerate(b.chunks):
                if "fee" in c["url"].lower() and i in fused:
                    boost(i, 0.02, "intent_fees")
        # OCR text is lossy (garbled dates/numbers): clean sources must win when both match
        for i in list(fused):
            if (b.chunks[i].get("meta") or {}).get("ocr") and b.chunks[i]["kind"] == "document":
                fused[i] *= 0.55
        # Compiled prerequisite chunks mention many course names; they should only compete when the
        # student is actually asking about prerequisites.
        if not PREREQ_CUES.search(query):
            for i in list(fused):
                if b.chunks[i]["kind"] == "prerequisites":
                    fused[i] *= 0.45
        # Fee tables repeat programme words (BS, MPhil, PhD, degree, admission); they must not crowd out
        # the real answer to a question that is not about fees.
        if not INTENT_FEES.search(query):
            for i in list(fused):
                if b.chunks[i]["kind"] == "fees":
                    fused[i] *= 0.4
        # publications are voluminous noise unless the question is about them
        for i in list(fused):
            c = b.chunks[i]
            if c["kind"] == "publications" and not ents.wants_publications and not ents.faculty:
                fused[i] *= 0.6
        order = sorted(fused, key=fused.get, reverse=True)[:k]
        hits = [Hit(i, b.chunks[i], fused[i], parts.get(i, {})) for i in order]

        rerank_top = rerank_top or self.rerank_top
        if self.reranker is not None and hits:
            top = hits[:rerank_top]
            raw = self.reranker.score(query, [h.chunk["index_text"] for h in top])
            sig = 1 / (1 + np.exp(-raw))
            fmax = max(h.score for h in top) or 1.0
            non_english = detect_language(query) != "en"
            w = 0.25 if non_english else 0.6  # cross-encoder is English-centric
            for h, s in zip(top, sig, strict=True):
                h.parts["rerank"] = float(s)
                # reranker decides mostly; fused score keeps entity knowledge in play
                h.score = w * float(s) + (1 - w) * (h.score / fmax)
            top.sort(key=lambda h: h.score, reverse=True)
            hits = top + hits[rerank_top:]
        return hits

    def context(self, hits: list[Hit], *, max_chunks: int, char_budget: int, per_doc: int = 8) -> list[Hit]:
        """Pick the final evidence set: best-first, bounded per document and by size."""
        chosen: list[Hit] = []
        per: dict[str, int] = {}
        used = 0
        for h in hits:
            if len(chosen) >= max_chunks:
                break
            doc = h.chunk["doc_id"]
            cap = 2 if h.chunk["kind"] == "publications" else per_doc
            if per.get(doc, 0) >= cap:
                continue
            size = len(h.chunk["text"])
            if used + size > char_budget and chosen:
                continue
            chosen.append(h)
            per[doc] = per.get(doc, 0) + 1
            used += size
        return chosen

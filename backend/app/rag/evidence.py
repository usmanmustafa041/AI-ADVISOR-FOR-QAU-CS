"""BM25 + dense retrieval, reciprocal rank fusion, and optional cross-encoder.

Dense vectors carry an exact corpus/model fingerprint. Hash vectors and vectors
from another embedding model are never compared with sentence embeddings.
"""

import hashlib
import json
import logging
import math
import re
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from threading import Lock

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.rag.corpus import EvidenceChunk, corpus_path, is_official_url, load_corpus, text_problem
from app.rag.encoding import encode_query

logger = logging.getLogger(__name__)
STOP = set(
    (
        "a an the is are was were be been do does did what which who whom how can could "
        "should would i me my you your it its this that these those and or of for to in "
        "on at by with from about tell please show know want need qau university department "
        "computer sciences hai hain kya ki ka ke ko mein mujhe apko iska aur kitni kitne"
    ).split()
)
STOP.update(
    {
        "science",
        "cs",
        "quaid",
        "azam",
        "explain",
        "required",
        "when",
        "where",
        "why",
        "his",
        "her",
        "ہے",
        "کی",
        "کتنی",
        "کیا",
        "کے",
        "کا",
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank",
        "bye",
        "goodbye",
        "okay",
        "ok",
        "salam",
        "salaam",
        "shukriya",
    }
)
ALIASES = {
    "بی ایس": "bs",
    "ایم فل": "mphil",
    "پی ایچ ڈی": "phd",
    "ڈیٹا سائنس": "data science",
    "کمپیوٹر سائنس": "computer science",
    "کریڈٹ آورز": "credit hours",
    "کریڈٹ": "credit",
    "سمسٹر": "semester",
    "بہار": "spring",
    "خزاں": "fall",
    "فیکلٹی": "faculty",
    "bscs": "bs computer science",
    "bs cs": "bs computer science",
    "how long": "duration",
    "how many years": "duration year",
    "prereq": "prerequisite",
    "pre req": "prerequisite",
    "pre-req": "prerequisite",
    "fyp": "final year project",
    "cgpa": "cumulative grade point average cgpa",
    "thesis": "thesis dissertation",
    "fee": "fee tuition",
    "fees": "fee tuition",
    "cost": "fee tuition",
    "admisson": "admission",
    "admisison": "admission",
    "tution": "tuition",
    "faculity": "faculty",
    "scholorship": "scholarship",
    "dakhla": "admission",
    "admission ka": "admission",
    "akhri tareekh": "deadline last date",
    "aakhri date": "deadline last date",
    "akhri date": "deadline last date",
    "fees kitni": "fee tuition",
    "kitne saal": "duration year",
    "muddat": "duration",
    "ustad": "faculty",
    "parhate": "teach faculty",
    "haazri": "attendance",
    "hazri": "attendance",
    "hafton": "weeks duration",
    "hafte": "weeks duration",
    "ہفتوں": "weeks duration",
    "ہفتے": "weeks duration",
    "پروبیشن": "probation",
    "سی جی پی اے": "cgpa",
    "جی پی اے": "gpa",
    "اخراج": "drop university rolls",
    "منجمد": "freeze semester",
    "زیادہ سے زیادہ": "maximum",
    "کم از کم": "minimum",
    "چھوٹ": "exemption",
    "مستثنیٰ": "exempted",
    "منتقلی": "transfer",
    "تدریس": "teaching",
    "رجسٹریشن": "registration",
    "مواقع": "chances",
    "ایم ایس": "ms",
    "داخلہ": "admission",
    "فیس": "fee tuition",
    "حاضری": "attendance",
    "وظائف": "scholarship",
    "مدت": "duration",
    "آخری تاریخ": "deadline last date",
    "تحقیق": "research",
    "اساتذہ": "faculty",
    "شرائط": "requirement eligibility",
    "ضروری": "requirement",
    "نصاب": "curriculum scheme",
}


def normalize_query(query: str) -> str:
    result = query.lower().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    # A single replacement pass prevents expansions being expanded again.
    pattern = "|".join(re.escape(p) for p in sorted(ALIASES, key=len, reverse=True))
    result = re.sub(r"(?<!\w)(?:" + pattern + r")(?!\w)", lambda m: ALIASES[m.group(0)], result)
    return re.sub(r"\b([a-z]{2,4})[ -]?(\d{3})\b", r"\1-\2", result)


def tokens(text_value: str) -> list[str]:
    words = re.findall(r"[\w]+(?:-\d{3})?", text_value.lower())
    return [
        w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w
        for w in words
        if w not in STOP and (len(w) > 1 or w.isdigit())
    ]


def query_programs(query: str) -> set[str]:
    result = set()
    for pattern, program in (
        (r"\b(?:bs|bscs|bachelor)\b", "bs"),
        (r"\bm\.?\s?phil\b", "mphil"),
        (r"\bph\.?d\b", "phd"),
        (r"\bms\b.*\bdata\b|\bdata science\b", "ms-ds"),
        (r"\bist\b|information science", "ms-ist"),
    ):
        if re.search(pattern, query, re.I):
            result.add(program)
    # Final-year projects belong to the bachelor curriculum. Do not substitute
    # postgraduate thesis regulations when their submission rules are missing.
    if not result and re.search(r"\bfyp\b|\bfinal[ -]year\b.*\bproject\b", query, re.I):
        result.add("bs")
    return result


def program_matches(chunk: EvidenceChunk, programs: set[str]) -> bool:
    program = chunk.program.lower()
    if program.startswith("bs"):
        program = "bs"
    return not programs or program in {"all", ""} or program in programs


def topic_boost(chunk: EvidenceChunk, query: str) -> float:
    """Metadata preferences improve ranking; they never prevent other topics being searched."""
    if "contact" in chunk.source_url.lower() and re.search(
        r"office|department.*(?:email|hours)|دفتر|daftar", query, re.I
    ):
        return 5.0
    patterns = {
        "fees": r"\bfee|tuition|cost",
        "curriculum": r"scheme|curriculum|study plan",
        "timetable": r"timetable|class.*(?:when|time)|schedule|room",
        "research": r"research (?:group|area)|research.*department",
        "academic_policy": r"thesis|regulation|policy|\brules?\b|attendance|probation|"
        r"freez|frozen|exempt|transfer.*credit|credit load|completion period",
        "admissions": r"admission|eligibility|apply|deadline",
    }
    if re.search(patterns.get(chunk.category, r"(?!)"), query, re.I):
        if chunk.category == "research":
            # The page's opening passage contains the group overview; later
            # passages describe just one group in detail.
            return 9.0 if chunk.chunk_index == 0 and re.search(r"groups", query, re.I) else 6.0
        return 1.6
    return 1.0


def fingerprint(chunks: list[EvidenceChunk], model: str) -> str:
    digest = hashlib.sha256(model.encode())
    for chunk in chunks:
        digest.update(f"{chunk.chunk_id}:{chunk.title}:{chunk.content}".encode())
    return digest.hexdigest()


@dataclass
class Hit:
    chunk: EvidenceChunk
    score: float
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    coverage: float = 0.0

    def citation(self, number: int) -> dict:
        return {**self.chunk.citation(), "number": number, "retrieval_score": round(self.score, 4)}


class EvidenceIndex:
    def __init__(self, chunks: list[EvidenceChunk], path: Path | None = None):
        self.chunks = chunks
        self.path = path
        self.counts = [Counter(tokens(c.title + "\n" + c.content)) for c in chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average_length = sum(self.lengths) / max(len(chunks), 1)
        self.postings: dict[str, list[int]] = defaultdict(list)
        for i, counts in enumerate(self.counts):
            for term in counts:
                self.postings[term].append(i)
        self.idf = {
            term: math.log(1 + (len(chunks) - len(ids) + 0.5) / (len(ids) + 0.5))
            for term, ids in self.postings.items()
        }
        self.people = {
            c.document_id: set(tokens(c.title.split(" - ")[0])) - {"dr", "prof", "professor"}
            for c in chunks
            if c.category == "faculty" and "Faculty Profile" in c.title
        }
        self.vectors = None
        self.encoder = None
        self.dense_status = "disabled" if path is None else "not_built"
        self.lock = Lock()
        self._dense_attempted = False
        self._query_vectors = OrderedDict()
        self._query_lock = Lock()

    def query_vector(self, query):
        # Cache is scoped to the exact corpus index and bounded in process memory.
        with self._query_lock:
            if query in self._query_vectors:
                self._query_vectors.move_to_end(query)
                return self._query_vectors[query]
            vector = encode_query(self.encoder, query, get_settings().embedding_model)
            self._query_vectors[query] = vector
            if len(self._query_vectors) > 256:
                self._query_vectors.popitem(last=False)
            return vector

    def _load_dense(self):
        with self.lock:
            if self._dense_attempted:
                return
            self._dense_attempted = True
            settings = get_settings()
            if not self.path or settings.embedding_provider not in {
                "sentence-transformer",
                "sentence-transformers",
            }:
                self.dense_status = "disabled"
                return
            manifest_path = self.path.with_suffix(".vectors.json")
            vector_path = self.path.with_suffix(".vectors.npy")
            if not manifest_path.exists() or not vector_path.exists():
                return
            try:
                import numpy as np

                manifest = json.loads(manifest_path.read_text())
                if manifest["fingerprint"] != fingerprint(self.chunks, settings.embedding_model):
                    self.dense_status = "stale_index"
                    return
                from sentence_transformers import SentenceTransformer

                encoder = SentenceTransformer(
                    settings.embedding_model,
                    local_files_only=settings.embedding_local_files_only,
                    cache_folder=settings.embedding_cache_path or None,
                    device=settings.embedding_device,
                )
                vectors = np.load(vector_path, allow_pickle=False)
                if vectors.shape != (len(self.chunks), encoder.get_sentence_embedding_dimension()):
                    raise ValueError("Embedding dimensions do not match corpus/model")
                self.encoder, self.vectors = encoder, vectors
                self.dense_status = "ready"
            except Exception:
                logger.exception("Semantic retrieval unavailable; BM25 remains active")
                self.dense_status = "unavailable"

    def _eligible(self, chunk: EvidenceChunk, query: str) -> bool:
        if not program_matches(chunk, query_programs(query)):
            return False
        if (
            "bs" in query_programs(query)
            and re.search(r"b\.?a\.?\s*ll\.?b|pharm|doctor of pharmacy", chunk.title, re.I)
            and not re.search(r"llb|law|pharm", query, re.I)
        ):
            return False
        if "bs" in query_programs(query) and chunk.category == "fees" and chunk.section_title:
            if "all other programmes" in chunk.section_title.lower():
                return False
        years = set(re.findall(r"\b20\d{2}\b", query))
        source_years = set(
            re.findall(r"\b20\d{2}\b", (chunk.effective_term or "") + " " + chunk.title)
        )
        if years and source_years and not years.intersection(source_years):
            return False
        temporal_question = re.search(r"timetable|schedule|calendar|datesheet", query, re.I)
        if years and not source_years and (chunk.is_time_sensitive or temporal_question):
            # An undated schedule cannot establish an explicitly requested year.
            return False
        if (
            years
            and not source_years
            and chunk.category in {"curriculum", "prerequisites", "programme"}
            and re.search(r"scheme|curriculum|credit|prereq", query, re.I)
        ):
            return False
        codes = re.findall(r"\b([a-z]{2,4})-(\d{3})\b", query.lower())
        if codes:
            # Preserve codes and tolerate CS/CSC nomenclature without rewriting their numbers.
            requested = {("csc" if prefix == "cs" else prefix, number) for prefix, number in codes}
            actual = {
                ("csc" if prefix.lower() == "cs" else prefix.lower(), number)
                for prefix, number in re.findall(
                    r"\b([A-Z]{2,4})[ -]?(\d{3})\b", chunk.content, re.I
                )
            }
            if not requested.intersection(actual):
                return False
        return True

    def search(self, query: str, limit: int = 6, dense: bool = True) -> list[Hit]:
        normalized = normalize_query(query)
        query_terms = set(tokens(normalized))
        if not query_terms:
            return []
        # Repair unknown retrieval terms conservatively; preserve the original question.
        repaired = set()
        for term in query_terms:
            matches = (
                get_close_matches(term, self.postings, n=1, cutoff=0.87)
                if term not in self.postings and len(term) > 5
                else []
            )
            repaired.add(matches[0] if matches else term)
        query_terms = repaired
        scores: dict[int, float] = defaultdict(float)
        for term in query_terms:
            for i in self.postings.get(term, []):
                tf = self.counts[i][term]
                length = self.lengths[i] / max(self.average_length, 1)
                scores[i] += self.idf[term] * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length))
        named_people = {
            doc for doc, names in self.people.items() if len(query_terms.intersection(names)) >= 2
        }
        eligible = {
            i
            for i, c in enumerate(self.chunks)
            if self._eligible(c, normalized) and (not named_people or c.document_id in named_people)
        }
        candidate_k = get_settings().rag_candidate_k
        lexical = sorted(
            (i for i in scores if i in eligible),
            key=lambda i: (-scores[i], self.chunks[i].chunk_id),
        )[:candidate_k]
        semantic_scores = {}
        semantic = []
        if dense:
            self._load_dense()
        if dense and self.vectors is not None and self.encoder is not None:
            vector = self.query_vector(normalized)
            similarities = self.vectors @ vector
            semantic = sorted(eligible, key=lambda i: -float(similarities[i]))[:candidate_k]
            semantic_scores = {i: float(similarities[i]) for i in semantic}
        fused: dict[int, float] = defaultdict(float)
        for ranking in (lexical, semantic):
            for rank, i in enumerate(ranking, 1):
                fused[i] += 1 / (60 + rank)
        total_idf = sum(self.idf.get(t, 3.0) for t in query_terms) or 1
        hits = []
        for i, score in fused.items():
            coverage = (
                sum(self.idf.get(t, 3.0) for t in query_terms if t in self.counts[i]) / total_idf
            )
            semantic_score = semantic_scores.get(i, 0.0)
            matched = len(query_terms.intersection(self.counts[i]))
            if (
                coverage < 0.22 or matched < min(2, len(query_terms))
            ) and semantic_score < get_settings().rag_semantic_min_score:
                continue
            boost = topic_boost(self.chunks[i], normalized)
            if self.chunks[i].category == "faculty" and re.search(
                r"e.?mail|ای.?میل|ای میل", normalized
            ):
                if re.search(r"[\w.+-]+@qau\.edu\.pk", self.chunks[i].content):
                    boost *= 6
            if self.chunks[i].category == "academic_policy":
                # A rule in a sentence is stronger evidence than a heading alone.
                # Avoid retrieving the dismissal paragraph for a probation question.
                for concept in ("probation", "attendance", "freeze", "exemption", "grievance"):
                    if re.search(r"\b" + concept + r"\w*\b", normalized) and re.search(
                        r"[^\n]{12,}\b" + concept + r"\w*\b", self.chunks[i].content, re.I
                    ):
                        boost *= 3
            if self.chunks[i].category == "fees" and re.search(r"fee|tuition", normalized):
                if re.search(r"Category B.{0,20}Per Semester", self.chunks[i].content, re.I):
                    boost *= 1.6
            if (
                re.search(r"duration|\byears?\b", normalized)
                and self.chunks[i].category == "programme"
            ):
                if re.search(
                    r"\b(?:four|two|three|4|2|3)[ -]years?\b|duration", self.chunks[i].content, re.I
                ):
                    boost *= 2
            if self.chunks[i].program != "ALL" and query_programs(normalized):
                boost *= 1.25
            strength = score * (0.65 + coverage) * (1 + max(0, semantic_score) * 1.5) * boost
            if not is_official_url(self.chunks[i].source_url):
                strength *= 0.4
            hits.append(Hit(self.chunks[i], strength, scores.get(i, 0), semantic_score, coverage))
        hits.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
        return diversify(hits, limit)


def diversify(hits: list[Hit], limit: int) -> list[Hit]:
    result = []
    seen = set()
    documents: Counter = Counter()
    # A locally copied PDF must never suppress the identical official passage.
    preferred = {}
    for hit in hits:
        digest = hashlib.sha256(" ".join(hit.chunk.content.split()).encode()).hexdigest()
        priority = (
            is_official_url(hit.chunk.source_url),
            hit.chunk.verification_status in {"verified", "approved"},
            bool(hit.chunk.source_version_id),
            hit.chunk.captured_at or "",
        )
        if digest not in preferred or priority > preferred[digest][0]:
            preferred[digest] = (priority, hit)
    for hit in hits:
        key = hashlib.sha256(" ".join(hit.chunk.content.split()).encode()).hexdigest()
        if preferred[key][1] is not hit:
            continue
        if key in seen or documents[hit.chunk.document_id] >= max(4, limit // 2):
            continue
        seen.add(key)
        documents[hit.chunk.document_id] += 1
        result.append(hit)
        if len(result) >= limit:
            break
    return result


@lru_cache(maxsize=2)
def _index_at(path: str, mtime: int) -> EvidenceIndex:
    return EvidenceIndex(load_corpus(Path(path)), Path(path))


def get_index() -> EvidenceIndex:
    path = corpus_path(get_settings().rag_corpus_path)
    return _index_at(str(path), path.stat().st_mtime_ns if path.exists() else 0)


def database_chunks(db) -> list[EvidenceChunk]:
    """CMS documents use BM25 until explicitly rebuilt with the selected encoder.

    Savepoints isolate optional-schema errors from session/history transactions.
    Legacy pgvector values have unknown provenance and are intentionally ignored.
    """
    rows = []
    try:
        with db.begin_nested():
            rows = list(
                db.execute(
                    text("""
                SELECT dc.id::text AS chunk_id, dc.document_id::text AS document_id,
                    dc.content, dc.chunk_index, dc.page_number, dc.section_title,
                    kd.title, kd.category, sr.source_code, sr.source_url,
                    sr.local_path, sr.verification_status, sr.is_time_sensitive,
                    sr.last_verified_at::text AS captured_at,
                    sr.effective_from::text AS effective_term
                FROM document_chunks dc JOIN knowledge_documents kd ON kd.id=dc.document_id
                JOIN source_records sr ON sr.id=kd.source_id
                WHERE kd.processing_status='ready' AND sr.verification_status='verified'
                ORDER BY dc.id LIMIT 10001
            """)
                ).mappings()
            )
        if len(rows) > 10000:
            logger.error("Database evidence exceeds 10000 chunks; build a corpus snapshot")
            return []
        return [
            EvidenceChunk(
                **{
                    **dict(r),
                    "source_url": r["source_url"] or "",
                    "local_path": r["local_path"] or "",
                }
            )
            for r in rows
            if is_official_url(r["source_url"] or "") and not text_problem(r["content"])
        ]
    except SQLAlchemyError:
        logger.warning("Database evidence unavailable", exc_info=False)
        return []


def cms_chunks(db) -> list[EvidenceChunk]:
    from app.rag.corpus import split_passages

    try:
        with db.begin_nested():
            rows = list(
                db.execute(
                    text("""SELECT id::text, sub_key, category, title,
                content_markdown, source_url, source_document, updated_at::text
                FROM knowledge_base WHERE is_active=TRUE AND is_verified=TRUE
                ORDER BY id LIMIT 10001""")
                ).mappings()
            )
        if len(rows) > 10000:
            logger.error("CMS exceeds snapshot limit; build a corpus snapshot")
            return []
        chunks = []
        categories = {
            "scheme": "curriculum",
            "fee_structure": "fees",
            "admission": "admissions",
            "policy": "academic_policy",
        }
        for row in rows:
            content = row["content_markdown"]
            url = row["source_url"] or ""
            if not is_official_url(url) or text_problem(content):
                continue
            category = categories.get(row["category"], row["category"])
            term = re.search(
                r"\b(?:Fall|Spring)\s+20\d{2}\b", row["title"] + " " + content[:500], re.I
            )
            for i, piece in enumerate(split_passages(content)):
                chunks.append(
                    EvidenceChunk(
                        chunk_id=f"cms:{row['id']}:{i}",
                        document_id=f"cms:{row['id']}",
                        title=row["title"],
                        content=piece,
                        source_url=url,
                        source_code=row["sub_key"],
                        local_path=row["source_document"] or "",
                        category=category,
                        chunk_index=i,
                        verification_status="verified",
                        captured_at=row["updated_at"],
                        effective_term=term.group(0) if term else None,
                        is_time_sensitive=category
                        in {"fees", "admissions", "timetable", "general_notice"},
                    )
                )
        return chunks
    except SQLAlchemyError:
        logger.info("Optional CMS evidence table is unavailable")
        return []


@lru_cache(maxsize=1)
def get_reranker(model: str):
    from sentence_transformers import CrossEncoder

    settings = get_settings()
    return CrossEncoder(
        model,
        local_files_only=settings.embedding_local_files_only,
        cache_folder=settings.embedding_cache_path or None,
        device=settings.embedding_device,
    )


def retrieve(query: str, db=None, limit: int | None = None) -> tuple[list[Hit], list[str]]:
    settings = get_settings()
    limit = limit or settings.rag_top_k
    index = get_index()
    notices = []
    hits = index.search(query, settings.rag_candidate_k)
    if db is not None and settings.rag_include_database:
        dynamic = database_chunks(db) + cms_chunks(db)
        if dynamic:
            hits.extend(EvidenceIndex(dynamic).search(query, settings.rag_candidate_k, dense=False))
    if index.dense_status != "ready":
        notices.append(f"Semantic retrieval: {index.dense_status}; lexical retrieval is active.")
    hits.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
    model = settings.rag_reranker_model
    if model and hits:
        try:
            candidates = diversify(hits, settings.rag_candidate_k)
            ranks = get_reranker(model).predict(
                [(query, h.chunk.title + "\n" + h.chunk.content) for h in candidates]
            )
            hits = [
                h
                for _, h in sorted(
                    zip(ranks, candidates, strict=True), key=lambda pair: -float(pair[0])
                )
            ]
        except Exception:
            logger.exception("Cross-encoder unavailable")
            notices.append("Cross-encoder unavailable; fused retrieval order is active.")
    return diversify(hits, limit), notices

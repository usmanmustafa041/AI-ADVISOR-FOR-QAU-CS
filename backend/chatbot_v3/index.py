import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np

from chatbot_v3.contracts import Task
from chatbot_v3.embeddings import Encoder
from chatbot_v3.parsing import PARSER_VERSION
from chatbot_v3.settings import settings
from chatbot_v3.store import Store


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with tmp.open("w") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def build_index(store, encoder, publish=False):
    chunks = store.chunks()
    encoded = json.dumps(chunks, sort_keys=True, ensure_ascii=False).encode()
    checksum = hashlib.sha256(encoded).hexdigest()
    folder = settings().data_dir / "indexes" / (checksum[:16] + "-" + uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "chunks.json").write_bytes(encoded)
    vectors = encoder.encode(
        [f"{c['title']}\n{c['section'] or ''}\n{c['content']}" for c in chunks]
    )
    np.save(folder / "vectors.npy", vectors, allow_pickle=False)
    manifest = {
        "model": encoder.name,
        "model_revision": encoder.revision,
        "encoding_signature": encoder.signature,
        "max_sequence_length": encoder.model.max_seq_length,
        "parser_version": PARSER_VERSION,
        "corpus_checksum": checksum,
        "dimensions": vectors.shape[1],
        "chunks": len(chunks),
        "created_at": datetime.now(UTC).isoformat(),
        "vector_sha256": hashlib.sha256((folder / "vectors.npy").read_bytes()).hexdigest(),
    }
    atomic_json(folder / "manifest.json", manifest)
    if publish:
        # This pointer affects ONLY the isolated preview. Old bundles remain available for rollback.
        pointer = settings().data_dir / "active-index.json"
        previous = json.loads(pointer.read_text()) if pointer.exists() else None
        atomic_json(
            pointer,
            {
                "folder": folder.name,
                "previous": previous,
                "published_at": datetime.now(UTC).isoformat(),
            },
        )
    return manifest, folder


def year(value):
    match = re.search(r"\b(20\d{2})\b", value or "")
    return int(match[1]) if match else None


TOPICS = {
    "faculty": {"faculty", "research"},
    "research": {"faculty", "research"},
    "curriculum": {"curriculum"},
    "admissions": {"admissions", "programme"},
    "fees": {"fees", "services"},
    "academic_policy": {"academic_policy", "registration"},
    "registration": {"academic_policy", "registration", "curriculum"},
    "timetable": {"timetable"},
    "exam_schedule": {"exam_schedule"},
    "services": {"services"},
    "programme": {"programme", "curriculum"},
}


class Index:
    def __init__(self, store, encoder=None, reranker=None, load_bundle=True):
        self.store, self.encoder, self.reranker = store, encoder, reranker
        self.chunks = store.chunks()
        self.vectors, self.manifest = None, None
        pointer = settings().data_dir / "active-index.json"
        if pointer.exists() and load_bundle:
            name = json.loads(pointer.read_text())["folder"]
            folder = (settings().data_dir / "indexes" / name).resolve()
            if not folder.is_relative_to((settings().data_dir / "indexes").resolve()):
                raise ValueError("Unsafe index path")
            m = json.loads((folder / "manifest.json").read_text())
            if m["model"] != settings().embedding_model or m["parser_version"] != PARSER_VERSION:
                raise ValueError("Index encoder/parser mismatch; rebuild before serving")
            if encoder and m.get("encoding_signature") != encoder.signature:
                raise ValueError(
                    "Index encoder revision/instruction mismatch; rebuild before serving"
                )
            if (
                hashlib.sha256((folder / "chunks.json").read_bytes()).hexdigest()
                != m["corpus_checksum"]
                or hashlib.sha256((folder / "vectors.npy").read_bytes()).hexdigest()
                != m["vector_sha256"]
            ):
                raise ValueError("Index checksum failure")
            self.chunks = json.loads((folder / "chunks.json").read_text())
            self.vectors = np.load(folder / "vectors.npy", allow_pickle=False)
            if self.vectors.shape != (len(self.chunks), m["dimensions"]):
                raise ValueError("Index shape mismatch")
            self.manifest = m
        # A rejected version must stay rejected after restart even if an older bundle included it.
        with store.connect() as db:
            reviews = {
                r[0]: r[1] for r in db.execute("SELECT id,review_status FROM document_version")
            }
        for chunk in self.chunks:
            chunk["review_status"] = reviews.get(chunk["source_version_id"], chunk["review_status"])
        self.by_id = {c["id"]: i for i, c in enumerate(self.chunks)}

    def eligible(self, task):
        if task.topic in {"academic_policy", "registration"} and not task.programme:
            return []
        if task.topic == "curriculum" and not task.admission_batch and not task.course_codes:
            return []
        cohort = year(task.admission_batch)
        topics = TOPICS.get(task.topic)
        candidates = [
            i
            for i, c in enumerate(self.chunks)
            if c["origin"] in {"official_archive", "official_live"}
            and c["review_status"] != "rejected"
            and (
                not (
                    task.high_stakes
                    or task.topic
                    in {
                        "academic_policy",
                        "registration",
                        "fees",
                        "admissions",
                        "timetable",
                        "exam_schedule",
                    }
                )
                or c["review_status"] == "approved"
            )
            and (
                not c.get("parser_version", "").endswith("-ocr1")
                or c["review_status"] == "approved"
            )
            and (not topics or c["topic"] in topics)
            and (not task.programme or not c["programme"] or c["programme"] == task.programme)
        ]
        if cohort and task.topic in {"curriculum", "registration"}:
            candidates = [
                i
                for i in candidates
                if self.chunks[i]["topic"] != "curriculum"
                or self.chunks[i]["cohort_start"] == cohort
                or (
                    self.chunks[i]["applies_onwards"]
                    and self.chunks[i]["cohort_start"] is not None
                    and self.chunks[i]["cohort_start"] <= cohort
                )
            ]
            starts = [
                self.chunks[i]["cohort_start"]
                for i in candidates
                if self.chunks[i]["topic"] == "curriculum"
            ]
            if starts:
                newest = max(x for x in starts if x is not None)
                candidates = [
                    i
                    for i in candidates
                    if self.chunks[i]["topic"] != "curriculum"
                    or self.chunks[i]["cohort_start"] == newest
                ]
        if task.operational_term and task.topic in {
            "fees",
            "admissions",
            "timetable",
            "exam_schedule",
        }:
            requested = task.operational_term.lower().strip()
            candidates = [
                i
                for i in candidates
                if self.chunks[i]["effective_term"]
                and self.chunks[i]["effective_term"].lower().strip() == requested
            ]
        if task.semester and task.topic == "curriculum":
            candidates = [
                i for i in candidates if self.chunks[i]["semester"] in {None, task.semester}
            ]
        return candidates

    def search(self, task: Task, k=8):
        eligible = self.eligible(task)
        if not eligible:
            return [], {
                "eligible": 0,
                "warning": "No evidence matches the requested academic scope",
            }
        allowed = set(eligible)
        tokens = re.findall(r"[^\W_]+", task.search_query, re.UNICODE)[:50]
        expr = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
        lexical = []
        if expr:
            with self.store.connect() as db:
                rows = db.execute(
                    "SELECT chunk_id,bm25(evidence_fts,0,3,2,1) rank FROM evidence_fts WHERE evidence_fts MATCH ? ORDER BY rank LIMIT 200",
                    (expr,),
                ).fetchall()
            lexical = [
                self.by_id[r["chunk_id"]]
                for r in rows
                if r["chunk_id"] in self.by_id and self.by_id[r["chunk_id"]] in allowed
            ]
        dense = []
        if self.vectors is not None and self.encoder:
            q = self.encoder.encode([task.search_query], query=True)[0]
            scores = self.vectors[eligible] @ q
            dense = [eligible[j] for j in np.argsort(-scores)[:30] if float(scores[j]) > 0.20]
        exact = []
        if task.course_codes:
            wanted = {re.sub(r"[^A-Z0-9]", "", code.upper()) for code in task.course_codes}
            exact = [
                i
                for i in eligible
                if any(
                    re.sub(r"[^A-Z0-9]", "", code) in wanted
                    for code in re.findall(r"\b[A-Z]{2,4}-?\d{3}\b", self.chunks[i]["content"])
                )
            ]
            # Course-specific university facts cannot be answered from other courses.
            allowed = set(exact)
            lexical = [i for i in lexical if i in allowed]
            dense = [i for i in dense if i in allowed]
        fused = defaultdict(float)
        for weight, ranking in [(1, lexical), (1, dense), (2, exact)]:
            for rank, idx in enumerate(ranking):
                fused[idx] += weight / (40 + rank + 1)
        ranked = sorted(fused, key=lambda i: -fused[i])[:24]
        rr = None
        if self.reranker and len(ranked) > 1 and not (exact and len(exact) <= 2):
            rr = self.reranker.scores(
                task.search_query,
                [self.chunks[i]["title"] + "\n" + self.chunks[i]["content"] for i in ranked],
            )
            ranked = [i for _, i in sorted(zip(rr, ranked, strict=False), key=lambda p: -p[0])]
        # Duplicate official aliases must not consume the evidence budget.
        result, seen = [], set()
        if task.topic == "curriculum" and not task.semester and not task.course_codes:
            # A whole-scheme tool must carry every semester, not six arbitrary fragments.
            versions = defaultdict(list)
            for i in eligible:
                versions[self.chunks[i]["source_version_id"]].append(i)
            if versions:
                canonical = max(
                    versions.values(),
                    key=lambda group: (
                        len(
                            {
                                self.chunks[i]["semester"]
                                for i in group
                                if self.chunks[i]["semester"]
                            }
                        ),
                        max((fused[i] for i in group), default=0),
                    ),
                )
                ranked = sorted(
                    canonical, key=lambda i: (self.chunks[i]["semester"] or 99, -fused[i])
                )
                k = max(k, len(ranked))
        for i in ranked:
            c = self.chunks[i]
            key = (c["checksum"], c["page"], c["content"])
            if key not in seen:
                seen.add(key)
                result.append({**c, "retrieval_score": fused[i]})
            if len(result) >= k:
                break
        return result, {
            "eligible": len(eligible),
            "lexical_ids": [self.chunks[i]["id"] for i in lexical[:10]],
            "dense_ids": [self.chunks[i]["id"] for i in dense[:10]],
            "exact_ids": [self.chunks[i]["id"] for i in exact],
            "reranked": rr is not None,
            "whole_scheme": task.topic == "curriculum"
            and not task.semester
            and not task.course_codes,
            "returned_ids": [c["id"] for c in result],
        }

    def lookup(self, task):
        """Bound, read-only academic lookup; no model-generated SQL."""
        if task.topic != "curriculum" or (not task.course_codes and not task.semester):
            return []
        clauses = ["v.parser_version=?", "v.review_status<>'rejected'"]
        values = [PARSER_VERSION]
        if task.programme:
            clauses.append("s.programme=?")
            values.append(task.programme)
        if task.semester:
            clauses.append("sc.semester=?")
            values.append(task.semester)
        if task.course_codes:
            clauses.append("sc.course_code IN (" + ",".join("?" for _ in task.course_codes) + ")")
            values.extend(task.course_codes)
        with self.store.connect() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    """SELECT sc.*,c.title,v.review_status,v.cohort_start,v.applies_onwards,v.effective_term FROM scheme_course sc JOIN study_scheme s ON s.id=sc.scheme_id JOIN course c ON c.code=sc.course_code JOIN document_version v ON v.id=s.version_id WHERE """
                    + " AND ".join(clauses),
                    values,
                )
            ]
        eligible = {self.chunks[i]["id"] for i in self.eligible(task)}
        return [r for r in rows if r["chunk_id"] in eligible]

    def course_candidates(self, task):
        """Suggest observed catalogue identifiers after an exact miss; never silently rename one."""
        candidates = []
        with self.store.connect() as db:
            for code in task.course_codes:
                suffix = re.search(r"(\d{3})$", code)
                if suffix:
                    rows = db.execute(
                        "SELECT code,title FROM course WHERE code LIKE ? LIMIT 8",
                        ("%" + suffix[1],),
                    ).fetchall()
                    prefix = re.sub(r"[^A-Z]", "", code.upper())
                    plausible = [
                        r for r in rows if re.sub(r"[^A-Z]", "", r["code"]).startswith(prefix)
                    ]
                    candidates.extend(dict(r) for r in (plausible or rows))
        return candidates

    def preflight(self, plan):
        """Academic tool preconditions, evaluated after model interpretation, never keyword routing."""
        if len(plan.tasks) != 1:
            return None
        task = plan.tasks[0]
        if task.topic in {"academic_policy", "registration"} and not task.programme:
            return {"field": "programme", "reason": "Degree-specific rules require a programme"}
        if task.topic == "curriculum" and task.course_codes and not self.lookup(task):
            candidates = self.course_candidates(task)
            if candidates:
                return {"field": "course_code_confirmation", "candidates": candidates}
        if task.topic == "curriculum" and not task.admission_batch and not task.course_codes:
            return {
                "field": "admission_batch",
                "reason": "Study scheme applicability requires the admission cohort",
            }
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish-preview", action="store_true")
    args = parser.parse_args()
    config = settings()
    encoder = Encoder(config.embedding_model, config.embedding_device, config.local_files_only)
    manifest, folder = build_index(Store(), encoder, args.publish_preview)
    print(
        json.dumps({**manifest, "folder": str(folder), "preview_published": args.publish_preview})
    )


if __name__ == "__main__":
    main()

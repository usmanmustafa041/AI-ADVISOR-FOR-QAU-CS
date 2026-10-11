import asyncio
import hashlib
import time
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from chatbot_v3.contracts import ChatResponse
from chatbot_v3.generation import (
    GROUNDED_FORMAT,
    AnswerDraft,
    BlockDecoder,
    GroundingError,
    answer_messages,
    numeric_tokens,
    reference,
    validate_paragraph,
)
from chatbot_v3.model import ModelUnavailable
from chatbot_v3.privacy import diagnostic_copy
from chatbot_v3.settings import settings
from chatbot_v3.understanding import apply_tool_requirements, understand


class CapacityError(RuntimeError):
    pass


class Service:
    def __init__(self, store, model, index):
        self.store, self.model, self.index = store, model, index
        self.slot = asyncio.Semaphore(1)
        self.waiting = 0
        self.guests = OrderedDict()
        self.traces = OrderedDict()
        source = hashlib.sha256()
        for path in sorted(Path(__file__).parent.rglob("*.py")):
            source.update(str(path.relative_to(Path(__file__).parent)).encode())
            source.update(path.read_bytes())
        self.runtime = {
            "started_at": datetime.now(UTC).isoformat(),
            "code_sha256": source.hexdigest(),
            "generator": getattr(getattr(model, "config", None), "model", type(model).__name__),
            "index_manifest": index.manifest,
        }
        self.metrics = {
            "completed": 0,
            "errors": 0,
            "cancelled": 0,
            "latencies_ms": [],
            "first_tokens_ms": [],
        }

    def remember_trace(self, trace, private):
        if settings().store_traces:
            self.traces[trace["trace_id"]] = diagnostic_copy(trace, private=private)
            while len(self.traces) > 100:
                self.traces.popitem(last=False)

    def conversation(self, request, owner, authenticated):
        if authenticated:
            if request.history:
                raise ValueError("Authenticated conversations use owner-scoped server history")
            return (
                self.store.history(request.conversation_id, owner)
                if request.conversation_id
                else ([], {})
            )
        now = time.time()
        for key in list(self.guests):
            if self.guests[key]["updated_at"] < now - settings().guest_ttl_seconds:
                del self.guests[key]
        if request.conversation_id:
            item = self.guests.get((owner, request.conversation_id))
            if item is None:
                raise KeyError("Conversation not found or expired")
            return item["history"], item["state"]
        return [h.model_dump() for h in request.history], {}

    async def events(self, request, owner, authenticated):
        started, trace_id = time.perf_counter(), str(uuid4())
        trace = {
            "trace_id": trace_id,
            "original": request.message,
            "stages": {},
            "validation_errors": [],
            "runtime": self.runtime,
        }
        private_trace = authenticated
        history, state = self.conversation(request, owner, authenticated)
        if self.waiting >= settings().queue_size:
            raise CapacityError("The assistant queue is full. Please retry shortly.")
        self.waiting += 1
        acquired = False
        try:
            yield "start", {"trace_id": trace_id}
            yield "status", {"stage": "queued", "message": "Waiting for the local model"}
            await asyncio.wait_for(self.slot.acquire(), settings().queue_timeout_seconds)
            acquired = True
            trace["stages"]["queue_ms"] = round((time.perf_counter() - started) * 1000)
            if not await self.model.available():
                raise ModelUnavailable(
                    "The configured local model is not available. Please retry after it has been installed."
                )
            yield "status", {"stage": "understanding", "message": "Understanding your question"}
            t = time.perf_counter()
            plan = await understand(self.model, request, history, state)
            private_trace = authenticated or plan.mode == "private_record"
            requirement = await asyncio.to_thread(self.index.preflight, plan)
            apply_tool_requirements(plan, requirement)
            trace["tool_preconditions"] = requirement
            trace["interpretation"] = plan.model_dump()
            trace["stages"]["understanding_ms"] = round((time.perf_counter() - t) * 1000)
            evidence, gaps = [], []
            if plan.needs_clarification:
                answer, status = plan.clarification_question, "clarification"
                trace["first_token_ms"] = round((time.perf_counter() - started) * 1000)
                yield "token", {"text": answer}
                used = []
            elif plan.mode == "private_record":
                answer = {
                    "english": "I can explain published rules, but I cannot access or disclose private student records. For your own marks or registration, use the official student portal or contact your department.",
                    "roman_urdu": "Main published rules samjha sakta hoon, lekin private student records ya marks access ya share nahi kar sakta. Apne record ke liye official student portal ya department se rabta karein.",
                    "urdu": "میں شائع شدہ قواعد سمجھا سکتا ہوں، لیکن کسی طالب علم کے نجی ریکارڈ یا نمبروں تک رسائی یا انہیں ظاہر نہیں کر سکتا۔ اپنے ریکارڈ کے لیے سرکاری طالب علم پورٹل یا شعبے سے رابطہ کریں۔",
                }[plan.language]
                trace["first_token_ms"] = round((time.perf_counter() - started) * 1000)
                yield "token", {"text": answer}
                used = []
                status = "private_record_boundary"
            else:
                yield "status", {"stage": "retrieving", "message": "Finding relevant sources"}
                t = time.perf_counter()
                groups = []
                for task in plan.tasks:
                    if task.topic == "general" and plan.mode in {"tutor", "conversation"}:
                        continue
                    exact_records = await asyncio.to_thread(self.index.lookup, task)
                    hits, diagnostic = await asyncio.to_thread(self.index.search, task, 6)
                    if exact_records:
                        exact_ids = {r["chunk_id"] for r in exact_records}
                        hits.sort(key=lambda h: h["id"] not in exact_ids)
                    diagnostic["structured_lookup"] = exact_records
                    trace.setdefault("retrieval", []).append(
                        {"task": task.model_dump(), **diagnostic}
                    )
                    groups.append(hits)
                    if not hits:
                        gaps.append(
                            {
                                "question": task.question,
                                "scope": task.model_dump(),
                                "reason": "No evidence matching programme, cohort, term and topic",
                                "observed_course_code_candidates": await asyncio.to_thread(
                                    self.index.course_candidates, task
                                ),
                                "missing_decisive_scope": ["programme"]
                                if task.topic in {"academic_policy", "registration"}
                                and not task.programme
                                else ["admission_batch"]
                                if task.topic == "curriculum"
                                and not task.admission_batch
                                and not task.course_codes
                                else [],
                            }
                        )
                seen = set()
                for rank in range(max((len(group) for group in groups), default=0)):
                    for group in groups:
                        if len(group) > rank and group[rank]["id"] not in seen:
                            evidence.append(group[rank])
                            seen.add(group[rank]["id"])
                evidence = evidence[:24]
                trace["stages"]["retrieval_ms"] = round((time.perf_counter() - t) * 1000)
                trace["evidence_ids"] = [c["id"] for c in evidence]
                yield "status", {"stage": "answering", "message": "Preparing your answer"}
                answer, used = "", []
                t = time.perf_counter()
                # Tutor tokens stream directly; complete academic blocks are checked before release.
                grounded = plan.mode not in {"tutor", "conversation"}
                messages = answer_messages(plan, history, evidence, gaps)
                if grounded:
                    messages[0]["content"] += "\n" + GROUNDED_FORMAT
                decoder = BlockDecoder()
                stream = (
                    self.model.stream(messages, AnswerDraft.model_json_schema())
                    if grounded
                    else self.model.stream(messages)
                )
                async for token in stream:
                    if plan.mode in {"tutor", "conversation"}:
                        if trace.get("first_token_ms") is None:
                            trace["first_token_ms"] = round((time.perf_counter() - started) * 1000)
                        answer += token
                        yield "token", {"text": token}
                    else:
                        for block in decoder.feed(token):
                            if not block.text.strip():
                                continue
                            paragraph = block.text
                            if block.sources:
                                import re

                                paragraph = re.sub(r"\[\d+\]", "", paragraph).rstrip()
                            if block.sources:
                                paragraph += " " + "".join(
                                    f"[{n}]" for n in dict.fromkeys(block.sources)
                                )
                            try:
                                if block.kind == "university_fact" and not block.sources:
                                    raise GroundingError(
                                        "University fact block has no supporting source"
                                    )
                                if block.kind == "general_explanation" and plan.mode != "mixed":
                                    raise GroundingError(
                                        "University answer cannot bypass grounding as general explanation"
                                    )
                                if block.kind == "clarification" and (
                                    not block.text.strip().endswith(("?", "؟"))
                                    or numeric_tokens(block.text) - numeric_tokens(plan.original)
                                ):
                                    raise GroundingError(
                                        "Clarification contains an unsupported numerical premise"
                                    )
                                if (
                                    block.kind == "limitation"
                                    and not block.sources
                                    and (numeric_tokens(block.text) - numeric_tokens(plan.original))
                                ):
                                    raise GroundingError(
                                        "Limitation contains an uncited numerical claim"
                                    )
                                cited = validate_paragraph(
                                    paragraph,
                                    evidence,
                                    plan.original,
                                    require_citation=block.kind == "university_fact",
                                )
                            except GroundingError as e:
                                trace["validation_errors"].append(str(e))
                                continue
                            used.extend(cited)
                            text = ("\n\n" if answer else "") + paragraph
                            answer += text
                            if trace.get("first_token_ms") is None:
                                trace["first_token_ms"] = round(
                                    (time.perf_counter() - started) * 1000
                                )
                            yield "token", {"text": text}
                trace["stages"]["generation_ms"] = round((time.perf_counter() - t) * 1000)
                if not answer.strip():
                    answer = {
                        "english": "I couldn't produce a supported answer from the available evidence. Please narrow the question or check the relevant official source with the department.",
                        "roman_urdu": "Available evidence se supported jawab tayyar nahi ho saka. Sawal thora specific karein, ya department se relevant official source confirm karein.",
                        "urdu": "دستیاب شواہد سے مستند جواب تیار نہیں ہو سکا۔ براہ کرم سوال کو واضح کریں یا متعلقہ سرکاری ماخذ کی شعبے سے تصدیق کریں۔",
                    }[plan.language]
                    yield "token", {"text": answer}
                status = (
                    "citation_provenance_checked"
                    if used
                    else "general_explanation"
                    if plan.mode in {"tutor", "conversation"}
                    else "insufficient_evidence"
                )
            references = [reference(evidence[n - 1], n) for n in sorted(set(used))]
            warnings = []
            if any(c.review_status == "needs_review" for c in references):
                warnings.append(
                    "Some cited source extractions await academic review; this answer is not registration approval."
                )
            if trace["validation_errors"]:
                warnings.append(
                    "Some generated passages were withheld because their citations or numbers could not be checked."
                )
            if self.index.vectors is None and plan.mode in {"university", "mixed"}:
                warnings.append("Semantic search is unavailable; retrieval used the keyword index.")
            for ref in references:
                yield "citation", ref.model_dump()
            for warning in warnings:
                yield "warning", {"message": warning}
            result = ChatResponse(
                answer=answer,
                mode=plan.mode,
                cited_sources=references,
                groundedness_status=status,
                scope={
                    "programme": plan.programme,
                    "admission_batch": plan.admission_batch,
                    "operational_term": plan.operational_term,
                    "tasks": [t.model_dump() for t in plan.tasks],
                },
                followup_question=plan.clarification_question if plan.needs_clarification else None,
                warnings=warnings,
                trace_id=trace_id,
                latency_ms=round((time.perf_counter() - started) * 1000),
                first_token_ms=trace.get("first_token_ms"),
            )
            state = {
                "programme": plan.programme,
                "admission_batch": plan.admission_batch,
                "operational_term": plan.operational_term,
                "course_codes": plan.course_codes,
                "person_names": plan.person_names,
                "last_tasks": [t.model_dump() for t in plan.tasks],
                "authenticated": authenticated,
            }
            if authenticated:
                result.conversation_id, result.message_id = await asyncio.to_thread(
                    self.store.save_turn,
                    owner,
                    request.conversation_id,
                    request.message,
                    result,
                    state,
                )
            else:
                result.conversation_id = request.conversation_id or str(uuid4())
                self.guests[(owner, result.conversation_id)] = {
                    "history": (
                        history
                        + [
                            {"role": "user", "content": request.message},
                            {"role": "assistant", "content": answer},
                        ]
                    )[-12:],
                    "state": state,
                    "updated_at": time.time(),
                }
                while len(self.guests) > 500:
                    self.guests.popitem(last=False)
            self.metrics["completed"] += 1
            self.metrics["latencies_ms"] = (self.metrics["latencies_ms"] + [result.latency_ms])[
                -1000:
            ]
            if result.first_token_ms is not None:
                self.metrics["first_tokens_ms"] = (
                    self.metrics["first_tokens_ms"] + [result.first_token_ms]
                )[-1000:]
            # Opt-in diagnostics are local developer data. Ordinary requests do not persist transcripts.
            if settings().store_traces:
                trace["response"] = result.model_dump()
                self.remember_trace(trace, private_trace)
            yield "done", result.model_dump()
        except asyncio.CancelledError:
            self.metrics["cancelled"] += 1
            trace["error"] = {"type": "cancelled"}
            self.remember_trace(trace, private_trace)
            raise
        except TimeoutError as e:
            self.metrics["errors"] += 1
            trace["error"] = {"type": "queue_timeout"}
            self.remember_trace(trace, private_trace)
            error = CapacityError("The local model queue timed out. Please retry shortly.")
            error.trace_id = trace_id
            raise error from e
        except Exception as e:
            self.metrics["errors"] += 1
            trace["error"] = {
                "type": type(e).__name__,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "dependency_error_type": type(e.__cause__).__name__ if e.__cause__ else None,
                "upstream_status": getattr(
                    getattr(e.__cause__, "response", None), "status_code", None
                ),
            }
            self.remember_trace(trace, private_trace)
            e.trace_id = trace_id
            raise
        finally:
            self.waiting -= 1
            if acquired:
                self.slot.release()

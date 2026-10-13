import asyncio
import hashlib
import time
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from chatbot_v3.contracts import ChatResponse
from chatbot_v3.facts import resolve_entities
from chatbot_v3.generation import (
    GROUNDED_FORMAT,
    BlockDecoder,
    GroundingError,
    answer_messages,
    answer_schema,
    is_source_data_block,
    language_matches,
    localize_blocks,
    missing_evidence_blocks,
    numeric_tokens,
    reference,
    validate_block,
    validate_paragraph,
)
from chatbot_v3.model import ModelUnavailable, OutputBudgetExceeded, call_metrics
from chatbot_v3.privacy import diagnostic_copy
from chatbot_v3.settings import settings
from chatbot_v3.understanding import apply_tool_requirements, understand


class CapacityError(RuntimeError):
    pass


class Service:
    def __init__(self, store, model, index):
        self.store, self.model, self.index = store, model, index
        from chatbot_v3.timetable.store import TimetableStore

        self.timetables = TimetableStore(store.path.parent / "timetables")
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
            "model_calls": [],
        }
        private_trace = authenticated
        history, state = self.conversation(request, owner, authenticated)
        if self.waiting >= settings().queue_size:
            trace["error"] = {"type": "queue_full", "queue_depth": self.waiting}
            self.remember_trace(trace, private_trace)
            error = CapacityError("The assistant queue is full. Please retry shortly.")
            error.trace_id = trace_id
            raise error
        self.waiting += 1
        metrics_context = call_metrics.set(trace["model_calls"])
        acquired = False
        try:
            yield "start", {"trace_id": trace_id}
            yield "status", {"stage": "queued", "message": "Waiting for the local model"}
            await asyncio.wait_for(self.slot.acquire(), settings().queue_timeout_seconds)
            acquired = True
            trace["stages"]["queue_ms"] = round((time.perf_counter() - started) * 1000)
            t = time.perf_counter()
            model_available = await self.model.available()
            trace["stages"]["availability_ms"] = round((time.perf_counter() - t) * 1000)
            if not model_available:
                raise ModelUnavailable(
                    "The configured local model is not available. Please retry after it has been installed."
                )
            yield "status", {"stage": "understanding", "message": "Understanding your question"}
            t = time.perf_counter()
            plan = await understand(self.model, request, history, state)
            timetable = plan.timetable_query
            if timetable:
                plan.programme = timetable.programme
                plan.operational_term = timetable.academic_term
            trace["entity_resolution"] = (
                {"tool": "timetable_legend"}
                if timetable
                else await asyncio.to_thread(resolve_entities, self.index, plan)
            )
            private_trace = authenticated or plan.mode == "private_record"
            requirement = (
                await asyncio.to_thread(self.index.preflight, plan)
                if not timetable and plan.mode not in {"private_record", "tutor", "conversation"}
                else None
            )
            academic = [task for task in plan.tasks if task.topic != "general"]
            if (
                plan.needs_clarification
                and academic
                and all(
                    task.evidence_type == "course_credits" and task.course_codes
                    for task in academic
                )
            ):
                observed = [await asyncio.to_thread(self.index.lookup, task) for task in academic]
                if all(
                    rows
                    and len(
                        {(r["lecture_credits"], r["lab_credits"], r["total_credits"]) for r in rows}
                    )
                    == 1
                    for rows in observed
                ):
                    plan.needs_clarification, plan.clarification_question = False, None
                    plan.ambiguous_fields = []
            if not timetable:
                apply_tool_requirements(plan, requirement)
            trace["tool_preconditions"] = requirement
            trace["interpretation"] = plan.model_dump()
            trace["stages"]["understanding_ms"] = round((time.perf_counter() - t) * 1000)
            evidence, gaps = [], []
            timetable_refs, timetable_result = None, None
            if timetable:
                from chatbot_v3.timetable.query import execute, render

                yield (
                    "status",
                    {"stage": "timetable", "message": "Reading the published timetable snapshot"},
                )
                t = time.perf_counter()
                timetable_result = await asyncio.to_thread(execute, self.timetables, timetable)
                answer, timetable_refs = render(timetable_result, plan.language)
                if any(
                    task.topic not in {"timetable", "general"}
                    and task.evidence_type != "teaching_assignment"
                    for task in plan.tasks
                ):
                    answer += "\n\nThis response covers the timetable part. Please ask the separate academic question in another message."
                trace["timetable"] = timetable_result
                trace["stages"]["timetable_query_ms"] = round((time.perf_counter() - t) * 1000)
                trace["first_token_ms"] = round((time.perf_counter() - started) * 1000)
                used = []
                status = (
                    "clarification"
                    if timetable_result.get("clarification")
                    else "structured_timetable"
                )
                yield "token", {"text": answer}
            elif plan.needs_clarification:
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
                groups, structured_records = [], []
                for task in plan.tasks:
                    if task.topic == "general":
                        continue
                    exact_records = await asyncio.to_thread(self.index.lookup, task)
                    structured_records.append({"task": task.model_dump(), "records": exact_records})
                    hits, diagnostic = await asyncio.to_thread(self.index.search, task, 6)
                    if task.topic == "procedures" and task.evidence_type in {
                        "procedure",
                        "resource",
                    }:
                        # A missing reviewed instruction must not hide a real official form.
                        # Navigation views expose titles/links only, never unreviewed rules.
                        navigation = task.model_copy(
                            update={"evidence_type": "resource", "high_stakes": False}
                        )
                        resource_hits, resource_diagnostic = await asyncio.to_thread(
                            self.index.search, navigation, 2
                        )
                        present = {h["id"] for h in hits}
                        hits.extend(h for h in resource_hits if h["id"] not in present)
                        diagnostic["resource_navigation"] = resource_diagnostic
                    if task.topic == "procedures":
                        # The department inquiry desk is a useful published contact,
                        # never evidence that it accepts this particular submission.
                        contact = task.model_copy(
                            update={
                                "search_query": "Computer Sciences student advisory contact office",
                                "evidence_type": "service_contact",
                                "high_stakes": False,
                            }
                        )
                        contact_hits, _ = await asyncio.to_thread(self.index.search, contact, 1)
                        present = {h["id"] for h in hits}
                        hits.extend(h for h in contact_hits if h["id"] not in present)
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
                                "requested_evidence_type": task.evidence_type,
                                "academic_review_required": task.high_stakes
                                or task.topic
                                in {
                                    "admissions",
                                    "academic_policy",
                                    "fees",
                                    "registration",
                                    "timetable",
                                    "exam_schedule",
                                },
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
                trace["stages"]["reranking_ms"] = round(
                    sum(r.get("reranking_ms", 0) for r in trace.get("retrieval", [])), 2
                )
                trace["evidence_ids"] = [c["id"] for c in evidence]
                trace["retrieved_evidence"] = [
                    {k: v for k, v in c.items() if k != "raw_path"} for c in evidence
                ]
                yield "status", {"stage": "answering", "message": "Preparing your answer"}
                answer, used = "", []
                t = time.perf_counter()
                # Tutor tokens stream directly; complete academic blocks are checked before release.
                grounded = plan.mode not in {"tutor", "conversation"}
                messages = answer_messages(plan, history, evidence, gaps, structured_records)
                if grounded:
                    messages[0]["content"] += "\n" + GROUNDED_FORMAT
                trace["generation_input"] = messages
                trace["generated_blocks"] = []
                trace["language_repairs"] = []
                trace["language_repair_attempts"] = 0
                decoder = BlockDecoder()
                from chatbot_v3.procedures import procedure_blocks

                procedure_output = procedure_blocks(plan, evidence)
                if procedure_output is not None or plan.mode == "university" and not evidence:
                    trace["generation_skipped"] = (
                        "Source-capability procedure tool"
                        if procedure_output is not None
                        else "No matching approved/eligible university evidence"
                    )
                    trace["generation_input"] = None

                    async def tool_gap_stream():
                        import json

                        yield json.dumps(
                            {
                                "blocks": [
                                    block.model_dump()
                                    for block in (
                                        procedure_output
                                        if procedure_output is not None
                                        else missing_evidence_blocks(plan)
                                    )
                                ]
                            },
                            ensure_ascii=False,
                        )

                    stream = tool_gap_stream()
                else:
                    stream = (
                        self.model.stream(
                            messages, answer_schema(plan.language, evidence, plan.mode)
                        )
                        if grounded
                        else self.model.stream(messages)
                    )

                async def bounded_tokens():
                    try:
                        async for piece in stream:
                            yield piece
                    except OutputBudgetExceeded:
                        trace["generation_incomplete"] = True
                        if not answer.strip():
                            raise

                tokens = bounded_tokens()

                async def answer_units():
                    deferred = []
                    async for token in tokens:
                        if not grounded:
                            yield token
                            continue
                        for block in decoder.feed(token):
                            trace.setdefault(
                                "tool_gap_blocks"
                                if trace.get("generation_skipped")
                                else "generated_blocks",
                                [],
                            ).append(block.model_dump())
                            if not block.text.strip():
                                continue
                            if language_matches(block.text, plan.language) or is_source_data_block(
                                block, evidence
                            ):
                                yield block
                            else:
                                deferred.append(block)
                    # Finish and close the original call before a translation call is admitted.
                    await stream.aclose()
                    if deferred:
                        trace["language_repair_attempts"] = 1
                        call_start = len(trace["model_calls"])
                        try:
                            repaired = await localize_blocks(self.model, deferred, plan.language)
                            for original_block, block in zip(deferred, repaired, strict=True):
                                trace["language_repairs"].append(
                                    {
                                        "original": original_block.model_dump(),
                                        "repaired": block.model_dump(),
                                    }
                                )
                                yield block
                        except (GroundingError, ModelUnavailable) as error:
                            trace["validation_errors"].append(str(error))
                        finally:
                            for call in trace["model_calls"][call_start:]:
                                call["stage"] = "language_repair"

                units = answer_units()
                async for unit in units:
                    if not grounded:
                        if trace.get("first_token_ms") is None:
                            trace["first_token_ms"] = round((time.perf_counter() - started) * 1000)
                        answer += unit
                        yield "token", {"text": unit}
                    else:
                        block = unit
                        paragraph = block.text
                        if block.sources:
                            import re

                            paragraph = re.sub(r"\[\d+\]", "", paragraph).rstrip()
                        if block.sources:
                            paragraph += " " + "".join(
                                f"[{n}]" for n in dict.fromkeys(block.sources)
                            )
                        try:
                            validate_block(block, evidence, plan.tasks)
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
                            trace["first_token_ms"] = round((time.perf_counter() - started) * 1000)
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
            references = (
                timetable_refs
                if timetable_refs is not None
                else [reference(evidence[n - 1], n) for n in sorted(set(used))]
            )
            warnings = timetable_result.get("warnings", []) if timetable_result else []
            if trace.get("generation_incomplete"):
                warnings.append(
                    "The model reached its answer budget. This response is incomplete; the supported portions are retained."
                )
                status = "incomplete_answer"
            if any(c.review_status == "needs_review" for c in references):
                warnings.append("Some cited source transcriptions await review.")
            if trace["validation_errors"]:
                warnings.append(
                    "Some generated passages were withheld because their citations, identifiers, numbers or response language failed validation."
                )
            if (
                not timetable
                and self.index.vectors is None
                and plan.mode in {"university", "mixed"}
            ):
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
                    **({"timetable": timetable_result} if timetable_result is not None else {}),
                },
                followup_question=plan.clarification_question if plan.needs_clarification else None,
                warnings=warnings,
                trace_id=trace_id,
                latency_ms=round((time.perf_counter() - started) * 1000),
                first_token_ms=trace.get("first_token_ms"),
            )
            state = {
                "timetable": timetable.model_dump(mode="json") if timetable else None,
                "programme": plan.programme,
                "admission_batch": plan.admission_batch,
                "operational_term": plan.operational_term,
                "course_codes": plan.course_codes,
                "person_names": plan.person_names,
                "last_tasks": [t.model_dump() for t in plan.tasks],
                "authenticated": authenticated,
                "preferred_language": request.preferred_language
                or plan.response_language
                or state.get("preferred_language"),
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
            if hasattr(e, "errors"):
                trace["error"]["validation_issues"] = e.errors(
                    include_input=False, include_context=False
                )
            self.remember_trace(trace, private_trace)
            e.trace_id = trace_id
            raise
        finally:
            try:
                if "units" in locals():
                    await units.aclose()
                if "tokens" in locals():
                    await tokens.aclose()
                if "stream" in locals():
                    await stream.aclose()
            finally:
                self.waiting -= 1
                if acquired:
                    self.slot.release()
                call_metrics.reset(metrics_context)

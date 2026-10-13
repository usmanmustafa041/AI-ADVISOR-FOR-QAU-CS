"""The answering pipeline: question → evidence → grounded, cited, streamed answer."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator

from advisor.config import Settings
from advisor.db import Database
from advisor.llm.base import GenParams, MidStreamError
from advisor.llm.extractive import extractive_answer
from advisor.llm.router import NoProviderAvailable, ProviderRouter
from advisor.rag import prompts
from advisor.rag import grounding
from advisor.rag.knowledge import KnowledgeBase
from advisor.timetable_store import TimetableStore
from advisor.rag.query import FOLLOWUP, is_conversational, rule_contextualize, smalltalk_kind
from advisor.prereq.graph import analyse as analyse_prereq
from advisor.retrieval.retriever import Hit, wants_listing
from advisor.retrieval.text import detect_language
from advisor.runtime_settings import RuntimeSettings

log = logging.getLogger("advisor.service")

CITATION = re.compile(r"\[(\d{1,2}(?:\s*[,;]\s*\d{1,2})*)\]")

SMALLTALK_REPLIES = {
    "en": (
        "Hello! I'm the QAU CS Advisor. Ask me about courses and prerequisites, schemes of study, "
        "faculty, admissions, fees, the academic calendar, timetables or the department's rules "
        "and regulations."
    ),
    "roman-ur": (
        "Assalam-o-Alaikum! Main QAU CS Advisor hoon. Aap mujh se courses, prerequisites, "
        "admissions, fees, faculty, timetable, academic calendar ya rules ke baare mein pooch sakte hain."
    ),
    "ur": (
        "السلام علیکم! میں QAU CS ایڈوائزر ہوں۔ آپ مجھ سے کورسز، پری ریکوزٹس، داخلوں، فیس، فیکلٹی، "
        "ٹائم ٹیبل، تعلیمی کیلنڈر اور قواعد و ضوابط کے بارے میں پوچھ سکتے ہیں۔"
    ),
}
HOW_ARE_YOU_REPLY = {
    "en": "I'm doing well, thank you for asking! I'm the QAU CS Advisor. Ask me about courses and prerequisites, "
          "fees, admissions, faculty, timetables, the academic calendar or the department's rules.",
    "roman-ur": "Main bilkul theek hoon, shukriya! Main QAU CS Advisor hoon. Aap mujh se courses, prerequisites, "
                "fees, admissions, faculty, timetable ya rules ke baare mein pooch sakte hain.",
    "ur": "میں ٹھیک ہوں، شکریہ! میں QAU CS ایڈوائزر ہوں۔ آپ مجھ سے کورسز، پری ریکوزٹس، فیس، داخلوں، فیکلٹی، "
          "ٹائم ٹیبل یا قواعد کے بارے میں پوچھ سکتے ہیں۔",
}
ACK_REPLY = {
    "en": "Glad to help! Ask me anything else about the department — courses, fees, admissions, timetables or rules.",
    "roman-ur": "Khushi hui! Department ke baare mein kuch aur poochna ho to zaroor poochiye.",
    "ur": "خوشی ہوئی! شعبے کے بارے میں مزید کچھ پوچھنا ہو تو ضرور پوچھیں۔",
}
THANKS_REPLY = {
    "en": "You're welcome! Ask me anything else about the department.",
    "roman-ur": "Koi baat nahi! Department ke baare mein kuch aur poochna ho to zaroor poochiye.",
    "ur": "کوئی بات نہیں! شعبے کے بارے میں مزید کچھ پوچھنا ہو تو ضرور پوچھیں۔",
}
UNAVAILABLE = {
    "en": "Sorry, I can't reach the AI service right now and couldn't find a reliable passage to show. "
          "Please try again in a minute, or contact the department office: " + prompts.CONTACT + ".",
    "roman-ur": "Maaf kijiye, abhi AI service available nahi hai. Thori der baad dobara try karein ya "
                "department office se rabta karein: " + prompts.CONTACT + ".",
    "ur": "معذرت، اس وقت اے آئی سروس دستیاب نہیں۔ کچھ دیر بعد دوبارہ کوشش کریں یا شعبے کے دفتر سے رابطہ کریں: "
          + prompts.CONTACT + "۔",
}
NOT_FOUND = {
    "en": "I couldn't find that in the department's published pages or documents. Please check with the "
          "department office: " + prompts.CONTACT + ".",
    "roman-ur": "Mujhe yeh maloomat department ke published pages ya documents mein nahi mili. Barah-e-karam "
                "department office se rabta karein: " + prompts.CONTACT + ".",
    "ur": "مجھے یہ معلومات شعبے کے شائع شدہ صفحات یا دستاویزات میں نہیں ملیں۔ براہِ کرم شعبے کے دفتر سے رابطہ کریں: "
          + prompts.CONTACT + "۔",
}


def _norm_question(q: str) -> str:
    return re.sub(r"[^\w؀-ۿ]+", " ", q.lower()).strip()


class AnswerCache:
    def __init__(self, ttl: int, max_items: int = 2000):
        self.ttl = ttl
        self.max_items = max_items
        self._items: OrderedDict[str, tuple[float, dict]] = OrderedDict()

    def get(self, key: str) -> dict | None:
        item = self._items.get(key)
        if not item:
            return None
        if time.monotonic() - item[0] > self.ttl:
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return item[1]

    def put(self, key: str, value: dict) -> None:
        self._items[key] = (time.monotonic(), value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)

    def drop_for_message(self, message_id: str) -> None:
        for k in [k for k, (_, v) in self._items.items() if v.get("message_id") == message_id]:
            self._items.pop(k, None)

    def clear(self) -> None:
        self._items.clear()


class _Turn:
    """One question/answer exchange. Guest ("ephemeral") turns are never written to the database:
    the browser supplies the recent history and nothing is kept, except that a question the
    assistant could not answer is logged (without any identity) so the website can be improved."""

    def __init__(self, svc: AdvisorService, cid: str | None, ephemeral: bool):
        self.svc, self.cid, self.ephemeral = svc, cid, ephemeral

    def store(self, role: str, content: str, meta: dict | None = None) -> str:
        if self.ephemeral or self.cid is None:
            return uuid.uuid4().hex
        return self.svc._store(self.cid, role, content, meta)

    def log(self, **kw) -> None:
        if self.ephemeral and kw.get("outcome") not in ("abstained", "error", "degraded"):
            kw["question"] = "[guest conversation - not stored]"
        self.svc._log(**kw)


class AdvisorService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        runtime: RuntimeSettings,
        router: ProviderRouter,
        kb: KnowledgeBase,
    ):
        self.s = settings
        self.db = db
        self.rt = runtime
        self.router = router
        self.kb = kb
        self.cache = AnswerCache(settings.answer_cache_ttl_seconds)
        self.timetables = TimetableStore(db, kb)  # PDF timetable + the department's manual edits
        self.timetables.on_change = self.cache.clear  # earlier answers may quote the old timetable

    # ------------------------------------------------------------------ helpers
    def _history(self, conversation_id: str) -> list[tuple[str, str]]:
        rows = self.db.all(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at DESC, rowid DESC LIMIT 8",
            (conversation_id,),
        )
        return [(r["role"], r["content"]) for r in reversed(rows)]

    def _ensure_conversation(self, conversation_id: str | None, owner: str | None = None, title: str = "") -> str:
        """Reuse a conversation only for the same owner; anything else starts a fresh one (no leaks)."""
        if conversation_id:
            row = self.db.one("SELECT owner_id FROM conversations WHERE id=?", (conversation_id,))
            if row and (row["owner_id"] or None) == (owner or None):
                self.db.execute(
                    "UPDATE conversations SET updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
                    (conversation_id,),
                )
                return conversation_id
        cid = uuid.uuid4().hex
        self.db.execute(
            "INSERT INTO conversations(id, owner_id, title) VALUES(?,?,?)", (cid, owner, title[:80] or None)
        )
        return cid

    def _store(self, cid: str, role: str, content: str, meta: dict | None = None) -> str:
        mid = uuid.uuid4().hex
        self.db.execute(
            "INSERT INTO messages(id, conversation_id, role, content, meta) VALUES(?,?,?,?,?)",
            (mid, cid, role, content, json.dumps(meta) if meta else None),
        )
        return mid

    def _log(self, **kw) -> None:
        if not self.rt.get("chat.log_questions"):
            kw["question"] = "[logging disabled]"
        cols = ", ".join(kw)
        self.db.execute(
            f"INSERT INTO query_log({cols}) VALUES({', '.join('?' for _ in kw)})", tuple(kw.values())
        )

    async def _in_thread(self, fn, *args):
        async with self.kb._compute:
            return await asyncio.to_thread(fn, *args)

    # ------------------------------------------------------------------ query rewriting
    async def _search_query(self, question: str, history: list[tuple[str, str]], lang: str) -> tuple[str, str]:
        """Return (retrieval_query, how) — an LLM rewrite when it can help, rules otherwise."""
        needs = (history and (FOLLOWUP.search(question) or len(question.split()) <= 9)) or lang != "en"
        if not needs:
            return question, "none"
        try:
            name, _model, text = await asyncio.wait_for(
                self.router.complete(
                    prompts.rewrite_messages(question, history),
                    GenParams(temperature=0.0, max_tokens=80, timeout=12),
                ),
                timeout=14,
            )
            text = text.strip().strip('"').split("\n")[0]
            if 3 <= len(text) <= 300:
                return text, f"llm:{name}"
        except Exception as exc:
            log.info("query rewrite fell back to rules: %s", exc)
        return rule_contextualize(question, history), "rules"

    # ------------------------------------------------------------------ evidence
    def _prerequisite_analysis(self, question: str, search_q: str):
        bundle = self.kb.bundle
        if not bundle or bundle.prereq is None:
            return None
        return analyse_prereq(bundle.prereq, bundle.prereq_resolver, search_q) or (
            analyse_prereq(bundle.prereq, bundle.prereq_resolver, question) if search_q != question else None
        )

    def _with_prerequisite_analysis(self, analysis, passages: list[dict]) -> list[dict]:
        """Prepend an exact, computed prerequisite analysis when the question is about prerequisites."""
        if analysis is None:
            return passages
        labels = "; ".join(s["label"] for s in analysis.sources)
        item = {
            "title": "Computed prerequisite analysis", "heading": "Computed prerequisite analysis",
            "url": "doc://prerequisite-analysis", "kind": "computed",
            "kind_label": "calculated from the department prerequisite list", "text": analysis.text,
            "note": f"Computed from: {labels}", "fetched": "", "score": 1.0, "chunk_id": "computed-prereq",
        }
        return [item, *passages]

    def _context_profile(self, search_q: str) -> tuple[int, int]:
        """How much evidence to send. A local model reads ~400 tokens/s, so it gets a leaner
        context; hosted models take the full set."""
        candidates = self.router.candidates()
        local = bool(candidates) and candidates[0].name == "ollama"
        k = int(self.rt.get("rag.context_chunks"))
        budget = self.s.context_char_budget
        if local:
            k, budget = min(k, 7), min(budget, 8500)
        if wants_listing(search_q):
            k += 3 if local else 4
            budget += 2500 if local else 4000
        return k, budget

    def _passages(self, hits: list[Hit]) -> list[dict]:
        out = []
        for h in hits:
            c = h.chunk
            out.append(
                {
                    "title": c["title"], "heading": c["heading"], "url": c["url"], "kind": c["kind"],
                    "kind_label": prompts.KIND_LABELS.get(c["kind"], "department page"),
                    "text": c["text"], "note": (c.get("meta") or {}).get("note", ""),
                    "fetched": c.get("fetched_at", ""),
                    "score": h.score, "chunk_id": c["chunk_id"],
                }
            )
        return out

    # ------------------------------------------------------------------ main entry
    async def stream_answer(
        self,
        question: str,
        conversation_id: str | None,
        *,
        owner: str | None = None,
        ephemeral: bool = False,
        history: list[tuple[str, str]] | None = None,
        language: str | None = None,
    ) -> AsyncIterator[dict]:
        started = time.monotonic()
        question = question.strip()
        lang = detect_language(question)
        if (language or "").lower() in ("ur", "urdu"):
            lang = "ur"  # the student asked for Urdu replies explicitly
        if ephemeral and owner is None:
            cid = None
            history = [(r, t) for r, t in (history or []) if r in ("user", "assistant")][-8:]
        else:
            cid = self._ensure_conversation(conversation_id, owner, question)
            history = self._history(cid)
        if lang == "en" and len(question.split()) <= 6:
            # a short follow-up ("aur DSA?", "and MS?") keeps the language the student was just using
            prev_user = [t for r, t in history if r == "user"]
            if prev_user and detect_language(prev_user[-1]) in ("ur", "roman-ur") and not re.search(r"[A-Za-z]{4,}\s+[A-Za-z]{4,}\s+[A-Za-z]{4,}", question):
                lang = detect_language(prev_user[-1])
        turn = _Turn(self, cid, ephemeral and owner is None)
        turn.store("user", question)
        yield {"event": "meta", "conversation_id": cid}

        if not self.rt.get("chat.enabled"):
            msg = "The assistant is temporarily switched off for maintenance. Please contact the department office: " + prompts.CONTACT + "."
            mid = turn.store("assistant", msg)
            yield {"event": "delta", "text": msg}
            yield {"event": "done", "message_id": mid, "outcome": "refused"}
            return

        # --- small talk ------------------------------------------------------------
        kind = smalltalk_kind(question)
        if kind:
            table = {"how": HOW_ARE_YOU_REPLY, "thanks": THANKS_REPLY, "ack": ACK_REPLY}.get(kind, SMALLTALK_REPLIES)
            reply = table.get(lang) or table["en"]
            mid = turn.store("assistant", reply)
            turn.log(message_id=mid, question=question, language=lang, outcome="smalltalk")
            yield {"event": "delta", "text": reply}
            yield {"event": "done", "message_id": mid, "outcome": "smalltalk"}
            return

        # --- exact lookups: timetable (day / class / teacher / room / time) and fees ----------------
        found, engine = None, ""
        try:
            tt = self.timetables.current() if self.kb.bundle else None
        except Exception:
            log.exception("could not load the timetable; falling back to retrieval")
            tt = None
        for name, source in (("timetable", tt), ("fees", getattr(self.kb.bundle, "fees", None) if self.kb.bundle else None)):
            if source is None:
                continue
            try:
                found = source.answer(question, lang, history)
            except Exception:
                log.exception("%s lookup failed; falling back to retrieval", name)
                found = None
            if found:
                engine = name
                break
        if found:
            yield {"event": "status", "stage": "searching"}
            text = found["text"]
            passages = found.get("passages") or ([found["passage"]] if found.get("passage") else [])
            sources = self._sources(passages, set(range(1, len(passages) + 1)), text) if passages else []
            mid = turn.store("assistant", text, {"provider": engine, "sources": [s["url"] for s in sources]})
            latency = int((time.monotonic() - started) * 1000)
            turn.log(message_id=mid, question=question, language=lang, outcome="answered", provider=engine,
                     latency_ms=latency, index_build=self.kb.bundle.build_id)
            yield {"event": "delta", "text": text}
            yield {"event": "sources", "sources": sources}
            if found["followups"]:
                yield {"event": "followups", "items": found["followups"], "title": found["followup_title"]}
            yield {"event": "done", "message_id": mid, "outcome": "answered", "provider": engine,
                   "latency_ms": latency, "rewrite": engine}
            return

        notice = self.rt.get("assistant.notice")
        build = self.kb.bundle.build_id if self.kb.bundle else "none"
        cache_key = None
        if not history:
            cache_key = f"{build}|{lang}|{hash(notice)}|{_norm_question(question)}"
            hit = self.cache.get(cache_key)
            if hit:
                mid = turn.store("assistant", hit["text"], {"cached": True})
                turn.log(message_id=mid, question=question, language=lang, outcome="cached",
                          latency_ms=int((time.monotonic() - started) * 1000), index_build=build)
                yield {"event": "delta", "text": hit["text"]}
                yield {"event": "sources", "sources": hit["sources"]}
                yield {"event": "done", "message_id": mid, "outcome": "cached", "cached": True}
                return

        if not self.kb.ready:
            msg = "The knowledge base is not ready yet. Please try again shortly."
            yield {"event": "error", "message": msg, "retryable": True}
            return

        # --- retrieval -------------------------------------------------------------
        yield {"event": "status", "stage": "searching"}
        search_q, how = await self._search_query(question, history, lang)
        retriever = self.kb.retriever
        use_rerank = bool(self.rt.get("rag.rerank"))
        saved = retriever.reranker
        if not use_rerank:
            retriever.reranker = None
        try:
            hits = await self._in_thread(retriever.search, search_q)
        finally:
            retriever.reranker = saved
        if self.timetables.pdf_ignored():
            hits = [h for h in hits if h.chunk["kind"] != "timetable"]
        k, budget = self._context_profile(search_q)
        ctx_hits = retriever.context(hits, max_chunks=k, char_budget=budget)
        passages = self._passages(ctx_hits)
        prereq = self._prerequisite_analysis(question, search_q)
        passages = self._with_prerequisite_analysis(prereq, passages)
        top_score = ctx_hits[0].score if ctx_hits else 0.0

        # --- generation ------------------------------------------------------------
        yield {"event": "status", "stage": "writing"}
        messages = prompts.build_messages(
            question, history, passages, today=dt.date.today(), notice=notice,
            extra_rules=self.rt.get("assistant.extra_rules"), language=lang,
            resolved=search_q if history else "",
        )
        params = GenParams(
            temperature=float(self.rt.get("llm.temperature")),
            max_tokens=int(self.rt.get("llm.max_tokens")),
            timeout=self.s.answer_timeout_seconds,
        )
        text = ""
        provider = model = ""
        first_token_ms = None
        failed: set[str] = set()
        outcome = "answered"
        error = None
        grounding_note = None
        while True:
            try:
                text = ""
                async for provider, model, chunk in self.router.stream(messages, params, skip=failed):
                    if first_token_ms is None:
                        first_token_ms = int((time.monotonic() - started) * 1000)
                    text += chunk
                    yield {"event": "delta", "text": chunk}
                break
            except MidStreamError as exc:
                failed.add(exc.provider)
                yield {"event": "reset"}
                first_token_ms = None
                continue
            except NoProviderAvailable as exc:
                error = str(exc)[:500]
                provider = "extractive"
                relevant = [p for p in passages if p["score"] > 0][:3]
                text = extractive_answer(question, relevant) if top_score >= 0.02 and relevant else ""
                if not text:
                    text = UNAVAILABLE.get(lang, UNAVAILABLE["en"])
                    outcome = "error"
                else:
                    outcome = "degraded"
                yield {"event": "reset"}
                yield {"event": "delta", "text": text}
                break

        # --- post-processing -------------------------------------------------------
        streamed = text
        addendum = ""
        if prereq is not None and outcome == "answered":
            named = bool(self.kb.bundle.prereq_resolver.find(question))
            addendum = prereq.addendum(question, text, course_named=named)  # disagreements + any omitted list items
            if addendum:
                text += addendum
                streamed = text
                yield {"event": "delta", "text": addendum}
        if outcome == "answered":
            evidence = "\n".join(f"{p['title']} {p['heading']} {p['text']}" for p in passages) + " " + notice
            student = question + " " + " ".join(t for _r, t in history)
            checked = grounding.ground(text, evidence, student, not_found=NOT_FOUND.get(lang, NOT_FOUND["en"]), trusted=addendum or "")
            if checked.repaired:
                log.warning("grounding guard stripped invented course code(s): %s", checked.repaired[:4])
                text = checked.text
                grounding_note = "invented course code removed: " + ", ".join(checked.repaired)[:200]
            fallback = SMALLTALK_REPLIES.get(lang, SMALLTALK_REPLIES["en"]) if is_conversational(question) else NOT_FOUND.get(lang, NOT_FOUND["en"])
            if checked.removed:
                log.warning("grounding guard removed %d sentence(s): %s", len(checked.removed), checked.reasons[:3])
                text = fallback if checked.replaced_all else checked.text
                grounding_note = "; ".join(checked.reasons)[:400]
            text = re.sub(r"\[\s*(?:n|no|source|src|s|ref)\.?\s*(\d{1,2})\s*\]", r"[\1]", text, flags=re.I)
            has_cite = bool(CITATION.search(text))
            abstain_like = bool(re.search(r"couldn.t find|could not find|not (?:explicitly )?(?:listed|mentioned|provided|available|published|specified)|nahi mili|نہیں ملیں", text, re.I))
            if grounding.is_unsupported_university_claim(text, has_cite, abstain_like, evidence):
                log.warning("grounding guard: uncited university claims replaced")
                text = fallback  # chit-chat gets the friendly capabilities reply, real questions get "not found"
                grounding_note = "uncited university claims"
        final, cited = self._check_citations(text, len(passages))
        if final != streamed:
            yield {"event": "replace", "text": final}
        sources = self._sources(passages, cited, final)
        answer_msg = final
        mid = turn.store("assistant", answer_msg, {"provider": provider, "sources": [s["url"] for s in sources]})
        latency = int((time.monotonic() - started) * 1000)
        abstained = len(final) < 700 and bool(
            re.search(r"couldn.t find|could not find|not (?:explicitly )?(?:listed|mentioned|available in)|nahi mili|نہیں ملیں", final, re.I)
        )
        if outcome == "answered" and abstained:
            outcome = "abstained"
        turn.log(
            message_id=mid, question=question, language=lang, outcome=outcome, provider=provider,
            model=model, latency_ms=latency, ttft_ms=first_token_ms, top_score=top_score,
            sources=json.dumps([s["url"] for s in sources]), index_build=build, error=error or grounding_note,
        )
        yield {"event": "sources", "sources": sources}
        yield {
            "event": "done", "message_id": mid, "outcome": outcome, "provider": provider,
            "latency_ms": latency, "rewrite": how,
        }
        if cache_key and outcome == "answered" and cited:
            self.cache.put(cache_key, {"text": final, "sources": sources, "message_id": mid})

    # ------------------------------------------------------------------ post-processing
    @staticmethod
    def _check_citations(text: str, n_sources: int) -> tuple[str, set[int]]:
        cited: set[int] = set()
        # models sometimes write [n.2], [Source 2], [S2], [n 2] ...: normalise to [2]
        text = re.sub(r"\[\s*(?:n|no|source|src|s|ref)\.?\s*(\d{1,2})\s*\]", r"[\1]", text, flags=re.I)

        def fix(m: re.Match) -> str:
            nums = [int(x) for x in re.split(r"[,;]\s*", m.group(1).replace(" ", ""))]
            valid = [n for n in nums if 1 <= n <= n_sources]
            cited.update(valid)
            return "".join(f"[{n}]" for n in valid)

        return CITATION.sub(fix, text), cited

    @staticmethod
    def _sources(passages: list[dict], cited: set[int], answer: str) -> list[dict]:
        order = sorted(cited) if cited else []
        if not order and not re.search(r"couldn.t find|could not find", answer, re.I):
            order = [1, 2, 3][: len(passages)]  # nothing cited: show the best matches as "related"
        out, seen = [], set()
        for n in order:
            p = passages[n - 1]
            key = (p["url"], p["heading"])
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "n": n, "title": p["title"], "url": p["url"], "heading": p["heading"],
                    "kind": p["kind_label"], "note": p["note"],
                    "snippet": re.sub(r"\s+", " ", re.sub(r"[*#|`]+", " ", p["text"])).strip()[:240],
                    "cited": n in cited,
                }
            )
        return out

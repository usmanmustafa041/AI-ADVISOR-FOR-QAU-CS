"""End-to-end evaluation: run every golden question through the real pipeline."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from advisor.context import Context
from advisor.eval.retrieval_eval import load_golden

NOT_FOUND = re.compile(
    r"couldn.t find|could not find|not (?:able to )?find|no (?:information|mention)|don.t have|"
    r"not (?:listed|available|mentioned|published|specified)|not (?:been )?(?:listed|published)|"
    r"does not (?:currently )?publish|none of the sources (?:mention|list)|(?:do|does) not mention|(?:does not|doesn't) have any (?:listed )?prerequisites?|none (?:is |are )?listed|no prerequisites? (?:is |are )?(?:listed|published)|nahi mili|نہیں ملیں|office",
    re.I,
)


async def ask(ctx: Context, question: str, history: list[tuple[str, str]]) -> dict:
    cid = uuid.uuid4().hex
    ctx.db.execute("INSERT INTO conversations(id) VALUES(?)", (cid,))
    for role, text in history:
        ctx.db.execute(
            "INSERT INTO messages(id, conversation_id, role, content) VALUES(?,?,?,?)",
            (uuid.uuid4().hex, cid, role, text),
        )
    text, sources, done = "", [], {}
    async for ev in ctx.service.stream_answer(question, cid):
        if ev["event"] == "delta":
            text += ev["text"]
        elif ev["event"] == "reset":
            text = ""
        elif ev["event"] == "replace":
            text = ev["text"]
        elif ev["event"] == "sources":
            sources = ev["sources"]
        elif ev["event"] == "done":
            done = ev
    return {"text": text, "sources": sources, "done": done}


def grade(item: dict, result: dict) -> tuple[bool, list[str]]:
    text = re.sub(r"[*_`]{1,3}", "", result["text"])  # bold/italic markers must not decide a pass or fail
    problems: list[str] = []
    expect = item.get("expect", "answer")
    if expect == "abstain":
        if not NOT_FOUND.search(text):
            problems.append("should have said it could not find this")
    elif expect in ("answer", "general", "smalltalk"):
        for pat in item.get("facts", []):
            if not re.search(pat, text, re.I):
                problems.append(f"missing fact /{pat}/")
    for pat in item.get("forbid", []):
        if re.search(pat, text, re.I):
            problems.append(f"contains forbidden /{pat}/")
    if expect == "answer" and NOT_FOUND.search(text) and "couldn" in text.lower() and not item.get("allow_nf"):
        problems.append("claimed not-found for an answerable question")
    if expect == "answer" and item.get("gold") and not result["sources"]:
        problems.append("no sources shown")
    return (not problems), problems


async def run(ctx: Context, items: list[dict], out: Path, only: set[str] | None = None) -> dict:
    rows, passed = [], 0
    by_cat: dict[str, list[int]] = {}
    for it in items:
        if only and it["id"] not in only:
            continue
        t0 = time.time()
        history = [tuple(h) for h in it.get("history", [])]
        res = await ask(ctx, it["q"], history)
        ok, problems = grade(it, res)
        passed += ok
        c = by_cat.setdefault(it["cat"], [0, 0])
        c[0] += ok
        c[1] += 1
        rows.append(
            {
                "id": it["id"], "cat": it["cat"], "q": it["q"], "ok": ok, "problems": problems,
                "answer": res["text"], "sources": [s["url"] for s in res["sources"]],
                "provider": res["done"].get("provider"), "outcome": res["done"].get("outcome"),
                "seconds": round(time.time() - t0, 1),
            }
        )
        print(("PASS " if ok else "FAIL ") + it["id"], f"{rows[-1]['seconds']}s", problems or "", flush=True)
    summary = {
        "passed": passed, "total": len(rows), "rate": passed / max(len(rows), 1),
        "by_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_cat.items())},
    }
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1))
    return summary

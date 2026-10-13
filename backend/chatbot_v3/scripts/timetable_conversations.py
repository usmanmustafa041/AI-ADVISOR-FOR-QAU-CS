"""Real local-model/HTTP timetable trials; automated constraints are not human grades."""

import argparse
import json
import math
import time

import httpx

from chatbot_v3.settings import settings


def cases():
    term = {"academic_term": "Spring 2026"}
    items = []

    def add(message, expect, language=None, group=None):
        items.append(
            {
                "id": len(items) + 1,
                "message": message,
                "expected_filters": expect,
                "language": language,
                "group": group,
            }
        )

    add(
        "Show BSCS semester IV Regular Monday classes in Spring 2026.",
        term | {"programme": "BSCS", "semester": 4, "section": "regular", "weekday": "Monday"},
        group="followup",
    )
    add(
        "What about Tuesday?",
        term | {"programme": "BSCS", "semester": 4, "section": "regular", "weekday": "Tuesday"},
        group="followup",
    )
    add(
        "No, I am self support, not regular.",
        term
        | {"programme": "BSCS", "semester": 4, "section": "self support", "weekday": "Tuesday"},
        group="followup",
    )
    add("Now explain binary search briefly.", {}, group="followup")
    add(
        "Spring 2026 mein BSCS sem 1 regular ki peer ko classes?",
        term | {"programme": "BSCS", "semester": 1, "section": "regular", "weekday": "Monday"},
        "roman_urdu",
    )
    add(
        "بہار 2026 میں بی ایس سی ایس پہلے سمسٹر ریگولر کی پیر کی کلاسیں بتائیں",
        term | {"programme": "BSCS", "semester": 1, "section": "regular", "weekday": "Monday"},
        "urdu",
    )
    add(
        "How many class meetings are there on Friday in Spring 2026 across all programmes?",
        term | {"weekday": "Friday", "operation": "count_meetings"},
    )
    add(
        "Spring 2026 jumma ki online classes dikhao",
        term | {"weekday": "Friday", "mode": "online"},
        "roman_urdu",
    )
    add(
        "CS104 regular Monday Spring 2026 room and teacher?",
        term | {"course": "CS-104", "section": "regular", "weekday": "Monday"},
    )
    add(
        "CS104 self support Monday Spring 2026 room and teacher?",
        term | {"course": "CS-104", "section": "self support", "weekday": "Monday"},
    )
    add(
        "What time is CS-325 Tuesday in Spring 2026?",
        term | {"course": "CS-325", "weekday": "Tuesday"},
    )
    add(
        "CS-215 COAL Tuesday Spring 2026 timings?",
        term | {"course": "CS-215", "weekday": "Tuesday"},
    )
    add(
        "Thursday CS-211 lab Spring 2026 timings?",
        term | {"course": "CS-211", "weekday": "Thursday"},
    )
    add(
        "CS-104 regular Tuesday lab Spring 2026 schedule?",
        term | {"course": "CS-104", "section": "regular", "weekday": "Tuesday"},
    )
    add("CS-489 Project I Spring 2026 exact class time?", term | {"course": "CS-489"})
    add("CS-490 Project II Spring 2026 exact class time?", term | {"course": "CS-490"})
    add("Nadia Saeed teaching schedule Spring 2026", term | {"teacher": "Nadia Saeed"})
    add("Room 217 Tuesday schedule Spring 2026", term | {"room": "217", "weekday": "Tuesday"})
    add("CS Lab Monday schedule Spring 2026", term | {"room": "CS Lab", "weekday": "Monday"})
    add(
        "Free rooms Monday 10:05 to 10:15 in Spring 2026?",
        term
        | {
            "weekday": "Monday",
            "operation": "free_room_intervals",
            "at_time": "10:05:00",
            "until_time": "10:15:00",
        },
    )
    add(
        "Free rooms Friday 10:00 to 11:00 in Spring 2026?",
        term | {"weekday": "Friday", "operation": "free_room_intervals"},
    )
    add(
        "Which days have BSCS semester 4 regular classes in Spring 2026?",
        term
        | {
            "programme": "BSCS",
            "semester": 4,
            "section": "regular",
            "operation": "days_with_classes",
        },
    )
    add(
        "Weekly scheduled load for BSCS semester 4 regular Spring 2026?",
        term
        | {"programme": "BSCS", "semester": 4, "section": "regular", "operation": "weekly_load"},
    )
    add(
        "Compare regular and self support semester 4 Monday Spring 2026 schedules",
        term | {"semester": 4, "weekday": "Monday", "operation": "compare_sections"},
    )
    add(
        "Find room timetable clashes on Tuesday Spring 2026",
        term | {"weekday": "Tuesday", "operation": "find_conflicts"},
    )
    add(
        "MS Data Science Thursday classes Spring 2026",
        term | {"programme": "MS-DS", "weekday": "Thursday"},
    )
    add("PhD Monday classes Spring 2026", term | {"programme": "PhD", "weekday": "Monday"})
    add("PSP timetable Spring 2026", term | {"course": "PSP"})
    add(
        "BSCS semester 4 regular next class today?",
        {"programme": "BSCS", "semester": 4, "section": "regular", "operation": "next_class"},
    )
    add("Monday classes?", {"weekday": "Monday"})
    for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
        for sem in [1, 2, 3, 4, 6, 7, 8, 9]:
            for sec in ["regular", "self support"]:
                wording = (
                    f"BSCS sem {sem} {sec} {day} clasess Spring 2026 plz"
                    if (i + sem) % 2
                    else f"Show the Spring 2026 {day} schedule for BSCS semester {sem}, {sec}."
                )
                add(
                    wording,
                    term | {"programme": "BSCS", "semester": sem, "section": sec, "weekday": day},
                )
    return items


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=110)
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--output", default="timetable-live")
    args = p.parse_args()
    out = settings().data_dir / "evaluation"
    out.mkdir(exist_ok=True)
    path = out / (args.output + ".jsonl")
    groups = {}
    records = []
    with (
        httpx.Client(base_url="http://127.0.0.1:8012", timeout=240, trust_env=False) as client,
        path.open("w") as f,
    ):
        for case in cases()[args.start - 1 : args.start - 1 + args.limit]:
            body = {"message": case["message"]}
            if case.get("language"):
                body["preferred_language"] = case["language"]
            if case.get("group") in groups:
                body["conversation_id"] = groups[case["group"]]
            began = time.perf_counter()
            try:
                response = client.post("/api/v3/chat", json=body)
                if response.status_code == 429:
                    time.sleep(10)
                    response = client.post("/api/v3/chat", json=body)
                data = response.json()
                if response.is_success and case.get("group"):
                    groups[case["group"]] = data["conversation_id"]
                observed = data.get("scope", {}).get("timetable", {}).get("query", {})
                failures = [
                    f"{k}: expected {v!r}, got {observed.get(k)!r}"
                    for k, v in case["expected_filters"].items()
                    if observed.get(k) != v
                ]
                if not response.is_success:
                    failures.append(f"HTTP {response.status_code}")
                if case["id"] == 4 and data.get("mode") != "tutor":
                    failures.append("topic switch failed")
                if data.get("groundedness_status") == "structured_timetable" and not data.get(
                    "cited_sources"
                ):
                    failures.append("missing source citation")
                versions = {r["source_version_id"] for r in data.get("cited_sources", [])}
                if len(versions) > 1:
                    failures.append("mixed version citations")
                record = case | {
                    "http_status": response.status_code,
                    "elapsed_ms": round((time.perf_counter() - began) * 1000),
                    "response": data,
                    "constraint_failures": failures,
                    "human_grade": None,
                    "test_only": True,
                }
            except Exception as e:
                record = case | {
                    "error": type(e).__name__,
                    "constraint_failures": ["request error"],
                    "human_grade": None,
                    "test_only": True,
                }
            records.append(record)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            print(
                json.dumps(
                    {
                        "id": case["id"],
                        "ms": record.get("elapsed_ms"),
                        "constraint_failures": record["constraint_failures"],
                    }
                ),
                flush=True,
            )
    latency = sorted(r["elapsed_ms"] for r in records if "elapsed_ms" in r)
    report = {
        "trials": len(records),
        "http_completions": sum(r.get("http_status") == 200 for r in records),
        "automated_filter_constraint_passes": sum(not r["constraint_failures"] for r in records),
        "failed_case_ids": [r["id"] for r in records if r["constraint_failures"]],
        "p50_ms": latency[math.ceil(len(latency) * 0.5) - 1] if latency else None,
        "p95_ms": latency[math.ceil(len(latency) * 0.95) - 1] if latency else None,
        "independent_accuracy": None,
        "dataset": "AI-authored development questions; isolated synthetic publication; not held out or independently graded",
    }
    (out / (args.output + ".summary.json")).write_text(json.dumps(report, indent=2))
    lines = ["# Real timetable conversation trials", "", json.dumps(report, indent=2), ""]
    for r in records:
        lines.extend(
            [
                f"## {r['id']}. {r['message']}",
                "",
                r.get("response", {}).get("answer", r.get("error", "")),
                "",
                f"Filter constraints: {r['constraint_failures']}. Human grade: pending.",
                "",
            ]
        )
    (out / (args.output + ".md")).write_text("\n".join(lines))


if __name__ == "__main__":
    main()

"""Application-owned SQL; a model can supply typed filters, never SQL text."""

import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chatbot_v3.contracts import EvidenceReference
from chatbot_v3.timetable.contracts import TimetableQuery

ZONE = ZoneInfo("Asia/Karachi")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def norm(value):
    return re.sub(r"[^\w]", "", value or "").casefold()


def programme_matches(offering, programme):
    return (
        not programme
        or offering == programme
        or offering == "MPhil/PhD"
        and programme in {"MPhil", "PhD"}
    )


def execute(store, query: TimetableQuery, clock=None):
    clock = (clock or datetime.now(ZONE)).astimezone(ZONE)
    q = query.model_copy(deep=True)
    if q.relative_day:
        q.on_date = (clock + timedelta(days=q.relative_day == "tomorrow")).date()
    if q.on_date:
        q.weekday = DAYS[q.on_date.weekday()]
    if q.operation == "next_class" and not q.weekday:
        q.weekday = DAYS[clock.weekday()]
        q.on_date = clock.date()
    if q.operation == "next_class" and q.at_time is None:
        q.at_time = clock.timetz().replace(tzinfo=None)
    result = {
        "query": q.model_dump(mode="json"),
        "rows": [],
        "warnings": [],
        "clock": clock.isoformat(),
        "time_zone": "Asia/Karachi",
    }
    with store.connect() as c:
        term = q.academic_term
        configured = c.execute(
            "SELECT academic_term FROM tt_current_term WHERE department=? AND campus=? AND valid_from<=? AND valid_until>=?",
            (q.department, q.campus, clock.date().isoformat(), clock.date().isoformat()),
        ).fetchone()
        if (q.relative_day or q.operation == "next_class" and q.on_date == clock.date()) and (
            not configured or term and configured[0] != term
        ):
            return result | {"clarification": "term"}
        if not term and not q.version_id:
            if not configured:
                return result | {
                    "clarification": "term",
                    "available_terms": sorted(
                        {
                            json.loads(r[0])["academic_term"]
                            for r in c.execute(
                                "SELECT v.metadata FROM tt_active a JOIN tt_version v ON v.id=a.version_id"
                            )
                        }
                    ),
                }
            term = configured[0]
        if q.version_id:
            if not q.historical:
                return result | {"clarification": "historical_permission"}
            candidates = [store.version(q.version_id, c)]
            if candidates[0]["status"] not in {"published", "archived"}:
                return result | {"clarification": "unpublished"}
        else:
            candidates = [
                store.version(r[0], c) for r in c.execute("SELECT version_id FROM tt_active")
            ]
        scoped_versions = [
            v
            for v in candidates
            if all(v["metadata"][k] == getattr(q, k) for k in ("department", "campus", "kind"))
            and (not term or v["metadata"]["academic_term"] == term)
        ]
        candidates = [
            v
            for v in scoped_versions
            if not q.programme or q.programme in v["metadata"]["programmes"]
        ]
        if not candidates or q.operation == "historical_comparison" and len(candidates) != 1:
            return result | {
                "clarification": "coverage" if not candidates else "scope",
                "available_scopes": [v["metadata"] for v in candidates],
            }
        v = candidates[0]
        version_ids = [item["id"] for item in candidates]
        placeholders = ",".join("?" for _ in version_ids)
        result["versions"] = [
            {
                k: item[k]
                for k in ("id", "scope", "metadata", "filename", "sha256", "status", "pages")
            }
            for item in candidates
        ]
        result["version_snapshot"] = {item["scope"]: item["id"] for item in candidates}
        result["version"] = {
            k: v[k] for k in ("id", "metadata", "filename", "sha256", "status", "pages")
        }
        date_versions = scoped_versions if q.operation == "free_room_intervals" else candidates
        if q.on_date and any(
            q.on_date.isoformat() < item["metadata"]["effective_from"]
            or item["metadata"].get("effective_until")
            and q.on_date.isoformat() > item["metadata"]["effective_until"]
            for item in date_versions
        ):
            return result | {"clarification": "effective_date"}
        omitted = c.execute(
            f"SELECT count(*) FROM tt_meeting WHERE version_id IN ({placeholders}) AND omitted=1",
            version_ids,
        ).fetchone()[0]
        if omitted:
            result["warnings"].append(
                f"{omitted} extracted sessions were omitted during review; answers cover the remaining published meetings."
            )
        offers = [
            dict(o)
            | {"aliases": json.loads(o["aliases"]), "provenance": json.loads(o["provenance"])}
            for o in c.execute(
                f"SELECT * FROM tt_offering WHERE version_id IN ({placeholders})", version_ids
            )
        ]
        if q.section and q.semester and q.operation != "compare_sections":
            group_offers = [
                o
                for o in offers
                if o["semester"] == q.semester and programme_matches(o["programme"], q.programme)
            ]
            if group_offers and all(o["section"] == "unknown" for o in group_offers):
                return result | {"clarification": "section"}
        if q.course:
            matched = [
                o
                for o in offers
                if programme_matches(o["programme"], q.programme)
                and (q.semester is None or q.semester == o["semester"])
                and (not q.section or q.section == o["section"])
                and any(
                    norm(q.course) == norm(alias)
                    for alias in [o["code"], o["title"], *o["aliases"]]
                )
            ]
            if not matched:
                return result | {"clarification": "course", "course_candidates": []}
            codes = sorted({o["code"] for o in matched})
            if len(codes) > 1:
                return result | {"clarification": "course", "course_candidates": codes}
        else:
            codes = []
        clauses, params = [f"m.version_id IN ({placeholders})", "m.omitted=0"], version_ids[:]
        for field, value in [
            ("m.weekday", q.weekday),
            ("m.room", q.room),
            ("m.mode", q.mode),
            ("o.semester", q.semester),
        ]:
            if value is not None:
                clauses.append(field + "=?")
                params.append(value)
        if q.programme:
            clauses.append("(o.programme=? OR (o.programme='MPhil/PhD' AND ? IN ('MPhil','PhD')))")
            params.extend([q.programme, q.programme])
        if q.section and q.operation != "compare_sections":
            clauses.append("o.section=?")
            params.append(q.section)
        if codes:
            clauses.append("mc.code=?")
            params.append(codes[0])
        if q.teacher:
            # Parameterized teacher filter; literal %/_ are escaped, never SQL fragments.
            needle = q.teacher.replace("%", "\\%").replace("_", "\\_")
            clauses.append(
                "EXISTS(SELECT 1 FROM tt_teacher_assignment t WHERE t.offering_id=o.id AND t.name LIKE ? ESCAPE '\\')"
            )
            params.append("%" + needle + "%")
        sql = (
            """SELECT m.*,mc.code,mc.offering_id,o.title,o.programme,o.semester,o.section,o.provenance legend_provenance
                 FROM tt_meeting m JOIN tt_meeting_course mc ON mc.meeting_id=m.id
                 LEFT JOIN tt_offering o ON o.id=mc.offering_id WHERE """
            + " AND ".join(clauses)
            + " ORDER BY m.start_time,m.room,mc.code,o.section"
        )
        rows = [dict(r) for r in c.execute(sql, params)]
        for r in rows:
            r["provenance"] = json.loads(r["provenance"])
            r["bbox"] = json.loads(r["bbox"])
            r["legend_provenance"] = json.loads(r["legend_provenance"] or "null")
            r["teachers"] = [
                dict(t)
                for t in c.execute(
                    "SELECT name,role FROM tt_teacher_assignment WHERE offering_id=?",
                    (r["offering_id"],),
                )
            ]
        if q.operation == "next_class":
            at = q.at_time.strftime("%H:%M")
            selected = (
                [r for r in rows if r["start_time"] <= at < r["end_time"]]
                if q.ongoing
                else [r for r in rows if r["start_time"] >= at]
            )
            if selected and not q.ongoing:
                earliest = selected[0]["start_time"]
                selected = [r for r in selected if r["start_time"] == earliest]
            rows = selected
        result["rows"] = rows
        result["meeting_count"] = len({r["id"] for r in rows})
        result["course_count"] = len({r["code"] for r in rows})
        result["course_mapping_count"] = len({(r["id"], r["code"]) for r in rows})
        result["offering_mapping_count"] = len(rows)
        unique = {r["id"]: r for r in rows}
        result["minutes"] = sum(
            minutes(r["end_time"]) - minutes(r["start_time"]) for r in unique.values()
        )
        result["days"] = [d for d in DAYS if any(r["weekday"] == d for r in rows)]
        if not rows and codes:
            result["omitted_course_rows"] = [
                dict(r)
                for r in c.execute(
                    f"SELECT m.weekday,m.raw,m.page FROM tt_meeting m JOIN tt_meeting_course mc ON mc.meeting_id=m.id WHERE m.version_id IN ({placeholders}) AND m.omitted=1 AND mc.code=?",
                    [*version_ids, codes[0]],
                )
            ]
            result["legend_only"] = [
                o
                for o in offers
                if o["code"] in codes and programme_matches(o["programme"], q.programme)
            ]
        if q.operation == "free_room_intervals":
            # Availability requires complete department-wide occupancy, independent of student filters.
            if not q.weekday or not q.at_time or not q.until_time or q.until_time <= q.at_time:
                return result | {"clarification": "interval"}
            occupancy_ids = [item["id"] for item in scoped_versions]
            occupancy_slots = ",".join("?" for _ in occupancy_ids)
            result["availability_versions"] = [
                {
                    k: item[k]
                    for k in ("id", "scope", "metadata", "filename", "sha256", "status", "pages")
                }
                for item in scoped_versions
            ]
            occupancy = [
                dict(r)
                for r in c.execute(
                    f"SELECT * FROM tt_meeting WHERE version_id IN ({occupancy_slots}) AND omitted=0 AND weekday=? AND mode='physical'",
                    [*occupancy_ids, q.weekday],
                )
            ]
            rooms = sorted(
                {
                    r[0]
                    for r in c.execute(
                        f"SELECT DISTINCT room FROM tt_meeting WHERE version_id IN ({occupancy_slots}) AND mode='physical' AND omitted=0",
                        occupancy_ids,
                    )
                }
            )
            if q.room:
                rooms = [r for r in rooms if norm(r) == norm(q.room)]
            start, end = q.at_time.strftime("%H:%M"), q.until_time.strftime("%H:%M")
            result["free_rooms"] = (
                [
                    room
                    for room in rooms
                    if not any(
                        r["room"] == room and max(start, r["start_time"]) < min(end, r["end_time"])
                        for r in occupancy
                    )
                ]
                if occupancy
                else []
            )
            result["availability_basis"] = (
                "Published physical meetings only; holidays, closures and non-timetable bookings are unknown"
                if occupancy
                else "No physical occupancy coverage for this day; room freedom cannot be established"
            )
        if q.operation == "find_conflicts":
            unique_rows = list(unique.values())
            result["conflicts"] = [
                [a["id"], b["id"]]
                for i, a in enumerate(unique_rows)
                for b in unique_rows[i + 1 :]
                if a["weekday"] == b["weekday"]
                and max(a["start_time"], b["start_time"]) < min(a["end_time"], b["end_time"])
                and (
                    a["room"] == b["room"]
                    and a["mode"] == b["mode"] == "physical"
                    or q.programme
                    and q.semester
                    and q.section
                )
            ]
        if q.operation == "historical_comparison":
            if not q.historical or not q.compare_version_id:
                return result | {"clarification": "comparison_versions"}
            other = store.version(q.compare_version_id, c)
            if other["scope"] != v["scope"] or other["status"] not in {"published", "archived"}:
                return result | {"clarification": "comparison_scope"}
            result["diff"] = store.diff(c, v["id"], other["id"])
            result["comparison_version"] = {
                k: other[k] for k in ("id", "metadata", "filename", "sha256", "status", "pages")
            }
        result["warnings"].append(
            "Normally scheduled classes; holidays, cancellations and temporary room changes are not confirmed."
        )
        if not q.programme:
            result["warnings"].append(
                "All covered programmes and sections; this is not an individual student's schedule."
            )
        return result


def minutes(value):
    return int(value[:2]) * 60 + int(value[3:5])


def render(result, language="english"):
    roman, urdu = language == "roman_urdu", language == "urdu"
    if result.get("clarification"):
        code = result["clarification"]
        en = {
            "term": "Which academic term should I use? The administrator has not confirmed a current term. Spring 2026 is a historical schedule.",
            "coverage": "No published timetable covers that term and programme. An uploaded draft cannot answer student questions.",
            "scope": "Which programme timetable should I use? Separate programme schedules have distinct ownership.",
            "section": "The published legend does not identify regular/self-support ownership for this semester. I can show the unqualified semester schedule if you omit the section filter; confirm applicability with the department.",
            "course": "Please specify the course code or programme; that course name is absent or ambiguous in the selected legend.",
            "effective_date": "That date falls outside the timetable's recorded effective interval.",
            "interval": "Please provide a weekday and a start/end time for room availability.",
            "historical_permission": "Please explicitly request a historical version to use an archived timetable.",
            "unpublished": "That timetable is awaiting administrator review and has not been published.",
            "comparison_versions": "Which two published timetable versions should I compare?",
            "comparison_scope": "The compared versions must have the same timetable ownership scope.",
        }[code]
        text = (
            "Barah-e-karam academic term, programme aur zaroori filter wazeh karein. Current term admin ne confirm nahi kiya ya is scope ka published timetable dastiyab nahi. "
            if roman
            else "براہ کرم تعلیمی مدت، پروگرام اور ضروری تفصیل واضح کریں۔ موجودہ مدت کی تصدیق یا اس دائرے کا شائع شدہ ٹائم ٹیبل دستیاب نہیں۔ "
            if urdu
            else ""
        ) + en
        return text, []
    v, q = result["version"], result["query"]
    meta = v["metadata"]
    scope = " / ".join(
        str(q[k]) for k in ("programme", "semester", "section", "weekday") if q.get(k)
    ) or (
        "tamam programmes aur sections"
        if roman
        else "تمام پروگرام اور سیکشن"
        if urdu
        else "all covered programmes and sections"
    )
    intro = f"{meta['academic_term']} · {scope} · w.e.f. {meta['effective_from']} · Asia/Karachi."
    intro += (
        " Yeh published schedule hai; holidays/cancellations confirm nahi hain."
        if roman
        else " یہ شائع شدہ شیڈول ہے؛ تعطیلات یا منسوخی کی تصدیق نہیں۔"
        if urdu
        else " These are normally scheduled classes; holidays and cancellations are unconfirmed."
    )
    refs = {}
    documents = {
        item["id"]: item
        for item in result.get("versions", [v]) + result.get("availability_versions", [])
    }

    def cite(provenance, quote, version_id=None):
        document = documents[version_id or v["id"]]
        page = provenance["page"]
        key = (document["id"], page)
        if key not in refs:
            n = len(refs) + 1
            refs[key] = EvidenceReference(
                source_id="tt-" + document["id"],
                source_version_id=document["id"],
                chunk_id=f"tt-{document['id']}-p{page}",
                number=n,
                document_title=document["filename"],
                page=page,
                effective_term=meta["academic_term"],
                quote=quote,
                origin_status="admin_provided",
                review_status="approved",
                checksum=document["sha256"],
            )
        return f"[{refs[key].number}]"

    lines = [intro]
    if len(result.get("versions", [])) > 1:
        lines.append(
            "The snapshot contains one active version per separate programme ownership scope: "
            + "; ".join(
                ", ".join(doc["metadata"]["programmes"])
                + " · effective "
                + doc["metadata"]["effective_from"]
                for doc in result["versions"]
            )
        )
    if q["operation"] == "count_meetings":
        lines.append(
            f"{result['meeting_count']} alag class meetings; {result['course_count']} mukhtalif course codes; {result['course_mapping_count']} meeting/course mappings. Joint class aik martaba count hui."
            if roman
            else f"{result['meeting_count']} الگ کلاس نشستیں؛ {result['course_count']} مختلف کورس کوڈ؛ {result['course_mapping_count']} نشست/کورس روابط۔ مشترکہ نشست ایک بار شمار ہوئی۔"
            if urdu
            else f"{result['meeting_count']} distinct scheduled meetings; {result['course_count']} distinct course codes; {result['course_mapping_count']} meeting/course mappings. Co-scheduled sessions count once."
        )
    if q["operation"] == "days_with_classes":
        lines.append(", ".join(result["days"]) or "No scheduled days match.")
    if q["operation"] == "weekly_load":
        lines.append(
            f"{result['meeting_count']} meetings · {result['minutes']} scheduled minutes ({result['minutes'] / 60:g} hours)."
        )
    if q["operation"] == "free_room_intervals":
        lines.append(
            "Schedule-only free rooms: "
            + (", ".join(result["free_rooms"]) or "none established")
            + ". "
            + result["availability_basis"]
        )
    if q["operation"] == "find_conflicts":
        lines.append(
            f"{len(result['conflicts'])} overlapping meeting pairs within the stated filter; joint course mappings are counted once."
        )
    if result.get("diff"):
        lines.append(
            f"Compared with version {result['comparison_version']['id']}: {len(result['diff']['removed'])} removed and {len(result['diff']['added'])} added course mappings."
        )
    for row in sorted(
        result["rows"],
        key=lambda r: (
            DAYS.index(r["weekday"]),
            r["start_time"],
            r["room"],
            r["code"],
            r["section"] or "",
        ),
    ):
        location = "online" if row["mode"] == "online" else row["room"]
        teachers = (
            "; ".join(t["name"] + (" (TA)" if t["role"] == "TA" else "") for t in row["teachers"])
            or "instructor not printed"
        )
        label = (
            " / ".join(str(row[k]) for k in ("programme", "semester", "section") if row.get(k))
            or "ownership unresolved"
        )
        citations = "".join(
            dict.fromkeys(cite(p, row["raw"], row["version_id"]) for p in row["provenance"])
        )
        if row["legend_provenance"]:
            citations += cite(
                row["legend_provenance"],
                json.dumps(row["legend_provenance"]["raw"], ensure_ascii=False),
                row["version_id"],
            )
        lines.append(
            f"- {row['weekday']} {row['start_time']}–{row['end_time']} · {row['code']} {row['title'] or ''} · {label} · {location} · {teachers} {citations}"
        )
    if not result["rows"]:
        lines.append(
            "Is filter ka koi scheduled meeting nahi mila."
            if roman
            else "اس دائرے میں کوئی طے شدہ نشست نہیں ملی۔"
            if urdu
            else "No scheduled meeting matches this filter."
        )
        for o in result.get("legend_only", []):
            lines.append(
                f"{o['code']} {o['title']}: "
                + (
                    "grid entries were omitted during review; their section/time has not been confirmed. "
                    if result.get("omitted_course_rows")
                    else "listed in the legend; no meeting time is shown. "
                )
                + cite(
                    o["provenance"],
                    json.dumps(o["provenance"]["raw"], ensure_ascii=False),
                    o["version_id"],
                )
            )
    # Aggregate/negative claims also point to all grid pages, not only one selected row.
    if not refs or q["operation"] in {"free_room_intervals", "historical_comparison"}:
        labels = []
        for document in documents.values():
            for page in range(1, document["pages"] + 1):
                labels.append(
                    cite(
                        {"page": page},
                        "Published timetable and legend; inspect the complete page",
                        document["id"],
                    )
                )
        lines.append("Source pages: " + "".join(labels))
    return "\n\n".join(lines), list(refs.values())

"""Digital grid/legend extraction. Uncertain geometry stays a blocking review issue.

Time columns are discovered from headers, not a fixed page size or row count.
PDF text is treated solely as data; parsing runs in a bounded subprocess.
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber

CODE = re.compile(r"\b(?:CSC|DSC|CS|DS|FQ|EN|IS|GEN|PH|MA|SW)\s*-?\s*\d{3}\b")
TIME = re.compile(r"(\d{1,2})[:.](\d{2})\s*-\s*(\d{1,2})[:.]\s*(\d{2})")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}


def compact(text):
    return re.sub(r"\s+", " ", text or "").strip()


def canonical(code):
    return re.sub(r"\s+", "", code).upper()


def times(text):
    match = TIME.search(text.replace("\n", ""))
    if not match:
        return None
    h, m, eh, em = map(int, match.groups())
    if h > 23 or eh > 23 or m > 59 or em > 59:
        return None
    return f"{h:02}:{m:02}", f"{eh:02}:{em:02}"


def section(text):
    if re.search(r"\bR\s*\+\s*S\b", text):
        return "combined"
    if re.search(r"\bS\b", text):
        return "self support"
    if re.search(r"\bR\b", text):
        return "regular"
    return "unknown"


def extract(path):
    meetings, offerings, issues, coverage = [], [], [], []
    header_columns, group, last_day, last_room = [], None, None, None
    title = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if len(words) > 50000 or page.width * page.height > 12_000_000:
                raise ValueError("PDF exceeds layout bounds")
            title = title or (page.extract_text() or "").split("\n")[0]
            page_count, grid_count, legend_count = 0, 0, 0
            for table in page.find_tables():
                rows = table.extract()
                is_legend = len(table.columns) == 3 and (
                    any("Faculty" in str(r) for r in rows[:2]) or (group and table.bbox[1] < 50)
                )
                if is_legend:
                    for row, geometry in zip(rows, table.rows, strict=True):
                        raw_code, course_title, faculty = (row + [None] * 3)[:3]
                        raw_code = compact(raw_code)
                        if not raw_code or raw_code == "Course Code":
                            continue
                        if not CODE.search(raw_code):
                            if "Semester" in raw_code:
                                num = re.search(r"Semester\s+(\w+)", raw_code)
                                token = num[1] if num else ""
                                group = {
                                    "programme": "BSCS",
                                    "semester": ROMAN.get(
                                        token, int(token) if token.isdigit() else None
                                    ),
                                    "section": "self support"
                                    if "Self" in raw_code
                                    else "regular"
                                    if "Regular" in raw_code
                                    else "unknown",
                                }
                            elif "MPhil" in raw_code:
                                group = {
                                    "programme": "MPhil/PhD",
                                    "semester": None,
                                    "section": "unknown",
                                }
                            elif "MS-DS" in raw_code:
                                group = {
                                    "programme": "MS-DS",
                                    "semester": None,
                                    "section": "unknown",
                                }
                            elif "Deficiency" in raw_code:
                                group = {
                                    "programme": "deficiency",
                                    "semester": None,
                                    "section": "unknown",
                                }
                            continue
                        if group is None:
                            issues.append({"kind": "legend_group", "detail": raw_code})
                            continue
                        sec = section(raw_code)
                        code = canonical(CODE.search(raw_code)[0])
                        aliases = [compact(CODE.sub("", raw_code)).strip()]
                        aliases = [re.sub(r"\s+[RS]$", "", a) for a in aliases if a]
                        full_title = re.sub(r"\s+\d+(?:\+\d+)?$", "", compact(course_title))
                        offerings.append(
                            {
                                **group,
                                "section": sec if sec != "unknown" else group["section"],
                                "code": code,
                                "title": full_title,
                                "aliases": aliases,
                                "faculty": compact(faculty),
                                "page": page.page_number,
                                "bbox": list(geometry.bbox),
                                "raw": row,
                            }
                        )
                        legend_count += 1
                    continue
                # Discover time headers and their exact horizontal cell bounds.
                for row, geometry in zip(rows, table.rows, strict=True):
                    discovered = [
                        (cell[0], cell[2], times(text or ""))
                        for text, cell in zip(row, geometry.cells, strict=True)
                        if cell and times(text or "") and not CODE.search(text or "")
                    ]
                    if len(discovered) >= 3:
                        header_columns = discovered
                        break
                if not header_columns:
                    if any(CODE.search(str(r)) for r in rows):
                        issues.append(
                            {
                                "kind": "unsupported_layout",
                                "detail": f"Page {page.page_number}: no time header or usable continuation",
                            }
                        )
                    continue
                seen_cells = set()
                for row, geometry in zip(rows, table.rows, strict=True):
                    row_text = compact(" ".join(t or "" for t in row))
                    day = next((d for d in DAYS if d.upper() in row_text.upper()), None)
                    if day:
                        last_day = day
                    # Room column is immediately left of the discovered time grid.
                    room_candidates = [
                        compact(text)
                        for text, cell in zip(row, geometry.cells, strict=True)
                        if cell
                        and cell[2] <= header_columns[0][0] + 1
                        and cell[0] > table.bbox[0] + 10
                        and compact(text) not in {"", "Room", "#"}
                    ]
                    if room_candidates:
                        last_room = room_candidates[-1]
                    for text, cell in zip(row, geometry.cells, strict=True):
                        if not cell or cell in seen_cells or cell[0] < header_columns[0][0] - 1:
                            continue
                        seen_cells.add(cell)
                        codes = list(CODE.finditer(text or ""))
                        if not codes:
                            # A time-only cell at the top of the next page may finish a lab.
                            if (
                                meetings
                                and times(text or "")
                                and page.page_number > meetings[-1]["page"]
                                and geometry.bbox[1] < 60
                            ):
                                previous = [
                                    m
                                    for m in meetings
                                    if abs(m["bbox"][0] - cell[0]) < 5
                                    and m["page"] == page.page_number - 1
                                ]
                                if previous:
                                    m = previous[-1]
                                    m["start_time"], m["end_time"] = times(text)
                                    m["time_source"] = "printed_override"
                                    m["provenance"].append(
                                        {"page": page.page_number, "bbox": list(cell), "raw": text}
                                    )
                                    m["flags"].append("cross_page_time")
                            continue
                        if not last_day or not last_room:
                            issues.append(
                                {"kind": "grid_scope", "detail": f"Page {page.page_number}: {text}"}
                            )
                            continue
                        # Multiple distinct adjacent courses inside a borderless merged cell:
                        # split at the next code's x-coordinate; vertically stacked joint codes stay one event.
                        code_words = [
                            w
                            for w in words
                            if w["x0"] >= cell[0] - 1
                            and w["x1"] <= cell[2] + 1
                            and w["top"] >= cell[1] - 1
                            and w["bottom"] <= cell[3] + 1
                            and CODE.fullmatch(w["text"])
                        ]
                        horizontal = (
                            len(code_words) > 1
                            and len({round(w["x0"] / 10) for w in code_words}) > 1
                            and max(w["top"] for w in code_words)
                            - min(w["top"] for w in code_words)
                            < 5
                        )
                        parts = []
                        if horizontal:
                            sorted_words = sorted(code_words, key=lambda w: w["x0"])
                            for k, word in enumerate(sorted_words):
                                x0 = max(x for x, _, _ in header_columns if x <= word["x0"] + 2)
                                x1 = (
                                    max(
                                        x
                                        for x, _, _ in header_columns
                                        if x <= sorted_words[k + 1]["x0"] + 2
                                    )
                                    if k + 1 < len(sorted_words)
                                    else cell[2]
                                )
                                box = (x0, cell[1], x1, cell[3])
                                parts.append((page.crop(box).extract_text() or "", box))
                        else:
                            parts = [(text, cell)]
                        for raw, box in parts:
                            matched = list(dict.fromkeys(canonical(c) for c in CODE.findall(raw)))
                            columns = [
                                t
                                for x0, x1, t in header_columns
                                if x0 < box[2] - 2 and x1 > box[0] + 2
                            ]
                            if not matched or not columns:
                                issues.append(
                                    {
                                        "kind": "cell_parse",
                                        "detail": f"Page {page.page_number}: {raw}",
                                    }
                                )
                                continue
                            override = times(raw)
                            start, end = override or (columns[0][0], columns[-1][1])
                            flags = (["printed_time_override"] if override else []) + (
                                ["split_borderless_cell"] if horizontal else []
                            )
                            meetings.append(
                                {
                                    "weekday": last_day,
                                    "start_time": start,
                                    "end_time": end,
                                    "room": last_room,
                                    "mode": "online"
                                    if "online" in row_text.lower()
                                    or (
                                        day is None
                                        and last_day == "Friday"
                                        and any("online" in str(r).lower() for r in rows)
                                    )
                                    else "physical",
                                    "class_kind": "lab"
                                    if "lab" in (last_room + " " + raw).lower()
                                    else "lecture",
                                    "page": page.page_number,
                                    "bbox": list(box),
                                    "raw": raw,
                                    "codes": matched,
                                    "section": section(raw),
                                    "confidence": 0.85,
                                    "time_source": "printed_override" if override else "grid",
                                    "flags": flags,
                                    "provenance": [
                                        {"page": page.page_number, "bbox": list(box), "raw": raw}
                                    ],
                                }
                            )
                            page_count += len(matched)
                            grid_count += 1
            coverage.append(
                {
                    "page": page.page_number,
                    "grid_cells": grid_count,
                    "course_mappings": page_count,
                    "legend_rows": legend_count,
                    "word_count": len(words),
                }
            )
            if not words:
                issues.append(
                    {
                        "kind": "ocr_required",
                        "detail": f"Page {page.page_number} has no digital text; scanned data was not silently omitted",
                    }
                )
    # Adjacent identical labels are provisional extended sessions, retained as a review flag.
    merged = []
    for m in meetings:
        previous = next(
            (
                p
                for p in reversed(merged)
                if p["weekday"] == m["weekday"]
                and p["room"] == m["room"]
                and p["codes"] == m["codes"]
                and p["section"] == m["section"]
                and p["page"] == m["page"]
                and abs(p["bbox"][2] - m["bbox"][0]) < 3
            ),
            None,
        )
        if previous:
            previous["end_time"] = max(previous["end_time"], m["end_time"])
            previous["provenance"].extend(m["provenance"])
            previous["bbox"][2] = m["bbox"][2]
            previous["raw"] += " | " + m["raw"]
            previous["flags"].append("adjacent_repeat_merge")
        else:
            merged.append(m)
    for m in merged:
        m["links"] = []
        for code in m["codes"]:
            candidates = [
                i
                for i, o in enumerate(offerings)
                if o["code"] == code
                and (
                    m["section"] in {"unknown", "combined"}
                    or o["section"] in {m["section"], "unknown"}
                )
            ]
            # R+S explicitly authorizes both offerings; other multiple ownership remains unresolved.
            if len(candidates) == 1 or (m["section"] == "combined" and candidates):
                m["links"].extend({"code": code, "offering": i} for i in candidates)
            else:
                m["links"].append({"code": code, "offering": None})
                m["flags"].append("ambiguous_ownership" if candidates else "missing_legend")
        if len(m["codes"]) > 1:
            m["flags"].append("co_scheduled_mapping")
    return {
        "parser": "digital-grid-1",
        "title": title,
        "pages": len(coverage),
        "coverage": coverage,
        "offerings": offerings,
        "meetings": merged,
        "issues": issues,
    }


if __name__ == "__main__":
    # Keep decoder crashes/expansion/time limits away from the API process.
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    result = extract(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False))

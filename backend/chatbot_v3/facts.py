"""Typed views of original evidence. These classify source fields, never student intent."""

import re


def normalized(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def field_section(text, heading, endings):
    match = re.search(r"(?:^|\n)" + heading + r"\s*\n", text, re.I)
    if not match:
        return ""
    body = text[match.end() :]
    end = re.search(r"(?:^|\n)(?:" + "|".join(endings) + r")\b", body, re.I)
    return body[: end.start()].strip() if end else body.strip()


def faculty_view(chunk, task):
    # A directory or lab member list cannot establish each member's research interests.
    if "/faculty/" not in chunk["uri"] or " - Faculty Profile" not in chunk["title"]:
        return None
    name = chunk["title"].split(" - Faculty Profile")[0]
    content = chunk["content"]
    interests = field_section(
        content,
        "Research Interests",
        ["Education", "Scholarly Profiles", "Courses Taught", "Publications", "Activities"],
    )
    publications = field_section(
        content, r"Publications\s*\(?", ["Activities", "Supervised Students"]
    )
    contacts = list(dict.fromkeys(re.findall(r"[\w.+-]+@[\w.-]+\.\w+|\+92[\d() -]{8,22}", content)))
    kind = task.evidence_type or "research_interests"
    if task.person_names and not any(normalized(n) in normalized(name) for n in task.person_names):
        return None
    if kind in {"research_interests", "faculty_contacts"}:
        if not interests and not (kind == "faculty_contacts" and contacts and task.person_names):
            return None
        if task.research_area:
            area = normalized(task.research_area)
            haystack = normalized(interests.replace("(re)", ""))
            # Acronyms must be explicitly present in the source or expanded by interpretation.
            if area not in haystack and not all(w in haystack.split() for w in area.split()):
                return None
        body = name + "\nResearch Interests\n" + interests
        if contacts:
            body += "\nPublished contacts\n" + "\n".join(contacts)
        types = ["research_interests", "faculty_contacts"]
    elif kind == "publications":
        if not publications:
            return None
        body, types = name + "\nPublications\n" + publications, ["publications"]
    else:
        return chunk
    return {**chunk, "content": body, "evidence_types": types, "published_name": name}


def typed_view(chunk, task):
    if task.topic == "procedures":
        return procedure_view(chunk, task)
    if task.evidence_type == "teaching_assignment" and chunk["topic"] != "timetable":
        return None
    if task.topic == "admissions" and task.evidence_type in {
        "admission_eligibility",
        "admission_test",
    }:
        headers = {
            "BSCS": r"BS \(Computer Science\)",
            "MPhil": r"MPhil \(Computer Science\)",
            "PhD": r"PhD \(Computer Science\)",
            "MS-DS": r"MS \(Data Science\)",
            "MS-IST": r"MS \(Information Science & Technology\)",
        }
        # The official admissions page contains several degrees. Keep their printed sections separate.
        if task.programme and "/admissions" in chunk["uri"] and "cs.qau.edu.pk" in chunk["uri"]:
            starts = list(
                re.finditer(
                    r"(?:^|\n)(?:" + "|".join(headers.values()) + r")\s*\n", chunk["content"]
                )
            )
            pieces = []
            for number, match in enumerate(starts):
                if re.fullmatch(headers[task.programme], match.group().strip()):
                    end = (
                        starts[number + 1].start()
                        if number + 1 < len(starts)
                        else len(chunk["content"])
                    )
                    pieces.append(chunk["content"][match.start() : end].strip())
            if not pieces:
                return None
            return {
                **chunk,
                "programme": task.programme,
                "content": "\n\n".join(pieces),
                "evidence_types": ["admission_eligibility", "admission_test"],
            }
        # This publication-only tool has no permission to certify personal eligibility or apply rules.
        return None
    if task.topic in {"faculty", "research"}:
        return faculty_view(chunk, task)
    types = {
        "curriculum": ["course_credits", "semester_courses", "scheme_overview", "degree_totals"],
        "timetable": ["teaching_assignment", "academic_dates"],
        "exam_schedule": ["academic_dates"],
        "academic_policy": ["policy"],
        "registration": ["policy", "prerequisite"],
        "admissions": ["admission_eligibility", "admission_test", "academic_dates"],
        "programme": ["programme_overview", "admission_eligibility", "admission_test"],
        "fees": ["fees"],
        "services": ["fees", "programme_overview"],
    }.get(chunk["topic"], [])
    if task.evidence_type == "prerequisite":
        # Only a separately extracted, reviewed prerequisite rule can establish the relation.
        # An ordinary curriculum table is intentionally absent even when both codes occur.
        if not chunk.get("prerequisite_rules"):
            return None
        types = ["prerequisite"]
    if task.evidence_type == "teaching_assignment" and chunk["topic"] != "timetable":
        return None
    if task.topic == "admissions" and task.programme == "BSCS":
        lateral = "lateral" in (chunk["title"] + " " + chunk["uri"]).lower()
        if task.entry_route == "regular" and lateral:
            return None
        if task.entry_route == "lateral" and not lateral:
            return None
    if task.evidence_type == "course_credits" and task.course_codes:
        wanted = {re.sub(r"[^A-Z0-9]", "", code.upper()) for code in task.course_codes}
        lines = [
            line
            for line in chunk["content"].splitlines()
            if any(
                re.sub(r"[^A-Z0-9]", "", code.upper()) in wanted
                for code in re.findall(r"\b[A-Za-z]{2,4}-?\d{3}\b", line)
            )
        ]
        if not lines:
            return None
        return {**chunk, "content": "\n".join(lines), "evidence_types": ["course_credits"]}
    return {**chunk, "evidence_types": types}


def procedure_view(chunk, task):
    """Published workflows and navigation; a resource title is not an instruction."""
    if task.audience == "main_campus" and re.search(
        r"\bICT\b|affiliated.colleges|college principal", chunk["title"] + " " + chunk["uri"], re.I
    ):
        return None
    # Legacy master's documents sometimes have no recognized programme metadata.
    # Missing metadata must not make their instructions applicable to every degree.
    title = chunk["title"]
    if task.programme and re.search(r"\b(?:M\.?Sc|MBA|MPA)\b", title, re.I):
        return None
    content = chunk["content"]
    resources = chunk.get("resources", [])
    if task.evidence_type == "resource":
        if "/course/" in chunk["uri"]:
            return None
        from chatbot_v3.resources import public_resource_url

        own = public_resource_url(chunk["uri"])
        links = ([{"title": chunk["title"], "url": own}] if own else []) + resources
        if not links:
            return None
        return {
            **chunk,
            "content": "Published resource: "
            + chunk["title"]
            + "\n"
            + (chunk["section"] or "")
            + "\n"
            + "\n".join(r["title"] for r in resources),
            "resources": links,
            "evidence_types": ["resource"],
        }
    if "/download/" in chunk["uri"] and re.fullmatch(
        re.escape(chunk["title"].split(" – QAU")[0]) + r"(?:\s*Download)?", content.strip(), re.I
    ):
        return procedure_view(chunk, task.model_copy(update={"evidence_type": "resource"}))
    if "/course/" in chunk["uri"]:
        # Course outcomes establish deliverables, not an administrative submission process.
        if task.evidence_type == "service_contact":
            return None
        # Remove prerequisite/navigation material from this tool's evidence entirely.
        body = re.split(r"(?:^|\n)Prerequisites\b", content, flags=re.I)[0]
        body = re.split(r"(?:^|\n)Back to Course Catalog\b", body, flags=re.I)[0].strip()
        if not body or re.fullmatch(r"Overview\s*Prerequisites", body, re.I):
            return None
        return {**chunk, "content": body, "resources": [], "evidence_types": ["course_description"]}
    if chunk["topic"] == "programme":
        if " | " in content or task.evidence_type == "service_contact":
            return None
        # Degree descriptions cannot establish submission instructions. Their actual
        # linked handbooks can still be discovered, without promoting unreviewed rules.
        return (
            procedure_view(chunk, task.model_copy(update={"evidence_type": "resource"}))
            if resources
            else None
        )
    if task.evidence_type == "service_contact":
        if chunk["topic"] != "services" or not re.search(
            r"[\w.+-]+@[\w.-]+\.\w+|\+92[\d() -]{8,22}|(?:Office|Address):\s*\n?\S+", content, re.I
        ):
            return None
        return {**chunk, "evidence_types": ["service_contact"]}
    if chunk["topic"] in {
        "academic_policy",
        "registration",
        "fees",
        "admissions",
        "exam_schedule",
        "timetable",
    }:
        if chunk["review_status"] != "approved":
            return None
    if re.search(
        r"milestones|calendar|academic dates|timetable|datesheet|rules.*regulations",
        chunk.get("section") or "",
        re.I,
    ):
        # Public navigation can point to these documents, but never promote their rules/dates.
        return None
    if chunk["topic"] == "services":
        contact = procedure_view(
            chunk, task.model_copy(update={"evidence_type": "service_contact"})
        )
        if contact:
            return contact
    # A download catalogue lists assets, not steps. Require substantive printed
    # instructions before assigning the procedure capability to a passage.
    if len(content.split()) >= 12 and re.search(
        r"\b(?:submit|send|attach|complete|fill|obtain|provide|apply|return)\b.{8,}[.!:]",
        content,
        re.I,
    ):
        return {**chunk, "evidence_types": ["procedure"]}
    if resources:
        return procedure_view(chunk, task.model_copy(update={"evidence_type": "resource"}))
    return None


def resolve_entities(index, plan):
    """Resolve a code only when the observed catalogue provides one unique matching identity."""
    changes = []
    for task in plan.tasks:
        resolved = []
        for code in task.course_codes:
            candidates = index.course_candidates(task.model_copy(update={"course_codes": [code]}))
            compact = re.sub(r"[^A-Z0-9]", "", code.upper())
            exact = [c for c in candidates if re.sub(r"[^A-Z0-9]", "", c["code"]) == compact]
            match = exact[0] if len(exact) == 1 else candidates[0] if len(candidates) == 1 else None
            if match:
                canonical = match["code"]
                prefix = re.sub(r"[^A-Z]", "", code.upper())
                if not re.sub(r"[^A-Z]", "", canonical).startswith(prefix):
                    resolved.append(code)
                    continue
                if canonical != code:
                    changes.append(
                        {"input": code, "canonical": canonical, "catalogue_title": match["title"]}
                    )
                    task.search_query = task.search_query.replace(code, canonical)
                resolved.append(canonical)
            else:
                resolved.append(code)
        task.course_codes = resolved
    plan.course_codes = list(dict.fromkeys(c for t in plan.tasks for c in t.course_codes))
    return changes

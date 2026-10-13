# Prerequisite intelligence

Questions like *"I haven't passed PSP — can I take DSA?"* need multi-step reasoning
(PSP → OOP → Data Structures). Language models, especially small local ones, get chains wrong, so the
chain is **calculated by code** (`backend/advisor/prereq/`) and the model only phrases the result.

## Sources and trust

| Source | What it gives | Covers |
|---|---|---|
| `advisor/prereq/data/bscs_approved_list_2021.json` (+ the original `.docx` next to it) | The department's *approved prerequisite list*, Aug 2021 — 19 prerequisite rows, 59 courses | BSCS Fall 2015 and Fall 2021 schemes (old `CS-xxx` codes) |
| Website course pages | The "Prerequisites" line of each page (31 courses) | Current (`CSC-xxx`) courses |

Every JSON row carries its `source_quote`. On each index build `advisor/prereq/verify.py` checks that
each quote appears **verbatim in the original document**, that codes exist, that nothing is its own
prerequisite and that there are no cycles. A file with errors is rejected (the build continues without it).

## What the assistant now does

* resolves student shorthand (`PSP, OOP, DSA, ADSS, SC, FYP1, FYP-II, HCI, COAL …`), course codes
  (`CS-211 ≡ CSC-211`) and titles (also typos such as "Complier Construction");
* answers **direct prerequisites**, the **full chain** (branches shown as `[A; B — in any order]`),
  **what a course unlocks** (direct and indirect, numbered), and **relationships between named courses**
  ("PSP must be passed before DS (indirectly): PSP → OOP → DS");
* says "none listed" for courses the sources are silent about — *never* "none exist";
* refuses to agree with prerequisites that are not in the sources ("FYP1 needs ADSS, right?" → not listed);
* when **sources disagree** (e.g. Net Centric Programming: approved list says Software Construction, the
  website says Computer Communications & Networks) it gives each source's rule separately. Code appends
  a "⚠️ The sources differ" notice and any list items the model omitted, so these guarantees do not
  depend on how well the language model behaves.

## Adding other schemes (2023 / 2025 / 2026) or corrections

1. Give ChatGPT the scheme document plus the extraction prompt in `docs/prerequisite_extraction_prompt.txt`.
2. Admin → Knowledge → **Prerequisite data** → upload the JSON (each row is validated).
3. Press **Rebuild only**. The *places where sources disagree* list shows exactly what staff should confirm.
4. Best practice: also keep the original document next to the JSON (same file name, `.docx`) in
   `advisor/prereq/data/` so quotes are verified against it.

## Known gaps (as of this data)

* The approved list has **no prerequisites for Project-I / Project-II**; the website says Project-II needs
  Project-I. Rules such as "FYP-I needs ADSS" or "FYP-II needs SC" are **not in any supplied document**, so
  the assistant will not state them. Supply the scheme document that contains them to add them.
* `CSC-104` is the code of Problem Solving and Programming on the timetable and in current schemes;
  `CSC-105` / `CS-105` appear only in prerequisite lines. They are treated as one course with `CSC-104` as
  the main code (`EQUIVALENT_CODES` in `graph.py`) — confirmed by the department.
* Timetable section letters: `R` = Regular (morning) programme, `S` = Self-support (evening) programme.
* Credit-hour limits, grade requirements and instructor consent are not modelled.

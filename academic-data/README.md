# QAU CS Academic Advisor — Academic Data

This directory is the authoritative input area for the academic-advisor system.
Only verified QAU or QAU Computer Science Department material should be placed
here. The chatbot must not treat generated text, informal notes, or assumptions
as academic facts.

## Step 1 status

**Status: Partially complete (official public and department web/PDF sources
archived on 11 August 2026; Fall 2026 operational data and department-only
records still required).**

The root document
`../QAU_CS_Academic_Advisor_Phase1_Official_Data_Pack.docx` contains the public
source research verified on 11 August 2026. It is a compiled research pack, not
an official QAU regulation. Original official documents should be stored in the
appropriate folders below when obtained.

The latest collection includes BSCS schemes for Fall 2021, Fall 2023, and Fall
2025; Spring 2026 semester schedule and timetable; Spring 2025 terminal exam
datesheet; MPhil and PhD regulations; MS-IST material; admission-test PDFs; and
official fee-page snapshots. Every item is registered in
`source-registry/source_inventory.csv` with its official URL and local path.

## Folder ownership

- `bs/`: BSCS curriculum schemes and BS regulations.
- `ms/`: MS IST and MS Data Science curricula and regulations.
- `mphil/`: MPhil CS curriculum, examination rules, and programme material.
- `phd/`: PhD CS curriculum, procedures, and coursework rules.
- `fees/`: versioned official fee circulars and fee structures.
- `timetable/`: current class and lab timetables, organized by semester.
- `exam-schedules/`: official date sheets, organized by semester.
- `registration/`: registration, add/drop, swap, and semester schedules.
- `thesis/`: thesis/project guidelines, forms, and departmental SOPs.
- `university-policies/`: university-wide academic and examination regulations.
- `course-outlines/`: official course descriptions and course files.
- `source-registry/`: inventories and verification metadata.

## Required metadata

Every collected item must be entered in `source-registry/source_inventory.csv`.
Time-sensitive items such as fees, deadlines, timetables, and date sheets must
include an effective semester/date and must not be reused as current data after
expiry without re-verification.

## Completion rule

Step 1 is complete only when all critical rows in
`source-registry/step1_checklist.csv` have status `verified`, or when a missing
dataset is explicitly approved as out of scope by the supervisor. In particular,
the personalized prerequisite and timetable features cannot be declared ready
until the department provides the prerequisite matrix and current timetables.

## File naming

Use stable, descriptive names:

`<program>_<document-type>_<effective-term-or-date>.<extension>`

Examples:

- `bscs_scheme_fall-2025.pdf`
- `bscs_prerequisites_fall-2026.csv`
- `cs_class-timetable_fall-2026.xlsx`
- `qau_bs_fee-structure_fall-2025.pdf`

Do not overwrite an older policy or schedule. Add a new version and update the
inventory instead.

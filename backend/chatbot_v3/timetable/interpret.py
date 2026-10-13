"""Small, flat local-model contract for schedule filters and follow-ups."""

import json

from chatbot_v3.timetable.contracts import TimetableQuery

PROMPT = """Extract timetable filters from the student's exact message. Return JSON only.
The recent conversation and timetable_state resolve follow-ups. Explicit corrections win.
Set unspecified fields to null/default; do not invent dates, instructors, course codes or facts.
Programme: BSCS, MPhil, PhD, MS-DS, MS-IST, deficiency. Roman semester IV = 4.
department defaults to CS; campus defaults to QAU. PSP is a course alias, never a department.
R = regular; S = self support. Keep section=null when neither is specified.
Weekdays: peer=Monday, mangal=Tuesday, budh=Wednesday, jumerat=Thursday, jumma=Friday.
academic_term is an explicit operational term, e.g. Spring 2026. Admission batch is not a term.
Ordinary list questions use list_classes; 'how many/kitni' uses count_meetings.
Which weekdays/days have classes => days_with_classes.
Weekly scheduled load/hours/minutes => weekly_load.
Compare regular vs self support schedules => compare_sections, section=null.
Find clashes/overlapping classes => find_conflicts (NOT free_room_intervals).
Free/empty/available rooms => free_room_intervals.
Teacher schedules use teacher_schedule; course schedules use course_schedule.
'next class/agli class' uses next_class, relative_day=today. 'ongoing/abhi' also ongoing=true.
Free room needs weekday, at_time and until_time. Unknown current term remains null.
Clock values are supplied by the application; never guess the date.
mode=null unless ONLINE or PHYSICAL is explicitly requested; room numbers never establish mode.
CS Lab and BS Lab are ROOM labels, not course names. Preserve room='CS Lab' or room='BS Lab'.
Time fields use local 24-hour HH:MM, without a timezone suffix.
Current teacher questions use teacher_schedule or course_schedule with the requested course.
Do not convert unqualified courses to unrelated CSC aliases. CS104 -> CS-104 is formatting only.
For 'what about Tuesday?' inherit programme/semester/section/term and change weekday.
For 'no, regular not self support' inherit previous query and replace section=regular.
Topic switches outside timetable do not inherit timetable filters.
"""


async def interpret(model, request, history, state, plan):
    schema = TimetableQuery.model_json_schema()
    schema["required"] = list(schema["properties"])
    examples = [
        (
            "Show BSCS semester IV Regular Monday classes in Spring 2026.",
            dict(
                academic_term="Spring 2026",
                programme="BSCS",
                semester=4,
                section="regular",
                weekday="Monday",
            ),
        ),
        (
            "Spring 2026 mein jumma ki kitni classes hain?",
            dict(operation="count_meetings", academic_term="Spring 2026", weekday="Friday"),
        ),
        (
            "Where is CS104 regular on Monday in Spring 2026?",
            dict(
                operation="course_schedule",
                academic_term="Spring 2026",
                course="CS-104",
                section="regular",
                weekday="Monday",
            ),
        ),
        ("Which weekdays do I attend classes?", {"operation": "days_with_classes"}),
        ("How many hours of classes each week?", {"operation": "weekly_load"}),
        ("Does this schedule have overlapping classes?", {"operation": "find_conflicts"}),
        (
            "Show both regular and self support schedules side by side",
            {"operation": "compare_sections"},
        ),
    ]
    examples.extend(
        [
            ("Show the BS Lab schedule", {"operation": "room_schedule", "room": "BS Lab"}),
            ("When is PSP scheduled?", {"operation": "course_schedule", "course": "PSP"}),
        ]
    )
    messages = [{"role": "system", "content": PROMPT}]
    for text, fields in examples:
        messages.extend(
            [
                {"role": "user", "content": json.dumps({"message": text})},
                {"role": "assistant", "content": TimetableQuery(**fields).model_dump_json()},
            ]
        )
    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {
                    "message": request.message,
                    "history": history[-8:],
                    "timetable_state": state.get("timetable"),
                    "student_context": request.student_context.model_dump()
                    if request.student_context
                    else None,
                },
                ensure_ascii=False,
            ),
        }
    )
    output = await model.structured(messages, schema)
    return TimetableQuery.model_validate(output)

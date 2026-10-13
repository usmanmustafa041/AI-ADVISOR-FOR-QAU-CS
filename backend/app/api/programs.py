"""
Programs and study plan endpoints.
Provides BSCS study plan based on official QAU CS scheme.
"""

from fastapi import APIRouter

router = APIRouter(tags=["programs"])

# Official BSCS Study Plan (Fall 2025 Scheme)
BSCS_STUDY_PLAN = {
    "program_code": "BSCS",
    "program_name": "Bachelor of Science in Computer Science",
    "scheme": "Fall 2025 onward",
    "total_credit_hours": 133,
    "normal_duration": "8 semesters",
    "maximum_duration": "12 semesters",
    "semesters": [
        {
            "semester": 1,
            "credit_hours": 17,
            "courses": [
                {"code": "CS-101", "title": "Introduction to Computing", "total_credit_hours": 3},
                {"code": "CS-102", "title": "Programming Fundamentals", "total_credit_hours": 4},
                {"code": "MA-101", "title": "Calculus and Analytical Geometry", "total_credit_hours": 3},
                {"code": "ENG-101", "title": "Functional English", "total_credit_hours": 3},
                {"code": "ISL-101", "title": "Islamic Studies", "total_credit_hours": 2},
                {"code": "PS-101", "title": "Pakistan Studies", "total_credit_hours": 2}
            ]
        },
        {
            "semester": 2,
            "credit_hours": 17,
            "courses": [
                {"code": "CS-211", "title": "Data Structures", "total_credit_hours": 4},
                {"code": "CS-214", "title": "Discrete Structures", "total_credit_hours": 3},
                {"code": "CS-215", "title": "Computer Organization and Assembly Language", "total_credit_hours": 4},
                {"code": "MA-102", "title": "Linear Algebra", "total_credit_hours": 3},
                {"code": "ENG-102", "title": "Communication and Presentation Skills", "total_credit_hours": 3}
            ]
        },
        {
            "semester": 3,
            "credit_hours": 16,
            "courses": [
                {"code": "CS-221", "title": "Object Oriented Programming", "total_credit_hours": 4},
                {"code": "CS-224", "title": "Database Systems", "total_credit_hours": 4},
                {"code": "CS-226", "title": "Analysis and Design of Software Systems", "total_credit_hours": 3},
                {"code": "MA-104", "title": "Probability and Statistics", "total_credit_hours": 3},
                {"code": "SW-100", "title": "Civics and Community Engagement", "total_credit_hours": 2}
            ]
        },
        {
            "semester": 4,
            "credit_hours": 17,
            "courses": [
                {"code": "CS-311", "title": "Operating Systems", "total_credit_hours": 4},
                {"code": "CS-312", "title": "Computer Communications and Networks", "total_credit_hours": 4},
                {"code": "CS-313", "title": "Computer Architecture", "total_credit_hours": 3},
                {"code": "CS-331", "title": "Theory of Automata", "total_credit_hours": 3},
                {"code": "HUM-XXX", "title": "Humanities Elective", "total_credit_hours": 3}
            ]
        },
        {
            "semester": 5,
            "credit_hours": 16,
            "courses": [
                {"code": "CS-321", "title": "Design and Analysis of Algorithms", "total_credit_hours": 3},
                {"code": "CS-322", "title": "Software Engineering", "total_credit_hours": 3},
                {"code": "CS-325", "title": "Advanced Database Systems", "total_credit_hours": 3},
                {"code": "CS-4XX", "title": "CS Elective I", "total_credit_hours": 3},
                {"code": "MGT-XXX", "title": "Management Sciences Elective", "total_credit_hours": 3}
            ]
        },
        {
            "semester": 6,
            "credit_hours": 15,
            "courses": [
                {"code": "CS-412", "title": "Compiler Construction", "total_credit_hours": 3},
                {"code": "CS-423", "title": "Artificial Intelligence", "total_credit_hours": 3},
                {"code": "CS-425", "title": "Computer Vision", "total_credit_hours": 3},
                {"code": "CS-4XX", "title": "CS Elective II", "total_credit_hours": 3},
                {"code": "CS-4XX", "title": "CS Elective III", "total_credit_hours": 3}
            ]
        },
        {
            "semester": 7,
            "credit_hours": 15,
            "courses": [
                {"code": "CS-432", "title": "Information Security", "total_credit_hours": 3},
                {"code": "CS-443", "title": "Parallel and Distributed Computing", "total_credit_hours": 3},
                {"code": "CS-4XX", "title": "CS Elective IV", "total_credit_hours": 3},
                {"code": "CS-4XX", "title": "CS Elective V", "total_credit_hours": 3},
                {"code": "CS-499", "title": "Final Year Project I", "total_credit_hours": 3}
            ]
        },
        {
            "semester": 8,
            "credit_hours": 15,
            "courses": [
                {"code": "CS-483", "title": "Software Quality Assurance", "total_credit_hours": 3},
                {"code": "CS-4XX", "title": "CS Elective VI", "total_credit_hours": 3},
                {"code": "CS-4XX", "title": "CS Elective VII", "total_credit_hours": 3},
                {"code": "CS-500", "title": "Final Year Project II", "total_credit_hours": 6}
            ]
        }
    ],
    "internship": "6-week mandatory internship during summer after 6th or 7th semester",
    "electives_note": "Students must complete at least 21 credit hours of CS electives from the approved list",
    "cgpa_requirement": "Minimum CGPA of 2.0 to graduate"
}


@router.get("/programs/BSCS/study-plan")
def get_bscs_study_plan():
    """
    Get the official BSCS study plan (Fall 2025 scheme).
    Returns complete 8-semester curriculum with course details.
    """
    return BSCS_STUDY_PLAN

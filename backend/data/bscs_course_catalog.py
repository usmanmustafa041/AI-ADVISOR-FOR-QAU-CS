"""
Complete BSCS Course Catalog with Prerequisite Relationships
Source: BSCS Scheme of Study with PreRequisites (Fall 2021)
Official Document: QAU Department of Computer Science

This module contains the authoritative BSCS course catalog and
explicit prerequisite relationships as documented in the official
prerequisite list dated August 17, 2021.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class Course:
    """Represents a single course with complete metadata"""
    code: str
    title: str
    credit_hours: float
    department: str = "Computer Science"
    program: str = "BS Computer Science"
    course_type: str = "core"  # core, elective, general, supporting
    semester: Optional[int] = None
    scheme_version: str = "Fall 2021"
    effective_from: str = "Fall 2021"
    theory_hours: float = 0.0
    lab_hours: float = 0.0
    description: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    has_explicit_prerequisite: bool = False
    prerequisite_codes: List[str] = field(default_factory=list)
    prerequisite_titles: List[str] = field(default_factory=list)
    required_by_codes: List[str] = field(default_factory=list)
    source: str = "BSCS Scheme of Study with PreRequisites"
    source_section: str = "List of BSCS Approved Courses With Pre-Requisite"


# ============================================================================
# FALL 2021 BSCS SCHEME - SEMESTER BY SEMESTER
# ============================================================================

SEMESTER_1_COURSES = [
    Course(code="EN-101", title="English – 1", credit_hours=3, department="English", course_type="general", semester=1),
    Course(code="PS-101", title="Pakistan Studies", credit_hours=2, department="Pakistan Studies", course_type="general", semester=1),
    Course(code="MA-101", title="Calculus & Analytical Geometry-I", credit_hours=3, department="Mathematics", course_type="supporting", semester=1),
    Course(code="PH-111", title="Introductory Mechanics & Waves", credit_hours=3, department="Physics", course_type="supporting", semester=1),
    Course(code="PH-193", title="Introductory Mechanics & Waves Lab.", credit_hours=1, department="Physics", course_type="supporting", semester=1, lab_hours=1),
    Course(code="CS-101", title="Introduction to Computing", credit_hours=3, semester=1, aliases=["Intro to Computing"]),
    Course(code="CS-105", title="Problem Solving and Programming", credit_hours=2, semester=1, aliases=["PSP", "Problem Solving Paradigms"]),
]

SEMESTER_2_COURSES = [
    Course(code="EN-102", title="English – 2", credit_hours=3, department="English", course_type="general", semester=2),
    Course(code="IS-101", title="Islamic Studies", credit_hours=2, department="Islamic Studies", course_type="general", semester=2),
    Course(code="MA-102", title="Calculus & Analytical Geometry-II", credit_hours=3, department="Mathematics", course_type="supporting", semester=2),
    Course(code="PH-112", title="Electricity, Magnetism and Thermal Physics", credit_hours=3, department="Physics", course_type="supporting", semester=2),
    Course(code="PH-194", title="Electricity, Magnetism and Thermal Physics Lab.", credit_hours=1, department="Physics", course_type="supporting", semester=2, lab_hours=1),
    Course(code="MA-203", title="Discrete Mathematics", credit_hours=3, department="Mathematics", course_type="supporting", semester=2),
    Course(code="CS-121", title="Object Oriented Programming", credit_hours=3, semester=2, aliases=["OOP"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-105"], prerequisite_titles=["Problem Solving and Programming"]),
]

SEMESTER_3_COURSES = [
    Course(code="CS-103", title="Introduction to Computer Organization", credit_hours=3, semester=3, aliases=["Intro to Comp Org"]),
    Course(code="EN-201", title="English - 3", credit_hours=3, department="English", course_type="general", semester=3),
    Course(code="PY-101", title="Introduction to Psychology", credit_hours=3, department="Psychology", course_type="general", semester=3),
    Course(code="CS-211", title="Data Structures", credit_hours=3, semester=3, aliases=["DS", "Data Structure"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-121"], prerequisite_titles=["Object Oriented Programming"]),
    Course(code="CS-291", title="Data Structures Lab.", credit_hours=1, semester=3, lab_hours=1, aliases=["DS Lab"]),
    Course(code="CS-212", title="Human Computer Interaction", credit_hours=3, semester=3, aliases=["HCI"]),
]

SEMESTER_4_COURSES = [
    Course(code="CH-100", title="General Chemistry", credit_hours=3, department="Chemistry", course_type="supporting", semester=4),
    Course(code="CH-190", title="General Chemistry Lab.", credit_hours=1, department="Chemistry", course_type="supporting", semester=4, lab_hours=1),
    Course(code="MA-205", title="Differential Equations & Linear Algebra", credit_hours=3, department="Mathematics", course_type="supporting", semester=4),
    Course(code="CS-222", title="Analysis & Design for Software Systems", credit_hours=3, semester=4, aliases=["ADSS"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-212"], prerequisite_titles=["Human Computer Interaction"]),
    Course(code="CS-225", title="Database System", credit_hours=3, semester=4, aliases=["DBS", "Database Systems"]),
    Course(code="CS-213", title="Computer Organization & Assembly Language", credit_hours=3, semester=4, aliases=["COAL"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-103"], prerequisite_titles=["Introduction to Computer Organization"]),
    Course(code="CS-293", title="Computer Organization & Assembly Language Lab.", credit_hours=1, semester=4, lab_hours=1, aliases=["COAL Lab"]),
]

SEMESTER_5_COURSES = [
    Course(code="ST-101", title="Probability & Statistics", credit_hours=3, department="Statistics", course_type="supporting", semester=5),
    Course(code="BY-201", title="Introductory Biology", credit_hours=3, department="Biology", course_type="supporting", semester=5),
    Course(code="CS-223", title="Operating Systems", credit_hours=3, semester=5, aliases=["OS"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-211"], prerequisite_titles=["Data Structures"]),
    Course(code="CS-311", title="Analysis & Design of Algorithms", credit_hours=3, semester=5, aliases=["ADA", "Algorithms"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-211"], prerequisite_titles=["Data Structures"]),
    Course(code="CS-322", title="Software Construction", credit_hours=3, semester=5, aliases=["SC"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-222"], prerequisite_titles=["Analysis & Design for Software Systems"]),
    Course(code="CS-414", title="Artificial Intelligence", credit_hours=3, semester=5, aliases=["AI"]),
]

SEMESTER_6_COURSES = [
    Course(code="EC-201", title="Economics", credit_hours=3, department="Economics", course_type="general", semester=6),
    Course(code="CS-331", title="Theory of Automata", credit_hours=3, semester=6, aliases=["TofA", "ToA"]),
    Course(code="CS-312", title="Computer Communications & Networks", credit_hours=3, semester=6, aliases=["CCN", "Networks"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-213"], prerequisite_titles=["Computer Organization & Assembly Language"]),
    Course(code="CS-423", title="Computer Graphics", credit_hours=3, semester=6, aliases=["CG"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-311"], prerequisite_titles=["Analysis & Design of Algorithms"]),
]

SEMESTER_7_COURSES = [
    Course(code="CS-489", title="Project-I", credit_hours=3, semester=7, course_type="project"),
    Course(code="CS-332", title="Net Centric Programming", credit_hours=3, semester=7, aliases=["NCP"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-322"], prerequisite_titles=["Software Construction"]),
    Course(code="CS-411", title="Compiler Construction", credit_hours=3, semester=7, aliases=["CC"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-331"], prerequisite_titles=["Theory of Automata"]),
]

SEMESTER_8_COURSES = [
    Course(code="CS-490", title="Project-II", credit_hours=3, semester=8, course_type="project"),
    Course(code="CS-413", title="Introduction to Information Security", credit_hours=3, semester=8, aliases=["Info Security"]),
    Course(code="CS-449", title="ICT and Society", credit_hours=3, semester=8),
]

# ============================================================================
# BSCS ELECTIVE COURSES
# ============================================================================

ELECTIVE_COURSES = [
    Course(code="CS-324", title="Web Application Development", credit_hours=3, course_type="elective", aliases=["WAD"]),
    Course(code="CS-442", title="Mobile Application Development", credit_hours=3, course_type="elective", aliases=["MAD"]),
    Course(code="CS-443", title="Network Architecture", credit_hours=3, course_type="elective"),
    Course(code="CS-444", title="Knowledge Based Systems", credit_hours=3, course_type="elective", aliases=["KBS"]),
    Course(code="CS-445", title="Information Systems", credit_hours=3, course_type="elective",
           has_explicit_prerequisite=True, prerequisite_codes=["CS-225"], prerequisite_titles=["Database System"]),
    Course(code="CS-446", title="Introduction to Multimedia Communication", credit_hours=3, course_type="elective"),
    Course(code="CS-448", title="Network Management", credit_hours=3, course_type="elective"),
    Course(code="CS-451", title="Introduction to Social Computing", credit_hours=3, course_type="elective",
           has_explicit_prerequisite=True, prerequisite_codes=["CS-211"], prerequisite_titles=["Data Structures"]),
    Course(code="CS-452", title="Introduction to Game Development", credit_hours=3, course_type="elective",
           has_explicit_prerequisite=True, prerequisite_codes=["CS-121"], prerequisite_titles=["Object Oriented Programming"]),
    Course(code="CS-454", title="Introduction to Semantic Web", credit_hours=3, course_type="elective"),
    Course(code="CS-455", title="Introduction to Natural Language Processing", credit_hours=3, course_type="elective", aliases=["NLP"]),
    Course(code="CS-456", title="Introduction to Web Services", credit_hours=3, course_type="elective",
           has_explicit_prerequisite=True, prerequisite_codes=["CS-324"], prerequisite_titles=["Web Application Development"]),
    Course(code="CS-457", title="Web Application Frameworks", credit_hours=3, course_type="elective",
           has_explicit_prerequisite=True, prerequisite_codes=["CS-324"], prerequisite_titles=["Web Application Development"]),
    Course(code="CS-458", title="Introduction to Data Mining", credit_hours=3, course_type="elective"),
    Course(code="CS-459", title="Introduction to Machine Learning", credit_hours=3, course_type="elective", aliases=["ML"]),
    Course(code="CS-462", title="Introduction to Cyber Security", credit_hours=3, course_type="elective"),
    Course(code="CS-464", title="Modeling & Simulation", credit_hours=3, course_type="elective"),
    Course(code="CS-466", title="Digital Image Processing", credit_hours=3, course_type="elective", aliases=["DIP"]),
    Course(code="CS-471", title="Theory of Programming", credit_hours=3, course_type="elective"),
    Course(code="CS-472", title="Information Interfaces", credit_hours=3, course_type="elective"),
    Course(code="CS-473", title="Multimedia Applications & Design", credit_hours=3, course_type="elective"),
    Course(code="CS-474", title="Software Testing Techniques", credit_hours=3, course_type="elective",
           has_explicit_prerequisite=True, prerequisite_codes=["CS-322"], prerequisite_titles=["Software Construction"]),
    Course(code="CS-475", title="Emerging Trends in Software Development", credit_hours=3, course_type="elective"),
    Course(code="CS-476", title="Enterprise Information Infrastructure", credit_hours=3, course_type="elective"),
    Course(code="CS-478", title="Web Technologies", credit_hours=3, course_type="elective"),
    Course(code="CS-480", title="Selected Topics in CS", credit_hours=3, course_type="elective"),
    Course(code="CS-482", title="Web Engineering", credit_hours=3, course_type="elective"),
    Course(code="CS-483", title="Software Quality Assurance", credit_hours=3, course_type="elective", aliases=["SQA"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-322"], prerequisite_titles=["Software Construction"]),
    Course(code="CS-484", title="Software Engineering", credit_hours=3, course_type="elective", aliases=["SE"]),
    Course(code="CS-486", title="Software Project Management", credit_hours=3, course_type="elective", aliases=["SPM"],
           has_explicit_prerequisite=True, prerequisite_codes=["CS-322"], prerequisite_titles=["Software Construction"]),
    Course(code="CS-487", title="Formal Methods for Software Engineering", credit_hours=3, course_type="elective"),
    Course(code="CS-488", title="Software Entrepreneurship", credit_hours=3, course_type="elective"),
    Course(code="CS-491", title="Real Time Systems", credit_hours=3, course_type="elective", aliases=["RTS"]),
    Course(code="CS-497", title="Computing Case Studies", credit_hours=3, course_type="elective"),
]

# ============================================================================
# COMPLETE COURSE CATALOG
# ============================================================================

ALL_COURSES = (
    SEMESTER_1_COURSES +
    SEMESTER_2_COURSES +
    SEMESTER_3_COURSES +
    SEMESTER_4_COURSES +
    SEMESTER_5_COURSES +
    SEMESTER_6_COURSES +
    SEMESTER_7_COURSES +
    SEMESTER_8_COURSES +
    ELECTIVE_COURSES
)

# ============================================================================
# EXPLICIT PREREQUISITE RELATIONSHIPS (AUTHORITATIVE)
# ============================================================================

EXPLICIT_PREREQUISITES = {
    "CS-121": ["CS-105"],
    "CS-211": ["CS-121"],
    "CS-213": ["CS-103"],
    "CS-222": ["CS-212"],
    "CS-223": ["CS-211"],
    "CS-311": ["CS-211"],
    "CS-312": ["CS-213"],
    "CS-322": ["CS-222"],
    "CS-332": ["CS-322"],
    "CS-411": ["CS-331"],
    "CS-423": ["CS-311"],
    "CS-445": ["CS-225"],
    "CS-451": ["CS-211"],
    "CS-452": ["CS-121"],
    "CS-456": ["CS-324"],
    "CS-457": ["CS-324"],
    "CS-474": ["CS-322"],
    "CS-483": ["CS-322"],
    "CS-486": ["CS-322"],
}

# Total: 19 explicit prerequisite relationships

# ============================================================================
# COURSE INDEX
# ============================================================================

COURSE_INDEX = {course.code: course for course in ALL_COURSES}

# Update required_by_codes for reverse relationships
for course_code, prereq_list in EXPLICIT_PREREQUISITES.items():
    for prereq_code in prereq_list:
        if prereq_code in COURSE_INDEX:
            COURSE_INDEX[prereq_code].required_by_codes.append(course_code)


# ============================================================================
# COURSE LOOKUP FUNCTIONS
# ============================================================================

def get_course(code: str) -> Optional[Course]:
    """Get course by code"""
    return COURSE_INDEX.get(code)


def get_all_courses() -> List[Course]:
    """Get all courses"""
    return ALL_COURSES


def get_courses_by_semester(semester: int) -> List[Course]:
    """Get all courses for a specific semester"""
    return [c for c in ALL_COURSES if c.semester == semester]


def get_elective_courses() -> List[Course]:
    """Get all elective courses"""
    return [c for c in ALL_COURSES if c.course_type == "elective"]


def get_core_courses() -> List[Course]:
    """Get all core CS courses"""
    return [c for c in ALL_COURSES if c.course_type == "core" and c.department == "Computer Science"]


def get_direct_prerequisites(course_code: str) -> List[str]:
    """Get direct prerequisites for a course"""
    return EXPLICIT_PREREQUISITES.get(course_code, [])


def get_courses_requiring(prerequisite_code: str) -> List[str]:
    """Get all courses that require this prerequisite"""
    course = COURSE_INDEX.get(prerequisite_code)
    return course.required_by_codes if course else []


def course_has_explicit_prerequisite(course_code: str) -> bool:
    """Check if course has an explicitly documented prerequisite"""
    return course_code in EXPLICIT_PREREQUISITES


def get_prerequisite_count() -> int:
    """Get total number of explicit prerequisite relationships"""
    return len(EXPLICIT_PREREQUISITES)


# ============================================================================
# VALIDATION
# ============================================================================

def validate_catalog():
    """Validate the course catalog integrity"""
    errors = []
    
    # Validate prerequisite relationships
    for course_code, prereqs in EXPLICIT_PREREQUISITES.items():
        if course_code not in COURSE_INDEX:
            errors.append(f"Course {course_code} has prerequisites but is not in catalog")
        
        for prereq in prereqs:
            if prereq not in COURSE_INDEX:
                errors.append(f"Prerequisite {prereq} for {course_code} is not in catalog")
    
    # Validate reverse relationships
    for course in ALL_COURSES:
        for required_by in course.required_by_codes:
            if required_by not in COURSE_INDEX:
                errors.append(f"Course {required_by} listed as requiring {course.code} but not in catalog")
    
    return errors


# ============================================================================
# SEMESTER METADATA
# ============================================================================

SEMESTER_METADATA = {
    1: {"total_credits": 17, "core_cs_courses": 2},
    2: {"total_credits": 18, "core_cs_courses": 1},
    3: {"total_credits": 16, "core_cs_courses": 3},
    4: {"total_credits": 16, "core_cs_courses": 3},
    5: {"total_credits": 18, "core_cs_courses": 4},
    6: {"total_credits": 15, "core_cs_courses": 3},
    7: {"total_credits": 15, "core_cs_courses": 3},
    8: {"total_credits": 15, "core_cs_courses": 3},
}

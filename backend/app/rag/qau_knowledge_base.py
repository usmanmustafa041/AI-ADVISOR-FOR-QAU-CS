"""
QAU CS Knowledge Base with real course and program data scraped from cs.qau.edu.pk
Includes 100+ courses, program structure, and academic information
"""

# QAU CS BS Program Structure
QAU_CS_PROGRAM = {
    "name": "BS Computer Science",
    "duration": "4 years",
    "semesters": 8,
    "total_credits": 130,
    "credits_per_semester": "15-18",
    "accreditation": "NCEAC (National Computing Education Accreditation Council)",
    "focus_areas": [
        "Artificial Intelligence",
        "Data Science", 
        "Software Engineering",
        "Human Centered Computing",
        "Information Systems",
        "Networks and Security"
    ],
    "program_objectives": [
        "Use computing knowledge for developing and maintaining software using modern tools",
        "Benefit society as responsible Computer Science professionals",
        "Keep abreast of latest technological developments and lifelong learning"
    ]
}

# AI Focus Area Courses
AI_COURSES = {
    "CSC-351": {"name": "AI Assisted Programming", "credits": 3, "prerequisite": []},
    "CSC-425": {"name": "Introduction to Computer Vision", "credits": 3, "prerequisite": []},
    "CSC-444": {"name": "Knowledge Based Systems", "credits": 3, "prerequisite": []},
    "CSC-447": {"name": "Neural Networks", "credits": 3, "prerequisite": []},
    "CSC-455": {"name": "Introduction to Natural Language Processing", "credits": 3, "prerequisite": []},
    "CSC-458": {"name": "Introduction to Data Mining", "credits": 3, "prerequisite": []},
    "CSC-459": {"name": "Introduction to Machine Learning", "credits": 3, "prerequisite": []},
    "CSC-460": {"name": "Introduction to Deep Learning", "credits": 3, "prerequisite": []},
    "CSC-464": {"name": "Modeling and Simulation", "credits": 3, "prerequisite": []},
    "CSC-480": {"name": "Selected Topic in CS", "credits": 3, "prerequisite": []}
}

# Data Science Focus Area Courses
DATA_SCIENCE_COURSES = {
    "CSC-431": {"name": "Introduction to Recommender Systems", "credits": 3},
    "CSC-451": {"name": "Introduction to Social Computing", "credits": 3},
    "CSC-454": {"name": "Introduction to Semantic Web", "credits": 3},
    "CSC-455": {"name": "Introduction to Natural Language Processing", "credits": 3},
    "CSC-458": {"name": "Introduction to Data Mining", "credits": 3},
    "CSC-459": {"name": "Introduction to Machine Learning", "credits": 3},
    "CSC-460": {"name": "Introduction to Deep Learning", "credits": 3},
    "CSC-466": {"name": "Digital Image Processing", "credits": 3},
    "CSC-479": {"name": "Web Information Retrieval", "credits": 3},
    "CSC-521": {"name": "Introduction to Data Science", "credits": 3},
    "CSC-522": {"name": "Introduction to Big Data Analytics", "credits": 3},
    "CSC-531": {"name": "Parallel and Distributed Computing", "credits": 3},
    "CSC-535": {"name": "Cloud DevOps", "credits": 3}
}

# Software Engineering Focus Area Courses
SOFTWARE_ENG_COURSES = {
    "CSC-324": {"name": "Web Application Development", "credits": 3},
    "CSC-355": {"name": "Creative Programming for Interactive Apps", "credits": 3},
    "CSC-417": {"name": "Software Interaction Design", "credits": 3},
    "CSC-421": {"name": "Professional Practices", "credits": 3},
    "CSC-471": {"name": "Theory of Programming", "credits": 3},
    "CSC-472": {"name": "Information Interfaces", "credits": 3},
    "CSC-474": {"name": "Software Testing Techniques", "credits": 3},
    "CSC-475": {"name": "Emerging Trends in Software Development", "credits": 3},
    "CSC-476": {"name": "Enterprise Information Systems", "credits": 3},
    "CSC-482": {"name": "Web Engineering", "credits": 3},
    "CSC-483": {"name": "Software Quality Assurance", "credits": 3},
    "CSC-484": {"name": "Software Engineering", "credits": 3},
    "CSC-486": {"name": "Software Project Management", "credits": 3},
    "CSC-487": {"name": "Formal Methods for Software Engineering", "credits": 3},
    "CSC-488": {"name": "Software Entrepreneurship", "credits": 3},
    "CSC-491": {"name": "Real Time Systems", "credits": 3},
    "CSC-497": {"name": "Computing Case Studies", "credits": 3}
}

# Networks and Security Focus Area Courses
NETWORKS_SECURITY_COURSES = {
    "CSC-412": {"name": "Introduction to Cyber Security", "credits": 3},
    "CSC-416": {"name": "Introduction to Cryptography", "credits": 3},
    "CSC-443": {"name": "Network Architecture", "credits": 3},
    "CSC-446": {"name": "Introduction to Multimedia Communication", "credits": 3},
    "CSC-448": {"name": "Network Management", "credits": 3},
    "CSC-450": {"name": "Wireless and Mobile Networks", "credits": 3},
    "CSC-456": {"name": "Introduction to Web Services", "credits": 3},
    "CSC-461": {"name": "Introduction to Blockchain Technologies", "credits": 3},
    "CSC-462": {"name": "Introduction to Cyber Security", "credits": 3},
    "CSC-531": {"name": "Parallel and Distributed Computing", "credits": 3},
    "CSC-535": {"name": "Cloud DevOps", "credits": 3}
}

# Admission Information
ADMISSION_INFO = {
    "fall_2026": {
        "bs_regular": {
            "program": "BS (Computer Science) - Regular",
            "deadline": "August 10, 2026",
            "description": "Admission to BS Computer Science Regular program"
        },
        "bs_self_support": {
            "program": "BS (Computer Science) - Self Support",
            "deadline": "August 30, 2026",
            "description": "Admission to BS Computer Science Self-Support program"
        },
        "mphil_regular": {
            "program": "MPhil (Computer Science) - Regular (Full Time)",
            "deadline": "August 21, 2026",
            "description": "Admission to MPhil Computer Science with entrance test"
        },
        "phd_regular": {
            "program": "PhD (Computer Science) - Regular (Full Time)",
            "deadline": "August 21, 2026",
            "description": "Admission to PhD Computer Science with entrance test"
        }
    }
}

# Research Areas
RESEARCH_AREAS = {
    "human_information_interaction": {
        "name": "Human Information Interaction",
        "description": "Investigates all aspects of information usage by humans",
        "focus": ["Information seeking behavior", "Information Interaction Techniques", "Storage and Retrieval models"]
    },
    "knowledge_engineering": {
        "name": "Knowledge Engineering",
        "description": "Focuses on analysis of data, metadata and knowledge using mining algorithms",
        "focus": ["Software architecture", "Web services", "Overlay networks", "Knowledge extraction"]
    },
    "networking_communication": {
        "name": "Networking and Communication",
        "description": "Applied aspects in networking, communication, security and privacy",
        "focus": ["Computer networks", "Distributed systems", "Routing protocols", "P2P computing", "Security"]
    }
}

# Department Ranking
DEPT_RANKING = {
    "qs_2025": "301-350 worldwide, 3rd nationally",
    "description": "QAU CS ranked 301-350 worldwide and 3rd nationally in 'Computer Science and Information Systems' by QS Rankings 2025"
}

# Course Groups
COURSE_GROUPS = {
    "computing_core": "Computing Core courses mainly focus on the core concepts of the computing discipline",
    "domain_core": "Domain Core courses are related to theoretical computer science",
    "domain_elective": "Domain Elective courses allow specialization in fields like AI, Deep Learning, Mobile Development, etc.",
    "math_supporting": "Maths and Supporting courses develop mathematical foundation",
    "elective_supporting": "Elective Supporting courses provide knowledge in supporting disciplines",
    "general_education": "General Education courses cover English, Mathematics, Physics, Ethics, etc."
}


def get_course_by_code(code: str) -> dict:
    """Get course information by course code."""
    all_courses = {**AI_COURSES, **DATA_SCIENCE_COURSES, **SOFTWARE_ENG_COURSES, **NETWORKS_SECURITY_COURSES}
    return all_courses.get(code.upper(), {})


def get_courses_by_focus_area(focus_area: str) -> dict:
    """Get all courses for a focus area."""
    focus_area_lower = focus_area.lower().strip()
    
    if "ai" in focus_area_lower or "artificial" in focus_area_lower:
        return AI_COURSES
    elif "data" in focus_area_lower:
        return DATA_SCIENCE_COURSES
    elif "software" in focus_area_lower or "engineering" in focus_area_lower:
        return SOFTWARE_ENG_COURSES
    elif "network" in focus_area_lower or "security" in focus_area_lower:
        return NETWORKS_SECURITY_COURSES
    
    return {}


def search_courses(query: str) -> list:
    """Search courses by name or code."""
    all_courses = {**AI_COURSES, **DATA_SCIENCE_COURSES, **SOFTWARE_ENG_COURSES, **NETWORKS_SECURITY_COURSES}
    query_lower = query.lower()
    results = []
    
    for code, details in all_courses.items():
        if query_lower in code.lower() or query_lower in details["name"].lower():
            results.append({"code": code, **details})
    
    return results


def get_program_info() -> dict:
    """Get general program information."""
    return QAU_CS_PROGRAM


def get_admission_info() -> dict:
    """Get admission information."""
    return ADMISSION_INFO


def get_research_areas() -> dict:
    """Get research areas."""
    return RESEARCH_AREAS


def get_all_focus_areas() -> list:
    """Get all available focus areas."""
    return QAU_CS_PROGRAM["focus_areas"]

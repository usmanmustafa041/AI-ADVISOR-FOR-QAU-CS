"""
Atomic RAG Chunk Generator for BSCS Course Knowledge
Creates semantically meaningful, searchable text chunks from structured course data

Chunk types:
1. Course profile chunks
2. Prerequisite relationship chunks (forward)
3. Reverse prerequisite chunks (backward)
4. Dependency chain chunks
5. Semester curriculum chunks
6. Eligibility reasoning chunks
"""

from typing import List, Dict
from dataclasses import dataclass

from data.bscs_course_catalog import (
    get_all_courses,
    get_courses_by_semester,
    get_elective_courses,
    SEMESTER_METADATA,
    Course
)
from app.core.prerequisite_graph import get_prerequisite_graph


@dataclass
class CourseChunk:
    """Represents a semantic chunk for vector embedding"""
    chunk_id: str
    chunk_type: str
    content: str
    metadata: Dict
    course_codes: List[str]  # For filtering


class CourseChunker:
    """
    Generates atomic RAG chunks from structured course data
    
    Each chunk is self-contained and semantically meaningful.
    Chunks are designed for both vector search AND metadata filtering.
    """
    
    def __init__(self):
        """Initialize chunker"""
        self.graph = get_prerequisite_graph()
        self.chunks = []
    
    def generate_all_chunks(self) -> List[CourseChunk]:
        """Generate all chunk types"""
        self.chunks = []
        
        # Generate different chunk types
        self.chunks.extend(self._generate_course_profile_chunks())
        self.chunks.extend(self._generate_prerequisite_chunks())
        self.chunks.extend(self._generate_reverse_prerequisite_chunks())
        self.chunks.extend(self._generate_dependency_chain_chunks())
        self.chunks.extend(self._generate_semester_chunks())
        self.chunks.extend(self._generate_elective_chunks())
        self.chunks.extend(self._generate_eligibility_chunks())
        
        return self.chunks
    
    def _generate_course_profile_chunks(self) -> List[CourseChunk]:
        """
        Generate comprehensive course profile chunks
        
        Example:
        CS-322 — Software Construction
        Program: BS Computer Science
        Course type: Core course
        Semester: 5 (Fall 2021 scheme)
        Credit hours: 3
        
        Direct prerequisite:
        CS-222 — Analysis and Design for Software Systems
        
        Courses explicitly requiring CS-322:
        - CS-332 — Net Centric Programming
        - CS-474 — Software Testing Techniques
        - CS-483 — Software Quality Assurance
        - CS-486 — Software Project Management
        """
        chunks = []
        
        for course in get_all_courses():
            # Build content
            content_parts = [
                f"{course.code} — {course.title}",
                f"Program: {course.program}",
                f"Department: {course.department}",
                f"Course type: {course.course_type.capitalize()}",
            ]
            
            if course.semester:
                content_parts.append(
                    f"Semester: {course.semester} ({course.scheme_version} scheme)"
                )
            
            content_parts.append(f"Credit hours: {course.credit_hours}")
            
            # Prerequisites
            if course.has_explicit_prerequisite:
                content_parts.append("\nDirect prerequisite:")
                for prereq_code, prereq_title in zip(
                    course.prerequisite_codes,
                    course.prerequisite_titles
                ):
                    content_parts.append(f"{prereq_code} — {prereq_title}")
            else:
                content_parts.append(
                    "\nThe provided official prerequisite document does not "
                    f"explicitly specify a prerequisite for {course.code}."
                )
            
            # Required by
            if course.required_by_codes:
                content_parts.append(
                    f"\nCourses explicitly requiring {course.code}:"
                )
                for req_code in course.required_by_codes:
                    req_course = next(
                        (c for c in get_all_courses() if c.code == req_code),
                        None
                    )
                    if req_course:
                        content_parts.append(f"- {req_code} — {req_course.title}")
            
            # Aliases
            if course.aliases:
                content_parts.append(f"\nAlso known as: {', '.join(course.aliases)}")
            
            content_parts.append(
                f"\nSource: {course.source}, {course.source_section}"
            )
            
            content = "\n".join(content_parts)
            
            chunk = CourseChunk(
                chunk_id=f"course_profile_{course.code}",
                chunk_type="course_profile",
                content=content,
                metadata={
                    "course_code": course.code,
                    "course_title": course.title,
                    "semester": course.semester,
                    "course_type": course.course_type,
                    "has_prerequisite": course.has_explicit_prerequisite,
                    "scheme_version": course.scheme_version,
                },
                course_codes=[course.code]
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _generate_prerequisite_chunks(self) -> List[CourseChunk]:
        """
        Generate forward prerequisite relationship chunks
        
        Example:
        CS-322 — Software Construction requires CS-222 — Analysis and Design for Software Systems.
        
        Prerequisite relationship: CS-322 requires CS-222.
        
        According to the provided BSCS prerequisite document, CS-222 must be 
        successfully completed before taking CS-322.
        
        Source: QAU Department of Computer Science, 
        List of BSCS Approved Courses With Pre-Requisite.
        """
        chunks = []
        
        for course in get_all_courses():
            if not course.has_explicit_prerequisite:
                continue
            
            for prereq_code, prereq_title in zip(
                course.prerequisite_codes,
                course.prerequisite_titles
            ):
                content = (
                    f"{course.code} — {course.title} requires "
                    f"{prereq_code} — {prereq_title}.\n\n"
                    f"Prerequisite relationship: {course.code} requires {prereq_code}.\n\n"
                    f"According to the provided BSCS prerequisite document, "
                    f"{prereq_code} must be successfully completed before taking {course.code}.\n\n"
                    f"Source: QAU Department of Computer Science, "
                    f"List of BSCS Approved Courses With Pre-Requisite."
                )
                
                chunk = CourseChunk(
                    chunk_id=f"prerequisite_{course.code}_requires_{prereq_code}",
                    chunk_type="prerequisite_forward",
                    content=content,
                    metadata={
                        "course_code": course.code,
                        "prerequisite_code": prereq_code,
                        "relationship": "requires",
                    },
                    course_codes=[course.code, prereq_code]
                )
                
                chunks.append(chunk)
        
        return chunks
    
    def _generate_reverse_prerequisite_chunks(self) -> List[CourseChunk]:
        """
        Generate reverse prerequisite relationship chunks
        
        Example:
        CS-222 — Analysis and Design for Software Systems is an explicitly 
        listed prerequisite for CS-322 — Software Construction.
        
        Reverse prerequisite relationship: CS-222 is required by CS-322.
        
        If a student has successfully completed CS-222, they have satisfied 
        the prerequisite requirement for CS-322 (assuming no other prerequisites exist).
        """
        chunks = []
        
        for course in get_all_courses():
            if not course.required_by_codes:
                continue
            
            for req_code in course.required_by_codes:
                req_course = next(
                    (c for c in get_all_courses() if c.code == req_code),
                    None
                )
                
                if not req_course:
                    continue
                
                content = (
                    f"{course.code} — {course.title} is an explicitly listed "
                    f"prerequisite for {req_code} — {req_course.title}.\n\n"
                    f"Reverse prerequisite relationship: {course.code} is required by {req_code}.\n\n"
                    f"If a student has successfully completed {course.code}, they have "
                    f"satisfied the prerequisite requirement for {req_code}.\n\n"
                    f"Courses that depend on {course.code}: {', '.join(course.required_by_codes)}"
                )
                
                chunk = CourseChunk(
                    chunk_id=f"reverse_prerequisite_{course.code}_required_by_{req_code}",
                    chunk_type="prerequisite_reverse",
                    content=content,
                    metadata={
                        "prerequisite_code": course.code,
                        "dependent_code": req_code,
                        "relationship": "required_by",
                    },
                    course_codes=[course.code, req_code]
                )
                
                chunks.append(chunk)
        
        return chunks
    
    def _generate_dependency_chain_chunks(self) -> List[CourseChunk]:
        """
        Generate prerequisite chain chunks for complex dependencies
        
        Example:
        CS-332 — Net Centric Programming has the following prerequisite chain:
        
        Direct prerequisite: CS-322 — Software Construction
        
        Indirect prerequisites:
        CS-322 → CS-222 — Analysis and Design for Software Systems
        CS-222 → CS-212 — Human Computer Interaction
        
        Complete prerequisite path:
        CS-332 → CS-322 → CS-222 → CS-212
        
        This means CS-212, CS-222, and CS-322 must all be successfully 
        completed before taking CS-332.
        """
        chunks = []
        
        for course in get_all_courses():
            chain = self.graph.get_all_prerequisites(course.code)
            
            # Only create chunk if there are indirect prerequisites
            if not chain.indirect_prerequisites:
                continue
            
            content_parts = [
                f"{course.code} — {course.title} has the following prerequisite chain:",
                ""
            ]
            
            if chain.direct_prerequisites:
                content_parts.append("Direct prerequisites:")
                for prereq in chain.direct_prerequisites:
                    prereq_course = next(
                        (c for c in get_all_courses() if c.code == prereq),
                        None
                    )
                    title = f" — {prereq_course.title}" if prereq_course else ""
                    content_parts.append(f"- {prereq}{title}")
                content_parts.append("")
            
            if chain.indirect_prerequisites:
                content_parts.append("Indirect prerequisites:")
                for prereq in chain.indirect_prerequisites:
                    prereq_course = next(
                        (c for c in get_all_courses() if c.code == prereq),
                        None
                    )
                    title = f" — {prereq_course.title}" if prereq_course else ""
                    content_parts.append(f"- {prereq}{title}")
                content_parts.append("")
            
            if chain.full_chain:
                content_parts.append("Complete prerequisite paths:")
                for path in chain.full_chain:
                    content_parts.append(" → ".join(path))
                content_parts.append("")
            
            all_prereqs = chain.direct_prerequisites + chain.indirect_prerequisites
            content_parts.append(
                f"This means all of the following must be successfully completed "
                f"before taking {course.code}: {', '.join(all_prereqs)}"
            )
            
            content = "\n".join(content_parts)
            
            chunk = CourseChunk(
                chunk_id=f"dependency_chain_{course.code}",
                chunk_type="dependency_chain",
                content=content,
                metadata={
                    "course_code": course.code,
                    "direct_count": len(chain.direct_prerequisites),
                    "indirect_count": len(chain.indirect_prerequisites),
                    "total_depth": len(chain.full_chain[0]) - 1 if chain.full_chain else 0,
                },
                course_codes=[course.code] + all_prereqs
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _generate_semester_chunks(self) -> List[CourseChunk]:
        """
        Generate semester curriculum chunks
        
        Example:
        BSCS Fall 2021 — Semester 5
        
        Courses:
        - ST-101 — Probability & Statistics (3 credits)
        - BY-201 — Introductory Biology (3 credits)
        - CS-223 — Operating Systems (3 credits)
        - CS-311 — Analysis & Design of Algorithms (3 credits)
        - CS-322 — Software Construction (3 credits)
        - CS-414 — Artificial Intelligence (3 credits)
        
        Total Credits: 18
        Core CS Courses: 4
        """
        chunks = []
        
        for semester_num in range(1, 9):
            courses = get_courses_by_semester(semester_num)
            
            if not courses:
                continue
            
            metadata_info = SEMESTER_METADATA.get(semester_num, {})
            
            content_parts = [
                f"BSCS Fall 2021 — Semester {semester_num}",
                "",
                "Courses:"
            ]
            
            course_codes = []
            for course in courses:
                content_parts.append(
                    f"- {course.code} — {course.title} ({course.credit_hours} credits)"
                )
                course_codes.append(course.code)
            
            content_parts.append("")
            content_parts.append(f"Total Credits: {metadata_info.get('total_credits', 'N/A')}")
            content_parts.append(f"Core CS Courses: {metadata_info.get('core_cs_courses', 'N/A')}")
            
            content = "\n".join(content_parts)
            
            chunk = CourseChunk(
                chunk_id=f"semester_{semester_num}",
                chunk_type="semester_curriculum",
                content=content,
                metadata={
                    "semester": semester_num,
                    "scheme_version": "Fall 2021",
                    "total_credits": metadata_info.get('total_credits'),
                    "course_count": len(courses),
                },
                course_codes=course_codes
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _generate_elective_chunks(self) -> List[CourseChunk]:
        """Generate elective course catalog chunk"""
        electives = get_elective_courses()
        
        content_parts = [
            "BSCS Fall 2021 — Elective Courses Catalog",
            "",
            "The BS Computer Science program offers the following elective courses:",
            ""
        ]
        
        # Group by prerequisite status
        with_prereq = [e for e in electives if e.has_explicit_prerequisite]
        without_prereq = [e for e in electives if not e.has_explicit_prerequisite]
        
        content_parts.append("Electives with explicit prerequisites:")
        for course in sorted(with_prereq, key=lambda x: x.code):
            prereq_str = ", ".join(course.prerequisite_codes)
            content_parts.append(
                f"- {course.code} — {course.title} (requires: {prereq_str})"
            )
        
        content_parts.append("")
        content_parts.append("Electives without explicit prerequisites:")
        for course in sorted(without_prereq, key=lambda x: x.code):
            content_parts.append(f"- {course.code} — {course.title}")
        
        content_parts.append("")
        content_parts.append(f"Total elective courses: {len(electives)}")
        content_parts.append("Students must take 5 elective courses (Semesters 6, 7, 8)")
        
        content = "\n".join(content_parts)
        
        chunk = CourseChunk(
            chunk_id="elective_catalog",
            chunk_type="elective_catalog",
            content=content,
            metadata={
                "elective_count": len(electives),
                "with_prerequisite": len(with_prereq),
                "without_prerequisite": len(without_prereq),
            },
            course_codes=[e.code for e in electives]
        )
        
        return [chunk]
    
    def _generate_eligibility_chunks(self) -> List[CourseChunk]:
        """
        Generate eligibility reasoning chunks
        
        Example chunks explaining prerequisite logic for common queries
        """
        chunks = []
        
        # General eligibility explanation
        content = """
        Course Eligibility Based on Prerequisites
        
        To determine if a student is eligible to take a course:
        
        1. Check if the course has an explicit prerequisite in the official document
        2. If yes, verify the student has SUCCESSFULLY COMPLETED the prerequisite
        3. "Successfully completed" means PASSED (not failed, not in progress, not enrolled)
        4. If prerequisite is FAILED: student is NOT eligible
        5. If prerequisite is IN PROGRESS: prerequisite not yet satisfied
        6. If prerequisite is NOT TAKEN: prerequisite not satisfied
        7. If prerequisite is COMPLETED/PASSED: prerequisite satisfied
        
        Important distinctions:
        - Course appearing in earlier semester ≠ automatic prerequisite
        - Only explicitly documented prerequisites count
        - Concurrent enrollment (same semester) requires both courses to be first-time enrollment
        
        The prerequisite document does not specify whether concurrent enrollment 
        exceptions are permitted.
        """
        
        chunk = CourseChunk(
            chunk_id="eligibility_logic",
            chunk_type="eligibility_reasoning",
            content=content,
            metadata={"topic": "general_eligibility"},
            course_codes=[]
        )
        
        chunks.append(chunk)
        
        # Same semester conflict explanation
        content2 = """
        Taking Multiple Courses in the Same Semester
        
        When a student wants to take multiple courses together:
        
        1. Check if any course requires another course in the list as a prerequisite
        2. If Course A requires Course B, and both are in the list:
           - If both are first-time enrollment: prerequisite conflict exists
           - If Course B was previously completed: no conflict
           - If Course B previously failed: prerequisite not satisfied
           - If Course B currently in progress: prerequisite not yet satisfied
        
        Example: CS-322 requires CS-222
        - Taking CS-222 and CS-322 together (first time): prerequisite conflict
        - Taking CS-322 (first time) after passing CS-222: no conflict
        
        The prerequisite document does not specify concurrent enrollment exception policies.
        """
        
        chunk2 = CourseChunk(
            chunk_id="same_semester_logic",
            chunk_type="eligibility_reasoning",
            content=content2,
            metadata={"topic": "same_semester_conflict"},
            course_codes=[]
        )
        
        chunks.append(chunk2)
        
        return chunks
    
    def get_chunks_by_type(self, chunk_type: str) -> List[CourseChunk]:
        """Get all chunks of a specific type"""
        return [c for c in self.chunks if c.chunk_type == chunk_type]
    
    def get_chunks_by_course(self, course_code: str) -> List[CourseChunk]:
        """Get all chunks related to a course"""
        return [c for c in self.chunks if course_code in c.course_codes]


# ============================================================================
# CHUNK EXPORT FUNCTIONS
# ============================================================================

def generate_course_chunks() -> List[CourseChunk]:
    """Generate all course-related chunks"""
    chunker = CourseChunker()
    return chunker.generate_all_chunks()


def export_chunks_for_embedding(chunks: List[CourseChunk]) -> List[Dict]:
    """
    Export chunks in format ready for embedding and storage
    
    Returns:
        List of dicts with content and metadata for vector store
    """
    return [
        {
            "chunk_id": chunk.chunk_id,
            "chunk_type": chunk.chunk_type,
            "content": chunk.content,
            "metadata": chunk.metadata,
            "course_codes": chunk.course_codes,
        }
        for chunk in chunks
    ]

"""
Prerequisite Intelligence System
Hybrid retrieval combining structured lookup + graph reasoning + vector search

CRITICAL: Structured prerequisite relationships take precedence over vector similarity.
Vector search provides supporting context, NOT prerequisite decisions.
"""

import re
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from app.core.prerequisite_graph import (
    get_prerequisite_graph,
    CourseStatus,
    PrerequisiteChain,
    DependencyImpact
)
from app.core.course_resolver import get_course_resolver
from data.bscs_course_catalog import get_course, get_all_courses


class QueryIntent(Enum):
    """Intent classification for prerequisite queries"""
    COURSE_INFO = "course_info"
    DIRECT_PREREQUISITE = "direct_prerequisite"
    REVERSE_PREREQUISITE = "reverse_prerequisite"
    PREREQUISITE_CHAIN = "prerequisite_chain"
    COURSE_ELIGIBILITY = "course_eligibility"
    SAME_SEMESTER_CONFLICT = "same_semester_conflict"
    FAILED_COURSE = "failed_course"
    PASSED_COURSE = "passed_course"
    IN_PROGRESS_COURSE = "in_progress_course"
    NOT_TAKEN_COURSE = "not_taken_course"
    AFFECTED_COURSES = "affected_courses"
    COURSE_PLANNING = "course_planning"
    WHAT_CAN_I_TAKE = "what_can_i_take"
    ELECTIVE_PREREQUISITE = "elective_prerequisite"
    SEMESTER_COURSES = "semester_courses"
    UNKNOWN = "unknown"


@dataclass
class StudentCourseHistory:
    """Student's academic history with courses"""
    completed_courses: Set[str]
    failed_courses: Set[str]
    in_progress_courses: Set[str]
    
    def get_status(self, course_code: str) -> CourseStatus:
        """Get status of a course for this student"""
        if course_code in self.completed_courses:
            return CourseStatus.COMPLETED
        elif course_code in self.failed_courses:
            return CourseStatus.FAILED
        elif course_code in self.in_progress_courses:
            return CourseStatus.IN_PROGRESS
        else:
            return CourseStatus.NOT_TAKEN


@dataclass
class EligibilityResult:
    """Result of prerequisite eligibility check"""
    course_code: str
    course_title: str
    is_eligible: bool
    reason: str
    missing_prerequisites: List[str]
    prerequisite_status: Dict[str, CourseStatus]


@dataclass
class PrerequisiteAnswer:
    """Structured answer for prerequisite queries"""
    intent: QueryIntent
    course_codes: List[str]
    answer_text: str
    structured_data: Dict
    confidence: float
    sources: List[str]


class PrerequisiteIntelligence:
    """
    Intelligent prerequisite reasoning system
    
    Architecture:
    1. Detect intent from natural language query
    2. Extract and resolve course references
    3. Use structured graph for prerequisite decisions
    4. Generate grounded, source-cited answers
    """
    
    def __init__(self):
        """Initialize intelligence system"""
        self.graph = get_prerequisite_graph()
        self.resolver = get_course_resolver()
    
    def answer_query(
        self,
        query: str,
        student_history: Optional[StudentCourseHistory] = None
    ) -> PrerequisiteAnswer:
        """
        Answer a prerequisite-related query
        
        Args:
            query: Natural language question
            student_history: Optional student academic history
        
        Returns:
            Structured answer with reasoning
        """
        # Step 1: Detect intent
        intent = self._detect_intent(query)
        
        # Step 2: Extract course codes
        course_codes = self.resolver.extract_course_codes(query)
        
        # Step 3: Normalize any CSC- codes to CS- codes (legacy compatibility)
        course_codes = [code.replace('CSC-', 'CS-') if code.startswith('CSC-') else code 
                       for code in course_codes]
        
        # Step 4: Route to appropriate handler
        if intent == QueryIntent.DIRECT_PREREQUISITE:
            return self._handle_direct_prerequisite(query, course_codes)
        
        elif intent == QueryIntent.REVERSE_PREREQUISITE:
            return self._handle_reverse_prerequisite(query, course_codes)
        
        elif intent == QueryIntent.PREREQUISITE_CHAIN:
            return self._handle_prerequisite_chain(query, course_codes)
        
        elif intent == QueryIntent.COURSE_ELIGIBILITY:
            return self._handle_course_eligibility(
                query, course_codes, student_history
            )
        
        elif intent == QueryIntent.SAME_SEMESTER_CONFLICT:
            return self._handle_same_semester(query, course_codes, student_history)
        
        elif intent == QueryIntent.AFFECTED_COURSES:
            return self._handle_affected_courses(query, course_codes)
        
        elif intent == QueryIntent.WHAT_CAN_I_TAKE:
            return self._handle_what_can_take(query, student_history)
        
        elif intent == QueryIntent.COURSE_INFO:
            return self._handle_course_info(query, course_codes)
        
        else:
            return self._handle_unknown(query)
    
    def _detect_intent(self, query: str) -> QueryIntent:
        """
        Detect query intent using keyword matching
        
        In production, this could use a classifier or LLM
        """
        query_lower = query.lower()
        
        # Check if query mentions student course status (passed/failed/completed)
        has_status_mention = any(kw in query_lower for kw in [
            'passed', 'completed', 'finished', 'done', 'cleared',
            'failed', 'flunked', 'didn\'t pass', 'did not pass',
            'taking', 'enrolled', 'currently doing'
        ])
        
        # Check for "X before Y" or "Y after X" patterns (asking about order/sequence)
        has_sequence_keyword = any(kw in query_lower for kw in [
            ' before ', ' after ', 'first then', 'then take', 'followed by'
        ])
        
        # Enhanced same semester detection - check for multiple courses mentioned
        course_codes = self.resolver.extract_course_codes(query)
        
        # If query asks "X before Y", this is asking about VALID SEQUENCE, not same-semester conflict
        # Example: "Can I study PSP before OOP?" → Asking if order is correct
        if len(course_codes) >= 2 and has_sequence_keyword:
            # This is a prerequisite sequence validation question
            # We should check if the mentioned order matches the prerequisite graph
            return QueryIntent.PREREQUISITE_CHAIN
        
        # If multiple courses mentioned with certain keywords, likely same-semester query
        # BUT: if status keywords present, might be "I passed X, can I take Y?" which is ELIGIBILITY
        if len(course_codes) >= 2:
            # Check for explicit "together" keywords first
            if any(kw in query_lower for kw in [
                'together', 'same semester', 'same time', 'both', 'simultaneously'
            ]):
                return QueryIntent.SAME_SEMESTER_CONFLICT
            
            # If has status mention + "can I take", likely asking about eligibility after completing prerequisite
            # Example: "I passed ADSS, can I take SC?" → ELIGIBILITY not SAME_SEMESTER
            if has_status_mention and any(kw in query_lower for kw in [
                'can i take', 'can i study', 'can i register', 'can i enroll'
            ]):
                # This is eligibility question - student stating their history
                return QueryIntent.COURSE_ELIGIBILITY
            
            # Multiple courses without "together" and without status mention
            # Example: "Can I take PSP and OOP?" → might be asking about both
            if any(kw in query_lower for kw in [
                'can i take', 'can i study', 'can i register',
                'taking', 'studying', 'enrolling'
            ]):
                return QueryIntent.SAME_SEMESTER_CONFLICT
        
        # Direct prerequisite patterns
        if any(kw in query_lower for kw in [
            'prerequisite of', 'prerequisite for', 'required before',
            'what comes before', 'what do i need before', 'what is required for',
            'pre-requisite', 'pre requisite'
        ]):
            return QueryIntent.DIRECT_PREREQUISITE

        if re.search(r'\bprerequisites?\b', query_lower) and 'chain' not in query_lower and 'all' not in query_lower:
            return QueryIntent.DIRECT_PREREQUISITE
        
        # Reverse prerequisite patterns
        if any(kw in query_lower for kw in [
            'which courses require', 'what requires', 'depends on',
            'what can i take after', 'courses that need'
        ]):
            return QueryIntent.REVERSE_PREREQUISITE
        
        # Prerequisite chain patterns
        if any(kw in query_lower for kw in [
            'prerequisite chain', 'all prerequisites', 'complete chain',
            'indirect prerequisite', 'dependency chain', 'show all'
        ]):
            return QueryIntent.PREREQUISITE_CHAIN
        
        # Failed course patterns
        if any(kw in query_lower for kw in [
            'failed', 'did not pass', 'which courses are affected',
            'impact of failing'
        ]):
            if 'which courses' in query_lower or 'affected' in query_lower:
                return QueryIntent.AFFECTED_COURSES
            else:
                return QueryIntent.FAILED_COURSE
        
        # Eligibility patterns
        if any(kw in query_lower for kw in [
            'what can i take', 'what courses can i', 'what should i take',
            'which courses am i eligible'
        ]):
            return QueryIntent.WHAT_CAN_I_TAKE

        if any(kw in query_lower for kw in [
            'can i take', 'eligible for', 'allowed to take', 'can i enroll'
        ]) and not ('together' in query_lower or 'both' in query_lower):
            return QueryIntent.COURSE_ELIGIBILITY
        
        # What can I take patterns
        if any(kw in query_lower for kw in [
            'what can i take', 'what courses can i', 'what should i take',
            'which courses am i eligible'
        ]):
            return QueryIntent.WHAT_CAN_I_TAKE
        
        # Course info patterns
        if any(kw in query_lower for kw in [
            'what is', 'tell me about', 'information about',
            'how many credits', 'which semester'
        ]):
            return QueryIntent.COURSE_INFO
        
        return QueryIntent.UNKNOWN
    
    def _handle_direct_prerequisite(
        self,
        query: str,
        course_codes: List[str]
    ) -> PrerequisiteAnswer:
        """Handle direct prerequisite queries"""
        if not course_codes:
            # Try to resolve from query text
            resolved = self.resolver.search(query, limit=1)
            if resolved:
                course_codes = [resolved[0][0]]
        
        if not course_codes:
            return PrerequisiteAnswer(
                intent=QueryIntent.DIRECT_PREREQUISITE,
                course_codes=[],
                answer_text="I couldn't identify which course you're asking about. Please specify a course code (e.g., CS-211) or full course name.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        course_code = course_codes[0]
        course = get_course(course_code)
        
        if not course:
            return PrerequisiteAnswer(
                intent=QueryIntent.DIRECT_PREREQUISITE,
                course_codes=[course_code],
                answer_text=f"Course {course_code} was not found in the BSCS catalog.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        prereqs = self.graph.get_direct_prerequisites(course_code)
        
        if not prereqs:
            answer = (
                f"{course.code} — {course.title}\n\n"
                f"The provided official prerequisite document does not explicitly "
                f"specify a prerequisite for {course.code}."
            )
        else:
            prereq_lines = []
            for prereq_code in prereqs:
                prereq_course = get_course(prereq_code)
                if prereq_course:
                    prereq_lines.append(f"{prereq_code} — {prereq_course.title}")
                else:
                    prereq_lines.append(prereq_code)
            
            answer = (
                f"{course.code} — {course.title}\n\n"
                f"Direct prerequisite:\n" +
                "\n".join(f"• {line}" for line in prereq_lines) +
                f"\n\nAccording to the provided BSCS prerequisite document, "
                f"the prerequisite must be successfully completed before taking {course.code}."
            )
        
        return PrerequisiteAnswer(
            intent=QueryIntent.DIRECT_PREREQUISITE,
            course_codes=[course_code],
            answer_text=answer,
            structured_data={
                "course": course_code,
                "prerequisites": prereqs,
                "has_prerequisite": len(prereqs) > 0
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites", 
                    "List of BSCS Approved Courses With Pre-Requisite"]
        )
    
    def _handle_reverse_prerequisite(
        self,
        query: str,
        course_codes: List[str]
    ) -> PrerequisiteAnswer:
        """Handle reverse prerequisite queries (what requires this course)"""
        if not course_codes:
            resolved = self.resolver.search(query, limit=1)
            if resolved:
                course_codes = [resolved[0][0]]
        
        if not course_codes:
            return PrerequisiteAnswer(
                intent=QueryIntent.REVERSE_PREREQUISITE,
                course_codes=[],
                answer_text="Please specify which course you want to check.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        course_code = course_codes[0]
        course = get_course(course_code)
        
        if not course:
            return PrerequisiteAnswer(
                intent=QueryIntent.REVERSE_PREREQUISITE,
                course_codes=[course_code],
                answer_text=f"Course {course_code} was not found in the BSCS catalog.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        dependents = self.graph.get_direct_dependents(course_code)
        
        if not dependents:
            answer = (
                f"{course.code} — {course.title}\n\n"
                f"The provided official prerequisite document does not list any courses "
                f"that explicitly require {course.code} as a prerequisite."
            )
        else:
            dependent_lines = []
            for dep_code in dependents:
                dep_course = get_course(dep_code)
                if dep_course:
                    dependent_lines.append(f"{dep_code} — {dep_course.title}")
                else:
                    dependent_lines.append(dep_code)
            
            answer = (
                f"{course.code} — {course.title} is an explicitly listed prerequisite for:\n\n" +
                "\n".join(f"• {line}" for line in dependent_lines)
            )
        
        return PrerequisiteAnswer(
            intent=QueryIntent.REVERSE_PREREQUISITE,
            course_codes=[course_code],
            answer_text=answer,
            structured_data={
                "prerequisite": course_code,
                "dependent_courses": dependents,
                "dependent_count": len(dependents)
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_prerequisite_chain(
        self,
        query: str,
        course_codes: List[str]
    ) -> PrerequisiteAnswer:
        """
        Handle prerequisite chain queries AND sequence validation queries
        
        Handles both:
        1. "What is the prerequisite chain for X?" → Show full chain
        2. "Can I study X before Y?" → Validate if X→Y order is correct
        """
        query_lower = query.lower()
        
        # Check if this is a sequence validation query (X before Y / Y after X)
        is_sequence_query = any(kw in query_lower for kw in [
            ' before ', ' after ', 'first then', 'then take'
        ])
        
        if is_sequence_query and len(course_codes) >= 2:
            # This is "Can I study X before Y?" type query
            return self._handle_sequence_validation(query, course_codes)
        
        # Original prerequisite chain logic
        if not course_codes:
            resolved = self.resolver.search(query, limit=1)
            if resolved:
                course_codes = [resolved[0][0]]
        
        if not course_codes:
            return PrerequisiteAnswer(
                intent=QueryIntent.PREREQUISITE_CHAIN,
                course_codes=[],
                answer_text="Please specify which course you want to analyze.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        course_code = course_codes[0]
        course = get_course(course_code)
        
        if not course:
            return PrerequisiteAnswer(
                intent=QueryIntent.PREREQUISITE_CHAIN,
                course_codes=[course_code],
                answer_text=f"Course {course_code} was not found.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        chain = self.graph.get_all_prerequisites(course_code)
        
        answer_parts = [f"{course.code} — {course.title}\n"]
        
        if chain.direct_prerequisites:
            answer_parts.append("Direct prerequisites:")
            for prereq_code in chain.direct_prerequisites:
                prereq = get_course(prereq_code)
                title = f" — {prereq.title}" if prereq else ""
                answer_parts.append(f"• {prereq_code}{title}")
            answer_parts.append("")
        
        if chain.indirect_prerequisites:
            answer_parts.append("Indirect prerequisites:")
            for prereq_code in chain.indirect_prerequisites:
                prereq = get_course(prereq_code)
                title = f" — {prereq.title}" if prereq else ""
                answer_parts.append(f"• {prereq_code}{title}")
            answer_parts.append("")
        
        if chain.full_chain:
            answer_parts.append("Complete prerequisite paths:")
            for path in chain.full_chain:
                answer_parts.append(" → ".join(path))
        
        if not chain.direct_prerequisites:
            answer_parts.append(
                "The provided official prerequisite document does not specify "
                f"a prerequisite for {course.code}."
            )
        
        return PrerequisiteAnswer(
            intent=QueryIntent.PREREQUISITE_CHAIN,
            course_codes=[course_code],
            answer_text="\n".join(answer_parts),
            structured_data={
                "course": course_code,
                "direct": chain.direct_prerequisites,
                "indirect": chain.indirect_prerequisites,
                "paths": chain.full_chain
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_sequence_validation(
        self,
        query: str,
        course_codes: List[str]
    ) -> PrerequisiteAnswer:
        """
        Handle sequence validation queries: "Can I study X before Y?"
        
        Determines if the mentioned order matches prerequisite relationships
        """
        if len(course_codes) < 2:
            return PrerequisiteAnswer(
                intent=QueryIntent.PREREQUISITE_CHAIN,
                course_codes=course_codes,
                answer_text="Please specify two courses to compare their order.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        query_lower = query.lower()
        
        # Determine which course is mentioned first in the query
        # Example: "Can I study PSP before OOP?" → PSP is first, OOP is second
        first_course = course_codes[0]
        second_course = course_codes[1]
        
        # Get course info
        first = get_course(first_course)
        second = get_course(second_course)
        
        if not first or not second:
            return PrerequisiteAnswer(
                intent=QueryIntent.PREREQUISITE_CHAIN,
                course_codes=course_codes,
                answer_text=f"One or more courses not found: {course_codes}",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        # Check prerequisite relationship
        # Does second_course require first_course?
        second_prereqs = self.graph.get_direct_prerequisites(second_course)
        second_all_prereqs_chain = self.graph.get_all_prerequisites(second_course)
        
        # Does first_course require second_course?
        first_prereqs = self.graph.get_direct_prerequisites(first_course)
        first_all_prereqs_chain = self.graph.get_all_prerequisites(first_course)
        
        # Determine if order is correct
        answer_parts = []
        
        if ' before ' in query_lower:
            # "Can I study X before Y?" means: Is X a prerequisite of Y?
            if first_course in second_prereqs:
                # Direct prerequisite - correct order!
                answer_parts.append(f"✓ **Yes**, {first.code} ({first.title}) should be studied **before** {second.code} ({second.title}).\n")
                answer_parts.append(f"{second.code} directly requires {first.code} as a prerequisite.\n")
                answer_parts.append("**Correct sequence:**")
                answer_parts.append(f"1. {first.code} — {first.title}")
                answer_parts.append(f"2. {second.code} — {second.title}")
            elif first_course in (second_all_prereqs_chain.direct_prerequisites + second_all_prereqs_chain.indirect_prerequisites):
                # Indirect prerequisite - correct order!
                answer_parts.append(f"✓ **Yes**, {first.code} ({first.title}) should be studied **before** {second.code} ({second.title}).\n")
                answer_parts.append(f"{first.code} is an indirect prerequisite of {second.code}.\n")
                answer_parts.append("**Prerequisite chain:**")
                for path in second_all_prereqs_chain.full_chain:
                    if first_course in path:
                        answer_parts.append(" → ".join(path))
                        break
            elif second_course in first_prereqs or second_course in (first_all_prereqs_chain.direct_prerequisites + first_all_prereqs_chain.indirect_prerequisites):
                # WRONG order - Y is prerequisite of X!
                answer_parts.append(f"✗ **No**, {first.code} ({first.title}) should **NOT** be studied before {second.code} ({second.title}).\n")
                answer_parts.append(f"**Reason**: {first.code} requires {second.code} as a prerequisite.\n")
                answer_parts.append("**Correct sequence:**")
                answer_parts.append(f"1. {second.code} — {second.title} (prerequisite)")
                answer_parts.append(f"2. {first.code} — {first.title}")
            else:
                # No prerequisite relationship
                answer_parts.append(f"✓ **Yes**, you can study {first.code} ({first.title}) before {second.code} ({second.title}).\n")
                answer_parts.append(f"The official prerequisite document does not specify a prerequisite relationship between these courses.\n")
                answer_parts.append(f"They are independent and can be taken in any order.")
        
        elif ' after ' in query_lower:
            # "Can I study X after Y?" means: Is Y a prerequisite of X?
            if second_course in first_prereqs:
                # Direct prerequisite - correct order!
                answer_parts.append(f"✓ **Yes**, {first.code} ({first.title}) should be studied **after** {second.code} ({second.title}).\n")
                answer_parts.append(f"{first.code} directly requires {second.code} as a prerequisite.\n")
                answer_parts.append("**Correct sequence:**")
                answer_parts.append(f"1. {second.code} — {second.title}")
                answer_parts.append(f"2. {first.code} — {first.title}")
            elif second_course in (first_all_prereqs_chain.direct_prerequisites + first_all_prereqs_chain.indirect_prerequisites):
                # Indirect prerequisite - correct order!
                answer_parts.append(f"✓ **Yes**, {first.code} ({first.title}) should be studied **after** {second.code} ({second.title}).\n")
                answer_parts.append(f"{second.code} is a prerequisite of {first.code}.\n")
                answer_parts.append("**Prerequisite chain:**")
                for path in first_all_prereqs_chain.full_chain:
                    if second_course in path:
                        answer_parts.append(" → ".join(path))
                        break
            elif first_course in second_prereqs or first_course in (second_all_prereqs_chain.direct_prerequisites + second_all_prereqs_chain.indirect_prerequisites):
                # WRONG order
                answer_parts.append(f"✗ **No**, {first.code} ({first.title}) should **NOT** be studied after {second.code} ({second.title}).\n")
                answer_parts.append(f"**Reason**: {second.code} requires {first.code} as a prerequisite.\n")
                answer_parts.append("**Correct sequence:**")
                answer_parts.append(f"1. {first.code} — {first.title} (prerequisite)")
                answer_parts.append(f"2. {second.code} — {second.title}")
            else:
                # No prerequisite relationship
                answer_parts.append(f"✓ **Yes**, you can study {first.code} ({first.title}) after {second.code} ({second.title}).\n")
                answer_parts.append(f"The official prerequisite document does not specify a prerequisite relationship between these courses.\n")
                answer_parts.append(f"They are independent and can be taken in any order.")
        
        return PrerequisiteAnswer(
            intent=QueryIntent.PREREQUISITE_CHAIN,
            course_codes=course_codes,
            answer_text="\n".join(answer_parts),
            structured_data={
                "first_course": first_course,
                "second_course": second_course,
                "has_relationship": first_course in second_all_prereqs_chain.direct_prerequisites + second_all_prereqs_chain.indirect_prerequisites
                    or second_course in first_all_prereqs_chain.direct_prerequisites + first_all_prereqs_chain.indirect_prerequisites
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_same_semester(
        self,
        query: str,
        course_codes: List[str],
        student_history: Optional[StudentCourseHistory]
    ) -> PrerequisiteAnswer:
        """Handle same-semester conflict detection"""
        if len(course_codes) < 2:
            return PrerequisiteAnswer(
                intent=QueryIntent.SAME_SEMESTER_CONFLICT,
                course_codes=course_codes,
                answer_text="Please specify at least two courses to check for conflicts.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        conflicts = self.graph.check_same_semester_conflict(course_codes)
        chain_conflicts = self.graph.check_prerequisite_chain_conflict(course_codes)
        
        answer_parts = [f"Checking courses: {', '.join(course_codes)}\n"]
        
        has_conflict = False
        
        if conflicts:
            has_conflict = True
            answer_parts.append("❌ **PREREQUISITE CONFLICT DETECTED**\n")
            answer_parts.append("The following courses cannot be taken together if you haven't completed their prerequisites:\n")
            
            for course_code, prereqs_in_list in conflicts.items():
                course = get_course(course_code)
                course_name = f"{course.code} — {course.title}" if course else course_code
                answer_parts.append(f"\n• **{course_name}** requires:")
                for prereq in prereqs_in_list:
                    prereq_course = get_course(prereq)
                    prereq_name = f"{prereq_course.code} — {prereq_course.title}" if prereq_course else prereq
                    answer_parts.append(f"  → {prereq_name} (also in your list)")
            
            answer_parts.append(
                "\n⚠️ **Important**: You cannot register for a course and its prerequisite in the same semester "
                "if you are taking the prerequisite for the first time. The prerequisite must be **completed first**."
            )
            
            # Check if student has completed any of the prerequisites
            if student_history:
                answer_parts.append("\n**Checking your course history:**")
                for course_code, prereqs_in_list in conflicts.items():
                    for prereq in prereqs_in_list:
                        status = student_history.get_status(prereq)
                        if status == CourseStatus.COMPLETED:
                            answer_parts.append(f"  ✓ {prereq}: Already completed - conflict resolved")
                        elif status == CourseStatus.IN_PROGRESS:
                            answer_parts.append(f"  ⧗ {prereq}: Currently in progress - not yet satisfied")
                        elif status == CourseStatus.FAILED:
                            answer_parts.append(f"  ✗ {prereq}: Failed - prerequisite not satisfied")
                        else:
                            answer_parts.append(f"  ✗ {prereq}: Not yet taken - prerequisite not satisfied")
        
        if chain_conflicts:
            has_conflict = True
            answer_parts.append("\n**Indirect prerequisite dependencies found:**")
            for course_code, chains in chain_conflicts.items():
                answer_parts.append(f"\n{course_code} has prerequisite chains involving other courses in your list:")
                for chain in chains:
                    answer_parts.append(f"  {' → '.join(chain)}")
        
        if not conflicts and not chain_conflicts:
            answer_parts.append(
                "✓ **No direct prerequisite conflicts** found between these courses based on "
                "the official prerequisite document.\n"
            )
            answer_parts.append(
                "You can potentially take these courses together, subject to:\n"
                "• Credit hour limits for your program\n"
                "• Course availability and seat capacity\n"
                "• Department approval\n"
                "• Any other academic regulations"
            )
        else:
            answer_parts.append(
                "\n**Recommendation**: You should take these courses in sequence, completing the "
                "prerequisites first before enrolling in the dependent courses."
            )
        
        answer_parts.append(
            "\n**Note**: The prerequisite document does not specify whether concurrent "
            "enrollment exceptions are permitted. Contact the department for special cases."
        )
        
        return PrerequisiteAnswer(
            intent=QueryIntent.SAME_SEMESTER_CONFLICT,
            course_codes=course_codes,
            answer_text="\n".join(answer_parts),
            structured_data={
                "courses": course_codes,
                "direct_conflicts": conflicts,
                "chain_conflicts": chain_conflicts,
                "has_conflict": has_conflict
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_affected_courses(
        self,
        query: str,
        course_codes: List[str]
    ) -> PrerequisiteAnswer:
        """Handle failed course impact analysis"""
        if not course_codes:
            return PrerequisiteAnswer(
                intent=QueryIntent.AFFECTED_COURSES,
                course_codes=[],
                answer_text="Please specify which course you want to analyze.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        course_code = course_codes[0]
        course = get_course(course_code)
        
        if not course:
            return PrerequisiteAnswer(
                intent=QueryIntent.AFFECTED_COURSES,
                course_codes=[course_code],
                answer_text=f"Course {course_code} was not found.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        impact = self.graph.get_all_dependents(course_code)
        
        answer_parts = [f"{course.code} — {course.title}\n"]
        
        if impact.directly_affected:
            answer_parts.append(f"{course.code} is an explicitly listed prerequisite for:")
            for dep_code in impact.directly_affected:
                dep = get_course(dep_code)
                dep_name = f"{dep.code} — {dep.title}" if dep else dep_code
                answer_parts.append(f"• {dep_name}")
            answer_parts.append("")
        
        if impact.indirectly_affected:
            answer_parts.append("Indirectly affected courses (through dependency chain):")
            for dep_code in impact.indirectly_affected:
                dep = get_course(dep_code)
                dep_name = f"{dep.code} — {dep.title}" if dep else dep_code
                answer_parts.append(f"• {dep_name}")
            answer_parts.append("")
        
        if impact.total_affected == 0:
            answer_parts.append(
                f"No courses explicitly list {course.code} as a prerequisite in the "
                "official document."
            )
        else:
            answer_parts.append(
                f"Total affected courses: {impact.total_affected}\n\n"
                f"If {course.code} has not been successfully completed, these courses "
                "have unsatisfied prerequisite requirements according to the provided document."
            )
        
        return PrerequisiteAnswer(
            intent=QueryIntent.AFFECTED_COURSES,
            course_codes=[course_code],
            answer_text="\n".join(answer_parts),
            structured_data={
                "course": course_code,
                "directly_affected": impact.directly_affected,
                "indirectly_affected": impact.indirectly_affected,
                "total_affected": impact.total_affected
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_course_eligibility(
        self,
        query: str,
        course_codes: List[str],
        student_history: Optional[StudentCourseHistory]
    ) -> PrerequisiteAnswer:
        """
        Handle course eligibility queries
        
        When query is "I passed X, can I take Y?", we need to identify:
        - X is history context (should be in student_history)
        - Y is the target course being asked about
        
        Heuristic: The course mentioned AFTER "can I take" is the target
        """
        if not course_codes:
            return PrerequisiteAnswer(
                intent=QueryIntent.COURSE_ELIGIBILITY,
                course_codes=[],
                answer_text="Please specify which course you want to check eligibility for.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        # Identify target course using heuristics
        query_lower = query.lower()
        target_course_code = None
        
        # Find the course mentioned after "can I take" / "can I study" / "can I register"
        eligibility_triggers = [
            'can i take', 'can i study', 'can i register', 'can i enroll',
            'able to take', 'allowed to take', 'eligible for'
        ]
        
        for trigger in eligibility_triggers:
            if trigger in query_lower:
                # Find position of trigger
                trigger_pos = query_lower.index(trigger)
                
                # Extract courses mentioned AFTER the trigger
                post_trigger_text = query[trigger_pos:]
                post_trigger_courses = self.resolver.extract_course_codes(post_trigger_text)
                
                if post_trigger_courses:
                    # The first course after the trigger is the target
                    target_course_code = post_trigger_courses[0]
                    break
        
        # Fallback: if no trigger found, use the LAST mentioned course as target
        # (heuristic: "I passed X, Y, Z. Course W?" → W is the target)
        if not target_course_code:
            target_course_code = course_codes[-1] if course_codes else None
        
        if not target_course_code:
            return PrerequisiteAnswer(
                intent=QueryIntent.COURSE_ELIGIBILITY,
                course_codes=[],
                answer_text="Please specify which course you want to check eligibility for.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        course = get_course(target_course_code)
        
        if not course:
            return PrerequisiteAnswer(
                intent=QueryIntent.COURSE_ELIGIBILITY,
                course_codes=[target_course_code],
                answer_text=f"Course {target_course_code} was not found.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        prereqs = self.graph.get_direct_prerequisites(target_course_code)
        
        answer_parts = [f"{course.code} — {course.title}\n"]
        
        if not prereqs:
            answer_parts.append(
                f"The provided official prerequisite document does not specify "
                f"a prerequisite for {course.code}."
            )
            
            return PrerequisiteAnswer(
                intent=QueryIntent.COURSE_ELIGIBILITY,
                course_codes=[target_course_code],
                answer_text="\n".join(answer_parts),
                structured_data={"course": target_course_code, "has_prerequisite": False},
                confidence=1.0,
                sources=["BSCS Scheme of Study with PreRequisites"]
            )
        
        answer_parts.append(f"{course.code} requires:")
        for prereq_code in prereqs:
            prereq = get_course(prereq_code)
            prereq_name = f"{prereq.code} — {prereq.title}" if prereq else prereq_code
            answer_parts.append(f"• {prereq_name}")
        answer_parts.append("")
        
        if not student_history:
            answer_parts.append(
                "To determine your eligibility, I need to know whether you have "
                "completed the prerequisite."
            )
        else:
            # Check each prerequisite status
            for prereq_code in prereqs:
                status = student_history.get_status(prereq_code)
                prereq = get_course(prereq_code)
                prereq_name = prereq.code if prereq else prereq_code
                
                if status == CourseStatus.COMPLETED:
                    answer_parts.append(
                        f"✓ {prereq_name}: Successfully completed\n"
                        f"The prerequisite requirement is satisfied."
                    )
                elif status == CourseStatus.FAILED:
                    answer_parts.append(
                        f"✗ {prereq_name}: Failed\n"
                        f"The prerequisite has not been successfully completed, "
                        f"so the requirement for {course.code} is not satisfied."
                    )
                elif status == CourseStatus.IN_PROGRESS:
                    answer_parts.append(
                        f"⧗ {prereq_name}: Currently in progress\n"
                        f"The prerequisite has not yet been successfully completed."
                    )
                else:
                    answer_parts.append(
                        f"✗ {prereq_name}: Not taken\n"
                        f"The prerequisite requirement is not satisfied."
                    )
        
        return PrerequisiteAnswer(
            intent=QueryIntent.COURSE_ELIGIBILITY,
            course_codes=[target_course_code],
            answer_text="\n".join(answer_parts),
            structured_data={
                "course": target_course_code,
                "prerequisites": prereqs,
                "has_prerequisite": True
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_what_can_take(
        self,
        query: str,
        student_history: Optional[StudentCourseHistory]
    ) -> PrerequisiteAnswer:
        """Handle 'what can I take' queries"""
        if not student_history:
            return PrerequisiteAnswer(
                intent=QueryIntent.WHAT_CAN_I_TAKE,
                course_codes=[],
                answer_text="To determine which courses you can take, please provide your completed courses.",
                structured_data={},
                confidence=0.5,
                sources=[]
            )
        
        eligible = self.graph.get_eligible_courses(student_history.completed_courses)
        
        answer_parts = ["Based on your completed courses:\n"]
        
        if eligible['eligible']:
            answer_parts.append("Courses with satisfied prerequisites:")
            for code in sorted(eligible['eligible'])[:20]:  # Limit display
                course = get_course(code)
                if course:
                    answer_parts.append(f"• {course.code} — {course.title}")
            
            if len(eligible['eligible']) > 20:
                answer_parts.append(f"... and {len(eligible['eligible']) - 20} more")
            answer_parts.append("")
        
        if eligible['no_prerequisite']:
            answer_parts.append("Courses with no explicit prerequisite:")
            for code in sorted(eligible['no_prerequisite'])[:10]:
                course = get_course(code)
                if course and code not in student_history.completed_courses:
                    answer_parts.append(f"• {course.code} — {course.title}")
            
            if len(eligible['no_prerequisite']) > 10:
                answer_parts.append(f"... and {len(eligible['no_prerequisite']) - 10} more")
        
        answer_parts.append(
            "\nNote: This analysis is based on prerequisite requirements only. "
            "Actual course availability, registration rules, and semester offerings "
            "are not reflected here."
        )
        
        return PrerequisiteAnswer(
            intent=QueryIntent.WHAT_CAN_I_TAKE,
            course_codes=[],
            answer_text="\n".join(answer_parts),
            structured_data={
                "eligible": eligible['eligible'],
                "no_prerequisite": eligible['no_prerequisite'],
                "not_eligible": eligible['not_eligible']
            },
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_course_info(
        self,
        query: str,
        course_codes: List[str]
    ) -> PrerequisiteAnswer:
        """Handle general course information queries"""
        if not course_codes:
            resolved = self.resolver.search(query, limit=1)
            if resolved:
                course_codes = [resolved[0][0]]
        
        if not course_codes:
            return PrerequisiteAnswer(
                intent=QueryIntent.COURSE_INFO,
                course_codes=[],
                answer_text="Please specify which course you want information about.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        course_code = course_codes[0]
        course_info = self.resolver.get_course_info(course_code)
        
        if not course_info:
            return PrerequisiteAnswer(
                intent=QueryIntent.COURSE_INFO,
                course_codes=[course_code],
                answer_text=f"Course {course_code} was not found in the BSCS catalog.",
                structured_data={},
                confidence=0.0,
                sources=[]
            )
        
        answer_parts = [
            f"{course_info['code']} — {course_info['title']}",
            f"Credit hours: {course_info['credit_hours']}",
            f"Department: {course_info['department']}",
            f"Course type: {course_info['course_type'].capitalize()}",
        ]
        
        if course_info['semester']:
            answer_parts.append(f"Semester: {course_info['semester']} (Fall 2021 scheme)")
        
        if course_info['has_prerequisite']:
            answer_parts.append(f"\nPrerequisites: {', '.join(course_info['prerequisite_codes'])}")
        
        if course_info['required_by']:
            answer_parts.append(f"\nRequired by: {', '.join(course_info['required_by'])}")
        
        if course_info['aliases']:
            answer_parts.append(f"\nAlso known as: {', '.join(course_info['aliases'])}")
        
        return PrerequisiteAnswer(
            intent=QueryIntent.COURSE_INFO,
            course_codes=[course_code],
            answer_text="\n".join(answer_parts),
            structured_data=course_info,
            confidence=1.0,
            sources=["BSCS Scheme of Study with PreRequisites"]
        )
    
    def _handle_unknown(self, query: str) -> PrerequisiteAnswer:
        """Handle unknown intent"""
        return PrerequisiteAnswer(
            intent=QueryIntent.UNKNOWN,
            course_codes=[],
            answer_text="I'm not sure what you're asking. I can help with prerequisite questions, course eligibility, and BSCS course information.",
            structured_data={},
            confidence=0.0,
            sources=[]
        )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_intelligence_instance = None


def get_prerequisite_intelligence() -> PrerequisiteIntelligence:
    """Get singleton instance of prerequisite intelligence"""
    global _intelligence_instance
    if _intelligence_instance is None:
        _intelligence_instance = PrerequisiteIntelligence()
    return _intelligence_instance

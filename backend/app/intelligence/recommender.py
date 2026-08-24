"""
Course recommendation engine.

Recommends courses based on student profile, completed courses,
prerequisites, CGPA, and focus areas.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CourseRecommendation:
    """Represents a course recommendation with rationale."""
    
    def __init__(
        self,
        course_code: str,
        course_title: str,
        credit_hours: int,
        rationale: str,
        priority: str = 'medium',  # 'high', 'medium', 'low'
        semester_offered: list[str] | None = None
    ):
        self.course_code = course_code
        self.course_title = course_title
        self.credit_hours = credit_hours
        self.rationale = rationale
        self.priority = priority
        self.semester_offered = semester_offered or []
    
    def to_dict(self) -> dict:
        return {
            'course_code': self.course_code,
            'course_title': self.course_title,
            'credit_hours': self.credit_hours,
            'rationale': self.rationale,
            'priority': self.priority,
            'semester_offered': self.semester_offered
        }


class CourseRecommender:
    """Recommends courses based on student profile and academic rules."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def recommend(
        self,
        program_id: UUID,
        current_semester: int,
        completed_courses: list[str],
        cgpa: float | None = None,
        focus_area: str | None = None,
        max_recommendations: int = 5
    ) -> list[CourseRecommendation]:
        """
        Recommend courses for a student.
        
        Args:
            program_id: Student's program ID
            current_semester: Current semester number
            completed_courses: List of completed course codes
            cgpa: Student's CGPA (optional)
            focus_area: Student's focus area (optional)
            max_recommendations: Maximum number of recommendations
            
        Returns:
            List of CourseRecommendation objects
        """
        logger.info(
            f"Generating recommendations for program={program_id}, "
            f"semester={current_semester}, completed={len(completed_courses)}"
        )
        
        recommendations = []
        
        # Get curriculum slots for the program
        try:
            slots = self.db.execute(
                text("""
                    SELECT cs.id, cs.semester, cs.slot_type, c.code, c.title, c.credit_hours
                    FROM curriculum_slots cs
                    JOIN courses c ON cs.course_id = c.id
                    WHERE cs.scheme_id IN (
                        SELECT id FROM curriculum_schemes 
                        WHERE program_id = :program_id AND active = TRUE
                    )
                    AND c.active = TRUE
                    AND c.code NOT IN :completed_courses
                    ORDER BY cs.semester, cs.slot_type
                """),
                {
                    'program_id': str(program_id),
                    'completed_courses': tuple(completed_courses) if completed_courses else ('',)
                }
            ).fetchall()
            
            for slot in slots:
                slot_id, semester, slot_type, code, title, credit_hours = slot
                
                # Check if prerequisites are met
                prereqs_met, missing_prereqs = self._check_prerequisites(code, completed_courses)
                
                if not prereqs_met:
                    continue
                
                # Determine priority and rationale
                priority, rationale = self._determine_priority(
                    code=code,
                    semester=semester,
                    current_semester=current_semester,
                    slot_type=slot_type,
                    cgpa=cgpa,
                    focus_area=focus_area
                )
                
                # Get semester offerings
                semester_offered = self._get_semester_offerings(code)
                
                recommendations.append(
                    CourseRecommendation(
                        course_code=code,
                        course_title=title,
                        credit_hours=credit_hours,
                        rationale=rationale,
                        priority=priority,
                        semester_offered=semester_offered
                    )
                )
                
                if len(recommendations) >= max_recommendations:
                    break
            
            # Sort by priority
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))
            
            logger.info(f"Generated {len(recommendations)} recommendations")
            return recommendations[:max_recommendations]
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []
    
    def _check_prerequisites(
        self,
        course_code: str,
        completed_courses: list[str]
    ) -> tuple[bool, list[str]]:
        """
        Check if prerequisites for a course are met.
        
        Returns:
            Tuple of (all_met, list_of_missing)
        """
        try:
            prereqs = self.db.execute(
                text("""
                    SELECT c.code
                    FROM course_prerequisites cp
                    JOIN courses c ON cp.prerequisite_id = c.id
                    WHERE cp.course_id = (SELECT id FROM courses WHERE code = :code)
                """),
                {'code': course_code}
            ).fetchall()
            
            missing = [p[0] for p in prereqs if p[0] not in completed_courses]
            return len(missing) == 0, missing
            
        except Exception as e:
            logger.error(f"Error checking prerequisites for {course_code}: {e}")
            return True, []  # Assume met if error
    
    def _determine_priority(
        self,
        code: str,
        semester: int,
        current_semester: int,
        slot_type: str,
        cgpa: float | None,
        focus_area: str | None
    ) -> tuple[str, str]:
        """
        Determine priority and rationale for a course recommendation.
        
        Returns:
            Tuple of (priority_level, rationale_text)
        """
        rationales = []
        priority = 'medium'
        
        # Core courses get higher priority
        if slot_type == 'core':
            priority = 'high'
            rationales.append("Required core course")
        
        # Courses in current semester range
        if semester <= current_semester + 1:
            if priority != 'high':
                priority = 'high'
            rationales.append(f"Scheduled for semester {semester}")
        elif semester <= current_semester + 2:
            rationales.append(f"Upcoming in semester {semester}")
        
        # Focus area match
        if focus_area and focus_area.lower() in code.lower():
            if priority == 'medium':
                priority = 'high'
            rationales.append(f"Matches {focus_area} focus area")
        
        # CGPA considerations
        if cgpa is not None:
            if cgpa < 2.5 and slot_type == 'elective':
                priority = 'low'
                rationales.append("Consider improving CGPA with core courses first")
            elif cgpa >= 3.5:
                rationales.append("Strong academic standing")
        
        rationale = '; '.join(rationales) if rationales else "Eligible course"
        return priority, rationale
    
    def _get_semester_offerings(self, course_code: str) -> list[str]:
        """Get which semesters (Fall/Spring) a course is typically offered."""
        try:
            result = self.db.execute(
                text("""
                    SELECT DISTINCT at.semester_type
                    FROM course_offerings co
                    JOIN academic_terms at ON co.term_id = at.id
                    JOIN courses c ON co.course_id = c.id
                    WHERE c.code = :code
                    ORDER BY at.semester_type
                """),
                {'code': course_code}
            ).fetchall()
            
            return [r[0] for r in result]
        except Exception as e:
            logger.debug(f"Could not get semester offerings for {course_code}: {e}")
            return []


def create_recommender(db: Session) -> CourseRecommender:
    """Factory function to create a CourseRecommender."""
    return CourseRecommender(db)

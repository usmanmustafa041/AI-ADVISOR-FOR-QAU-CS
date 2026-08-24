"""
Prerequisite validation module.

Validates course prerequisites with recursive chain resolution and
cycle detection.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PrerequisiteValidator:
    """Validates course prerequisites with recursive resolution."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate(
        self,
        course_code: str,
        completed_courses: list[str],
        student_grades: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        Validate if prerequisites for a course are met.
        
        Args:
            course_code: Course code to validate
            completed_courses: List of completed course codes
            student_grades: Optional dict mapping course codes to grades
            
        Returns:
            Dict with validation result and details
        """
        logger.info(f"Validating prerequisites for {course_code}")
        
        try:
            # Get direct prerequisites
            direct_prereqs = self._get_direct_prerequisites(course_code)
            
            if not direct_prereqs:
                return {
                    'valid': True,
                    'course_code': course_code,
                    'message': 'No prerequisites required',
                    'direct_prerequisites': [],
                    'missing_prerequisites': [],
                    'prerequisite_chain': []
                }
            
            # Check each prerequisite
            missing = []
            grade_issues = []
            chains = []
            
            for prereq in direct_prereqs:
                prereq_code = prereq['code']
                min_grade = prereq.get('minimum_grade')
                
                # Check if prerequisite is completed
                if prereq_code not in completed_courses:
                    missing.append(prereq_code)
                    
                    # Get prerequisite chain
                    chain = self._get_prerequisite_chain(prereq_code, visited=set())
                    if chain:
                        chains.append({
                            'for_course': prereq_code,
                            'chain': chain
                        })
                else:
                    # Check minimum grade if specified
                    if min_grade and student_grades:
                        student_grade = student_grades.get(prereq_code)
                        if student_grade and not self._grade_meets_minimum(student_grade, min_grade):
                            grade_issues.append({
                                'course': prereq_code,
                                'required_grade': min_grade,
                                'actual_grade': student_grade
                            })
            
            # Build response
            is_valid = len(missing) == 0 and len(grade_issues) == 0
            
            result = {
                'valid': is_valid,
                'course_code': course_code,
                'direct_prerequisites': [p['code'] for p in direct_prereqs],
                'missing_prerequisites': missing,
                'grade_issues': grade_issues,
                'prerequisite_chains': chains
            }
            
            if is_valid:
                result['message'] = 'All prerequisites met'
            else:
                messages = []
                if missing:
                    messages.append(f"Missing: {', '.join(missing)}")
                if grade_issues:
                    messages.append(f"Grade requirements not met for: {', '.join([g['course'] for g in grade_issues])}")
                result['message'] = '; '.join(messages)
            
            logger.info(f"Validation result for {course_code}: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"Error validating prerequisites for {course_code}: {e}")
            return {
                'valid': False,
                'course_code': course_code,
                'message': f'Validation error: {str(e)}',
                'error': str(e)
            }
    
    def _get_direct_prerequisites(self, course_code: str) -> list[dict]:
        """Get direct prerequisites for a course."""
        try:
            result = self.db.execute(
                text("""
                    SELECT c.code, c.title, cp.minimum_grade
                    FROM course_prerequisites cp
                    JOIN courses c ON cp.prerequisite_id = c.id
                    WHERE cp.course_id = (SELECT id FROM courses WHERE code = :code AND active = TRUE)
                """),
                {'code': course_code}
            ).fetchall()
            
            return [
                {
                    'code': row[0],
                    'title': row[1],
                    'minimum_grade': row[2]
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Error fetching prerequisites for {course_code}: {e}")
            return []
    
    def _get_prerequisite_chain(
        self,
        course_code: str,
        visited: set[str] | None = None,
        max_depth: int = 10
    ) -> list[str]:
        """
        Get the full prerequisite chain for a course (recursive).
        
        Args:
            course_code: Course code
            visited: Set of already visited courses (for cycle detection)
            max_depth: Maximum recursion depth
            
        Returns:
            List of course codes in prerequisite chain
        """
        if visited is None:
            visited = set()
        
        # Cycle detection
        if course_code in visited:
            logger.warning(f"Cycle detected in prerequisite chain at {course_code}")
            return []
        
        # Depth limit
        if len(visited) >= max_depth:
            logger.warning(f"Max depth reached in prerequisite chain")
            return []
        
        visited.add(course_code)
        
        # Get direct prerequisites
        direct_prereqs = self._get_direct_prerequisites(course_code)
        
        if not direct_prereqs:
            return [course_code]
        
        # Build chain recursively
        chain = [course_code]
        
        for prereq in direct_prereqs:
            prereq_code = prereq['code']
            sub_chain = self._get_prerequisite_chain(prereq_code, visited.copy(), max_depth)
            chain.extend(sub_chain)
        
        return chain
    
    def _grade_meets_minimum(self, actual_grade: str, minimum_grade: str) -> bool:
        """
        Check if actual grade meets minimum requirement.
        
        Args:
            actual_grade: Student's actual grade (e.g., 'A', 'B+', 'C')
            minimum_grade: Minimum required grade
            
        Returns:
            True if requirement is met
        """
        # Grade hierarchy (higher is better)
        grade_values = {
            'A': 4.0,
            'A-': 3.7,
            'B+': 3.3,
            'B': 3.0,
            'B-': 2.7,
            'C+': 2.3,
            'C': 2.0,
            'C-': 1.7,
            'D+': 1.3,
            'D': 1.0,
            'F': 0.0
        }
        
        actual_value = grade_values.get(actual_grade.upper(), 0.0)
        minimum_value = grade_values.get(minimum_grade.upper(), 0.0)
        
        return actual_value >= minimum_value
    
    def get_all_prerequisites(self, course_code: str) -> dict[str, Any]:
        """
        Get complete prerequisite information for a course.
        
        Args:
            course_code: Course code
            
        Returns:
            Dict with direct and indirect prerequisites
        """
        direct_prereqs = self._get_direct_prerequisites(course_code)
        chain = self._get_prerequisite_chain(course_code, visited=set())
        
        # Remove duplicates and the course itself
        unique_chain = list(dict.fromkeys(chain))
        if course_code in unique_chain:
            unique_chain.remove(course_code)
        
        return {
            'course_code': course_code,
            'direct_prerequisites': [p['code'] for p in direct_prereqs],
            'all_prerequisites': unique_chain,
            'prerequisite_details': direct_prereqs
        }


def create_validator(db: Session) -> PrerequisiteValidator:
    """Factory function to create a PrerequisiteValidator."""
    return PrerequisiteValidator(db)

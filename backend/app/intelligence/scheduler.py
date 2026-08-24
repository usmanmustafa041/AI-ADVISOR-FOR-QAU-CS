"""
Schedule conflict detection module.

Detects time conflicts between courses and suggests alternatives.
"""

import logging
from datetime import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ScheduleConflict:
    """Represents a schedule conflict between courses."""
    
    def __init__(
        self,
        course1_code: str,
        course2_code: str,
        day: str,
        time_overlap: str,
        conflict_type: str = 'time_overlap'
    ):
        self.course1_code = course1_code
        self.course2_code = course2_code
        self.day = day
        self.time_overlap = time_overlap
        self.conflict_type = conflict_type
    
    def to_dict(self) -> dict:
        return {
            'course1': self.course1_code,
            'course2': self.course2_code,
            'day': self.day,
            'time_overlap': self.time_overlap,
            'conflict_type': self.conflict_type
        }


class ScheduleConflictDetector:
    """Detects schedule conflicts and suggests alternatives."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_conflicts(
        self,
        course_codes: list[str],
        term_id: str | None = None
    ) -> dict[str, Any]:
        """
        Detect conflicts among a list of courses.
        
        Args:
            course_codes: List of course codes to check
            term_id: Optional academic term ID for specific term schedules
            
        Returns:
            Dict with conflict information
        """
        logger.info(f"Checking conflicts for courses: {course_codes}")
        
        if len(course_codes) < 2:
            return {
                'has_conflicts': False,
                'conflicts': [],
                'total_credit_hours': self._get_total_credits(course_codes),
                'message': 'Need at least 2 courses to check conflicts'
            }
        
        # Get course schedules
        schedules = self._get_course_schedules(course_codes, term_id)
        
        if not schedules:
            return {
                'has_conflicts': False,
                'conflicts': [],
                'total_credit_hours': self._get_total_credits(course_codes),
                'message': 'No schedule information available'
            }
        
        # Detect time overlaps
        conflicts = []
        
        for i, schedule1 in enumerate(schedules):
            for schedule2 in schedules[i+1:]:
                if schedule1['course_code'] == schedule2['course_code']:
                    continue
                
                conflict = self._check_time_overlap(schedule1, schedule2)
                if conflict:
                    conflicts.append(conflict)
        
        # Check credit hour load
        total_credits = self._get_total_credits(course_codes)
        credit_warning = None
        
        if total_credits > 21:
            credit_warning = f"Credit hour load ({total_credits}) exceeds maximum of 21"
        elif total_credits < 12:
            credit_warning = f"Credit hour load ({total_credits}) is below minimum of 12 for full-time"
        
        result = {
            'has_conflicts': len(conflicts) > 0,
            'conflicts': [c.to_dict() for c in conflicts],
            'total_credit_hours': total_credits,
            'credit_warning': credit_warning
        }
        
        if result['has_conflicts']:
            result['message'] = f"Found {len(conflicts)} schedule conflict(s)"
        else:
            result['message'] = 'No schedule conflicts detected'
        
        logger.info(f"Conflict detection: {result['message']}")
        return result
    
    def suggest_alternatives(
        self,
        course_code: str,
        conflicting_with: list[str],
        term_id: str | None = None
    ) -> list[dict]:
        """
        Suggest alternative sections for a course that has conflicts.
        
        Args:
            course_code: Course with conflicts
            conflicting_with: List of courses it conflicts with
            term_id: Optional term ID
            
        Returns:
            List of alternative section suggestions
        """
        logger.info(f"Finding alternatives for {course_code}")
        
        try:
            # Get all sections of the course
            query = """
                SELECT 
                    co.section,
                    co.days_of_week,
                    co.start_time,
                    co.end_time,
                    co.instructor,
                    co.room
                FROM course_offerings co
                JOIN courses c ON co.course_id = c.id
                WHERE c.code = :course_code
                AND c.active = TRUE
            """
            
            params = {'course_code': course_code}
            
            if term_id:
                query += " AND co.term_id = :term_id"
                params['term_id'] = term_id
            
            result = self.db.execute(text(query), params).fetchall()
            
            alternatives = []
            conflicting_schedules = self._get_course_schedules(conflicting_with, term_id)
            
            for row in result:
                section, days, start_time, end_time, instructor, room = row
                
                section_schedule = {
                    'course_code': course_code,
                    'section': section,
                    'days': days,
                    'start_time': start_time,
                    'end_time': end_time
                }
                
                # Check if this section conflicts
                has_conflict = False
                for conflict_schedule in conflicting_schedules:
                    if self._check_time_overlap(section_schedule, conflict_schedule):
                        has_conflict = True
                        break
                
                if not has_conflict:
                    alternatives.append({
                        'section': section,
                        'days': days,
                        'time': f"{start_time} - {end_time}" if start_time and end_time else 'TBA',
                        'instructor': instructor,
                        'room': room,
                        'conflicts': False
                    })
            
            logger.info(f"Found {len(alternatives)} alternative sections for {course_code}")
            return alternatives
            
        except Exception as e:
            logger.error(f"Error finding alternatives for {course_code}: {e}")
            return []
    
    def _get_course_schedules(
        self,
        course_codes: list[str],
        term_id: str | None = None
    ) -> list[dict]:
        """Get schedule information for courses."""
        try:
            query = """
                SELECT 
                    c.code,
                    co.section,
                    co.days_of_week,
                    co.start_time,
                    co.end_time
                FROM course_offerings co
                JOIN courses c ON co.course_id = c.id
                WHERE c.code IN :course_codes
                AND c.active = TRUE
            """
            
            params = {'course_codes': tuple(course_codes)}
            
            if term_id:
                query += " AND co.term_id = :term_id"
                params['term_id'] = term_id
            
            result = self.db.execute(text(query), params).fetchall()
            
            schedules = []
            for row in result:
                code, section, days, start_time, end_time = row
                
                if days and start_time and end_time:
                    schedules.append({
                        'course_code': code,
                        'section': section,
                        'days': days,
                        'start_time': start_time,
                        'end_time': end_time
                    })
            
            return schedules
            
        except Exception as e:
            logger.error(f"Error fetching course schedules: {e}")
            return []
    
    def _check_time_overlap(
        self,
        schedule1: dict,
        schedule2: dict
    ) -> ScheduleConflict | None:
        """
        Check if two schedules have time overlaps.
        
        Returns:
            ScheduleConflict if overlap exists, None otherwise
        """
        days1 = set(schedule1['days'].split(',')) if schedule1['days'] else set()
        days2 = set(schedule2['days'].split(',')) if schedule2['days'] else set()
        
        # Check for common days
        common_days = days1 & days2
        
        if not common_days:
            return None
        
        # Check time overlap on common days
        start1 = schedule1['start_time']
        end1 = schedule1['end_time']
        start2 = schedule2['start_time']
        end2 = schedule2['end_time']
        
        if not all([start1, end1, start2, end2]):
            return None
        
        # Convert to comparable format
        if isinstance(start1, str):
            start1 = self._parse_time(start1)
            end1 = self._parse_time(end1)
            start2 = self._parse_time(start2)
            end2 = self._parse_time(end2)
        
        # Check if time ranges overlap
        if start1 < end2 and start2 < end1:
            overlap_start = max(start1, start2)
            overlap_end = min(end1, end2)
            
            return ScheduleConflict(
                course1_code=schedule1['course_code'],
                course2_code=schedule2['course_code'],
                day=', '.join(sorted(common_days)),
                time_overlap=f"{overlap_start} - {overlap_end}",
                conflict_type='time_overlap'
            )
        
        return None
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object."""
        try:
            # Handle various time formats
            if ':' in time_str:
                parts = time_str.split(':')
                hour = int(parts[0])
                minute = int(parts[1].split()[0]) if len(parts) > 1 else 0
                return time(hour, minute)
            return time(0, 0)
        except Exception:
            return time(0, 0)
    
    def _get_total_credits(self, course_codes: list[str]) -> int:
        """Get total credit hours for courses."""
        try:
            result = self.db.execute(
                text("""
                    SELECT COALESCE(SUM(credit_hours), 0)
                    FROM courses
                    WHERE code IN :course_codes
                    AND active = TRUE
                """),
                {'course_codes': tuple(course_codes) if course_codes else ('',)}
            ).scalar()
            
            return int(result) if result else 0
            
        except Exception as e:
            logger.error(f"Error calculating total credits: {e}")
            return 0


def create_scheduler(db: Session) -> ScheduleConflictDetector:
    """Factory function to create a ScheduleConflictDetector."""
    return ScheduleConflictDetector(db)

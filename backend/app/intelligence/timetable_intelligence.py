"""
Timetable intelligence module for chatbot query handling.

Provides intelligent responses to timetable-related queries including:
- Course schedules
- Instructor schedules
- Room availability
- Day-specific queries
- Time-based queries
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TimetableQueryHandler:
    """Handles timetable-related queries intelligently."""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_name = "Spring 2026"  # Default session
    
    def handle_query(self, query: str, entities: dict[str, Any]) -> dict[str, Any]:
        """
        Main handler for timetable queries.
        
        Args:
            query: User's natural language query
            entities: Extracted entities (course codes, instructors, days, etc.)
            
        Returns:
            Dict with answer and structured data
        """
        query_lower = query.lower()
        
        # Determine query type
        if entities.get('course_code'):
            return self._handle_course_schedule_query(entities['course_code'][0], query_lower)
        
        elif any(word in query_lower for word in ['instructor', 'teach', 'professor', 'dr.', 'dr ', 'ms.', 'ms ', 'mr.', 'mr ']):
            return self._handle_instructor_query(query_lower, entities)
        
        elif any(word in query_lower for word in ['room', 'lab', 'class room', 'where']):
            return self._handle_room_query(query_lower, entities)
        
        elif any(day in query_lower for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
            return self._handle_day_query(query_lower)
        
        elif any(word in query_lower for word in ['time', 'when', 'timing', 'schedule', 'timetable']):
            return self._handle_general_schedule_query(query_lower, entities)
        
        else:
            return self._handle_general_timetable_info()
    
    def _handle_course_schedule_query(self, course_code: str, query: str) -> dict[str, Any]:
        """Handle queries about specific course schedules."""
        logger.info(f"Handling course schedule query for: {course_code}")
        
        try:
            # Query the timetable database
            result = self.db.execute(
                text("""
                    SELECT 
                        cs.day_of_week,
                        cs.time_slot,
                        cs.shift,
                        cs.room,
                        cs.course_code,
                        cs.course_abbreviation,
                        cs.course_name,
                        cs.credit_hours,
                        cs.program,
                        cs.semester,
                        cs.section_type,
                        COALESCE(
                            array_agg(DISTINCT i.name ORDER BY i.name) FILTER (WHERE i.name IS NOT NULL),
                            ARRAY[]::VARCHAR[]
                        ) as instructors,
                        COALESCE(
                            array_agg(DISTINCT ta.name ORDER BY ta.name) FILTER (WHERE ta.name IS NOT NULL),
                            ARRAY[]::VARCHAR[]
                        ) as teaching_assistants
                    FROM course_schedules cs
                    JOIN academic_sessions asess ON cs.academic_session_id = asess.id
                    LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
                    LEFT JOIN instructors i ON csi.instructor_id = i.id
                    LEFT JOIN course_schedule_tas csta ON cs.id = csta.course_schedule_id
                    LEFT JOIN teaching_assistants ta ON csta.ta_id = ta.id
                    WHERE UPPER(cs.course_code) = UPPER(:course_code)
                        AND asess.session_name = :session_name
                        AND cs.is_active = TRUE
                    GROUP BY 
                        cs.day_of_week, cs.time_slot, cs.shift, cs.room, cs.course_code,
                        cs.course_abbreviation, cs.course_name, cs.credit_hours,
                        cs.program, cs.semester, cs.section_type
                    ORDER BY 
                        CASE cs.day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                            WHEN 'Saturday' THEN 6
                            WHEN 'Sunday' THEN 7
                        END,
                        cs.time_slot
                """),
                {"course_code": course_code, "session_name": self.session_name}
            ).mappings().all()
            
            if not result:
                return {
                    "answer": f"I couldn't find any schedule information for {course_code} in {self.session_name}. Please verify the course code or check if the course is offered this semester.",
                    "data": None,
                    "found": False
                }
            
            # Format the answer
            schedules = [dict(row) for row in result]
            answer = self._format_course_schedule_answer(schedules)
            
            return {
                "answer": answer,
                "data": schedules,
                "found": True,
                "query_type": "course_schedule"
            }
            
        except Exception as e:
            logger.error(f"Error handling course schedule query: {e}")
            return {
                "answer": f"I encountered an error while retrieving the schedule for {course_code}. Please try again or contact support.",
                "data": None,
                "found": False,
                "error": str(e)
            }
    
    def _handle_instructor_query(self, query: str, entities: dict) -> dict[str, Any]:
        """Handle queries about instructor schedules."""
        # Extract instructor name from query
        instructor_name = self._extract_instructor_name(query)
        
        if not instructor_name:
            return {
                "answer": "Could you please specify which instructor you're asking about? For example, 'Dr. Farooq' or 'Ms. Ifrah'.",
                "data": None,
                "found": False
            }
        
        logger.info(f"Handling instructor query for: {instructor_name}")
        
        try:
            # Search for instructor
            result = self.db.execute(
                text("""
                    SELECT 
                        cs.day_of_week,
                        cs.time_slot,
                        cs.shift,
                        cs.room,
                        cs.course_code,
                        cs.course_name,
                        cs.program,
                        cs.semester,
                        cs.section_type
                    FROM course_schedules cs
                    JOIN academic_sessions asess ON cs.academic_session_id = asess.id
                    JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
                    JOIN instructors i ON csi.instructor_id = i.id
                    WHERE i.name ILIKE :name
                        AND asess.session_name = :session_name
                        AND cs.is_active = TRUE
                    ORDER BY 
                        CASE cs.day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                            WHEN 'Saturday' THEN 6
                            WHEN 'Sunday' THEN 7
                        END,
                        cs.time_slot
                """),
                {"name": f"%{instructor_name}%", "session_name": self.session_name}
            ).mappings().all()
            
            if not result:
                return {
                    "answer": f"I couldn't find any teaching schedule for '{instructor_name}' in {self.session_name}. Please check the instructor's name spelling.",
                    "data": None,
                    "found": False
                }
            
            schedules = [dict(row) for row in result]
            answer = self._format_instructor_schedule_answer(instructor_name, schedules)
            
            return {
                "answer": answer,
                "data": schedules,
                "found": True,
                "query_type": "instructor_schedule"
            }
            
        except Exception as e:
            logger.error(f"Error handling instructor query: {e}")
            return {
                "answer": f"I encountered an error while retrieving the schedule for {instructor_name}.",
                "data": None,
                "found": False,
                "error": str(e)
            }
    
    def _handle_room_query(self, query: str, entities: dict) -> dict[str, Any]:
        """Handle queries about room schedules."""
        # Extract room name from query
        room_name = self._extract_room_name(query)
        
        if not room_name:
            return {
                "answer": "Could you please specify which room you're asking about? For example, 'Room 201' or 'CS Lab'.",
                "data": None,
                "found": False
            }
        
        logger.info(f"Handling room query for: {room_name}")
        
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        cs.day_of_week,
                        cs.time_slot,
                        cs.shift,
                        cs.course_code,
                        cs.course_name,
                        cs.program,
                        cs.section_type,
                        COALESCE(
                            array_agg(DISTINCT i.name) FILTER (WHERE i.name IS NOT NULL),
                            ARRAY[]::VARCHAR[]
                        ) as instructors
                    FROM course_schedules cs
                    JOIN academic_sessions asess ON cs.academic_session_id = asess.id
                    LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
                    LEFT JOIN instructors i ON csi.instructor_id = i.id
                    WHERE cs.room ILIKE :room
                        AND asess.session_name = :session_name
                        AND cs.is_active = TRUE
                    GROUP BY 
                        cs.day_of_week, cs.time_slot, cs.shift, cs.course_code,
                        cs.course_name, cs.program, cs.section_type
                    ORDER BY 
                        CASE cs.day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                            WHEN 'Saturday' THEN 6
                            WHEN 'Sunday' THEN 7
                        END,
                        cs.time_slot
                """),
                {"room": f"%{room_name}%", "session_name": self.session_name}
            ).mappings().all()
            
            if not result:
                return {
                    "answer": f"I couldn't find any classes scheduled in '{room_name}' for {self.session_name}.",
                    "data": None,
                    "found": False
                }
            
            schedules = [dict(row) for row in result]
            answer = self._format_room_schedule_answer(room_name, schedules)
            
            return {
                "answer": answer,
                "data": schedules,
                "found": True,
                "query_type": "room_schedule"
            }
            
        except Exception as e:
            logger.error(f"Error handling room query: {e}")
            return {
                "answer": f"I encountered an error while retrieving the schedule for {room_name}.",
                "data": None,
                "found": False,
                "error": str(e)
            }
    
    def _handle_day_query(self, query: str) -> dict[str, Any]:
        """Handle queries about specific day schedules."""
        # Extract day from query
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day = None
        for d in days:
            if d.lower() in query:
                day = d
                break
        
        if not day:
            return {
                "answer": "Which day would you like to see the schedule for?",
                "data": None,
                "found": False
            }
        
        logger.info(f"Handling day query for: {day}")
        
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        cs.time_slot,
                        cs.shift,
                        cs.room,
                        cs.course_code,
                        cs.course_name,
                        cs.program,
                        cs.semester,
                        cs.section_type,
                        COALESCE(
                            array_agg(DISTINCT i.name) FILTER (WHERE i.name IS NOT NULL),
                            ARRAY[]::VARCHAR[]
                        ) as instructors
                    FROM course_schedules cs
                    JOIN academic_sessions asess ON cs.academic_session_id = asess.id
                    LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
                    LEFT JOIN instructors i ON csi.instructor_id = i.id
                    WHERE cs.day_of_week = :day
                        AND asess.session_name = :session_name
                        AND cs.is_active = TRUE
                    GROUP BY 
                        cs.time_slot, cs.shift, cs.room, cs.course_code,
                        cs.course_name, cs.program, cs.semester, cs.section_type
                    ORDER BY cs.time_slot
                    LIMIT 20
                """),
                {"day": day, "session_name": self.session_name}
            ).mappings().all()
            
            if not result:
                return {
                    "answer": f"No classes are scheduled on {day} in {self.session_name}.",
                    "data": None,
                    "found": False
                }
            
            schedules = [dict(row) for row in result]
            answer = self._format_day_schedule_answer(day, schedules, len(schedules) >= 20)
            
            return {
                "answer": answer,
                "data": schedules,
                "found": True,
                "query_type": "day_schedule"
            }
            
        except Exception as e:
            logger.error(f"Error handling day query: {e}")
            return {
                "answer": f"I encountered an error while retrieving the schedule for {day}.",
                "data": None,
                "found": False,
                "error": str(e)
            }
    
    def _handle_general_schedule_query(self, query: str, entities: dict) -> dict[str, Any]:
        """Handle general schedule queries."""
        return self._handle_general_timetable_info()
    
    def _handle_general_timetable_info(self) -> dict[str, Any]:
        """Provide general timetable information."""
        answer = f"""# {self.session_name} Timetable

The timetable for {self.session_name} is now available. You can ask me about:

**By Course:** "When is CS-104 class?" or "Show me Database Systems schedule"
**By Instructor:** "What does Dr. Farooq teach?" or "Dr. Khalid's schedule"
**By Day:** "Show me Monday's classes" or "What's on Tuesday?"
**By Room:** "Which classes are in Room 201?" or "CS Lab schedule"

The schedule includes:
- 100+ class sessions
- BS, MPhil, PhD, and MS-DS programs
- Regular and Self-Finance sections
- Morning, Afternoon, and Evening shifts

**Coordinator:** Ifrah Farrukh Khan (Timetable/Datesheet Coordinator)

For the complete timetable, visit the Timetable page in the app or ask me about specific courses!"""

        return {
            "answer": answer,
            "data": None,
            "found": True,
            "query_type": "general_info"
        }
    
    # Helper methods for formatting answers
    
    def _format_course_schedule_answer(self, schedules: list[dict]) -> str:
        """Format course schedule into readable answer."""
        if not schedules:
            return "No schedule found."
        
        first = schedules[0]
        course_code = first['course_code']
        course_name = first['course_name']
        credit_hours = first['credit_hours']
        
        answer = f"# {course_code}: {course_name}\n\n"
        answer += f"**Credit Hours:** {credit_hours}\n\n"
        
        # Group by section type
        sections = {}
        for sched in schedules:
            section = sched['section_type']
            if section not in sections:
                sections[section] = []
            sections[section].append(sched)
        
        for section_type, section_schedules in sections.items():
            answer += f"## {section_type} Section\n\n"
            
            for sched in section_schedules:
                answer += f"**{sched['day_of_week']}** {sched['time_slot']} ({sched['shift']})\n"
                answer += f"- Room: {sched['room']}\n"
                
                if sched['instructors']:
                    answer += f"- Instructor(s): {', '.join(sched['instructors'])}\n"
                
                if sched['teaching_assistants']:
                    answer += f"- TA(s): {', '.join(sched['teaching_assistants'])}\n"
                
                answer += f"- Program: {sched['program']} • {sched['semester']}\n\n"
        
        return answer.strip()
    
    def _format_instructor_schedule_answer(self, instructor_name: str, schedules: list[dict]) -> str:
        """Format instructor schedule into readable answer."""
        answer = f"# Teaching Schedule: {instructor_name}\n\n"
        answer += f"**Total Classes:** {len(schedules)} sessions per week\n\n"
        
        # Group by day
        by_day = {}
        for sched in schedules:
            day = sched['day_of_week']
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(sched)
        
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for day in day_order:
            if day not in by_day:
                continue
            
            answer += f"## {day}\n\n"
            
            for sched in by_day[day]:
                answer += f"**{sched['time_slot']}** • {sched['course_code']}: {sched['course_name']}\n"
                answer += f"- Room: {sched['room']}\n"
                answer += f"- {sched['program']} • {sched['section_type']}\n\n"
        
        return answer.strip()
    
    def _format_room_schedule_answer(self, room_name: str, schedules: list[dict]) -> str:
        """Format room schedule into readable answer."""
        answer = f"# Room Schedule: {room_name}\n\n"
        answer += f"**Total Classes:** {len(schedules)} sessions per week\n\n"
        
        # Group by day
        by_day = {}
        for sched in schedules:
            day = sched['day_of_week']
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(sched)
        
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for day in day_order:
            if day not in by_day:
                continue
            
            answer += f"## {day}\n\n"
            
            for sched in by_day[day]:
                answer += f"**{sched['time_slot']}** • {sched['course_code']}: {sched['course_name']}\n"
                if sched['instructors']:
                    answer += f"- Instructor: {', '.join(sched['instructors'])}\n"
                answer += f"- {sched['program']} • {sched['section_type']}\n\n"
        
        return answer.strip()
    
    def _format_day_schedule_answer(self, day: str, schedules: list[dict], truncated: bool) -> str:
        """Format day schedule into readable answer."""
        answer = f"# {day} Class Schedule\n\n"
        
        if truncated:
            answer += f"**Showing first 20 classes** (Total classes may be more)\n\n"
        else:
            answer += f"**Total Classes:** {len(schedules)}\n\n"
        
        current_time = None
        
        for sched in schedules:
            if sched['time_slot'] != current_time:
                current_time = sched['time_slot']
                answer += f"## {current_time} ({sched['shift']})\n\n"
            
            answer += f"**{sched['course_code']}**: {sched['course_name']}\n"
            answer += f"- Room: {sched['room']}\n"
            
            if sched['instructors']:
                answer += f"- Instructor: {', '.join(sched['instructors'])}\n"
            
            answer += f"- {sched['program']} • {sched['semester']} • {sched['section_type']}\n\n"
        
        if truncated:
            answer += "\n*For the complete schedule, visit the Timetable page or ask about specific courses.*"
        
        return answer.strip()
    
    def _extract_instructor_name(self, query: str) -> str | None:
        """Extract instructor name from query."""
        # Common patterns
        import re
        
        # Try to match Dr./Ms./Mr. patterns
        patterns = [
            r'(?:dr\.?|ms\.?|mr\.?|prof\.?)\s+(\w+(?:\s+\w+)?)',
            r'instructor\s+(\w+(?:\s+\w+)?)',
            r'professor\s+(\w+(?:\s+\w+)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        return None
    
    def _extract_room_name(self, query: str) -> str | None:
        """Extract room name from query."""
        import re
        
        # Common room patterns
        patterns = [
            r'room\s+\w+\d+',
            r'room\s+[a-z]\d+',
            r'cs\s+lab',
            r'bs\s+lab',
            r'computer\s+lab',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        # Fallback: look for common room names
        common_rooms = ['Room 201', 'Room 217', 'Room 235', 'Room F6', 'Room F8', 'CS Lab', 'BS Lab', 'Online']
        for room in common_rooms:
            if room.lower() in query:
                return room
        
        return None


def create_timetable_handler(db: Session) -> TimetableQueryHandler:
    """Factory function to create a TimetableQueryHandler."""
    return TimetableQueryHandler(db)

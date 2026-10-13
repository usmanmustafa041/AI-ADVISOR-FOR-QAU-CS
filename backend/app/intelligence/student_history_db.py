"""
Student Course History Database Integration
Fetches authenticated student's actual course history from database

Schema: student_course_history table
Columns: student_id, course_id, status, letter_grade, grade_points, term_id
Status values: 'registered', 'in_progress', 'passed', 'failed', 'withdrawn', 'exempted'
"""

from typing import Set, Optional, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.intelligence.prerequisite_intelligence import StudentCourseHistory
from app.core.prerequisite_graph import CourseStatus


def fetch_student_course_history(
    db: Session,
    user_id: str
) -> Optional[StudentCourseHistory]:
    """
    Fetch authenticated student's course history from database
    
    Args:
        db: SQLAlchemy database session
        user_id: UUID of the authenticated user
    
    Returns:
        StudentCourseHistory with completed/failed/in_progress courses
        None if user has no student profile
    """
    try:
        # Query student course history
        # Join student_profiles to get student_id from user_id
        # Join courses to get course codes
        query = text("""
            SELECT 
                c.code as course_code,
                sch.status,
                sch.letter_grade,
                sch.grade_points
            FROM student_course_history sch
            JOIN student_profiles sp ON sp.id = sch.student_id
            JOIN courses c ON c.id = sch.course_id
            WHERE sp.user_id = :user_id
            ORDER BY sch.term_id NULLS LAST, c.code
        """)
        
        rows = db.execute(query, {"user_id": user_id}).mappings().all()
        
        if not rows:
            # User has no course history (might be new student, or not a student)
            return None
        
        # Categorize courses by status
        completed_courses: Set[str] = set()
        failed_courses: Set[str] = set()
        in_progress_courses: Set[str] = set()
        
        for row in rows:
            course_code = row['course_code']
            status = row['status']
            
            # Map database status to course status categories
            if status == 'passed':
                completed_courses.add(course_code)
            elif status == 'exempted':
                # Exempted courses count as completed
                completed_courses.add(course_code)
            elif status == 'failed':
                failed_courses.add(course_code)
            elif status in ('in_progress', 'registered'):
                in_progress_courses.add(course_code)
            elif status == 'withdrawn':
                # Withdrawn courses don't count for prerequisite checking
                pass
        
        return StudentCourseHistory(
            completed_courses=completed_courses,
            failed_courses=failed_courses,
            in_progress_courses=in_progress_courses
        )
    
    except Exception as e:
        # Log error but don't crash
        import traceback
        print(f"Error fetching student course history: {e}")
        traceback.print_exc()
        return None


def fetch_student_profile_summary(
    db: Session,
    user_id: str
) -> Optional[Dict]:
    """
    Fetch basic student profile information
    
    Args:
        db: SQLAlchemy database session
        user_id: UUID of the authenticated user
    
    Returns:
        Dict with student profile info or None
    """
    try:
        query = text("""
            SELECT 
                sp.student_number,
                sp.full_name,
                sp.current_semester,
                sp.current_cgpa,
                p.code as program_code,
                p.name as program_name,
                cs.name as curriculum_name
            FROM student_profiles sp
            JOIN programs p ON p.id = sp.program_id
            JOIN curriculum_schemes cs ON cs.id = sp.curriculum_id
            WHERE sp.user_id = :user_id
        """)
        
        row = db.execute(query, {"user_id": user_id}).mappings().first()
        
        if not row:
            return None
        
        return {
            'student_number': row['student_number'],
            'full_name': row['full_name'],
            'current_semester': row['current_semester'],
            'current_cgpa': float(row['current_cgpa']) if row['current_cgpa'] else None,
            'program_code': row['program_code'],
            'program_name': row['program_name'],
            'curriculum': row['curriculum_name']
        }
    
    except Exception as e:
        print(f"Error fetching student profile: {e}")
        return None


def fetch_course_grade(
    db: Session,
    user_id: str,
    course_code: str
) -> Optional[Dict]:
    """
    Fetch specific course grade for a student
    
    Args:
        db: SQLAlchemy database session
        user_id: UUID of the authenticated user
        course_code: Course code (e.g., 'CS-211')
    
    Returns:
        Dict with course status and grade info or None
    """
    try:
        query = text("""
            SELECT 
                c.code as course_code,
                c.title as course_title,
                sch.status,
                sch.letter_grade,
                sch.grade_points,
                at.year as term_year,
                at.term as term_name
            FROM student_course_history sch
            JOIN student_profiles sp ON sp.id = sch.student_id
            JOIN courses c ON c.id = sch.course_id
            LEFT JOIN academic_terms at ON at.id = sch.term_id
            WHERE sp.user_id = :user_id
                AND c.code = :course_code
            ORDER BY at.year DESC NULLS LAST, at.term DESC NULLS LAST
            LIMIT 1
        """)
        
        row = db.execute(query, {
            "user_id": user_id,
            "course_code": course_code
        }).mappings().first()
        
        if not row:
            return None
        
        return {
            'course_code': row['course_code'],
            'course_title': row['course_title'],
            'status': row['status'],
            'letter_grade': row['letter_grade'],
            'grade_points': float(row['grade_points']) if row['grade_points'] else None,
            'term_year': row['term_year'],
            'term_name': row['term_name']
        }
    
    except Exception as e:
        print(f"Error fetching course grade: {e}")
        return None


def get_completed_course_codes(
    db: Session,
    user_id: str
) -> Set[str]:
    """
    Get just the set of completed course codes for a student
    
    Convenience function for quick prerequisite checking
    
    Args:
        db: SQLAlchemy database session
        user_id: UUID of the authenticated user
    
    Returns:
        Set of completed course codes
    """
    history = fetch_student_course_history(db, user_id)
    if history:
        return history.completed_courses
    return set()


def check_student_has_profile(
    db: Session,
    user_id: str
) -> bool:
    """
    Quick check if user has a student profile
    
    Args:
        db: SQLAlchemy database session
        user_id: UUID of the authenticated user
    
    Returns:
        True if user is a student with profile
    """
    try:
        query = text("""
            SELECT EXISTS(
                SELECT 1 FROM student_profiles WHERE user_id = :user_id
            ) as has_profile
        """)
        
        result = db.execute(query, {"user_id": user_id}).scalar()
        return result
    
    except Exception:
        return False

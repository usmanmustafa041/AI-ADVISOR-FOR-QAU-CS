"""
Student Course History Parser
Extracts student course status from natural language queries

Handles patterns like:
- "I already passed PSP"
- "I failed Data Structures"
- "I completed CS-211"
- "I am currently taking OOP"
- "I have done DS and OOP"
"""

import re
from typing import Set, Tuple, Dict, List
from dataclasses import dataclass

from app.core.course_resolver import get_course_resolver


@dataclass
class ParsedCourseStatus:
    """Result of parsing course status from query text"""
    completed_courses: Set[str]
    failed_courses: Set[str]
    in_progress_courses: Set[str]
    raw_mentions: Dict[str, List[str]]  # status -> list of course mentions


class StudentHistoryParser:
    """
    Extracts student course history from natural language text
    
    Detects patterns like:
    - Past tense (completed): "I passed X", "I completed Y", "I have done Z"
    - Failed: "I failed X", "I didn't pass Y", "I got F in Z"
    - In progress: "I'm taking X", "currently enrolled in Y"
    """
    
    def __init__(self):
        """Initialize parser with course resolver"""
        self.resolver = get_course_resolver()
        
        # Define status patterns
        self._build_patterns()
    
    def _build_patterns(self):
        """Build regex patterns for status detection"""
        
        # COMPLETED/PASSED patterns
        self.completed_patterns = [
            # Direct past tense
            r'(?:i|i\'ve|ive|i have)\s+(?:already\s+)?(?:passed|completed|finished|done|cleared|taken)\s+([^.,;?!]+)',
            r'(?:i|i\'ve|ive|i have)\s+(?:successfully\s+)?(?:passed|completed)\s+([^.,;?!]+)',
            
            # "have done" patterns
            r'(?:i|i\'ve|ive|i have)\s+(?:already\s+)?done\s+(?:with\s+)?([^.,;?!]+)',
            r'(?:i|i\'ve|ive|i have)\s+(?:already\s+)?(?:taken|studied)\s+(?:and passed\s+)?([^.,;?!]+)',
            
            # "got" patterns with good grades
            r'(?:i|i\'ve|ive)\s+(?:got|gotten|received)\s+(?:a\s+)?[a-cA-C][\+\-]?\s+in\s+([^.,;?!]+)',
            
            # Course first patterns
            r'([A-Z\-\s\d]+)\s+(?:is|was)\s+(?:already\s+)?(?:passed|completed|done|finished|cleared)',
            r'([A-Z\-\s\d]+)\s+(?:has been|was)\s+(?:successfully\s+)?(?:completed|passed)',
        ]
        
        # FAILED patterns
        self.failed_patterns = [
            # Direct failed
            r'(?:i|i\'ve|ive|i have)\s+(?:failed|flunked)\s+([^.,;?!]+)',
            r'(?:i|i\'ve|ive)\s+(?:didn\'t|didnt|did not)\s+pass\s+([^.,;?!]+)',
            r'(?:i|i\'ve|ive)\s+(?:couldn\'t|couldnt|could not)\s+(?:pass|clear)\s+([^.,;?!]+)',
            
            # Got F/D
            r'(?:i|i\'ve|ive)\s+(?:got|gotten|received)\s+(?:an?\s+)?[fFdD][\+\-]?\s+in\s+([^.,;?!]+)',
            
            # Course first patterns
            r'([A-Z\-\s\d]+)\s+(?:is|was)\s+(?:failed|not passed)',
            r'([A-Z\-\s\d]+)\s+(?:has been|was)\s+(?:failed)',
        ]
        
        # IN PROGRESS patterns
        self.in_progress_patterns = [
            # Currently taking
            r'(?:i|i\'m|im|i am)\s+(?:currently\s+)?(?:taking|studying|enrolled in|doing)\s+([^.,;?!]+)',
            r'(?:i|i\'m|im|i am)\s+(?:currently\s+)?(?:in|attending)\s+([^.,;?!]+)',
            r'(?:i|i\'m|im|i am)\s+(?:currently\s+)?(?:registered for)\s+([^.,;?!]+)',
            
            # This semester patterns
            r'(?:this semester|this term),?\s+(?:i|i\'m|im|i am)\s+(?:taking|studying|doing)\s+([^.,;?!]+)',
            r'(?:i|i\'m|im|i am)\s+(?:taking|studying|doing)\s+([^.,;?!]+)\s+(?:this semester|this term|right now)',
            
            # Course first patterns
            r'([A-Z\-\s\d]+)\s+(?:is|are)\s+(?:my\s+)?(?:current|ongoing)\s+(?:course|class)',
        ]
    
    def parse(self, query: str) -> ParsedCourseStatus:
        """
        Parse query text to extract student course status
        
        Args:
            query: Natural language query
        
        Returns:
            ParsedCourseStatus with extracted courses by status
        """
        query_clean = query.strip()
        query_lower = query_clean.lower()
        
        completed = set()
        failed = set()
        in_progress = set()
        
        raw_mentions = {
            'completed': [],
            'failed': [],
            'in_progress': []
        }
        
        # Extract COMPLETED courses
        for pattern in self.completed_patterns:
            matches = re.finditer(pattern, query_lower, re.IGNORECASE)
            for match in matches:
                course_text = match.group(1).strip()
                raw_mentions['completed'].append(course_text)
                
                # Extract course codes from the matched text
                codes = self.resolver.extract_course_codes(course_text)
                completed.update(codes)
        
        # Extract FAILED courses
        for pattern in self.failed_patterns:
            matches = re.finditer(pattern, query_lower, re.IGNORECASE)
            for match in matches:
                course_text = match.group(1).strip()
                raw_mentions['failed'].append(course_text)
                
                # Extract course codes from the matched text
                codes = self.resolver.extract_course_codes(course_text)
                failed.update(codes)
        
        # Extract IN PROGRESS courses
        for pattern in self.in_progress_patterns:
            matches = re.finditer(pattern, query_lower, re.IGNORECASE)
            for match in matches:
                course_text = match.group(1).strip()
                raw_mentions['in_progress'].append(course_text)
                
                # Extract course codes from the matched text
                codes = self.resolver.extract_course_codes(course_text)
                in_progress.update(codes)
        
        # Remove conflicts: failed and in_progress take precedence over completed
        # (if someone says "I passed X but failed Y", both should be respected)
        # But if same course mentioned in multiple statuses, use most recent/specific
        
        # Priority: failed > in_progress > completed (for conflicts)
        completed = completed - failed - in_progress
        in_progress = in_progress - failed
        
        return ParsedCourseStatus(
            completed_courses=completed,
            failed_courses=failed,
            in_progress_courses=in_progress,
            raw_mentions=raw_mentions
        )
    
    def extract_multiple_status_statements(self, query: str) -> Dict[str, Set[str]]:
        """
        Handle complex queries with multiple status statements
        
        Example: "I passed PSP and DS but failed OOP, can I take SC?"
        
        Returns:
            Dict with 'completed', 'failed', 'in_progress' keys
        """
        parsed = self.parse(query)
        
        return {
            'completed': parsed.completed_courses,
            'failed': parsed.failed_courses,
            'in_progress': parsed.in_progress_courses
        }
    
    def has_status_mention(self, query: str) -> bool:
        """
        Quick check if query contains any course status mentions
        
        Returns:
            True if query mentions passed/failed/taking courses
        """
        query_lower = query.lower()
        
        status_keywords = [
            'passed', 'completed', 'finished', 'done', 'cleared',
            'failed', 'flunked', 'didn\'t pass', 'did not pass',
            'taking', 'studying', 'enrolled', 'currently doing',
            'got a', 'got an', 'received a'
        ]
        
        return any(kw in query_lower for kw in status_keywords)


# Singleton instance
_parser_instance = None


def get_student_history_parser() -> StudentHistoryParser:
    """Get singleton parser instance"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = StudentHistoryParser()
    return _parser_instance


def parse_student_history_from_query(query: str) -> ParsedCourseStatus:
    """
    Convenience function to parse student history from query
    
    Args:
        query: Natural language query
    
    Returns:
        ParsedCourseStatus with extracted courses
    """
    parser = get_student_history_parser()
    return parser.parse(query)

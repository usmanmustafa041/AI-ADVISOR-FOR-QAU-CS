"""
Course Alias Resolution System
Maps natural language course references to canonical course codes

Handles variations like:
- CS-211, CS 211, CS211
- Data Structures, DS
- Object Oriented Programming, OOP
"""

import re
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

from data.bscs_course_catalog import COURSE_INDEX, get_course


class CourseResolver:
    """
    Resolves course references to canonical course codes
    
    Supports:
    - Exact code match: CS-211
    - Code variations: CS 211, CS211
    - Full title: Data Structures
    - Common abbreviations: DS, OOP, AI
    - Fuzzy matching for typos
    """
    
    def __init__(self):
        """Initialize resolver with course catalog"""
        self.courses = COURSE_INDEX
        
        # Build lookup tables
        self._build_lookup_tables()
    
    def _build_lookup_tables(self):
        """Build efficient lookup tables for resolution"""
        # Exact code lookup (already exists in COURSE_INDEX)
        
        # Normalized code lookup (without hyphens/spaces)
        self.normalized_codes = {}
        
        # Title lookup (lowercase)
        self.title_lookup = {}
        
        # Alias lookup
        self.alias_lookup = {}
        
        # Word-based lookup for partial matching
        self.word_index = {}
        
        for code, course in self.courses.items():
            # Normalized codes: CS-211, CS 211, CS211 all map to CS-211
            normalized = self._normalize_code(code)
            self.normalized_codes[normalized] = code
            
            # Title lookup
            title_lower = course.title.lower()
            self.title_lookup[title_lower] = code
            
            # Aliases
            for alias in course.aliases:
                alias_lower = alias.lower()
                self.alias_lookup[alias_lower] = code
            
            # Word index for partial matching
            words = self._extract_words(course.title)
            for word in words:
                if word not in self.word_index:
                    self.word_index[word] = []
                self.word_index[word].append(code)
    
    def _normalize_code(self, code: str) -> str:
        """Normalize course code by removing hyphens and spaces"""
        return re.sub(r'[-\s]', '', code).upper()
    
    def _extract_words(self, text: str) -> List[str]:
        """Extract significant words from text"""
        # Lowercase and split
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common words
        stop_words = {'and', 'to', 'of', 'the', 'a', 'an', 'for', 'with', 'in'}
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def resolve(self, query: str) -> Optional[str]:
        """
        Resolve a course reference to canonical code
        
        Args:
            query: Natural language course reference
        
        Returns:
            Canonical course code or None if not found
        """
        if not query:
            return None
        
        query_clean = query.strip()
        
        # Try exact code match
        if query_clean in self.courses:
            return query_clean
        
        # Try normalized code match
        normalized = self._normalize_code(query_clean)
        if normalized in self.normalized_codes:
            return self.normalized_codes[normalized]
        
        # Try exact title match
        query_lower = query_clean.lower()
        if query_lower in self.title_lookup:
            return self.title_lookup[query_lower]
        
        # Try alias match
        if query_lower in self.alias_lookup:
            return self.alias_lookup[query_lower]
        
        # Try fuzzy matching
        return self._fuzzy_resolve(query_clean)
    
    def _fuzzy_resolve(self, query: str) -> Optional[str]:
        """
        Fuzzy matching for typos and variations
        
        Uses word-based matching and string similarity
        """
        query_lower = query.lower()
        query_words = self._extract_words(query)
        
        candidates = []
        
        # Word-based matching
        for word in query_words:
            if word in self.word_index:
                candidates.extend(self.word_index[word])
        
        if not candidates:
            # Try partial code match
            for code in self.courses.keys():
                if query_lower in code.lower() or code.lower() in query_lower:
                    candidates.append(code)
        
        if not candidates:
            return None
        
        # Score candidates by similarity
        scored = []
        for code in set(candidates):
            course = self.courses[code]
            
            # Compare with code
            code_score = SequenceMatcher(None, query_lower, code.lower()).ratio()
            
            # Compare with title
            title_score = SequenceMatcher(None, query_lower, course.title.lower()).ratio()
            
            # Compare with aliases
            alias_scores = [
                SequenceMatcher(None, query_lower, alias.lower()).ratio()
                for alias in course.aliases
            ]
            max_alias_score = max(alias_scores) if alias_scores else 0
            
            # Best score
            best_score = max(code_score, title_score, max_alias_score)
            
            scored.append((code, best_score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return best match if score is good enough
        if scored and scored[0][1] >= 0.6:
            return scored[0][0]
        
        return None
    
    def resolve_multiple(self, queries: List[str]) -> List[Tuple[str, Optional[str]]]:
        """
        Resolve multiple course references
        
        Args:
            queries: List of course references
        
        Returns:
            List of (original_query, resolved_code) tuples
        """
        return [(q, self.resolve(q)) for q in queries]
    
    def extract_course_codes(self, text: str) -> List[str]:
        """
        Extract and resolve all course codes from text
        
        Args:
            text: Natural language text
        
        Returns:
            List of resolved course codes IN ORDER OF APPEARANCE
        """
        # Pattern for course codes: CS-211, CS 211, etc.
        code_pattern = r'\b[A-Z]{2}[-\s]?\d{3}\b'
        
        matches = re.findall(code_pattern, text, re.IGNORECASE)
        
        resolved = []
        seen = set()  # Track duplicates
        
        for match in matches:
            code = self.resolve(match)
            if code and code not in seen:
                resolved.append(code)
                seen.add(code)
        
        # Also check for common aliases in text
        # Split text into words and check each
        words = re.findall(r'\b\w+\b', text)
        for word in words:
            word_lower = word.lower()
            # Check if word is an alias
            if word_lower in self.alias_lookup:
                code = self.alias_lookup[word_lower]
                if code not in seen:
                    resolved.append(code)
                    seen.add(code)
        
        # Check for course names (multi-word)
        # Process in order of appearance
        remaining_text = text.lower()
        title_positions = []
        
        for title_lower, code in self.title_lookup.items():
            pos = remaining_text.find(title_lower)
            if pos != -1:
                title_positions.append((pos, code))
        
        # Sort by position in text
        title_positions.sort(key=lambda x: x[0])
        
        for pos, code in title_positions:
            if code not in seen:
                resolved.append(code)
                seen.add(code)
        
        return resolved  # Preserves order of appearance
    
    def search(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        """
        Search for courses matching query
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of (course_code, relevance_score) tuples
        """
        query_lower = query.lower()
        query_words = self._extract_words(query)
        
        scored = []
        
        for code, course in self.courses.items():
            # Code similarity
            code_score = SequenceMatcher(None, query_lower, code.lower()).ratio()
            
            # Title similarity
            title_score = SequenceMatcher(None, query_lower, course.title.lower()).ratio()
            
            # Word overlap
            course_words = self._extract_words(course.title)
            if query_words and course_words:
                overlap = len(set(query_words) & set(course_words))
                word_score = overlap / len(query_words)
            else:
                word_score = 0
            
            # Alias match
            alias_scores = [
                SequenceMatcher(None, query_lower, alias.lower()).ratio()
                for alias in course.aliases
            ]
            max_alias_score = max(alias_scores) if alias_scores else 0
            
            # Combined score (weighted)
            score = max(
                code_score,
                title_score * 0.9,
                word_score * 0.8,
                max_alias_score * 0.85
            )
            
            if score > 0.3:  # Minimum threshold
                scored.append((code, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored[:limit]
    
    def get_course_info(self, query: str) -> Optional[dict]:
        """
        Get full course information from query
        
        Args:
            query: Course reference
        
        Returns:
            Dict with course information or None
        """
        code = self.resolve(query)
        if not code:
            return None
        
        course = get_course(code)
        if not course:
            return None
        
        return {
            'code': course.code,
            'title': course.title,
            'credit_hours': course.credit_hours,
            'department': course.department,
            'semester': course.semester,
            'course_type': course.course_type,
            'has_prerequisite': course.has_explicit_prerequisite,
            'prerequisite_codes': course.prerequisite_codes,
            'prerequisite_titles': course.prerequisite_titles,
            'required_by': course.required_by_codes,
            'aliases': course.aliases,
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_resolver_instance = None


def get_course_resolver() -> CourseResolver:
    """Get singleton instance of course resolver"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = CourseResolver()
    return _resolver_instance

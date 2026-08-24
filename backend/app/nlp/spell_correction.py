"""
Spell correction module for academic vocabulary using edit distance algorithm.

This module corrects spelling errors in user queries by matching against academic
vocabulary built from courses, academic_rules, and faculty_members tables.
"""

import logging
import re
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_session_factory

logger = logging.getLogger(__name__)


class SpellCorrector:
    """
    Spell corrector using edit distance algorithm for academic vocabulary.
    
    Builds vocabulary from courses, academic_rules, and faculty_members tables
    and corrects spelling errors with confidence scoring.
    """
    
    def __init__(self, db: Session | None = None):
        """
        Initialize spell corrector.
        
        Args:
            db: Optional database session. If None, creates a new session.
        """
        self._vocabulary: set[str] = set()
        self._word_frequency: dict[str, int] = {}
        self._initialized = False
        
        # Build vocabulary on initialization
        if db is not None:
            self._build_vocabulary(db)
        else:
            # Use a temporary session
            session_factory = get_session_factory()
            session = session_factory()
            try:
                self._build_vocabulary(session)
            finally:
                session.close()
    
    def _build_vocabulary(self, db: Session) -> None:
        """
        Build vocabulary from database tables.
        
        Args:
            db: Database session
        """
        logger.info("Building spell correction vocabulary from database...")
        
        # Extract words from courses table
        try:
            course_results = db.execute(text("""
                SELECT code, title FROM courses WHERE active = TRUE
            """)).fetchall()
            
            for row in course_results:
                # Add course code as-is (e.g., CS-101)
                if row[0]:
                    self._vocabulary.add(row[0].lower())
                    self._word_frequency[row[0].lower()] = self._word_frequency.get(row[0].lower(), 0) + 5
                
                # Add words from course title
                if row[1]:
                    words = self._tokenize(row[1])
                    for word in words:
                        self._vocabulary.add(word.lower())
                        self._word_frequency[word.lower()] = self._word_frequency.get(word.lower(), 0) + 1
            
            logger.info(f"Loaded {len(course_results)} courses into vocabulary")
        except Exception as e:
            logger.error(f"Error loading courses: {e}")
        
        # Extract words from academic_rules table (if exists)
        try:
            rules_results = db.execute(text("""
                SELECT description FROM academic_rules
            """)).fetchall()
            
            for row in rules_results:
                if row[0]:
                    words = self._tokenize(row[0])
                    for word in words:
                        self._vocabulary.add(word.lower())
                        self._word_frequency[word.lower()] = self._word_frequency.get(word.lower(), 0) + 1
            
            logger.info(f"Loaded {len(rules_results)} academic rules into vocabulary")
        except Exception as e:
            logger.warning(f"Could not load academic_rules (table may not exist): {e}")
        
        # Extract words from faculty_members table (if exists)
        try:
            faculty_results = db.execute(text("""
                SELECT full_name, title FROM faculty_members
            """)).fetchall()
            
            for row in faculty_results:
                if row[0]:  # full_name
                    words = self._tokenize(row[0])
                    for word in words:
                        self._vocabulary.add(word.lower())
                        self._word_frequency[word.lower()] = self._word_frequency.get(word.lower(), 0) + 2
                
                if row[1]:  # title
                    words = self._tokenize(row[1])
                    for word in words:
                        self._vocabulary.add(word.lower())
                        self._word_frequency[word.lower()] = self._word_frequency.get(word.lower(), 0) + 1
            
            logger.info(f"Loaded {len(faculty_results)} faculty members into vocabulary")
        except Exception as e:
            logger.warning(f"Could not load faculty_members (table may not exist): {e}")
        
        # Add common academic terms
        common_terms = [
            'course', 'courses', 'semester', 'credit', 'credits', 'prerequisite', 
            'prerequisites', 'fee', 'fees', 'registration', 'timetable', 'schedule',
            'exam', 'examination', 'deadline', 'admission', 'program', 'degree',
            'faculty', 'professor', 'instructor', 'teacher', 'research', 'thesis',
            'cgpa', 'gpa', 'grade', 'policy', 'requirement', 'elective', 'core',
            'probation', 'exemption', 'attendance', 'project'
        ]
        
        for term in common_terms:
            self._vocabulary.add(term.lower())
            self._word_frequency[term.lower()] = self._word_frequency.get(term.lower(), 0) + 10
        
        self._initialized = True
        logger.info(f"Vocabulary built with {len(self._vocabulary)} unique words")
    
    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into words, filtering out very short tokens.
        
        Args:
            text: Input text
            
        Returns:
            List of word tokens
        """
        # Split on non-alphanumeric characters, keep hyphens for course codes
        tokens = re.findall(r'\b[a-zA-Z][a-zA-Z0-9\-]*\b', text)
        # Filter out very short tokens (< 3 chars) unless they look like course codes
        return [t for t in tokens if len(t) >= 3 or re.match(r'^[A-Z]+$', t)]
    
    def correct(self, text: str) -> str:
        """
        Correct spelling errors in text.
        
        Args:
            text: Input text with potential spelling errors
            
        Returns:
            Corrected text
        """
        if not self._initialized:
            logger.warning("SpellCorrector not initialized, returning original text")
            return text
        
        words = text.split()
        corrected_words = []
        has_correction = False
        
        for word in words:
            # Skip if word is too short or contains only punctuation
            if len(word) < 3 or not any(c.isalnum() for c in word):
                corrected_words.append(word)
                continue
            
            # Extract the actual word (remove punctuation)
            match = re.match(r'([^\w\-]*)([\w\-]+)([^\w]*)', word)
            if not match:
                corrected_words.append(word)
                continue
            
            prefix, core_word, suffix = match.groups()
            
            # Check if word is in vocabulary (case-insensitive)
            if core_word.lower() in self._vocabulary:
                corrected_words.append(word)
                continue
            
            # Try to find correction
            correction, confidence = self._find_correction(core_word)
            
            if correction and confidence >= 0.80:
                # Preserve original case pattern
                corrected = self._preserve_case(core_word, correction)
                corrected_words.append(prefix + corrected + suffix)
                has_correction = True
                logger.info(f"Corrected '{core_word}' to '{correction}' (confidence: {confidence:.2f})")
            elif correction and confidence < 0.80:
                # Low confidence, preserve original but log
                corrected_words.append(word)
                logger.debug(f"Low confidence correction for '{core_word}' -> '{correction}' ({confidence:.2f}), keeping original")
            else:
                # No correction found
                corrected_words.append(word)
        
        corrected_text = ' '.join(corrected_words)
        
        # Log if corrections were made
        if has_correction:
            logger.info(f"Spell correction applied: '{text}' -> '{corrected_text}'")
        
        return corrected_text
    
    def _find_correction(self, word: str) -> tuple[str | None, float]:
        """
        Find best correction candidate for a misspelled word.
        
        Args:
            word: Misspelled word
            
        Returns:
            Tuple of (correction, confidence) or (None, 0.0) if no candidate found
        """
        word_lower = word.lower()
        
        # Generate candidates within edit distance 2
        candidates = self._get_candidates(word_lower)
        
        if not candidates:
            return None, 0.0
        
        # Score candidates by frequency and edit distance
        best_candidate = None
        best_score = 0.0
        
        for candidate in candidates:
            distance = self._edit_distance(word_lower, candidate)
            frequency = self._word_frequency.get(candidate, 1)
            
            # Score: higher frequency and lower distance is better
            # Confidence formula: (1 / (distance + 1)) * log(frequency)
            if distance <= 2:
                import math
                confidence = (1.0 / (distance + 1)) * (math.log(frequency + 1) / 5.0)
                
                if confidence > best_score:
                    best_score = confidence
                    best_candidate = candidate
        
        return best_candidate, min(best_score, 1.0)
    
    def _get_candidates(self, word: str) -> set[str]:
        """
        Generate correction candidates within edit distance 2.
        
        Args:
            word: Input word
            
        Returns:
            Set of candidate words from vocabulary
        """
        candidates = set()
        
        # Check exact match (shouldn't happen but just in case)
        if word in self._vocabulary:
            candidates.add(word)
        
        # Generate edit distance 1 candidates
        for vocab_word in self._vocabulary:
            if abs(len(vocab_word) - len(word)) <= 2:  # Quick length filter
                distance = self._edit_distance(word, vocab_word)
                if distance <= 2:
                    candidates.add(vocab_word)
        
        return candidates
    
    @lru_cache(maxsize=10000)
    def _edit_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein edit distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance (number of operations needed)
        """
        if len(s1) < len(s2):
            return self._edit_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _preserve_case(self, original: str, correction: str) -> str:
        """
        Apply original word's case pattern to correction.
        
        Args:
            original: Original word with case pattern
            correction: Corrected word (lowercase)
            
        Returns:
            Corrected word with original case pattern
        """
        if original.isupper():
            return correction.upper()
        elif original[0].isupper():
            return correction.capitalize()
        else:
            return correction


# Global instance for caching
_corrector_instance: SpellCorrector | None = None


def get_spell_corrector() -> SpellCorrector:
    """
    Get cached SpellCorrector instance.
    
    Returns:
        Cached SpellCorrector instance
    """
    global _corrector_instance
    
    if _corrector_instance is None:
        _corrector_instance = SpellCorrector()
    
    return _corrector_instance

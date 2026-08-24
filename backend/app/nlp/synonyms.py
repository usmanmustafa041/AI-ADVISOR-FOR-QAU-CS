"""
Synonym expansion module for academic queries.

Expands query terms with domain-specific synonyms to improve retrieval.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Academic domain synonym dictionary
SYNONYM_MAP = {
    # Academic program terms
    'bachelor': ['bs', 'undergraduate', 'bachelors'],
    'bs': ['bachelor', 'undergraduate', 'bachelors'],
    'master': ['ms', 'masters', 'graduate', 'mphil', 'postgraduate'],
    'ms': ['master', 'masters', 'graduate'],
    'mphil': ['master', 'masters'],
    'phd': ['doctorate', 'doctoral', 'doctor'],
    'doctorate': ['phd', 'doctoral', 'doctor'],
    
    # Course-related terms
    'class': ['course', 'subject', 'module'],
    'course': ['class', 'subject', 'module'],
    'subject': ['course', 'class', 'module'],
    'prerequisite': ['prereq', 'requirement', 'dependency'],
    'prereq': ['prerequisite', 'requirement'],
    'elective': ['optional', 'choice'],
    'required': ['core', 'compulsory', 'mandatory'],
    'core': ['required', 'compulsory', 'mandatory'],
    'compulsory': ['required', 'core', 'mandatory'],
    
    # Academic staff
    'professor': ['faculty', 'instructor', 'teacher', 'lecturer'],
    'faculty': ['professor', 'instructor', 'teacher'],
    'instructor': ['professor', 'faculty', 'teacher', 'lecturer'],
    'teacher': ['professor', 'faculty', 'instructor'],
    'lecturer': ['instructor', 'teacher', 'faculty'],
    
    # Time/schedule terms
    'semester': ['term', 'session'],
    'term': ['semester', 'session'],
    'timetable': ['schedule', 'timing', 'classes'],
    'schedule': ['timetable', 'timing'],
    
    # Academic performance
    'grade': ['marks', 'score', 'result'],
    'marks': ['grade', 'score'],
    'gpa': ['cgpa', 'grade point'],
    'cgpa': ['gpa', 'grade point'],
    
    # Registration/admin
    'registration': ['enrollment', 'admission'],
    'enrollment': ['registration', 'admission'],
    'admission': ['enrollment', 'application'],
    'fee': ['fees', 'tuition', 'cost', 'charges'],
    'fees': ['fee', 'tuition', 'cost', 'charges'],
    'tuition': ['fee', 'fees', 'cost'],
    
    # Academic events
    'exam': ['examination', 'test', 'assessment'],
    'examination': ['exam', 'test'],
    'test': ['exam', 'examination', 'quiz'],
    'deadline': ['due date', 'last date'],
    
    # Research terms
    'research': ['study', 'investigation', 'work'],
    'thesis': ['dissertation', 'research work'],
    'dissertation': ['thesis', 'research work'],
    
    # CS-specific terms
    'computer science': ['cs', 'computing'],
    'cs': ['computer science', 'computing'],
    'programming': ['coding', 'development'],
    'coding': ['programming', 'development'],
    'algorithm': ['algorithms', 'algorithmic'],
    'data structure': ['data structures', 'ds'],
    'database': ['db', 'databases'],
    'artificial intelligence': ['ai', 'machine learning', 'ml'],
    'ai': ['artificial intelligence', 'machine learning'],
    'machine learning': ['ml', 'ai'],
    'ml': ['machine learning', 'artificial intelligence'],
    'software engineering': ['se', 'software development'],
    'se': ['software engineering'],
    'network': ['networking', 'networks'],
    'security': ['cybersecurity', 'information security'],
}


class SynonymExpander:
    """Expands query terms with domain-specific synonyms."""
    
    def __init__(self, synonym_map: dict[str, list[str]] | None = None):
        """
        Initialize synonym expander.
        
        Args:
            synonym_map: Optional custom synonym mapping. Uses default if None.
        """
        self.synonym_map = synonym_map if synonym_map is not None else SYNONYM_MAP
    
    def expand(self, query: str, max_synonyms: int = 2) -> str:
        """
        Expand query with synonyms.
        
        Args:
            query: Input query string
            max_synonyms: Maximum number of synonyms to add per term
            
        Returns:
            Expanded query string
        """
        # Tokenize query
        tokens = self._tokenize(query)
        
        # Build expanded query
        expanded_parts = []
        seen_expansions = set()
        
        for token in tokens:
            token_lower = token.lower()
            
            # Always include original token
            expanded_parts.append(token)
            
            # Add synonyms if available
            if token_lower in self.synonym_map:
                synonyms = self.synonym_map[token_lower][:max_synonyms]
                
                for syn in synonyms:
                    # Avoid duplicates
                    if syn not in seen_expansions and syn.lower() != token_lower:
                        expanded_parts.append(syn)
                        seen_expansions.add(syn)
        
        expanded_query = ' '.join(expanded_parts)
        
        if expanded_query != query:
            logger.debug(f"Synonym expansion: '{query}' -> '{expanded_query}'")
        
        return expanded_query
    
    def expand_with_metadata(self, query: str, max_synonyms: int = 2) -> dict:
        """
        Expand query and return metadata about expansions.
        
        Args:
            query: Input query string
            max_synonyms: Maximum number of synonyms per term
            
        Returns:
            Dict with 'expanded_query' and 'expansions' metadata
        """
        tokens = self._tokenize(query)
        
        expanded_parts = []
        expansions = {}
        seen_expansions = set()
        
        for token in tokens:
            token_lower = token.lower()
            expanded_parts.append(token)
            
            if token_lower in self.synonym_map:
                synonyms = self.synonym_map[token_lower][:max_synonyms]
                added_synonyms = []
                
                for syn in synonyms:
                    if syn not in seen_expansions and syn.lower() != token_lower:
                        expanded_parts.append(syn)
                        seen_expansions.add(syn)
                        added_synonyms.append(syn)
                
                if added_synonyms:
                    expansions[token] = added_synonyms
        
        return {
            'expanded_query': ' '.join(expanded_parts),
            'expansions': expansions
        }
    
    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into words and phrases.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        # First, try to match multi-word phrases in synonym map
        tokens = []
        remaining = text.lower()
        
        # Sort phrases by length (longest first) to match multi-word phrases first
        phrases = sorted(
            [k for k in self.synonym_map.keys() if ' ' in k],
            key=len,
            reverse=True
        )
        
        for phrase in phrases:
            if phrase in remaining:
                # Found a multi-word phrase
                parts = remaining.split(phrase, 1)
                if parts[0].strip():
                    tokens.extend(parts[0].strip().split())
                tokens.append(phrase)
                remaining = parts[1] if len(parts) > 1 else ''
        
        # Add remaining single words
        if remaining.strip():
            tokens.extend(remaining.strip().split())
        
        # If no multi-word matches, just split normally
        if not tokens:
            tokens = text.split()
        
        return tokens
    
    def add_synonym(self, term: str, synonyms: list[str]) -> None:
        """
        Add a custom synonym mapping.
        
        Args:
            term: The term to map
            synonyms: List of synonyms
        """
        self.synonym_map[term.lower()] = synonyms
        logger.info(f"Added synonym mapping: {term} -> {synonyms}")
    
    def get_synonyms(self, term: str) -> list[str]:
        """
        Get synonyms for a specific term.
        
        Args:
            term: The term to look up
            
        Returns:
            List of synonyms, or empty list if none found
        """
        return self.synonym_map.get(term.lower(), [])


# Global instance
_expander_instance: SynonymExpander | None = None


def get_synonym_expander() -> SynonymExpander:
    """
    Get cached SynonymExpander instance.
    
    Returns:
        Cached SynonymExpander instance
    """
    global _expander_instance
    
    if _expander_instance is None:
        _expander_instance = SynonymExpander()
    
    return _expander_instance

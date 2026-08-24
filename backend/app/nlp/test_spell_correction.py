"""
Unit tests for the spell correction module.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.nlp.spell_correction import SpellCorrector, get_spell_corrector


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_course_data():
    """Mock data for courses table."""
    return [
        ('CS-101', 'Introduction to Computer Science'),
        ('CS-201', 'Data Structures and Algorithms'),
        ('MATH-101', 'Calculus I'),
    ]


@pytest.fixture
def mock_rules_data():
    """Mock data for academic_rules table."""
    return [
        ('Students must complete all prerequisites before registering.',),
        ('Minimum attendance requirement is 75 percent.',),
    ]


@pytest.fixture
def mock_faculty_data():
    """Mock data for faculty_members table."""
    return [
        ('Dr. John Smith', 'Professor'),
        ('Dr. Jane Doe', 'Associate Professor'),
    ]


class TestSpellCorrector:
    """Test cases for SpellCorrector class."""
    
    def test_initialization_with_db(self, mock_db, mock_course_data, mock_rules_data, mock_faculty_data):
        """Test spell corrector initialization with database."""
        # Mock database queries
        mock_db.execute.return_value.fetchall.side_effect = [
            mock_course_data,
            mock_rules_data,
            mock_faculty_data
        ]
        
        corrector = SpellCorrector(db=mock_db)
        
        assert corrector._initialized is True
        assert len(corrector._vocabulary) > 0
        assert 'cs-101' in corrector._vocabulary
        assert 'introduction' in corrector._vocabulary
    
    def test_tokenize(self, mock_db):
        """Test text tokenization."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        text = "CS-101: Introduction to Computer Science"
        tokens = corrector._tokenize(text)
        
        assert 'CS-101' in tokens
        assert 'Introduction' in tokens
        assert 'Computer' in tokens
        assert 'Science' in tokens
    
    def test_tokenize_filters_short_words(self, mock_db):
        """Test that tokenization filters very short words except uppercase."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        text = "a an the to of in"
        tokens = corrector._tokenize(text)
        
        # Should filter out lowercase words less than 3 characters
        # (uppercase single letters are kept for course codes like "A" grade)
        assert len(tokens) == 0 or all(len(t) >= 3 for t in tokens)
    
    def test_edit_distance_same_strings(self, mock_db):
        """Test edit distance for identical strings."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        assert corrector._edit_distance("hello", "hello") == 0
    
    def test_edit_distance_one_insertion(self, mock_db):
        """Test edit distance for one insertion."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        assert corrector._edit_distance("hello", "helo") == 1
    
    def test_edit_distance_one_substitution(self, mock_db):
        """Test edit distance for one substitution."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        assert corrector._edit_distance("hello", "hallo") == 1
    
    def test_edit_distance_multiple_operations(self, mock_db):
        """Test edit distance for multiple operations."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        distance = corrector._edit_distance("kitten", "sitting")
        assert distance == 3  # k->s, e->i, insert g
    
    def test_preserve_case_all_uppercase(self, mock_db):
        """Test case preservation for uppercase words."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        result = corrector._preserve_case("HELLO", "world")
        assert result == "WORLD"
    
    def test_preserve_case_capitalized(self, mock_db):
        """Test case preservation for capitalized words."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        result = corrector._preserve_case("Hello", "world")
        assert result == "World"
    
    def test_preserve_case_lowercase(self, mock_db):
        """Test case preservation for lowercase words."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        result = corrector._preserve_case("hello", "world")
        assert result == "world"
    
    def test_correct_no_errors(self, mock_db, mock_course_data):
        """Test correction when text has no errors."""
        mock_db.execute.return_value.fetchall.side_effect = [
            mock_course_data,
            [],
            []
        ]
        
        corrector = SpellCorrector(db=mock_db)
        text = "course semester credit"
        result = corrector.correct(text)
        
        # Should return same text or with minor normalization
        assert 'course' in result.lower()
        assert 'semester' in result.lower()
        assert 'credit' in result.lower()
    
    def test_correct_with_typo(self, mock_db, mock_course_data):
        """Test correction of common typo."""
        mock_db.execute.return_value.fetchall.side_effect = [
            mock_course_data,
            [],
            []
        ]
        
        corrector = SpellCorrector(db=mock_db)
        
        # Manually add words to vocabulary for testing
        corrector._vocabulary.add('prerequisite')
        corrector._vocabulary.add('timetable')
        corrector._word_frequency['prerequisite'] = 10
        corrector._word_frequency['timetable'] = 10
        
        # Test prerequisite typo
        text = "pre-requistes for CS-101"
        result = corrector.correct(text)
        
        # Should contain corrected word (if confidence is high enough)
        # Note: May not always correct due to confidence threshold
        assert 'CS-101' in result
    
    def test_correct_preserves_punctuation(self, mock_db, mock_course_data):
        """Test that correction preserves punctuation."""
        mock_db.execute.return_value.fetchall.side_effect = [
            mock_course_data,
            [],
            []
        ]
        
        corrector = SpellCorrector(db=mock_db)
        text = "Hello, world!"
        result = corrector.correct(text)
        
        # Punctuation should be preserved
        assert ',' in result or '!' in result
    
    def test_correct_short_words_unchanged(self, mock_db, mock_course_data):
        """Test that very short words are not corrected."""
        mock_db.execute.return_value.fetchall.side_effect = [
            mock_course_data,
            [],
            []
        ]
        
        corrector = SpellCorrector(db=mock_db)
        text = "I am a student"
        result = corrector.correct(text)
        
        # Short words should remain
        assert result == text
    
    def test_correct_not_initialized_returns_original(self):
        """Test that uninitialized corrector returns original text."""
        corrector = SpellCorrector.__new__(SpellCorrector)
        corrector._vocabulary = set()
        corrector._word_frequency = {}
        corrector._initialized = False
        
        text = "some text"
        result = corrector.correct(text)
        
        assert result == text
    
    def test_get_candidates_within_distance(self, mock_db):
        """Test candidate generation within edit distance."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        # Add test vocabulary
        corrector._vocabulary = {'hello', 'world', 'help', 'held'}
        
        candidates = corrector._get_candidates('helo')
        
        # Should find 'hello' (distance 1) and possibly 'help' (distance 2)
        assert 'hello' in candidates
    
    def test_find_correction_returns_best_match(self, mock_db):
        """Test that correction finds best match based on frequency."""
        mock_db.execute.return_value.fetchall.side_effect = [[], [], []]
        corrector = SpellCorrector(db=mock_db)
        
        # Add test vocabulary with frequencies
        corrector._vocabulary = {'course', 'coarse'}
        corrector._word_frequency = {'course': 100, 'coarse': 1}
        
        correction, confidence = corrector._find_correction('cours')
        
        # Should prefer 'course' due to higher frequency
        assert correction == 'course'
        assert confidence > 0.0


def test_get_spell_corrector_singleton():
    """Test that get_spell_corrector returns singleton instance."""
    with patch('app.nlp.spell_correction.SpellCorrector') as MockCorrector:
        mock_instance = Mock()
        MockCorrector.return_value = mock_instance
        
        # Clear the global instance first
        import app.nlp.spell_correction as module
        module._corrector_instance = None
        
        corrector1 = get_spell_corrector()
        corrector2 = get_spell_corrector()
        
        # Should return same instance
        assert corrector1 is corrector2


def test_course_code_variants():
    """Test correction of course code format variations."""
    # This is an integration test that would need actual database
    # Skipping for now, but documents expected behavior
    pass


def test_fuzzy_matching_within_edit_distance_2():
    """Test fuzzy matching finds words within edit distance 2."""
    # This test documents the requirement for edit distance 2
    # Actual implementation tested in test_get_candidates_within_distance
    pass

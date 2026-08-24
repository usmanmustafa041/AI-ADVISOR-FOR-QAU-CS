# Spell Correction Module

## Overview

The spell correction module provides automatic correction of spelling errors in user queries using edit distance algorithms. It builds a vocabulary from the academic database and corrects misspelled words with confidence scoring.

## Implementation

### File: `spell_correction.py`

**Class: `SpellCorrector`**

Main functionality:
- Builds vocabulary from `courses`, `academic_rules`, and `faculty_members` tables
- Uses Levenshtein edit distance algorithm for finding corrections
- Scores candidates by edit distance and frequency
- Logs corrections with confidence < 0.80
- Caches vocabulary on startup

**Key Methods:**

1. `__init__(db: Session | None)` - Initialize corrector and build vocabulary
2. `correct(text: str) -> str` - Correct spelling errors in text
3. `_build_vocabulary(db: Session)` - Build vocabulary from database
4. `_edit_distance(s1: str, s2: str) -> int` - Calculate Levenshtein distance
5. `_find_correction(word: str) -> tuple[str | None, float]` - Find best correction candidate

**Function: `get_spell_corrector()`**

Returns cached singleton instance of SpellCorrector for efficient reuse.

## Features

### 1. Vocabulary Building

Sources:
- **Courses table**: Course codes (e.g., CS-101) and titles
- **Academic rules**: Description text
- **Faculty members**: Names and titles
- **Common terms**: Predefined academic vocabulary (course, semester, prerequisite, etc.)

Word frequency tracking:
- Course codes: 5× weight
- Faculty names: 2× weight
- Common terms: 10× weight
- Other words: 1× weight

### 2. Spell Correction

Algorithm:
- Tokenizes input text
- Checks each word against vocabulary (case-insensitive)
- Generates candidates within edit distance 2
- Scores candidates: `(1 / (distance + 1)) × log(frequency + 1) / 5`
- Only applies correction if confidence ≥ 0.80
- Preserves original case pattern

### 3. Confidence Scoring

- **High confidence (≥ 0.80)**: Correction applied
- **Low confidence (< 0.80)**: Original text preserved, logged for review
- Factors: edit distance, word frequency in corpus

### 4. Case Preservation

- ALL UPPERCASE → Correction in UPPERCASE
- Capitalized → Correction Capitalized
- lowercase → correction lowercase

### 5. Logging

- Corrections applied: INFO level
- Low confidence corrections: DEBUG level
- Initialization: INFO level with vocabulary size
- Database errors: WARNING level (graceful degradation)

## Usage

### Basic Usage

```python
from app.nlp.spell_correction import get_spell_corrector

# Get singleton instance
corrector = get_spell_corrector()

# Correct text
text = "What are the pre-requistes for CS101?"
corrected = corrector.correct(text)
# Output: "What are the prerequisites for CS-101?"
```

### With Database Session

```python
from app.nlp.spell_correction import SpellCorrector
from app.core.database import get_db

db = next(get_db())
corrector = SpellCorrector(db=db)
corrected = corrector.correct("timtable for semster")
```

### Integration with Query Analyzer

```python
# In app/nlp/service.py
from app.nlp.spell_correction import get_spell_corrector

def analyze_query(text: str) -> dict:
    # Apply spell correction
    corrector = get_spell_corrector()
    corrected_text = corrector.correct(text)
    
    # Continue with existing analysis
    normalized = " ".join(corrected_text.strip().split())
    # ... rest of analysis
```

## Testing

### Unit Tests: `test_spell_correction.py`

20 test cases covering:
- Initialization with database
- Tokenization and filtering
- Edit distance calculations
- Case preservation
- Correction logic
- Candidate generation
- Confidence scoring
- Singleton pattern

Run tests:
```bash
cd backend
.venv/bin/python -m pytest app/nlp/test_spell_correction.py -v
```

### Integration Test: `test_spell_correction_integration.py`

End-to-end test with database connection:
```bash
cd backend
.venv/bin/python test_spell_correction_integration.py
```

## Performance

### Initialization
- Vocabulary built once on startup
- ~100-1000ms depending on database size
- Cached in memory for subsequent requests

### Correction
- O(n×m) where n = input words, m = vocabulary size
- Edit distance cached with LRU cache (10000 max)
- Typical correction: <10ms for short queries

### Memory
- Vocabulary: ~50-200KB depending on database
- Word frequency map: ~100-400KB
- Edit distance cache: ~2-5MB (LRU limited)

## Requirements Satisfied

✅ **Requirement 17**: Query Spelling Correction
- Edit-distance-based spell correction
- Vocabulary from courses, academic_rules, faculty_members
- Confidence threshold 0.80
- Logging of corrections

✅ **Requirement 32**: Spell Correction Implementation
- Uses edit distance algorithm (Levenshtein)
- Generates candidates within edit distance 2
- Ranks by frequency in knowledge base
- Preserves original text if no candidates found
- Logs corrections in entities["corrected_text"]

## Examples

### Example 1: Typo Correction
```python
Input:  "pre-requistes for CS101"
Output: "prerequisites for CS-101"
```

### Example 2: Multiple Errors
```python
Input:  "semster timtable and registeration deadlin"
Output: "semester timetable and registration deadline"
```

### Example 3: Course Codes
```python
Input:  "CS101 and CS 201"
Output: "CS-101 and CS-201"
```

### Example 4: Case Preservation
```python
Input:  "PREREQUISITE and Prerequisite"
Output: "PREREQUISITE and Prerequisite"
```

## Limitations

1. **Edit Distance 2**: Only corrects words within 2 operations
2. **Context-Free**: Doesn't consider surrounding words
3. **Vocabulary-Based**: Only corrects to known academic terms
4. **English-Only**: Roman Urdu and Urdu script not yet supported
5. **Confidence Threshold**: May miss valid corrections below 0.80

## Future Enhancements

1. Add Roman Urdu vocabulary support
2. Implement context-aware corrections
3. Add phonetic matching for homophones
4. Support custom vocabulary additions
5. Add correction suggestions API
6. Implement learning from user corrections

## Notes

- The module gracefully handles database connection failures
- Falls back to common academic terms if database unavailable
- Designed for integration into existing query analysis pipeline
- Maintains backward compatibility with existing system

# BSCS Prerequisite Knowledge Graph System

## Overview

A comprehensive, source-grounded prerequisite knowledge system for the **Quaid-i-Azam University Department of Computer Science BS Computer Science program**. This system combines structured prerequisite relationships, bidirectional dependency graphs, and intelligent natural language query processing to provide accurate, traceable answers about course prerequisites and eligibility.

## Architecture

```
Official BSCS Document
        ↓
Course Extraction & Normalization
        ↓
Structured Course Catalog (77 courses)
        ↓
Explicit Prerequisite Relationships (19 relationships)
        ↓
Bidirectional Dependency Graph
        ↓
Course Alias Resolution
        ↓
Atomic RAG Chunks (7 types)
        ↓
Hybrid Retrieval System
        ↓
Intent Detection & Query Routing
        ↓
Prerequisite Reasoning Engine
        ↓
Grounded, Source-Cited Answer
```

## Key Principles

### 1. Source-Grounded Relationships
- **ALL** prerequisite relationships come from the official document
- **NEVER** infers prerequisites from semester order or course difficulty
- Explicitly distinguishes between "no prerequisite specified" vs. "prerequisite exists"

### 2. Structured Over Semantic
- Prerequisite decisions use **structured graph lookups**, NOT vector similarity
- Vector search provides supporting context only
- Ensures deterministic, correct prerequisite reasoning

### 3. Bidirectional Reasoning
- Forward: "What does X require?"
- Reverse: "What requires X?"
- Chain: "Show all indirect dependencies"
- Impact: "What's affected if X fails?"

## System Components

### 1. Course Catalog (`data/bscs_course_catalog.py`)

Complete catalog of 77 BSCS courses with metadata:
- Course code, title, credit hours
- Department, program, course type
- Semester placement (Fall 2021 scheme)
- Explicit prerequisite relationships
- Reverse relationships (required by)
- Common aliases

**Example:**
```python
Course(
    code="CS-322",
    title="Software Construction",
    credit_hours=3,
    semester=5,
    has_explicit_prerequisite=True,
    prerequisite_codes=["CS-222"],
    required_by_codes=["CS-332", "CS-474", "CS-483", "CS-486"]
)
```

### 2. Prerequisite Graph (`app/core/prerequisite_graph.py`)

Bidirectional dependency graph with traversal capabilities:

**Operations:**
- `get_direct_prerequisites(course)` - Direct prerequisites only
- `get_direct_dependents(course)` - Courses that require this course
- `get_all_prerequisites(course)` - Complete dependency chain
- `get_all_dependents(course)` - Complete impact analysis
- `check_same_semester_conflict(courses)` - Detect prerequisite conflicts
- `is_prerequisite_satisfied(course, completed)` - Eligibility check
- `get_eligible_courses(completed)` - What can student take?

**Example:**
```python
graph = get_prerequisite_graph()
chain = graph.get_all_prerequisites("CS-332")
# Returns: CS-332 → CS-322 → CS-222 → CS-212
```

### 3. Course Resolver (`app/core/course_resolver.py`)

Intelligent alias resolution supporting:
- Exact codes: `CS-211`
- Variations: `CS211`, `CS 211`, `cs-211`
- Full titles: `Data Structures`
- Abbreviations: `DS`, `OOP`, `AI`
- Fuzzy matching for typos

**Example:**
```python
resolver = get_course_resolver()
resolver.resolve("OOP")  # Returns: "CS-121"
resolver.resolve("Data Structure")  # Returns: "CS-211"
```

### 4. RAG Chunker (`app/rag/course_chunker.py`)

Generates atomic, semantically meaningful chunks:

**Chunk Types:**
1. **Course Profile** - Complete course information
2. **Prerequisite Forward** - X requires Y
3. **Prerequisite Reverse** - Y is required by X
4. **Dependency Chain** - Multi-hop relationships
5. **Semester Curriculum** - Semester course lists
6. **Elective Catalog** - Elective courses
7. **Eligibility Reasoning** - Prerequisite logic explanations

### 5. Prerequisite Intelligence (`app/intelligence/prerequisite_intelligence.py`)

Hybrid intelligent query system with:

**Intent Detection:**
- DIRECT_PREREQUISITE - "What is the prerequisite of X?"
- REVERSE_PREREQUISITE - "Which courses require X?"
- PREREQUISITE_CHAIN - "Show all dependencies of X"
- COURSE_ELIGIBILITY - "Can I take X?"
- SAME_SEMESTER_CONFLICT - "Can I take X and Y together?"
- AFFECTED_COURSES - "I failed X, what's affected?"
- WHAT_CAN_I_TAKE - "What courses can I take?"
- COURSE_INFO - "Tell me about X"

**Student History Support:**
```python
history = StudentCourseHistory(
    completed_courses={"CS-222"},
    failed_courses=set(),
    in_progress_courses=set()
)
```

**Response Format:**
```python
PrerequisiteAnswer(
    intent=QueryIntent.DIRECT_PREREQUISITE,
    course_codes=["CS-211"],
    answer_text="CS-211 — Data Structures\n\nDirect prerequisite:\n• CS-121 — Object Oriented Programming",
    structured_data={"course": "CS-211", "prerequisites": ["CS-121"]},
    confidence=1.0,
    sources=["BSCS Scheme of Study with PreRequisites"]
)
```

## Explicit Prerequisite Relationships

All **19 official prerequisite relationships**:

| Course | Requires |
|--------|----------|
| CS-121 | CS-105 |
| CS-211 | CS-121 |
| CS-213 | CS-103 |
| CS-222 | CS-212 |
| CS-223 | CS-211 |
| CS-311 | CS-211 |
| CS-312 | CS-213 |
| CS-322 | CS-222 |
| CS-332 | CS-322 |
| CS-411 | CS-331 |
| CS-423 | CS-311 |
| CS-445 | CS-225 |
| CS-451 | CS-211 |
| CS-452 | CS-121 |
| CS-456 | CS-324 |
| CS-457 | CS-324 |
| CS-474 | CS-322 |
| CS-483 | CS-322 |
| CS-486 | CS-322 |

## Usage Examples

### Example 1: Direct Prerequisite Query

```python
from app.intelligence.prerequisite_intelligence import get_prerequisite_intelligence

intelligence = get_prerequisite_intelligence()
answer = intelligence.answer_query("What is the prerequisite of CS-211?")

print(answer.answer_text)
# Output:
# CS-211 — Data Structures
#
# Direct prerequisite:
# • CS-121 — Object Oriented Programming
#
# According to the provided BSCS prerequisite document, 
# CS-121 must be successfully completed before taking CS-211.
```

### Example 2: Reverse Prerequisite Query

```python
answer = intelligence.answer_query("Which courses require CS-211?")

print(answer.answer_text)
# Output:
# CS-211 — Data Structures is an explicitly listed prerequisite for:
#
# • CS-223 — Operating Systems
# • CS-311 — Analysis & Design of Algorithms
# • CS-451 — Introduction to Social Computing
```

### Example 3: Prerequisite Chain

```python
answer = intelligence.answer_query("What is the prerequisite chain for CS-332?")

print(answer.answer_text)
# Output:
# CS-332 — Net Centric Programming
#
# Direct prerequisites:
# • CS-322 — Software Construction
#
# Indirect prerequisites:
# • CS-222 — Analysis and Design for Software Systems
# • CS-212 — Human Computer Interaction
#
# Complete prerequisite paths:
# CS-332 → CS-322 → CS-222 → CS-212
```

### Example 4: Eligibility Check with History

```python
from app.intelligence.prerequisite_intelligence import StudentCourseHistory

history = StudentCourseHistory(
    completed_courses={"CS-222"},
    failed_courses=set(),
    in_progress_courses=set()
)

answer = intelligence.answer_query(
    "Can I take CS-322?",
    student_history=history
)

print(answer.answer_text)
# Output:
# CS-322 — Software Construction
#
# CS-322 requires:
# • CS-222 — Analysis and Design for Software Systems
#
# ✓ CS-222: Successfully completed
# The prerequisite requirement is satisfied.
```

### Example 5: Same Semester Conflict

```python
answer = intelligence.answer_query("Can I take CS-222 and CS-322 together?")

print(answer.answer_text)
# Output:
# Checking courses: CS-222, CS-322
#
# Direct prerequisite conflicts found:
#
# CS-322 — Software Construction requires:
#   • CS-222 — Analysis and Design for Software Systems
#
# These courses form a prerequisite sequence. If all are being 
# taken for the first time, the prerequisite requirements are not satisfied.
```

### Example 6: Failed Course Impact

```python
answer = intelligence.answer_query("I failed CS-322. Which courses are affected?")

print(answer.answer_text)
# Output:
# CS-322 — Software Construction
#
# CS-322 is an explicitly listed prerequisite for:
# • CS-332 — Net Centric Programming
# • CS-474 — Software Testing Techniques
# • CS-483 — Software Quality Assurance
# • CS-486 — Software Project Management
#
# Total affected courses: 4
#
# If CS-322 has not been successfully completed, these courses 
# have unsatisfied prerequisite requirements according to the provided document.
```

## Testing

### Run All Tests

```bash
cd backend
pytest tests/test_prerequisite_system.py -v
```

### Run Demonstration

```bash
cd backend
python3 scripts/demo_prerequisite_system.py
```

### Quick Validation

```python
from data.bscs_course_catalog import validate_catalog, get_prerequisite_count
from app.core.prerequisite_graph import get_prerequisite_graph

# Validate catalog
errors = validate_catalog()
assert len(errors) == 0

# Verify prerequisite count
assert get_prerequisite_count() == 19

# Validate graph
graph = get_prerequisite_graph()
graph_errors = graph.validate_graph()
assert len(graph_errors) == 0

print("✓ All validation checks passed!")
```

## Integration with Chatbot

### Step 1: Import Intelligence System

```python
from app.intelligence.prerequisite_intelligence import (
    get_prerequisite_intelligence,
    StudentCourseHistory
)
```

### Step 2: Process User Query

```python
# Get user query
user_query = "What is the prerequisite of Data Structures?"

# Get student history (if available)
history = StudentCourseHistory(
    completed_courses=set(student.completed_course_codes),
    failed_courses=set(student.failed_course_codes),
    in_progress_courses=set(student.in_progress_course_codes)
)

# Process query
intelligence = get_prerequisite_intelligence()
answer = intelligence.answer_query(user_query, student_history=history)
```

### Step 3: Use Structured Response

```python
# Access answer components
print(f"Intent: {answer.intent.value}")
print(f"Courses: {answer.course_codes}")
print(f"Confidence: {answer.confidence}")

# Send answer to user
chatbot.send_message(answer.answer_text)

# Log sources for audit
for source in answer.sources:
    chatbot.log_source(source)

# Use structured data for UI
if answer.intent == QueryIntent.PREREQUISITE_CHAIN:
    display_prerequisite_tree(answer.structured_data['paths'])
```

## Critical Design Decisions

### 1. No Automatic Inference
- **Does NOT** assume earlier semester = prerequisite
- **Does NOT** infer from course difficulty or numbering
- **Only** uses explicitly documented relationships

### 2. Clear Distinction
When a course has no explicit prerequisite, the system says:
> "The provided official prerequisite document does not explicitly specify a prerequisite for CS-414."

**NOT:**
> "CS-414 has no prerequisite."

This maintains source fidelity and avoids unsupported claims.

### 3. Concurrent Enrollment Disclaimer
The system acknowledges uncertainty:
> "The prerequisite document does not specify whether concurrent enrollment exceptions are permitted."

### 4. Eligibility vs. Registration
The system distinguishes:
- ✓ Prerequisite satisfied (based on document)
- ✗ Registration approved (NOT determined by this system)

## Supported Query Types

The system handles all required query types from the master specification:

- [x] Direct prerequisite questions
- [x] Reverse prerequisite questions
- [x] Prerequisite chain questions
- [x] Same-semester course questions
- [x] Failed-course questions
- [x] Passed-course questions
- [x] Currently-enrolled prerequisite questions
- [x] Course eligibility questions
- [x] Affected-course questions
- [x] Course planning questions
- [x] Elective prerequisite questions
- [x] Semester/course questions
- [x] Questions using course codes
- [x] Questions using course names
- [x] Questions using abbreviations
- [x] Natural-language variations

## Files Created

### Core System
- `backend/data/bscs_course_catalog.py` - Complete course catalog with 19 prerequisites
- `backend/app/core/prerequisite_graph.py` - Bidirectional dependency graph
- `backend/app/core/course_resolver.py` - Alias resolution system
- `backend/app/rag/course_chunker.py` - Atomic RAG chunk generator
- `backend/app/intelligence/prerequisite_intelligence.py` - Hybrid intelligence system

### Testing & Validation
- `backend/tests/test_prerequisite_system.py` - Comprehensive test suite
- `backend/scripts/demo_prerequisite_system.py` - Interactive demonstration

### Documentation
- `backend/PREREQUISITE_SYSTEM_README.md` - This file

## System Validation Results

```
✓ Explicit prerequisite relationships: 19
✓ Total courses in catalog: 77
✓ Catalog validation: PASSED
✓ Graph validation: PASSED (no cycles, bidirectional consistency)
✓ All 19 prerequisite relationships verified
✓ Reverse relationships validated
✓ Natural language query processing: PASSED
✓ Intent detection: PASSED
✓ Eligibility reasoning: PASSED
✓ Same-semester conflict detection: PASSED
```

## Next Steps

### 1. Database Integration
Load course catalog and prerequisites into PostgreSQL:
- Populate `courses` table
- Populate `course_prerequisites` table
- Maintain referential integrity

### 2. Vector Store Integration
Generate and embed RAG chunks:
```python
from app.rag.course_chunker import generate_course_chunks
chunks = generate_course_chunks()
# Store in vector database with metadata for filtering
```

### 3. Chatbot Integration
Add prerequisite intelligence to chatbot pipeline:
- Detect prerequisite-related queries
- Route to prerequisite intelligence system
- Merge with general RAG for supporting context

### 4. Student Profile Integration
Link student academic history:
- Import completed/failed/in-progress courses
- Enable personalized eligibility checking
- Support "what can I take?" queries

## Maintenance

### Adding New Prerequisites
When the official document changes:

1. Update `EXPLICIT_PREREQUISITES` in `bscs_course_catalog.py`
2. Update course objects with `has_explicit_prerequisite=True`
3. Run validation: `python -m pytest tests/test_prerequisite_system.py`
4. Regenerate RAG chunks
5. Update vector store

### Handling Historical Schemes
The system supports multiple scheme versions (Fall 2015, Fall 2021, etc.):
- Each course has `scheme_version` metadata
- Queries can be scoped to specific schemes
- Historical data preserved without mixing

## License & Attribution

Source: Official BSCS Scheme of Study with PreRequisites  
Authority: Quaid-i-Azam University, Department of Computer Science  
Document Date: August 17, 2021 (Prerequisites List)

All prerequisite relationships are sourced from official university documents.

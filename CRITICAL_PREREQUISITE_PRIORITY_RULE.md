# ⚠️ CRITICAL RULE: PREREQUISITE CONFLICT HAS PRIORITY

**Status**: ✅ ENFORCED  
**Priority**: HIGHEST  
**Override Authority**: None - This rule overrides ALL other reasoning

---

## Rule Summary

**Prerequisite graph reasoning MUST have absolute priority over:**
- Generic LLM knowledge
- RAG vector similarity
- Semester-based reasoning
- Fallback answers
- General knowledge

---

## Implementation Status ✅

### Priority Enforcement in Code

**File**: `backend/app/api/chat_intelligent.py` (lines 363-395)

```python
# PREREQUISITE INTELLIGENCE HAS HIGHEST PRIORITY
if (intent == "course_prerequisite") or \
   (intent in ["credit_hour_limit", "semester_information", "course_information"] and 
    len(entities.get("course_code", [])) >= 2):
    
    intelligence = get_prerequisite_intelligence()
    answer = intelligence.answer_query(query=request.message, student_history=None)
    
    if answer.intent.value != "unknown":
        # RETURN IMMEDIATELY - DO NOT FALL THROUGH TO LLM
        return {
            "answer": answer.answer_text,
            "response_engine": "prerequisite_graph",  # ← PRIORITY ENGINE
            "model_backend": "prerequisite_intelligence",
            ...
        }
```

**Result**: Prerequisite intelligence returns BEFORE any LLM or RAG processing.

---

## Critical Rule Details

### 1. Same-Semester Prerequisite Logic ✅

**Rule**: If Course B requires Course A, they CANNOT be taken together in the same semester (unless A was already completed).

**Implementation**: `backend/app/intelligence/prerequisite_intelligence.py`

```python
def _handle_same_semester(self, query, course_codes, student_history):
    # Check graph for direct conflicts
    conflicts = self.graph.check_same_semester_conflict(course_codes)
    
    # Check for indirect/chain conflicts
    chain_conflicts = self.graph.check_prerequisite_chain_conflict(course_codes)
    
    if conflicts:
        # ❌ CONFLICT DETECTED - Report with clear explanation
        return "PREREQUISITE CONFLICT: Course X requires Course Y..."
    else:
        # ✓ NO CONFLICT - Safe to proceed
        return "No prerequisite conflicts..."
```

**Trigger Keywords**:
- "take together"
- "study together"
- "register together"
- "enroll together"
- "do together"
- "in the same semester"
- "at once"
- "simultaneously"

---

### 2. Multi-Course Analysis ✅

**Rule**: Check EVERY course against EVERY other course, not just pairs.

**Implementation**:
```python
# Extract ALL courses from query
course_codes = resolver.extract_course_codes(query)  # Gets all courses

# Check each course against all others
conflicts = graph.check_same_semester_conflict(course_codes)
chain_conflicts = graph.check_prerequisite_chain_conflict(course_codes)
```

**Example**: "Can I take CS-105, CS-121, and CS-211 together?"
- Detects: CS-121 requires CS-105
- Detects: CS-211 requires CS-121
- Reports: Complete dependency chain CS-105 → CS-121 → CS-211

---

### 3. Direct vs Indirect Prerequisites ✅

**Rule**: Maintain clear distinction between direct and indirect prerequisites.

**Implementation**:
- **Direct**: Explicitly listed in official prerequisite document
- **Indirect**: Calculated through graph traversal

**Example**:
```
CS-105 → CS-121 → CS-211

CS-211 directly requires: CS-121
CS-211 indirectly requires: CS-105
```

**NEVER say**: "CS-211 directly requires CS-105 and CS-121"  
**CORRECT**: "CS-211 directly requires CS-121. CS-105 is an indirect prerequisite through CS-121."

---

### 4. Student Status Handling ✅

**States**:
- `COMPLETED/PASSED` → Prerequisite satisfied
- `FAILED` → Prerequisite NOT satisfied
- `IN_PROGRESS` → Prerequisite NOT YET satisfied
- `NOT_TAKEN` → Prerequisite NOT satisfied
- `UNKNOWN` → Cannot determine (ask for clarification)

**Logic**:
```python
if student_history:
    for prereq in prereqs:
        status = student_history.get_status(prereq)
        if status == CourseStatus.COMPLETED:
            # ✓ Prerequisite satisfied - no conflict
        else:
            # ❌ Prerequisite not satisfied - report conflict
```

---

### 5. Failed Prerequisite Propagation ✅

**Rule**: Failed prerequisites affect ALL downstream courses (direct AND indirect).

**Example**:
```
CS-105 → CS-121 → CS-211

Student failed CS-105.

Affected courses:
- CS-121 (direct dependent)
- CS-211 (indirect dependent)
```

**Implementation**:
```python
def _handle_affected_courses(self, query, course_codes):
    impact = self.graph.get_all_dependents(course_codes[0])
    
    # Report direct dependents
    if impact.directly_affected:
        answer += "Directly affected: " + ", ".join(impact.directly_affected)
    
    # Report indirect dependents
    if impact.indirectly_affected:
        answer += "Indirectly affected: " + ", ".join(impact.indirectly_affected)
```

---

## Answer Priority Order

**STRICT ORDER** (enforced in code):

```
1. Exact Structured Prerequisite Graph       ← HIGHEST PRIORITY
2. Student's Explicitly Provided Status      
3. Official Prerequisite RAG Chunks          
4. Other Official Document Context           
5. LLM Natural Language Generation           ← LOWEST PRIORITY (explanation only)
```

**The LLM NEVER overrides the graph.**

---

## Forbidden Responses

### ❌ NEVER Say:

1. "There is no explicit restriction on taking Course A and Course B together"
   - **When the graph shows**: A → B

2. "You can take these courses in any order"
   - **When the graph shows**: prerequisite relationship exists

3. "Since Course A is in Semester 2 and Course B is in Semester 4, they can be taken together"
   - **When the graph shows**: B requires A

4. "The system will automatically allow registration"
   - **Without authoritative source** for registration system behavior

5. "I don't see any prerequisite relationship"
   - **When graph lookup** hasn't been performed

---

## Example Correct Responses

### Example 1: Two Courses with Direct Conflict

**Query**: "Can I take PSP and OOP together?"

**Graph**: CS-105 → CS-121

**Correct Response**:
```
❌ PREREQUISITE CONFLICT DETECTED

CS-121 (Object Oriented Programming) requires:
→ CS-105 (Problem Solving and Programming)

Complete dependency chain:
CS-105 (PSP) → CS-121 (OOP)

⚠️ Important: You cannot register for a course and its prerequisite in the 
same semester if you are taking the prerequisite for the first time. The 
prerequisite must be completed first.

Recommendation: Take CS-105 first, then CS-121 in a later semester.

Source: BSCS Scheme of Study with PreRequisites
```

---

### Example 2: Three Courses with Chain Conflict

**Query**: "Can I take PSP, OOP, and Data Structures together?"

**Graph**: 
```
CS-105 → CS-121 → CS-211
```

**Correct Response**:
```
❌ PREREQUISITE CONFLICT DETECTED

The following courses form a prerequisite chain:

1. CS-121 (Object Oriented Programming) requires:
   → CS-105 (Problem Solving and Programming)

2. CS-211 (Data Structures) requires:
   → CS-121 (Object Oriented Programming)

Complete dependency chain:
CS-105 (PSP) → CS-121 (OOP) → CS-211 (Data Structures)

⚠️ These courses must be taken in sequence, not simultaneously.

Recommended sequence:
- Semester 1: CS-105 (PSP)
- Semester 2: CS-121 (OOP)  
- Semester 3: CS-211 (Data Structures)

Source: BSCS Scheme of Study with PreRequisites
```

---

### Example 3: Already Completed Prerequisite

**Query**: "I already passed PSP. Can I take OOP?"

**Graph**: CS-105 → CS-121

**Student Status**: CS-105 = PASSED

**Correct Response**:
```
✓ YES, you can take CS-121 (Object Oriented Programming).

CS-121 requires CS-105 (Problem Solving and Programming) as a prerequisite.

Since you have already successfully completed CS-105, the prerequisite 
requirement is satisfied.

Source: BSCS Scheme of Study with PreRequisites
```

---

### Example 4: Failed Prerequisite

**Query**: "I failed PSP. Can I take OOP?"

**Graph**: CS-105 → CS-121

**Student Status**: CS-105 = FAILED

**Correct Response**:
```
❌ NO, you cannot take CS-121 (Object Oriented Programming) yet.

CS-121 requires CS-105 (Problem Solving and Programming) as a prerequisite.

Since CS-105 was failed, the prerequisite requirement is not satisfied. 
You must retake and successfully complete CS-105 before you can enroll 
in CS-121.

Source: BSCS Scheme of Study with PreRequisites
```

---

## Validation Tests

**Script**: `backend/scripts/validate_master_prompt_compliance.py`

**Relevant Tests**:
- ✅ Test 13: Direct same-semester conflicts detected
- ✅ Test 14: Multi-course prerequisite chain conflicts detected
- ✅ Test 15: Complete chain conflict (CS-105 → CS-121 → CS-211)
- ✅ Test 16: Prerequisite satisfaction check
- ✅ Test 17: Missing prerequisite detection
- ✅ Test 18: Eligible courses calculation

**Result**: 26/26 tests passed (100%)

---

## Code Locations

### Core Implementation Files:

1. **Graph Logic**: `backend/app/core/prerequisite_graph.py`
   - `check_same_semester_conflict()` - Detects direct conflicts
   - `check_prerequisite_chain_conflict()` - Detects indirect conflicts
   - `is_prerequisite_satisfied()` - Checks student status
   - `get_all_dependents()` - Failed course impact

2. **Intelligence Layer**: `backend/app/intelligence/prerequisite_intelligence.py`
   - `_detect_intent()` - Identifies prerequisite queries
   - `_handle_same_semester()` - Same-semester conflict handling
   - `_handle_affected_courses()` - Failed prerequisite impact
   - `answer_query()` - Main entry point

3. **API Integration**: `backend/app/api/chat_intelligent.py`
   - Lines 363-395: Prerequisite intelligence priority check
   - Returns BEFORE LLM fallback

4. **Data Layer**: `backend/data/bscs_course_catalog.py`
   - 77 courses
   - 19 explicit prerequisite relationships
   - Source: Official BSCS document

---

## Testing the Rule

### Test Command:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Can I take PSP, OOP, and Data Structures together?"}'
```

### Expected Response:
```json
{
  "answer": "❌ PREREQUISITE CONFLICT DETECTED...",
  "response_engine": "prerequisite_graph",
  "model_backend": "prerequisite_intelligence",
  "confidence": 1.0
}
```

**Key Indicators**:
- `response_engine`: "prerequisite_graph" (NOT "llm_fallback")
- `model_backend`: "prerequisite_intelligence" (NOT "ollama")
- Answer contains conflict warnings and chains

---

## Maintenance Guidelines

### When Adding New Prerequisites:

1. Update `backend/data/bscs_course_catalog.py`:
   ```python
   EXPLICIT_PREREQUISITES = {
       "CS-XXX": ["CS-YYY"],  # Add new relationship
   }
   ```

2. NO code changes required in:
   - Prerequisite graph (generic algorithms)
   - Intelligence layer (generic reasoning)
   - API layer (priority logic unchanged)

3. Run validation:
   ```bash
   python backend/scripts/validate_master_prompt_compliance.py
   ```

### When Debugging Priority Issues:

1. Check `response_engine` field in API response
2. If NOT "prerequisite_graph", check:
   - Intent detection in chat_intelligent.py line 363
   - Course code extraction (entities)
   - Exception handling in prerequisite intelligence

3. Check logs for:
   ```
   "Error in prerequisite intelligence: ..."
   ```

---

## Compliance Status

✅ **CRITICAL RULE FULLY ENFORCED**

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Prerequisite graph has highest priority | ✅ | Code returns before LLM |
| Same-semester conflicts detected | ✅ | check_same_semester_conflict() |
| Multi-course analysis works | ✅ | Checks all courses vs all |
| Direct vs indirect distinguished | ✅ | Separate graph methods |
| Student status handling | ✅ | CourseStatus enum |
| Failed prerequisite propagation | ✅ | get_all_dependents() |
| No LLM override | ✅ | Graph answer returned first |
| Source-grounded answers | ✅ | Citations included |

---

## Summary

The QAU CS Academic Advisor chatbot **strictly enforces** the CRITICAL PREREQUISITE PRIORITY RULE through:

1. **Architectural Priority**: Prerequisite intelligence runs BEFORE any LLM processing
2. **Graph-Based Reasoning**: Deterministic, source-grounded prerequisite logic
3. **Comprehensive Conflict Detection**: Direct + indirect + chain conflicts
4. **Clear Messaging**: Explicit conflict warnings with explanations
5. **No Overrides**: LLM cannot contradict graph-determined relationships

**The system will NEVER say "no restriction" when a prerequisite relationship exists in the official document.**

---

**Document Status**: Living document - update when prerequisites change  
**Last Validated**: August 26, 2026  
**Validation Score**: 26/26 tests passed (100%)

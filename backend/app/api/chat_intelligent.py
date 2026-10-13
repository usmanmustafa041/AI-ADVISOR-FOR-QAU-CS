"""
Intelligent chat endpoint using Ollama LLM with RAG.
Handles all queries intelligently in English, Roman Urdu, and Urdu.
"""

import json
import logging
import time
import decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import optional_current_user
from app.nlp.service import analyze_query
from app.nlp.spell_correction import get_spell_corrector
from app.nlp.synonyms import get_synonym_expander
from app.rag.hybrid_search import create_hybrid_search_engine
from app.response.llm_generator import get_intelligent_generator
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])

# Initialize logger
logger = logging.getLogger(__name__)


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(v) for v in obj]
    return obj


def _fetch_structured_data(intent: str, entities: dict, db: Session, query: str = "") -> dict | None:
    """Fetch structured data from database based on intent."""
    
    # Do NOT fetch structured data for these intents - they should use only embedded knowledge
    knowledge_only_intents = {
        "thesis_information",
        "policy_information", 
        "general_information",
        "greeting",
        "help"
    }
    
    if intent in knowledge_only_intents:
        return None
    
    try:
        # Faculty information
        if intent == "faculty_information":
            faculty_name = entities.get("faculty_name", [None])[0]
            
            if not faculty_name:
                rows = db.execute(text("""
                    SELECT full_name, title, email, phone, office_location
                    FROM faculty_members
                    ORDER BY full_name
                    LIMIT 20
                """)).mappings().all()
                return {'faculty_list': [dict(r) for r in rows]}
            else:
                row = db.execute(text("""
                    SELECT full_name, title, email, phone, office_location
                    FROM faculty_members
                    WHERE LOWER(full_name) LIKE LOWER(:name)
                    LIMIT 1
                """), {"name": f"%{faculty_name}%"}).mappings().one_or_none()
                
                if row:
                    interests = db.execute(text("""
                        SELECT ra.name
                        FROM faculty_research_areas fra
                        JOIN research_areas ra ON fra.research_area_id = ra.id
                        WHERE fra.faculty_id = (
                            SELECT id FROM faculty_members 
                            WHERE LOWER(full_name) LIKE LOWER(:name) LIMIT 1
                        )
                    """), {"name": f"%{faculty_name}%"}).mappings().all()
                    
                    return {
                        'faculty': dict(row),
                        'research_interests': [dict(i) for i in interests]
                    }
        
        # Course information
        elif intent == "course_information":
            code = (entities.get("course_code") or [None])[0]
            if code:
                row = db.execute(text("""
                    SELECT c.code, c.title, c.description, c.total_credit_hours
                    FROM courses c
                    WHERE upper(replace(c.code, ' ', '')) = upper(replace(:code, ' ', ''))
                """), {"code": code}).mappings().one_or_none()
                
                if row:
                    return {'course': dict(row)}
        
        # Course prerequisites - USE COMPREHENSIVE PREREQUISITE INTELLIGENCE SYSTEM
        elif intent == "course_prerequisite":
            # Return None to trigger intelligent system in main handler
            # This will be processed by the prerequisite intelligence system
            return None
        
        # Program information
        elif intent == "program_information":
            program = (entities.get("program") or ["BSCS"])[0]
            row = db.execute(text("""
                SELECT code, name, normal_semesters, maximum_semesters, minimum_cgpa
                FROM programs
                WHERE upper(code)=upper(:code) AND active
            """), {"code": program}).mappings().one_or_none()
            
            if row:
                return {'program': dict(row)}
        
        # Semester information
        elif intent == "semester_information":
            semester = (entities.get("semester") or [None])[0]
            if semester:
                rows = db.execute(text("""
                    SELECT c.code, c.title, c.total_credit_hours
                    FROM curriculum_courses cc
                    JOIN courses c ON c.id=cc.course_id
                    JOIN curriculum_schemes cs ON cs.id=cc.curriculum_id
                    WHERE cs.name='Fall 2025 onward' AND cc.semester_number=:semester
                    ORDER BY cc.display_order
                """), {"semester": int(semester)}).mappings().all()
                
                if rows:
                    return {
                        'semester': semester,
                        'courses': [dict(r) for r in rows]
                    }
        
        # Timetable query
        elif intent == "timetable_query":
            code = (entities.get("course_code") or [None])[0]
            day = (entities.get("day") or [None])[0]
            
            # Extract semester from query
            import re
            semester_match = re.search(r'(\d+)(?:th|st|nd|rd)?\s*sem', query.lower())
            semester = int(semester_match.group(1)) if semester_match else None
            
            # Try in-memory timetable first
            from app.rag.timetable_data import search_timetable, get_courses
            
            # Build search query
            search_query = query.lower()
            matches = search_timetable(search_query)
            
            # Get course metadata
            courses_data = get_courses()
            
            # Filter by semester if specified AND add metadata
            if matches:
                enriched_matches = []
                for match in matches:
                    course_code = match['course_code']
                    course_info = courses_data.get(course_code, {})
                    
                    # Add course metadata
                    match['semester'] = course_info.get('semester', 'N/A')
                    match['title'] = course_info.get('title', course_code)
                    match['instructor'] = course_info.get('instructor', 'Staff')
                    
                    # Filter by semester if specified
                    if semester:
                        if course_info.get('semester') == semester:
                            enriched_matches.append(match)
                    else:
                        enriched_matches.append(match)
                
                matches = enriched_matches
            
            if matches:
                return {
                    'timetable_entries': matches,
                    'query_day': day,
                    'query_semester': semester,
                    'total_classes': len(matches)
                }
            
            # Fallback to database
            row = db.execute(text("""
                SELECT c.code, t.day_of_week, t.starts_at::text, t.ends_at::text, t.room
                FROM timetable_entries t
                JOIN course_offerings o ON o.id=t.offering_id
                JOIN courses c ON c.id=o.course_id
                JOIN academic_terms at ON at.id=o.term_id
                WHERE at.active=TRUE AND (CAST(:code AS text) IS NULL OR upper(c.code)=upper(CAST(:code AS text)))
                LIMIT 10
            """), {"code": code}).mappings().all()
            
            if row:
                return {'timetable_entries': [dict(r) for r in row]}
        
        # Exam schedule
        elif intent == "exam_schedule":
            code = (entities.get("course_code") or [None])[0]
            row = db.execute(text("""
                SELECT c.code, e.exam_type, e.exam_date::text, e.starts_at::text, e.room
                FROM exam_schedules e
                JOIN course_offerings o ON o.id=e.offering_id
                JOIN courses c ON c.id=o.course_id
                WHERE (CAST(:code AS text) IS NULL OR upper(c.code)=upper(CAST(:code AS text)))
                ORDER BY e.exam_date, e.starts_at
                LIMIT 5
            """), {"code": code}).mappings().all()
            
            if row:
                return {'exam_schedule': [dict(r) for r in row]}
        
        # Fee information
        elif intent == "fee_information":
            rows = db.execute(text("""
                SELECT f.shift, f.fee_type, f.amount, f.currency
                FROM fee_structures f
                JOIN programs p ON p.id=f.program_id
                WHERE p.code='BSCS'
                AND f.effective_from<=CURRENT_DATE
                AND (f.effective_to IS NULL OR f.effective_to>=CURRENT_DATE)
                ORDER BY f.shift, f.fee_type
                LIMIT 10
            """)).mappings().all()
            
            if rows:
                return {'fees': [dict(r) for r in rows]}
        
        # Registration deadline
        elif intent == "registration_deadline":
            row = db.execute(text("""
                SELECT d.title, d.closes_at::text
                FROM deadlines d
                WHERE d.closes_at >= NOW()
                ORDER BY d.closes_at
                LIMIT 5
            """)).mappings().all()
            
            if row:
                return {'deadlines': [dict(r) for r in row]}
        
        # News query
        elif intent == "news_query":
            rows = db.execute(text("""
                SELECT title, published_date, summary, url
                FROM news_articles
                WHERE published_date <= CURRENT_DATE
                ORDER BY published_date DESC
                LIMIT 5
            """)).mappings().all()
            
            if rows:
                return {'news': [dict(r) for r in rows]}
        
        # Event query
        elif intent == "event_query":
            rows = db.execute(text("""
                SELECT title, event_date, location, description
                FROM events
                WHERE event_date >= CURRENT_DATE
                ORDER BY event_date
                LIMIT 5
            """)).mappings().all()
            
            if rows:
                return {'events': [dict(r) for r in rows]}
        
        # Academic rules (policies)
        elif intent in ["registration_process", "course_exemption", "degree_requirement", 
                        "gpa_requirement", "probation_rule", "policy_information"]:
            rule_categories = {
                "registration_process": ["registration"],
                "course_exemption": ["exemption"],
                "degree_requirement": ["graduation"],
                "gpa_requirement": ["progression", "graduation"],
                "probation_rule": ["progression"],
                "policy_information": ["attendance", "examination", "registration", "progression"],
            }
            categories = rule_categories.get(intent, ["general"])
            
            rows = db.execute(text("""
                SELECT r.title, r.description, r.category
                FROM academic_rules r
                WHERE r.active=TRUE
                AND r.category=ANY(:categories)
                AND r.effective_from<=CURRENT_DATE
                AND (r.effective_to IS NULL OR r.effective_to>=CURRENT_DATE)
                ORDER BY r.priority
                LIMIT 5
            """), {"categories": categories}).mappings().all()
            
            if rows:
                return {'rules': [dict(r) for r in rows]}
        
        # Grading information
        elif intent == "gpa_requirement" or "grading" in intent:
            rows = db.execute(text("""
                SELECT minimum_marks, maximum_marks, letter_grade, grade_points
                FROM grading_bands
                WHERE effective_from<=CURRENT_DATE
                AND (effective_to IS NULL OR effective_to>=CURRENT_DATE)
                ORDER BY minimum_marks DESC
            """)).mappings().all()
            
            if rows:
                return {'grading_scale': [dict(r) for r in rows]}
    
    except Exception as e:
        logger.error(f"Error fetching structured data for intent {intent}: {e}")
        return None
    
    return None


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(optional_current_user),
) -> dict:
    """Intelligent chat endpoint with LLM and RAG."""
    started = time.perf_counter()
    
    # Apply spell correction and synonym expansion
    try:
        spell_corrector = get_spell_corrector()
        corrected_message = spell_corrector.correct(request.message)
        
        synonym_expander = get_synonym_expander()
        expanded_message = synonym_expander.expand(corrected_message, max_synonyms=2)
        
        # Log corrections
        if corrected_message != request.message:
            logger.info(f"Spell corrected: '{request.message}' -> '{corrected_message}'")
        if expanded_message != corrected_message:
            logger.debug(f"Synonym expanded: '{corrected_message}' -> '{expanded_message}'")
        
        # Use expanded message for analysis
        analysis_message = expanded_message
    except Exception as e:
        logger.warning(f"Error in preprocessing: {e}")
        analysis_message = request.message
    
    # Analyze query (intent, entities, language)
    result = analyze_query(analysis_message)
    intent = result["intent"]
    entities = result["entities"]
    language = result["language"]
    confidence = result.get("confidence", 0.0)
    
    logger.info(f"Query: '{request.message}' | Intent: {intent} | Language: {language} | Confidence: {confidence:.2f}")

    session_id: str | None = None
    chat_history: list[dict] = []
    
    try:
        user_id_val = user["id"] if user else None
        
        if request.session_id:
            try:
                UUID(request.session_id)
                is_valid_uuid = True
            except ValueError:
                is_valid_uuid = False
                
            if is_valid_uuid:
                if user_id_val:
                    session_row = db.execute(text("""
                        SELECT id::text FROM chat_sessions
                        WHERE id=:session_id AND user_id=:user_id AND ended_at IS NULL
                    """), {"session_id": request.session_id, "user_id": user_id_val}).mappings().one_or_none()
                else:
                    session_row = db.execute(text("""
                        SELECT id::text FROM chat_sessions
                        WHERE id=:session_id AND ended_at IS NULL
                    """), {"session_id": request.session_id}).mappings().one_or_none()

                if session_row:
                    session_id = session_row["id"]
                    
                    # Fetch recent history for this session (last 10 messages)
                    history_rows = db.execute(text("""
                        SELECT role, content 
                        FROM (
                            SELECT role, content, created_at 
                            FROM chat_messages 
                            WHERE session_id=:session_id 
                            ORDER BY created_at DESC 
                            LIMIT 10
                        ) sub
                        ORDER BY created_at ASC
                    """), {"session_id": session_id}).mappings().all()
                    chat_history = [dict(r) for r in history_rows]

        if not session_id:
            title = request.message[:50] + "..." if len(request.message) > 50 else request.message
            session_id = db.execute(text("""
                INSERT INTO chat_sessions (user_id, language, title)
                VALUES (:user_id, :language, :title) RETURNING id::text
            """), {"user_id": user_id_val, "language": language, "title": title}).scalar_one()
            db.commit()
            
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error managing chat session: {e}")
        db.rollback()
        session_id = None
        chat_history = []

    
    # Initialize intelligent generator with database session for dynamic knowledge
    intelligent_gen = get_intelligent_generator(model="llama3.2:3b", db_session=db)
    search_engine = create_hybrid_search_engine(db)
    
    # ========================================================================
    # SCHEME QUERY INTERCEPTOR (HIGH PRIORITY)
    # Detect queries about BSCS schemes and route directly to embedded knowledge
    # ========================================================================
    
    query_lower = request.message.lower()
    
    # Detect scheme-specific queries
    scheme_patterns = [
        r'scheme\s*(?:of\s*study\s*)?(?:20)?21',  # "scheme 2021", "scheme 21", "scheme of study 2021"
        r'scheme\s*(?:of\s*study\s*)?(?:20)?23',  # "scheme 2023", "scheme 23"
        r'scheme\s*(?:of\s*study\s*)?(?:20)?25',  # "scheme 2025", "scheme 25"
        r'2021\s*scheme',
        r'2023\s*scheme',
        r'2025\s*scheme',
    ]
    
    import re
    is_scheme_query = any(re.search(pattern, query_lower) for pattern in scheme_patterns)
    
    # Also detect general scheme queries without year (default to 2025)
    general_scheme_patterns = [
        r'^scheme$',
        r'^scheme\s*of\s*study$',
        r'^curriculum$',
        r'show\s*(?:me\s*)?(?:the\s*)?scheme',
        r'(?:what|which)\s*scheme',
    ]
    
    is_general_scheme_query = any(re.search(pattern, query_lower) for pattern in general_scheme_patterns)
    
    if is_scheme_query or is_general_scheme_query:
        logger.info(f"Detected scheme query - routing to embedded knowledge base")
        
        # Extract year if specified, default to 2025
        scheme_year = "2025"  # Default to current scheme
        if '2021' in query_lower or ' 21' in query_lower:
            scheme_year = "2021"
        elif '2023' in query_lower or ' 23' in query_lower:
            scheme_year = "2023"
        elif '2025' in query_lower or ' 25' in query_lower:
            scheme_year = "2025"
        
        # Generate response using dedicated scheme handler
        try:
            response_text = intelligent_gen.generate_scheme_response(
                query=request.message,
                scheme_year=scheme_year,
                language=language
            , chat_history=chat_history)
            
            
            response_type = "rule"
            if session_id:
                try:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    db.execute(text("""
                        INSERT INTO chat_messages
                            (session_id, role, content, intent, intent_confidence, entities, response_engine)
                        VALUES (:session_id, 'user', :content, :intent, :confidence,
                                CAST(:entities AS jsonb), NULL)
                    """), {
                        "session_id": session_id, "content": request.message,
                        "intent": intent, "confidence": confidence,
                        "entities": json.dumps(entities),
                    })
                    db.execute(text("""
                        INSERT INTO chat_messages
                            (session_id, role, content, intent, intent_confidence, entities,
                             response_engine, response_time_ms)
                        VALUES (:session_id, 'assistant', :content, :intent, :confidence,
                                CAST(:entities AS jsonb), :engine, :elapsed_ms)
                    """), {
                        "session_id": session_id, "content": response_text, "intent": intent,
                        "confidence": confidence, "entities": json.dumps(entities),
                        "engine": response_type,
                        "elapsed_ms": elapsed_ms,
                    })
                    db.execute(text("UPDATE chat_sessions SET updated_at=NOW() WHERE id=:session_id"), {"session_id": session_id})
                    db.commit()
                except SQLAlchemyError as e:
                    logger.error(f"Error saving chat messages: {e}")
                    db.rollback()

            elapsed = time.perf_counter() - started
            
            return {
                "answer": response_text,
                "intent": intent,
                "language": language,
                "confidence": 1.0,  # High confidence for embedded knowledge
                "entities": entities,
                "model_backend": "ollama",
                "model_name": "llama3.2:3b",
                "response_engine": "embedded_scheme_knowledge",
                "citations": [{"title": f"BSCS Scheme of Study {scheme_year} (Embedded)", "source_url": None}],
                "verified": True,
                "session_id": session_id,
                "response_time_ms": int(elapsed * 1000)
            }
        
        except Exception as e:
            logger.error(f"Error in scheme query handler: {e}")
            import traceback
            traceback.print_exc()
            # Fall through to regular handling
    
    # ========================================================================
    # ADMISSION QUERY INTERCEPTOR (HIGH PRIORITY)
    # Detect queries about QAU admissions and route directly to embedded knowledge
    # ========================================================================
    
    # Detect admission-specific queries
    admission_patterns = [
        r'admission',
        r'apply',
        r'application',
        r'merit',
        r'eligibility',
        r'deadline',
        r'last\s*date',
        r'entry\s*test',
        r'lat\s*score',
        r'fee\s*structure',
        r'fees?',
        r'cost',
        r'tuition',
        r'semester\s*fee',
        r'how\s*much',
        r'scholarship',
        r'quota',
        r'reserved\s*seat',
        r'how\s*(?:to|can\s*i)\s*(?:apply|get\s*admission)',
        r'when\s*(?:is|are)\s*admission',
        r'fall\s*2026',
        r'undergraduate\s*admission',
    ]
    
    is_admission_query = any(re.search(pattern, query_lower) for pattern in admission_patterns)
    
    if is_admission_query:
        logger.info(f"Detected admission query - routing to embedded admission knowledge base")
        
        # Generate response using general handler with embedded knowledge
        try:
            # Build explicit admission prompt
            admission_prompt = f"""USER QUERY: {request.message}

TASK: Answer this query about QAU Fall 2026 Undergraduate Admissions using the embedded knowledge in your system instructions.

INSTRUCTIONS:
1. You have complete QAU Fall 2026 admission information embedded in your system instructions
2. Provide accurate dates, deadlines, requirements, and procedures
3. For programme-specific queries (CS/IT/etc.), provide exact eligibility criteria
4. For merit formula queries, explain the calculation clearly
5. For deadline queries, provide exact dates (BS/LLB: 10/08/2026, Pharm-D: 22/09/2026)
6. For scholarship queries, mention the Self-Finance restriction
7. Use clear formatting with bullet points or tables

CRITICAL: Use ONLY the information from your embedded admission knowledge base. Do NOT hallucinate dates or requirements.

LANGUAGE: Respond in {language} (match the user's language exactly)."""
            
            response_text = intelligent_gen.llm.generate(
                prompt=admission_prompt,
                system_prompt=intelligent_gen.system_prompt,
                temperature=0.2,  # Low temperature for factual accuracy
                max_tokens=2500
            )
            
            if not response_text:
                # Fallback message
                if language == 'urdu':
                    response_text = "QAU Fall 2026 داخلہ کی معلومات دستیاب ہے۔ براہ کرم دوبارہ کوشش کریں۔"
                elif language == 'roman_urdu':
                    response_text = "QAU Fall 2026 admission ki information available hai. Dobara try karein."
                else:
                    response_text = "QAU Fall 2026 admission information is available. Please try again with a more specific question."
            
            
            response_type = "rule"
            if session_id:
                try:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    db.execute(text("""
                        INSERT INTO chat_messages
                            (session_id, role, content, intent, intent_confidence, entities, response_engine)
                        VALUES (:session_id, 'user', :content, :intent, :confidence,
                                CAST(:entities AS jsonb), NULL)
                    """), {
                        "session_id": session_id, "content": request.message,
                        "intent": intent, "confidence": confidence,
                        "entities": json.dumps(entities),
                    })
                    db.execute(text("""
                        INSERT INTO chat_messages
                            (session_id, role, content, intent, intent_confidence, entities,
                             response_engine, response_time_ms)
                        VALUES (:session_id, 'assistant', :content, :intent, :confidence,
                                CAST(:entities AS jsonb), :engine, :elapsed_ms)
                    """), {
                        "session_id": session_id, "content": response_text, "intent": intent,
                        "confidence": confidence, "entities": json.dumps(entities),
                        "engine": response_type,
                        "elapsed_ms": elapsed_ms,
                    })
                    db.execute(text("UPDATE chat_sessions SET updated_at=NOW() WHERE id=:session_id"), {"session_id": session_id})
                    db.commit()
                except SQLAlchemyError as e:
                    logger.error(f"Error saving chat messages: {e}")
                    db.rollback()

            elapsed = time.perf_counter() - started
            
            return {
                "answer": response_text,
                "intent": "admission_information",
                "language": language,
                "confidence": 1.0,
                "entities": entities,
                "model_backend": "ollama",
                "model_name": "llama3.2:3b",
                "response_engine": "embedded_admission_knowledge",
                "citations": [{"title": "QAU Undergraduate Admissions Fall 2026 (Official)", "source_url": "qau.edu.pk"}],
                "verified": True,
                "session_id": session_id,
                "response_time_ms": int(elapsed * 1000)
            }
        
        except Exception as e:
            logger.error(f"Error in admission query handler: {e}")
            import traceback
            traceback.print_exc()
            # Fall through to regular handling
    
    # Fetch structured data from database
    structured_data = _fetch_structured_data(intent, entities, db, analysis_message)
    if structured_data:
        structured_data = decimal_to_float(structured_data)
    
    # HANDLE PREREQUISITE QUERIES WITH COMPREHENSIVE INTELLIGENCE SYSTEM
    # CRITICAL: Always check for prerequisite keywords regardless of NLP intent classification
    # The NLP classifier may misclassify prerequisite queries
    
    query_lower = request.message.lower()
    prerequisite_keywords = [
        # Core prerequisite keywords
        'prerequisite', 'prereq', 'pre-req', 'pre req',
        # Requirement keywords  
        'required', 'requirement', 'require', 'need', 'needed', 'necessary',
        # Before/after keywords
        'before', 'after', 'comes before', 'comes after',
        # Together keywords
        'together', 'same semester', 'both', 'simultaneously', 'at once',
        # Action keywords
        'take', 'study', 'register', 'enroll', 'do',
        # Dependency keywords
        'depend', 'depends', 'dependency', 'affected',
        # Status keywords
        'failed', 'fail', 'passed', 'pass', 'completed', 'complete',
        # Question patterns
        'can i take', 'can i study', 'can i register', 'can i enroll',
        'what is required', 'what do i need', 'what comes',
        'what requires', 'what depends',
        'is', 'required for', 'needed for'
    ]
    
    has_prerequisite_keyword = any(kw in query_lower for kw in prerequisite_keywords)
    
    # Trigger prerequisite intelligence if:
    # 1. Intent is explicitly prerequisite-related, OR
    # 2. Multiple courses mentioned with prerequisite keywords, OR  
    # 3. Query contains explicit prerequisite keywords (prereq, prerequisite), OR
    # 4. Query contains general requirement keywords AND mentions a course code
    explicit_prereq_keywords = ['prerequisite', 'prereq', 'pre-req', 'pre req']
    has_explicit_prereq = any(kw in query_lower for kw in explicit_prereq_keywords)
    has_course_code = bool(entities.get("course_code"))
    
    should_use_prerequisite_intelligence = (
        (intent == "course_prerequisite") or
        (intent in ["credit_hour_limit", "semester_information", "course_information"] and 
         len(entities.get("course_code", [])) >= 2) or
        has_explicit_prereq or
        (has_prerequisite_keyword and has_course_code)
    )
    
    if should_use_prerequisite_intelligence:
        try:
            from app.intelligence.prerequisite_intelligence import (
                get_prerequisite_intelligence,
                StudentCourseHistory,
                QueryIntent
            )
            from app.intelligence.student_history_parser import (
                get_student_history_parser,
                parse_student_history_from_query
            )
            from app.intelligence.student_history_db import (
                fetch_student_course_history
            )
            
            intelligence = get_prerequisite_intelligence()
            
            # Build student history from multiple sources (hybrid approach)
            student_history = None
            
            # Source 1: Authenticated user's database records
            if user:
                try:
                    db_history = fetch_student_course_history(db, user["id"])
                    if db_history:
                        student_history = db_history
                        logger.info(f"Loaded student history from database: "
                                  f"{len(db_history.completed_courses)} completed, "
                                  f"{len(db_history.failed_courses)} failed, "
                                  f"{len(db_history.in_progress_courses)} in progress")
                except Exception as e:
                    logger.error(f"Error fetching student history from database: {e}")
            
            # Source 2: Parse query text for status mentions (works for unauthenticated users)
            parser = get_student_history_parser()
            if parser.has_status_mention(request.message):
                try:
                    parsed = parse_student_history_from_query(request.message)
                    
                    if parsed.completed_courses or parsed.failed_courses or parsed.in_progress_courses:
                        logger.info(f"Parsed student status from query: "
                                  f"{len(parsed.completed_courses)} completed, "
                                  f"{len(parsed.failed_courses)} failed, "
                                  f"{len(parsed.in_progress_courses)} in progress")
                        
                        # Merge with database history if available
                        if student_history:
                            # Combine both sources: database + query mentions
                            # Query mentions take precedence for explicit overrides
                            student_history = StudentCourseHistory(
                                completed_courses=student_history.completed_courses | parsed.completed_courses,
                                failed_courses=student_history.failed_courses | parsed.failed_courses,
                                in_progress_courses=student_history.in_progress_courses | parsed.in_progress_courses
                            )
                            logger.info(f"Merged database + query history")
                        else:
                            # Use only query-parsed history
                            student_history = StudentCourseHistory(
                                completed_courses=parsed.completed_courses,
                                failed_courses=parsed.failed_courses,
                                in_progress_courses=parsed.in_progress_courses
                            )
                            logger.info(f"Using query-parsed history (no database history available)")
                except Exception as e:
                    logger.error(f"Error parsing student history from query: {e}")
            
            # Process query with prerequisite intelligence
            answer = intelligence.answer_query(
                query=request.message,
                student_history=student_history
            )
            
            # Only use the prerequisite answer if it's not "unknown" intent
            if answer.intent.value != "unknown":
                # Return the intelligent answer
                
                response_text = answer.answer_text
                response_type = "rule"
                if session_id:
                    try:
                        elapsed_ms = int((time.perf_counter() - started) * 1000)
                        db.execute(text("""
                            INSERT INTO chat_messages
                                (session_id, role, content, intent, intent_confidence, entities, response_engine)
                            VALUES (:session_id, 'user', :content, :intent, :confidence,
                                    CAST(:entities AS jsonb), NULL)
                        """), {
                            "session_id": session_id, "content": request.message,
                            "intent": intent, "confidence": confidence,
                            "entities": json.dumps(entities),
                        })
                        db.execute(text("""
                            INSERT INTO chat_messages
                                (session_id, role, content, intent, intent_confidence, entities,
                                 response_engine, response_time_ms)
                            VALUES (:session_id, 'assistant', :content, :intent, :confidence,
                                    CAST(:entities AS jsonb), :engine, :elapsed_ms)
                        """), {
                            "session_id": session_id, "content": response_text, "intent": intent,
                            "confidence": confidence, "entities": json.dumps(entities),
                            "engine": response_type,
                            "elapsed_ms": elapsed_ms,
                        })
                        db.execute(text("UPDATE chat_sessions SET updated_at=NOW() WHERE id=:session_id"), {"session_id": session_id})
                        db.commit()
                    except SQLAlchemyError as e:
                        logger.error(f"Error saving chat messages: {e}")
                        db.rollback()

                elapsed = time.perf_counter() - started
                logger.info(f"Prerequisite intelligence handled query: {answer.intent.value}")
                return {
                    "answer": answer.answer_text,
                    "intent": intent,
                    "language": language,
                    "confidence": answer.confidence,
                    "entities": entities,
                    "model_backend": "prerequisite_intelligence",
                    "model_name": "graph_reasoning",
                    "response_engine": "prerequisite_graph",
                    "citations": [{"title": src, "source_url": None} for src in answer.sources],
                    "verified": True,
                    "session_id": session_id,
                    "response_time_ms": int(elapsed * 1000)
                }
            else:
                logger.info(f"Prerequisite intelligence returned unknown intent, falling through")
        except Exception as e:
            logger.error(f"Error in prerequisite intelligence: {e}")
            import traceback
            traceback.print_exc()
            # Fall through to LLM handler
            pass
    
    # Perform hybrid search for additional context
    search_results = None
    try:
        search_results = search_engine.search(
            query=analysis_message,
            top_k=5
        )
        logger.info(f"Hybrid search returned {len(search_results)} results")
    except Exception as e:
        logger.error(f"Error in hybrid search: {e}")
    
    # Generate intelligent response using LLM
    try:
        response_text = intelligent_gen.generate_response(
            query=request.message,
            intent=intent,
            language=language,
            search_results=search_results,
            structured_data=structured_data,
            entities=entities
        , chat_history=chat_history)
        
        response_type = "rag" if search_results else "sql" if structured_data else "fallback"
        verified = True  # LLM-generated responses based on verified data
        
    except Exception as e:
        logger.error(f"Error generating LLM response: {e}")
        # Fallback response
        if language == 'urdu':
            response_text = "معذرت، میں اس وقت آپ کے سوال کا جواب نہیں دے سکتا۔"
        elif language == 'roman_urdu':
            response_text = "Maazrat, main is waqt jawab nahi de sakta."
        else:
            response_text = "I apologize, but I'm unable to answer that question at the moment."
        response_type = "fallback"
        verified = False
    
    # Calculate response time

    if session_id:
        try:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            db.execute(text("""
                INSERT INTO chat_messages
                    (session_id, role, content, intent, intent_confidence, entities, response_engine)
                VALUES (:session_id, 'user', :content, :intent, :confidence,
                        CAST(:entities AS jsonb), NULL)
            """), {
                "session_id": session_id, "content": request.message,
                "intent": intent, "confidence": confidence,
                "entities": json.dumps(entities),
            })
            db.execute(text("""
                INSERT INTO chat_messages
                    (session_id, role, content, intent, intent_confidence, entities,
                     response_engine, response_time_ms)
                VALUES (:session_id, 'assistant', :content, :intent, :confidence,
                        CAST(:entities AS jsonb), :engine, :elapsed_ms)
            """), {
                "session_id": session_id, "content": response_text, "intent": intent,
                "confidence": confidence, "entities": json.dumps(entities),
                "engine": response_type,
                "elapsed_ms": elapsed_ms,
            })
            db.execute(text("UPDATE chat_sessions SET updated_at=NOW() WHERE id=:session_id"), {"session_id": session_id})
            db.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error saving chat messages: {e}")
            db.rollback()

    elapsed = time.perf_counter() - started
    
    # Build response
    response = {
        "answer": response_text,
        "intent": intent,
        "language": language,
        "confidence": confidence,
        "entities": entities,
        "model_backend": "ollama",
        "model_name": "llama3.2:3b",
        "response_engine": response_type,
        "citations": [],
        "verified": verified,
        "session_id": session_id
    }
    
    logger.info(f"Response generated in {elapsed:.2f}s | Type: {response_type}")
    
    return response

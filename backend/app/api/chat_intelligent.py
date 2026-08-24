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
        
        # Course prerequisites
        elif intent == "course_prerequisite":
            code = (entities.get("course_code") or [None])[0]
            if code:
                rows = db.execute(text("""
                    SELECT pc.code, pc.title, cp.minimum_grade
                    FROM course_prerequisites cp
                    JOIN courses c ON c.id=cp.course_id
                    JOIN courses pc ON pc.id=cp.prerequisite_course_id
                    WHERE upper(c.code)=upper(:code)
                    ORDER BY pc.code
                """), {"code": code}).mappings().all()
                
                if rows:
                    return {
                        'course_code': code,
                        'prerequisites': [dict(r) for r in rows]
                    }
        
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
    
    # Initialize intelligent generator and search engine
    intelligent_gen = get_intelligent_generator(model="qwen3:8b")
    search_engine = create_hybrid_search_engine(db)
    
    # Fetch structured data from database
    structured_data = _fetch_structured_data(intent, entities, db, analysis_message)
    if structured_data:
        structured_data = decimal_to_float(structured_data)
    
    # Perform hybrid search for additional context
    search_results = None
    if intent in ["research_area_query", "admission_information", "policy_information", 
                  "course_information", "program_information", "general_query"]:
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
        )
        
        response_type = "llm_rag" if search_results else "llm_sql" if structured_data else "llm_fallback"
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
        response_type = "error"
        verified = False
    
    # Calculate response time
    elapsed = time.perf_counter() - started
    
    # Build response
    response = {
        "answer": response_text,
        "intent": intent,
        "language": language,
        "confidence": confidence,
        "entities": entities,
        "model_backend": "ollama",
        "model_name": "qwen3:8b",
        "response_engine": response_type,
        "citations": [],
        "verified": verified,
        "session_id": request.session_id
    }
    
    logger.info(f"Response generated in {elapsed:.2f}s | Type: {response_type}")
    
    return response

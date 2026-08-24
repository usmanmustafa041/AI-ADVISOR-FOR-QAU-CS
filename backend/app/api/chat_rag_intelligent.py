"""
Intelligent RAG Chatbot for QAU CS Academic Advisor
Uses local knowledge base and Ollama Qwen3.5 for intelligent responses
Implements professional RAG with context retrieval and response generation
"""

import json
import time
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.rag.qau_knowledge_base import (
    get_course_by_code, get_courses_by_focus_area, search_courses,
    get_program_info, get_admission_info, get_research_areas, get_all_focus_areas
)
from app.rag.timetable_data import get_timetable, search_timetable

router = APIRouter(tags=["chat"])

# Conversation memory
conversation_memory = {}


class RAGQueryProcessor:
    """Process queries using RAG - Retrieval Augmented Generation"""
    
    @staticmethod
    def classify_query(message: str) -> dict:
        """Classify the query intent and extract entities."""
        msg_lower = message.lower()
        
        # Detect query type
        if any(x in msg_lower for x in ["when", "schedule", "class", "time", "room"]):
            intent = "timetable"
        elif any(x in msg_lower for x in ["course", "cs-", "prerequisite", "credit", "elective"]):
            intent = "course"
        elif any(x in msg_lower for x in ["focus", "specialization", "concentration", "ai", "data science", "software"]):
            intent = "focus_area"
        elif any(x in msg_lower for x in ["admission", "deadline", "apply", "fall 2026"]):
            intent = "admission"
        elif any(x in msg_lower for x in ["research", "lab", "group", "faculty"]):
            intent = "research"
        elif any(x in msg_lower for x in ["program", "bs", "structure", "semester", "requirement"]):
            intent = "program"
        elif any(x in msg_lower for x in ["help", "what can", "hello", "hi", "greeting"]):
            intent = "help"
        else:
            intent = "general"
        
        return {"intent": intent, "message": message}
    
    @staticmethod
    def retrieve_context(query: dict) -> list:
        """Retrieve relevant context from knowledge base."""
        intent = query["intent"]
        message = query["message"]
        context = []
        
        if intent == "timetable":
            # Retrieve timetable information
            matches = search_timetable(message)
            context = matches[:5] if matches else []
        
        elif intent == "course":
            # Extract course code if present
            import re
            course_codes = re.findall(r'[A-Z]+-\d+', message.upper())
            if course_codes:
                for code in course_codes[:3]:
                    course = get_course_by_code(code)
                    if course:
                        context.append({"type": "course", "code": code, "details": course})
            
            # Also search by name
            results = search_courses(message)
            context.extend([{"type": "search_result", "course": r} for r in results[:3]])
        
        elif intent == "focus_area":
            # Get focus area courses
            for focus in get_all_focus_areas():
                if focus.lower() in message.lower():
                    courses = get_courses_by_focus_area(focus)
                    context.append({
                        "type": "focus_area",
                        "name": focus,
                        "courses": courses,
                        "course_count": len(courses)
                    })
        
        elif intent == "admission":
            context.append({"type": "admission", "info": get_admission_info()})
        
        elif intent == "research":
            context.append({"type": "research", "areas": get_research_areas()})
        
        elif intent == "program":
            context.append({"type": "program", "info": get_program_info()})
        
        return context
    
    @staticmethod
    def generate_response(query: dict, context: list) -> str:
        """Generate professional response using context."""
        intent = query["intent"]
        message = query["message"]
        
        if intent == "timetable":
            if context:
                m = context[0]
                return (
                    f"📅 **{m['course_code']}** Schedule\n\n"
                    f"**Day**: {m['day']}\n"
                    f"**Time**: {m['start_time']} - {m['end_time']}\n"
                    f"**Room**: {m['room']}\n"
                    f"**Section**: {m['section']}\n"
                    f"**Instructor**: {m.get('instructor', 'TBA')}\n"
                    f"**Term**: {m.get('term', 'Spring 2026')}"
                )
            else:
                return "I couldn't find that course in the current timetable. Please check the course code or try another query."
        
        elif intent == "course":
            if context:
                resp = "**Course Information**\n\n"
                for item in context[:2]:
                    if item.get("type") == "course":
                        course = item["details"]
                        resp += f"📚 **{item['code']}**: {course.get('name', 'N/A')}\n"
                        resp += f"   • Credits: {course.get('credits', 'N/A')}\n"
                    elif item.get("type") == "search_result":
                        course = item["course"]
                        resp += f"📚 **{course['code']}**: {course.get('name', 'N/A')}\n"
                return resp
            else:
                return "No course information found. Please provide a valid course code (e.g., CSC-459)."
        
        elif intent == "focus_area":
            if context:
                item = context[0]
                resp = f"**{item['name']} Focus Area**\n\n"
                resp += f"Available courses ({item['course_count']}):\n\n"
                for code, details in list(item['courses'].items())[:8]:
                    resp += f"• **{code}**: {details['name']} ({details['credits']} credits)\n"
                return resp
            else:
                resp = "**Available Focus Areas**\n\n"
                for i, focus in enumerate(get_all_focus_areas(), 1):
                    resp += f"{i}. {focus}\n"
                return resp
        
        elif intent == "admission":
            if context:
                info = context[0]["info"]["fall_2026"]
                resp = "**QAU CS Admissions - Fall 2026**\n\n"
                for prog, details in info.items():
                    resp += f"📢 **{details['program']}**\n"
                    resp += f"   Deadline: {details['deadline']}\n\n"
                return resp
            return "Admission information is currently unavailable."
        
        elif intent == "program":
            if context:
                info = context[0]["info"]
                resp = f"**{info['name']} Program**\n\n"
                resp += f"📚 Duration: {info['duration']}\n"
                resp += f"📋 Semesters: {info['semesters']}\n"
                resp += f"⏱️ Total Credits: {info['total_credits']}\n"
                resp += f"📊 Credits/Semester: {info['credits_per_semester']}\n"
                resp += f"✅ Accreditation: {info['accreditation']}\n\n"
                resp += "**Program Objectives**\n"
                for i, obj in enumerate(info['program_objectives'], 1):
                    resp += f"{i}. {obj}\n"
                return resp
            return "Program information not available."
        
        elif intent == "research":
            if context:
                areas = context[0]["areas"]
                resp = "**QAU CS Research Areas**\n\n"
                for area_key, area in areas.items():
                    resp += f"🔬 **{area['name']}**\n"
                    resp += f"   {area['description']}\n\n"
                return resp
            return "Research information not available."
        
        elif intent == "help":
            return (
                "**Welcome to QAU CS Academic Advisor** 🎓\n\n"
                "I can help you with:\n\n"
                "📅 **Timetables** - \"When is CS-104?\"\n"
                "📚 **Courses** - \"Tell me about CSC-459\"\n"
                "🎯 **Focus Areas** - \"What courses in Data Science?\"\n"
                "🏫 **Program Info** - \"BS program structure?\"\n"
                "📢 **Admissions** - \"When are admissions?\"\n"
                "🔬 **Research** - \"What research areas exist?\"\n\n"
                "What would you like to know?"
            )
        
        else:
            return (
                "I'm the QAU CS Academic Advisor. I can help with:\n"
                "• Course schedules and information\n"
                "• Program structure and requirements\n"
                "• Focus areas and specializations\n"
                "• Admission information\n"
                "• Research areas\n\n"
                "What can I help you with?"
            )


@router.post("/chat", response_model=ChatResponse)
def chat_rag_intelligent(request: ChatRequest) -> dict:
    """
    Intelligent RAG chatbot endpoint.
    Retrieves context from knowledge base and generates professional responses.
    """
    try:
        session_id = request.session_id or f"session_{int(time.time())}"
        started = time.perf_counter()
        
        # Initialize session
        if session_id not in conversation_memory:
            conversation_memory[session_id] = []
        
        # Classify and process query
        query = RAGQueryProcessor.classify_query(request.message)
        context = RAGQueryProcessor.retrieve_context(query)
        answer = RAGQueryProcessor.generate_response(query, context)
        
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        
        # Store in conversation memory
        conversation_memory[session_id].append({
            "timestamp": datetime.now().isoformat(),
            "user": request.message,
            "assistant": answer,
            "intent": query["intent"],
            "context_count": len(context)
        })
        
        return {
            "answer": answer,
            "intent": query["intent"],
            "language": "english",
            "confidence": 0.9 if context else 0.5,
            "entities": {},
            "model_backend": "RAG",
            "model_name": "QAU-CS-RAG",
            "response_engine": "rag_retrieval",
            "citations": [],
            "verified": True if context else False,
            "session_id": session_id,
            "response_type": "rag_response",
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": elapsed_ms,
            "context_sources": len(context)
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "answer": f"I encountered an error. Please try again. Error: {str(e)[:50]}",
            "intent": "error",
            "language": "english",
            "confidence": 0.0,
            "entities": {},
            "model_backend": "error",
            "model_name": "error",
            "response_engine": "fallback",
            "citations": [],
            "verified": False,
            "session_id": request.session_id or "error",
            "response_type": "error",
            "timestamp": datetime.now().isoformat()
        }

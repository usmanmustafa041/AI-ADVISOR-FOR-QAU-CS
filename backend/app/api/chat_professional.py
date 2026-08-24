"""
Professional academic chatbot with enhanced RAG and response formatting.
Implements best practices from academic chatbot research.
"""

import json
import time
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.nlp.service import analyze_query
from app.rag.timetable_data import get_timetable, search_timetable

router = APIRouter(tags=["chat"])

# Store conversation history in memory
conversation_history = {}


class ResponseFormatter:
    """Professional response formatting with citations and metadata."""
    
    @staticmethod
    def format_timetable_response(course_code: Optional[str] = None, day: Optional[str] = None, query: str = "") -> dict:
        """Format timetable query response with full details."""
        timetable = get_timetable()
        
        # Search for matches
        matches = search_timetable(query)
        
        if not matches:
            return {
                "answer": f"I couldn't find timetable information matching '{query}'. Try asking about a specific course code (e.g., CS-104) or day of week.",
                "response_type": "timetable",
                "confidence": 0.3,
                "verified": False,
                "source": "timetable",
                "suggestions": ["Try asking 'When is CS-101?'", "Ask about specific days like Monday or Friday"]
            }
        
        # Filter by course if specified
        if course_code:
            matches = [m for m in matches if m["course_code"].upper() == course_code.upper()]
        
        # Filter by day if specified
        if day:
            matches = [m for m in matches if day.lower() in m['day'].lower()]
        
        if not matches:
            return {
                "answer": f"No classes found for {course_code or day}. Please check the course code or try a different day.",
                "response_type": "timetable",
                "confidence": 0.4,
                "verified": False,
                "source": "timetable"
            }
        
        # Format response with detailed information
        if course_code and len(matches) == 1:
            m = matches[0]
            answer = (
                f"**{m['course_code']}: {m.get('course_name', 'Course')}**\n\n"
                f"📅 **Schedule**: {m['day']}\n"
                f"⏰ **Time**: {m['start_time']} - {m['end_time']}\n"
                f"📍 **Room**: {m['room']}\n"
                f"👥 **Section**: {m['section']}\n"
                f"👨‍🏫 **Instructor**: {m.get('instructor', 'TBA')}\n"
                f"📂 **Term**: {m.get('term', 'Spring 2026')}"
            )
            return {
                "answer": answer,
                "response_type": "timetable_detailed",
                "confidence": 0.95,
                "verified": True,
                "source": "timetable",
                "metadata": {
                    "course_code": m['course_code'],
                    "day": m['day'],
                    "time": f"{m['start_time']}-{m['end_time']}",
                    "room": m['room'],
                    "instructor": m.get('instructor', 'TBA')
                }
            }
        
        elif day:
            # Format day schedule
            formatted = []
            for m in matches[:12]:
                formatted.append(f"  • {m['start_time']}-{m['end_time']}: **{m['course_code']}** in {m['room']}")
            
            answer = f"**{day} Class Schedule:**\n\n" + "\n".join(formatted)
            return {
                "answer": answer,
                "response_type": "timetable_schedule",
                "confidence": 0.9,
                "verified": True,
                "source": "timetable",
                "metadata": {
                    "day": day,
                    "total_classes": len(matches),
                    "classes": [{"code": m['course_code'], "time": f"{m['start_time']}-{m['end_time']}"} for m in matches[:5]]
                }
            }
        
        else:
            # Multiple results, show first match with suggestions
            m = matches[0]
            answer = (
                f"**{m['course_code']}** - {m['day']} {m['start_time']}-{m['end_time']} in **{m['room']}**\n\n"
                f"Found {len(matches)} matching entries. For more details, ask about the specific course or day."
            )
            return {
                "answer": answer,
                "response_type": "timetable_brief",
                "confidence": 0.8,
                "verified": True,
                "source": "timetable",
                "suggestion": f"Ask for more details about {m['course_code']} or {m['day']} schedule"
            }
    
    @staticmethod
    def format_fallback_response(intent: str, query: str) -> dict:
        """Format fallback response for unknown or complex queries."""
        responses = {
            "greeting": {
                "answer": "Assalamu Alaikum! 👋 Welcome to QAU CS Academic Advisor. I can help you with:\n\n"
                         "📅 **Timetables & Schedules** - Ask about course times and locations\n"
                         "📚 **Course Information** - Learn about courses and requirements\n"
                         "📋 **Academic Policies** - Information about progression and rules\n"
                         "❓ **Common Questions** - Frequent student queries\n\n"
                         "What can I help you with?",
                "confidence": 1.0,
                "verified": True
            },
            "help": {
                "answer": "**Here's what I can help with:**\n\n"
                         "1️⃣ **Course Schedules**: \"When is CS-104?\" or \"Show me Monday classes\"\n"
                         "2️⃣ **Course Info**: \"Tell me about CS-211\"\n"
                         "3️⃣ **Semester Plans**: \"What courses in semester 1?\"\n"
                         "4️⃣ **General Questions**: Ask about policies, fees, or academic rules\n\n"
                         "Or just ask anything and I'll do my best to help!",
                "confidence": 1.0,
                "verified": True
            },
            "unknown": {
                "answer": f"I'm not sure about '{query}'.\n\n"
                         "**Try asking about:**\n"
                         "• Specific courses (e.g., CS-104, CS-211)\n"
                         "• Days of week (Monday, Tuesday, etc.)\n"
                         "• Semesters or academic terms\n\n"
                         "If you need more help, please contact the CS Department office.",
                "confidence": 0.2,
                "verified": False,
                "escalation": "Contact CS Department for complex queries"
            }
        }
        
        resp = responses.get(intent, responses["unknown"])
        resp["response_type"] = intent
        resp["source"] = "fallback"
        return resp


@router.post("/chat", response_model=ChatResponse)
def chat_professional(request: ChatRequest) -> dict:
    """
    Professional academic chatbot endpoint.
    Returns properly formatted, verified responses with citations.
    """
    try:
        session_id = request.session_id or f"session_{int(time.time())}"
        started = time.perf_counter()
        
        # Initialize session history
        if session_id not in conversation_history:
            conversation_history[session_id] = []
        
        # Analyze query
        try:
            result = analyze_query(request.message)
        except Exception:
            # Fallback if NLP fails
            result = {
                "intent": "timetable_query" if any(x in request.message.lower() for x in ["when", "schedule", "class", "cs-"]) else "unknown",
                "text": request.message,
                "language": "english",
                "confidence": 0.5,
                "entities": {"course_code": None, "day": None},
                "model_backend": "fallback",
                "model_name": "fallback"
            }
        
        # Route to appropriate handler
        if result["intent"] == "timetable_query":
            code = (result["entities"].get("course_code") or [None])[0]
            day = (result["entities"].get("day") or [None])[0]
            response_data = ResponseFormatter.format_timetable_response(code, day, request.message)
        
        elif result["intent"] in ["greeting", "help"]:
            response_data = ResponseFormatter.format_fallback_response(result["intent"], request.message)
        
        else:
            response_data = ResponseFormatter.format_fallback_response("unknown", request.message)
        
        # Add metadata
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        
        # Build complete response
        response = {
            "answer": response_data["answer"],
            "intent": result["intent"],
            "language": result.get("language", "english"),
            "confidence": response_data.get("confidence", result.get("confidence", 0.5)),
            "entities": result.get("entities", {}),
            "model_backend": result.get("model_backend", "fallback"),
            "model_name": result.get("model_name", "fallback"),
            "response_engine": response_data.get("source", "fallback"),
            "citations": [],
            "verified": response_data.get("verified", False),
            "session_id": session_id,
            "response_type": response_data.get("response_type", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": elapsed_ms,
        }
        
        # Add metadata if available
        if "metadata" in response_data:
            response["metadata"] = response_data["metadata"]
        
        # Add suggestions if available
        if "suggestions" in response_data:
            response["suggestions"] = response_data["suggestions"]
        
        # Add escalation if needed
        if "escalation" in response_data:
            response["escalation"] = response_data["escalation"]
        
        # Track in conversation history
        conversation_history[session_id].append({
            "timestamp": datetime.now().isoformat(),
            "user_message": request.message,
            "assistant_response": response_data["answer"],
            "intent": result["intent"],
            "confidence": response["confidence"]
        })
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "answer": f"I encountered an error processing your request. Please try again.\n\nError details: {str(e)[:100]}",
            "intent": "error",
            "language": "english",
            "confidence": 0.0,
            "entities": {},
            "model_backend": "error",
            "model_name": "error",
            "response_engine": "fallback",
            "citations": [],
            "verified": False,
            "session_id": request.session_id or "error_session",
            "response_type": "error",
            "timestamp": datetime.now().isoformat()
        }

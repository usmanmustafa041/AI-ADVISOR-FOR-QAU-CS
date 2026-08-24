"""Simple chat endpoint that works without database for timetable queries."""

import json
import time
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.nlp.service import analyze_query

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    """
    Simple chat endpoint for timetable queries.
    Works without database connection for MVP.
    """
    try:
        started = time.perf_counter()
        result = analyze_query(request.message)
        
        # Handle timetable query intent
        if result["intent"] == "timetable_query":
            from app.rag.timetable_data import search_timetable
            
            code = (result["entities"].get("course_code") or [None])[0]
            day = (result["entities"].get("day") or [None])[0]
            query = request.message.lower()
            
            # Try in-memory search
            matches = search_timetable(query)
            
            if matches:
                if code:
                    filtered = [m for m in matches if m["course_code"] == code]
                    if filtered:
                        m = filtered[0]
                        answer = f"{m['course_code']} meets on {m['day']} from {m['start_time']} to {m['end_time']} in Room {m['room']}"
                        elapsed_ms = int((time.perf_counter() - started) * 1000)
                        return {
                            "answer": answer,
                            "intent": result["intent"],
                            "language": result["language"],
                            "confidence": result["confidence"],
                            "entities": result["entities"],
                            "model_backend": result["model_backend"],
                            "model_name": result["model_name"],
                            "response_engine": "timetable",
                            "citations": [],
                            "verified": True,
                            "session_id": None,
                        }
                
                if day:
                    day_entries = [m for m in matches if day.lower() in m['day'].lower()]
                    if day_entries:
                        formatted = [f"{m['start_time']}-{m['end_time']}: {m['course_code']} in {m['room']}" for m in day_entries]
                        answer = f"{day} Classes: " + " | ".join(formatted[:10])
                        elapsed_ms = int((time.perf_counter() - started) * 1000)
                        return {
                            "answer": answer,
                            "intent": result["intent"],
                            "language": result["language"],
                            "confidence": result["confidence"],
                            "entities": result["entities"],
                            "model_backend": result["model_backend"],
                            "model_name": result["model_name"],
                            "response_engine": "timetable",
                            "citations": [],
                            "verified": True,
                            "session_id": None,
                        }
                
                # Return first match
                m = matches[0]
                answer = f"{m['course_code']} - {m['day']} {m['start_time']}-{m['end_time']} in Room {m['room']}"
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                return {
                    "answer": answer,
                    "intent": result["intent"],
                    "language": result["language"],
                    "confidence": result["confidence"],
                    "entities": result["entities"],
                    "model_backend": result["model_backend"],
                    "model_name": result["model_name"],
                    "response_engine": "timetable",
                    "citations": [],
                    "verified": True,
                    "session_id": None,
                }
        
        # For other intents, return a default response
        answer = "I can help with timetable queries. Try asking 'When is CS-104?' or 'What classes on Monday?'"
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        
        return {
            "answer": answer,
            "intent": result["intent"],
            "language": result["language"],
            "confidence": result["confidence"],
            "entities": result["entities"],
            "model_backend": result["model_backend"],
            "model_name": result["model_name"],
            "response_engine": "fallback",
            "citations": [],
            "verified": False,
            "session_id": None,
        }
        
    except Exception as e:
        print(f"Chat error: {str(e)}")
        return {
            "answer": f"Error: {str(e)}. Try asking about courses or timetables.",
            "intent": "error",
            "language": "english",
            "confidence": 0.0,
            "entities": {},
            "model_backend": "error",
            "model_name": "error",
            "response_engine": "fallback",
            "citations": [],
            "verified": False,
            "session_id": None,
        }

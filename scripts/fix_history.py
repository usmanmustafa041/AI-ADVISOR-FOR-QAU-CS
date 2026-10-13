with open('/Users/mm/AI-ADVISOR-FOR-QAU-CS/backend/app/api/history.py', 'r') as f:
    content = f.read()

old_get_session_messages = """@router.get("/sessions/{session_id}")
def get_session_messages(session_id: str, limit: int = Query(50, ge=1, le=100), user: dict = Depends(current_user), db: Session = Depends(get_db)):
    # Verify session belongs to user
    session = db.execute(text("SELECT id FROM chat_sessions WHERE id=:session_id AND user_id=:user_id"),
                         {"session_id": session_id, "user_id": user["id"]}).fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")"""

new_get_session_messages = """@router.get("/sessions/{session_id}")
def get_session_messages(session_id: str, limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    # Allow anonymous fetching if the user has the session_id
    session = db.execute(text("SELECT id FROM chat_sessions WHERE id=:session_id"),
                         {"session_id": session_id}).fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")"""

content = content.replace(old_get_session_messages, new_get_session_messages)

old_delete_session = """@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    count = db.execute(text("DELETE FROM chat_sessions WHERE id=:session_id AND user_id=:user_id"),
                       {"session_id": session_id, "user_id": user["id"]}).rowcount"""

new_delete_session = """@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    count = db.execute(text("DELETE FROM chat_sessions WHERE id=:session_id"),
                       {"session_id": session_id}).rowcount"""

content = content.replace(old_delete_session, new_delete_session)

# Add POST /history/sessions/batch
batch_endpoint = """
from pydantic import BaseModel
class SessionBatchRequest(BaseModel):
    session_ids: list[str]

@router.post("/sessions/batch")
def get_sessions_batch(request: SessionBatchRequest, db: Session = Depends(get_db)):
    if not request.session_ids:
        return []
    
    # Filter valid UUIDs
    from uuid import UUID
    valid_ids = []
    for s_id in request.session_ids:
        try:
            UUID(s_id)
            valid_ids.append(s_id)
        except ValueError:
            pass
            
    if not valid_ids:
        return []
        
    rows = db.execute(text(\"\"\"
        SELECT id::text, title, created_at, updated_at
        FROM chat_sessions
        WHERE id = ANY(:session_ids)
        ORDER BY updated_at DESC
    \"\"\"), {"session_ids": valid_ids}).mappings()
    return [dict(row) for row in rows]
"""

content += batch_endpoint

with open('/Users/mm/AI-ADVISOR-FOR-QAU-CS/backend/app/api/history.py', 'w') as f:
    f.write(content)

print("history.py updated")

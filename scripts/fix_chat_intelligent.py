import re

with open('/Users/mm/AI-ADVISOR-FOR-QAU-CS/backend/app/api/chat_intelligent.py', 'r') as f:
    content = f.read()

# Replace session management block
old_session_block = """    if user:
        try:
            if request.session_id:
                try:
                    UUID(request.session_id)
                except ValueError:
                    raise HTTPException(status_code=422, detail="Invalid chat session id") from None
                session_row = db.execute(text(\"\"\"
                    SELECT id::text FROM chat_sessions
                    WHERE id=:session_id AND user_id=:user_id AND ended_at IS NULL
                \"\"\"), {"session_id": session_id, "user_id": user["id"]}).mappings().one_or_none()
                if not session_row:
                    raise HTTPException(status_code=404, detail="Chat session was not found")
                session_id = session_row["id"]
                
                # Fetch recent history for this session (last 10 messages)
                history_rows = db.execute(text(\"\"\"
                    SELECT role, content 
                    FROM (
                        SELECT role, content, created_at 
                        FROM chat_messages 
                        WHERE session_id=:session_id 
                        ORDER BY created_at DESC 
                        LIMIT 10
                    ) sub
                    ORDER BY created_at ASC
                \"\"\"), {"session_id": session_id}).mappings().all()
                chat_history = [dict(r) for r in history_rows]
            else:
                session_id = db.execute(text(\"\"\"
                    INSERT INTO chat_sessions (user_id, language)
                    VALUES (:user_id, :language) RETURNING id::text
                \"\"\"), {"user_id": user["id"], "language": language}).scalar_one()
                db.commit()
        except HTTPException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error managing chat session: {e}")
            db.rollback()
            session_id = None
            chat_history = []"""

new_session_block = """    try:
        user_id_val = user["id"] if user else None
        
        if request.session_id:
            try:
                UUID(request.session_id)
                is_valid_uuid = True
            except ValueError:
                is_valid_uuid = False
                
            if is_valid_uuid:
                if user_id_val:
                    session_row = db.execute(text(\"\"\"
                        SELECT id::text FROM chat_sessions
                        WHERE id=:session_id AND user_id=:user_id AND ended_at IS NULL
                    \"\"\"), {"session_id": request.session_id, "user_id": user_id_val}).mappings().one_or_none()
                else:
                    session_row = db.execute(text(\"\"\"
                        SELECT id::text FROM chat_sessions
                        WHERE id=:session_id AND ended_at IS NULL
                    \"\"\"), {"session_id": request.session_id}).mappings().one_or_none()

                if session_row:
                    session_id = session_row["id"]
                    
                    # Fetch recent history for this session (last 10 messages)
                    history_rows = db.execute(text(\"\"\"
                        SELECT role, content 
                        FROM (
                            SELECT role, content, created_at 
                            FROM chat_messages 
                            WHERE session_id=:session_id 
                            ORDER BY created_at DESC 
                            LIMIT 10
                        ) sub
                        ORDER BY created_at ASC
                    \"\"\"), {"session_id": session_id}).mappings().all()
                    chat_history = [dict(r) for r in history_rows]

        if not session_id:
            title = request.message[:50] + "..." if len(request.message) > 50 else request.message
            session_id = db.execute(text(\"\"\"
                INSERT INTO chat_sessions (user_id, language, title)
                VALUES (:user_id, :language, :title) RETURNING id::text
            \"\"\"), {"user_id": user_id_val, "language": language, "title": title}).scalar_one()
            db.commit()
            
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error managing chat session: {e}")
        db.rollback()
        session_id = None
        chat_history = []"""

content = content.replace(old_session_block, new_session_block)

# Replace all occurrences of `if user and session_id:`
content = content.replace("    if user and session_id:", "    if session_id:")

# Replace db.commit() in the chat message saving block with db.execute(update...) + db.commit()
commit_replacement = """            db.execute(text(\"UPDATE chat_sessions SET updated_at=NOW() WHERE id=:session_id\"), {"session_id": session_id})
            db.commit()"""

# Be careful, we only want to replace the db.commit() that follows the insert into chat_messages
# A regex would be better:
content = re.sub(r'(\s+)db\.commit\(\)(\s+except SQLAlchemyError as e:)', r'\1db.execute(text("UPDATE chat_sessions SET updated_at=NOW() WHERE id=:session_id"), {"session_id": session_id})\1db.commit()\2', content)

with open('/Users/mm/AI-ADVISOR-FOR-QAU-CS/backend/app/api/chat_intelligent.py', 'w') as f:
    f.write(content)

print("Replacement successful")

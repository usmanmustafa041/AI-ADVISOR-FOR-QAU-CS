# 🚀 Quick Access Guide

## Open the Application

### 🌐 Web Interface
```
http://localhost:5173
```
Open this URL in your browser to use the chatbot!

### 📚 API Documentation
```
http://localhost:8000/docs
```
Interactive Swagger UI for testing APIs directly

---

## Test the Chatbot

### Using the Web Interface
1. Open http://localhost:5173
2. Type your question in the chat box
3. Press Enter or click Send

### Using curl (Terminal)
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Who is Dr. Onaiza Maqbool?"}'
```

---

## Sample Questions to Try

### Faculty Questions ✅
- "Who is Dr. Onaiza Maqbool?"
- "Tell me about faculty members"
- "What are the research areas?"

### Course Questions ✅
- "Tell me about Data Structures course"
- "What is CS-211?"
- "What courses are in semester 3?"

### Prerequisite Questions ✅
- "Can I take Data Structures without OOP?"
- "Can I study PSP, OOP, and Data Structures in the same semester?"
- "What are prerequisites for Software Engineering?"

### Program Questions ✅
- "What programs does the CS department offer?"
- "Tell me about the MPhil program"
- "What are admission requirements?"

---

## Service Status

| Service | Status | URL |
|---------|--------|-----|
| Database | 🟢 Running | localhost:55432 |
| Backend | 🟢 Running | http://localhost:8000 |
| Frontend | 🟢 Running | http://localhost:5173 |

---

## If Services Stop

### Restart Backend
```bash
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS/backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Restart Frontend
```bash
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS/frontend
npm run dev
```

### Restart Database
```bash
docker start qau-advisor-postgres
```

---

## System Capabilities

✅ **77 BSCS courses** in catalog  
✅ **19 prerequisite relationships** tracked  
✅ **68 CS website pages** embedded  
✅ **28 faculty members** with research interests  
✅ **Intelligent prerequisite conflict detection**  
✅ **RAG-powered answers** with vector search  
✅ **Natural language understanding**

---

## 🎉 Everything is Ready!

Your QAU CS Academic Advisor is fully operational and ready to answer questions about:
- Faculty and their research
- Course information and prerequisites
- Program details (BS, MPhil, PhD)
- Admission requirements
- Department information

**Start chatting at: http://localhost:5173** 🚀

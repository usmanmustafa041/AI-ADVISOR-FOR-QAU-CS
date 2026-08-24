# Timetable & Scheme Integration - Complete Setup

## ✅ What's Been Done

### 1. **In-Memory Timetable Parser** (`app/rag/timetable_data.py`)
- Parses QAU CS timetable PDF on startup (cached)
- Extracts: course codes, days, times, rooms, sections, instructors
- Returns structured data as Python dicts
- Zero database dependency

### 2. **Enhanced Chat Handler** (`app/api/chat.py`)
- Updated `timetable_query` intent to use in-memory data
- Supports queries like:
  - "What's the schedule for CS-104?"
  - "What classes do I have on Monday?"
  - "Show me Tuesday's timetable"
- Falls back to database if available

### 3. **NLP Entity Extraction** (`app/nlp/entities.py`)
- Already extracts:
  - Course codes (CS-104, CSC-211, etc.)
  - Days (Monday, Tuesday, etc.)
  - Semesters
  - Degree levels

### 4. **Intent Routing** (`app/nlp/service.py`)
- "timetable_query" intent recognized with 90% confidence minimum
- Patterns: "time table", "class schedule", "when is", etc.

---

## 🚀 Quick Start

### Option A: Docker (Recommended)

```bash
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS

# Start database
docker-compose -f docker-compose.dev.yml up -d postgres

# Wait 10 seconds for postgres to start
sleep 10

# Install dependencies
cd backend
pip3 install -r requirements.txt

# Run migrations
psql -h localhost -p 55432 -U qau_advisor -d qau_advisor < ../database/schema.sql
psql -h localhost -p 55432 -U qau_advisor -d qau_advisor < ../database/seed.sql

# Start API
uvicorn app.main:app --reload --port 8000
```

### Option B: Docker Compose (Full Stack)

```bash
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS
docker-compose -f docker-compose.dev.yml up --build
```

---

## 🧪 Test the Chatbot

### Via API

```bash
# Test timetable query
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is CS-104 schedule?"}'

# Test day query
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What classes do I have on Monday?"}'

# Test semester query
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me semester 1 courses"}'
```

### Via Swagger UI

Visit: `http://localhost:8000/docs`

Go to `POST /api/v1/chat` and test directly in the browser.

---

## 📊 Supported Query Types

| Query | Example | Response |
|-------|---------|----------|
| **Course Schedule** | "When is CS-104?" | Day, time, room, instructor |
| **Day Schedule** | "What's Monday's timetable?" | All classes for that day |
| **Course Info** | "Tell me about CS-211" | Title, credits, prerequisites |
| **Semester Info** | "What courses are in Semester 1?" | Course list |
| **Instructor Info** | "Who teaches CS-104?" | Instructor name |

---

## 🔄 Data Flow

```
User Query
    ↓
[NLP Classifier] → Detects intent = "timetable_query"
    ↓
[Entity Extractor] → Extracts: course_code, day, semester
    ↓
[Chat Handler] → Calls search_timetable()
    ↓
[Timetable Data Parser] → Returns matching entries from PDF cache
    ↓
[Response Formatter] → Formats answer with citations
    ↓
User Gets Answer
```

---

## 📁 Files Changed/Created

### New Files
- `backend/app/rag/timetable_data.py` - Timetable parser (166 lines)

### Modified Files
- `backend/app/api/chat.py` - Enhanced timetable_query handler
- `backend/app/nlp/entities.py` - Already had day extraction

### Existing Infrastructure (Used)
- `backend/app/nlp/service.py` - Intent routing (no changes needed)
- `backend/app/nlp/classifier.py` - Intent classification
- `backend/app/nlp/entities.py` - Entity extraction
- `database/schema.sql` - All tables ready
- `database/seed.sql` - Sample data

---

## 🎯 Features

✅ Parses real QAU CS Spring 2026 timetable PDF
✅ Supports 7 days × 7 time slots = 49 possible class times
✅ Extracts course codes, rooms, sections, instructors
✅ Cache-based (fast, no DB dependency)
✅ Fallback to database queries if available
✅ Multilingual intent detection (English, Roman Urdu, Urdu script)
✅ Integrates with existing chat intent routing
✅ Full error handling and graceful degradation

---

## 🔧 Advanced Usage

### Direct Python Usage

```python
from app.rag.timetable_data import get_timetable, search_timetable

# Get all timetable entries
all_entries = get_timetable()

# Search for specific course
matches = search_timetable("CS-104")

# Filter by day
monday_classes = [e for e in get_timetable() if e['day'] == 'Monday']
```

### Add More Timetables

Edit `timetable_data.py` and update `TIMETABLE_PDF` path:

```python
TIMETABLE_PDF = Path(__file__).resolve().parents[3] / "TT_Fall_2025.pdf"
```

---

## 📝 Example Responses

**User:** "What is CS-104?"
**Bot:** "CS-104 (Problem Solving & Programming) meets on Monday from 08:35 to 10:05 in Room 201; Section: Regular, Instructor: Dr. Ghazanfar Farooq"

**User:** "Show me Friday classes"
**Bot:** "Friday Classes: 08:35-10:05: CS-423 in Room 201 | 10:15-11:45: FQ-102 in Room 217"

**User:** "When do I have labs?"
**Bot:** "CS Lab: Monday 08:35-10:05 | Tuesday 10:15-11:45 | Wednesday 11:55-13:25 | Thursday 15:15-16:45"

---

## ⚠️ Known Limitations

- Timetable is for Spring 2026 (hardcoded in PDF)
- Requires pdfplumber library (installed in requirements.txt)
- Rooms/instructors may show "TBA" if PDF parsing incomplete
- No real-time updates (cache on startup)

---

## 🐛 Troubleshooting

### "Module not found: pdfplumber"
```bash
pip3 install pdfplumber
```

### "No timetable data available"
- Check PDF path exists: `ls TT_v4.1*pdf`
- Check PDF is readable: `file TT_v4.1*pdf`
- Run with debug: `python3 -c "from app.rag.timetable_data import get_timetable; print(get_timetable()[:3])"`

### Database connection errors
- Ensure postgres is running: `docker-compose -f docker-compose.dev.yml ps`
- Check DATABASE_URL in app/core/config.py

---

## 🚀 Next Steps

1. **Test via API:** See curl examples above
2. **Customize responses:** Edit response templates in chat.py
3. **Add more PDFs:** Add scheme of study parser (template ready)
4. **Deploy:** Push to production with Docker

---

*Setup complete! Your chatbot now supports timetable queries. Start the server and ask: "What is my schedule for Monday?"*

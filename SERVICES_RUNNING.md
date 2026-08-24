# QAU CS Academic Advisor - Services Running

**Date**: August 24, 2026  
**Status**: ✅ ALL SERVICES OPERATIONAL

---

## Running Services

### 1. PostgreSQL Database (Docker Container)
- **Container Name**: `qau-advisor-postgres`
- **Image**: `pgvector/pgvector:pg16`
- **Status**: Up 2 hours (healthy)
- **Port Mapping**: `0.0.0.0:55432 -> 5432`
- **Connection**:
  - Host: `localhost`
  - Port: `55432`
  - Database: `qau_advisor`
  - User: `qau_advisor`
  - Password: `qau_advisor_local`

**Features Enabled:**
- ✅ pgvector extension for vector similarity search
- ✅ Full schema with all tables
- ✅ 39 knowledge documents processed
- ✅ 413 document chunks with embeddings
- ✅ 11 faculty members indexed
- ✅ 3 news articles stored

**Health Check:**
```bash
docker ps --filter "name=qau-advisor-postgres"
# or
PGPASSWORD=qau_advisor_local psql -h localhost -p 55432 -U qau_advisor -d qau_advisor -c "SELECT 1"
```

---

### 2. Backend API (FastAPI + Uvicorn)
- **Framework**: FastAPI
- **Server**: Uvicorn (with auto-reload)
- **Status**: Running
- **URL**: http://localhost:8000
- **Process**: Background process (term_1787523584989_hyfpto4dp8h)

**Endpoints Available:**
- Health: `GET http://localhost:8000/health`
- Chat: `POST http://localhost:8000/chat`
- Study Plan: `GET http://localhost:8000/study-plan`
- Timetable: `GET http://localhost:8000/timetable`

**Current Status Response:**
```json
{
  "status": "operational",
  "service": "QAU CS Academic Advisor",
  "version": "2.0.0",
  "mode": "RAG-Intelligent",
  "timetable_entries": 102,
  "courses_indexed": 100,
  "focus_areas": 6
}
```

**Features Enabled:**
- ✅ Hybrid RAG search (keyword 0.6 + semantic 0.4)
- ✅ Spell correction with academic vocabulary
- ✅ Synonym expansion for CS terms
- ✅ 5 new intents (faculty, research, admission, news, events)
- ✅ Intelligence layer (recommendations, prerequisites, scheduling)
- ✅ Response generation with citations
- ✅ Vector similarity search with pgvector
- ✅ Structured timetable extraction

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Starting Command:**
```bash
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 3. Frontend Web Application (React + Vite)
- **Framework**: React
- **Build Tool**: Vite 8.2.1
- **Status**: Running
- **URL**: http://localhost:5173
- **Process**: Background process (term_1787523643215_n5u3h3ewo9)

**Features:**
- ✅ Chat interface
- ✅ Study plan viewer
- ✅ Timetable display
- ✅ Real-time updates (Vite HMR)

**Health Check:**
```bash
curl -I http://localhost:5173/
```

**Starting Command:**
```bash
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS/frontend
npm run dev
```

---

## Service Architecture

```
┌─────────────────────────────────────────────┐
│  Frontend (React + Vite)                    │
│  http://localhost:5173                      │
└───────────────┬─────────────────────────────┘
                │ HTTP/REST API
                ▼
┌─────────────────────────────────────────────┐
│  Backend (FastAPI + Uvicorn)                │
│  http://localhost:8000                      │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ Chat Endpoint (POST /chat)           │  │
│  │  - Spell Correction                  │  │
│  │  - Synonym Expansion                 │  │
│  │  - Intent Detection (10+ intents)    │  │
│  │  - Entity Extraction                 │  │
│  │  - Hybrid RAG Search                 │  │
│  │  - Response Generation               │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ Intelligence Layer                   │  │
│  │  - Course Recommendations            │  │
│  │  - Prerequisite Validation           │  │
│  │  - Schedule Conflict Detection       │  │
│  └──────────────────────────────────────┘  │
└───────────────┬─────────────────────────────┘
                │ SQL + Vector Queries
                ▼
┌─────────────────────────────────────────────┐
│  PostgreSQL + pgvector (Docker)             │
│  localhost:55432                            │
│                                             │
│  - 39 knowledge_documents (ready)           │
│  - 413 document_chunks (with embeddings)    │
│  - 11 faculty_members                       │
│  - 3 news_articles                          │
│  - 100+ courses indexed                     │
│  - 102 timetable entries                    │
└─────────────────────────────────────────────┘
```

---

## Quick Access URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:5173 | Main web interface |
| Backend Health | http://localhost:8000/health | API status check |
| Backend Chat | http://localhost:8000/chat | Chat endpoint (POST) |
| PostgreSQL | localhost:55432 | Database connection |

---

## Testing the System

### 1. Test Backend Health
```bash
curl http://localhost:8000/health | python3 -m json.tool
```

### 2. Test Chat Endpoint
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Who is Dr. Rabeeh Abbasi?",
    "session_id": null,
    "context_course_code": null
  }' | python3 -m json.tool
```

### 3. Test Database Connection
```bash
PGPASSWORD=qau_advisor_local psql -h localhost -p 55432 -U qau_advisor -d qau_advisor -c "
SELECT 
  COUNT(*) as total_chunks,
  COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings
FROM document_chunks;
"
```

### 4. Test Frontend
Open browser: http://localhost:5173

---

## Process Management

### Check Running Processes
```bash
# List all background processes
docker ps  # For PostgreSQL
ps aux | grep uvicorn  # For backend
ps aux | grep vite  # For frontend
```

### Stop Services
```bash
# Stop backend (use Kiro process control or):
pkill -f "uvicorn app.main:app"

# Stop frontend:
pkill -f "vite"

# Stop PostgreSQL container:
docker stop qau-advisor-postgres
```

### Restart Services
```bash
# Restart PostgreSQL:
docker restart qau-advisor-postgres

# Restart backend:
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Restart frontend:
cd /Users/mm/AI-ADVISOR-FOR-QAU-CS/frontend
npm run dev
```

---

## Logs and Monitoring

### Backend Logs
The backend is running with auto-reload enabled. Logs show:
- Request/response activity
- Spell corrections applied
- Synonym expansions
- Intent detection results
- Database queries
- Error traces

Check logs in the Kiro process output or terminal where uvicorn is running.

### Frontend Logs
Vite development server shows:
- HMR updates
- Build warnings/errors
- HTTP requests
- Console output from React app

### Database Logs
```bash
docker logs qau-advisor-postgres -f
```

---

## Environment Variables

### Backend (.env or environment)
```bash
DATABASE_URL=postgresql+psycopg://qau_advisor:qau_advisor_local@localhost:55432/qau_advisor
APP_ENV=development
APP_DEBUG=true
CORS_ORIGINS='["http://localhost:5173"]'
NLP_CLASSIFIER_BACKEND=transformer
NLP_MODEL_PATH=models/qau-intent-distilmbert
AUTH_SECRET=qau-local-demo-change-before-production-2026
```

### Frontend
- API Base URL: http://localhost:8000 (configured in source)

---

## Recent Implementation (Phase 1-5)

All services are running with the newly implemented features:

✅ **Phase 1**: Database + RAG Foundation  
✅ **Phase 2**: Data Ingestion + Embeddings  
✅ **Phase 3**: NLP + Hybrid Search  
✅ **Phase 4**: Intelligence Layer  
✅ **Phase 5**: Chat Integration  

**New Capabilities Active:**
- Faculty information queries
- Research area exploration
- Admission information retrieval
- News and events display
- Hybrid search with spell correction and synonyms
- Intelligent course recommendations
- Prerequisite validation
- Schedule conflict detection

---

## Troubleshooting

### Backend Won't Start
**Error**: "Address already in use"
```bash
# Kill the process on port 8000
lsof -ti:8000 | xargs kill -9
# Restart
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Error**: "Module not found"
```bash
# Install missing dependencies
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Won't Start
**Error**: "Port 5173 is already in use"
```bash
# Kill vite process
pkill -f vite
# Restart
cd frontend && npm run dev
```

### Database Connection Issues
```bash
# Check if container is running
docker ps --filter "name=qau-advisor-postgres"

# Restart if needed
docker restart qau-advisor-postgres

# Check logs
docker logs qau-advisor-postgres --tail 50
```

### Embeddings Not Working
```bash
# Verify embeddings exist
PGPASSWORD=qau_advisor_local psql -h localhost -p 55432 -U qau_advisor -d qau_advisor -c "
SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL;
"

# If 0, regenerate embeddings
cd backend
source .venv/bin/activate
python scripts/generate_embeddings.py
```

---

## Development Workflow

### Making Changes

**Backend Code Changes:**
- Files in `backend/app/` are watched
- Uvicorn auto-reloads on file changes
- No restart needed

**Frontend Code Changes:**
- Files in `frontend/src/` are watched
- Vite HMR updates browser automatically
- No restart needed

**Database Schema Changes:**
- Requires migration/SQL execution
- Connection pool might need restart
- Restart backend after schema changes

### Testing New Features

1. **Test Backend Endpoint:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test query"}'
```

2. **Test Frontend:**
- Open http://localhost:5173
- Use browser DevTools console
- Check Network tab for API calls

3. **Test Database:**
```bash
PGPASSWORD=qau_advisor_local psql -h localhost -p 55432 -U qau_advisor -d qau_advisor
```

---

## Summary

**All three core services are operational:**

1. ✅ **PostgreSQL Database** (Docker on port 55432)
2. ✅ **Backend API** (FastAPI on port 8000)
3. ✅ **Frontend App** (React+Vite on port 5173)

**System is ready for:**
- User interaction via web interface
- API testing via curl/Postman
- Development with auto-reload
- Database queries and analysis

**Access the application at:** http://localhost:5173

**Monitor services using process managers or docker/lsof commands as documented above.**

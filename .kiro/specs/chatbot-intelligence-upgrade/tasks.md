# Implementation Plan: Chatbot Intelligence Upgrade

## Overview

This plan implements a comprehensive upgrade to the existing QAU CS academic advisor chatbot at `backend/app/api/chat.py`. The upgrade adds web scraping capabilities, hybrid RAG search, intelligent features (recommendations, validations, conflict detection), expanded domain coverage (faculty, research, news, events), and professional response formatting while maintaining backward compatibility and sub-second response times.

**Key Constraints:**
- All 50 requirements from requirements.md must be implemented
- Existing API signature and database schema preserved
- Response time ≤ 1 second for 95% of queries
- Answer accuracy ≥ 95%
- Multi-language support (English, Roman Urdu, Urdu) maintained

**Context:**
- Web scraper completed: 68 pages, 423,417 words stored in `academic-data/scraped/cs_website_full.json`
- Backend: FastAPI on port 8000
- Database: PostgreSQL with pgvector extension
- Frontend: React

## Tasks

### Phase 1: Foundation & Database Setup

- [x] 1. Create database schema extensions for new content types
  - [x] 1.1 Create migration script for new tables
    - Create `database/migrations/upgrade_chatbot_schema.sql`
    - Add `faculty_members` table with columns: id, source_id, full_name, title, email, phone, office_location, created_at, updated_at
    - Add `faculty_research_interests` table with columns: id, faculty_id, interest_text, created_at
    - Add `research_areas` table with columns: id, name, description, created_at, updated_at
    - Add `faculty_research_areas` junction table with columns: faculty_id, research_area_id
    - Add `news_articles` table with columns: id, source_id, title, content, published_at, expires_at, category, created_at
    - Add `events` table with columns: id, source_id, title, description, event_date, event_time, location, registration_url, expires_at, created_at
    - Add `knowledge_documents` table with columns: id, source_id, document_type, content, processing_status, created_at, updated_at
    - Add `document_chunks` table with columns: id, document_id, chunk_index, content, embedding vector(384), metadata JSONB, created_at
    - Add `scraper_runs` table with columns: id, started_at, completed_at, duration_seconds, pages_processed, pages_changed, pages_new, errors_encountered, error_log, status, created_at
    - Add `chat_feedback` table with columns: id, message_id, rating, comment, created_at
    - Add indexes: GIN on faculty full_name, news content, IVFFlat on embeddings, B-tree on dates
    - _Requirements: 27, 28, 22_

  - [ ]* 1.2 Write migration tests
    - Test table creation succeeds
    - Test foreign key constraints work
    - Test indexes are created
    - Verify pgvector extension available
    - _Requirements: 22_

  - [x] 1.3 Run migration on development database
    - Execute `database/migrations/upgrade_chatbot_schema.sql`
    - Verify all tables created with `\dt` in psql
    - Check indexes with `\di`
    - Verify foreign keys with `\d+ faculty_members`
    - _Requirements: 22_

- [x] 2. Set up hybrid search infrastructure
  - [x] 2.1 Create vector store module
    - Create `backend/app/rag/vector_store.py`
    - Implement `VectorStore` class using pgvector
    - Add `store_embedding(document_id, chunk_index, content, embedding)` method
    - Add `similarity_search(query_embedding, top_k=10, filters=None)` method returning list of (document_chunk, score)
    - Add `delete_document(document_id)` method to remove all chunks
    - Use cosine similarity via `<=>` operator
    - _Requirements: 3, 30_

  - [x] 2.2 Create embedding generator module
    - Create `backend/app/rag/embedder.py`
    - Implement `Embedder` class using sentence-transformers
    - Load model `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
    - Add `embed_text(text: str) -> np.ndarray` method
    - Add `embed_batch(texts: list[str]) -> list[np.ndarray]` method
    - Cache loaded model as singleton
    - _Requirements: 30_

  - [ ]* 2.3 Write vector store unit tests
    - Test embedding storage and retrieval
    - Test similarity search returns correct results
    - Test filtering by document_type
    - Test delete cascades properly
    - _Requirements: 3, 30_

- [~] 3. Checkpoint - Verify foundation setup
  - Ensure all tests pass, ask the user if questions arise.

### Phase 2: Web Scraping Implementation

- [ ] 4. Create scraper data ingestion pipeline
  - [x] 4.1 Create scraper storage module
    - Create `backend/app/scraper/storage.py`
    - Implement `ScraperStorage` class with database session
    - Add `store_faculty(data: dict, source_url: str) -> UUID` method
    - Add `store_news(data: dict, source_url: str) -> UUID` method
    - Add `store_event(data: dict, source_url: str) -> UUID` method
    - Add `create_or_update_source(url: str, title: str, checksum: str, category: str) -> UUID` method
    - Add `log_scraper_run(stats: dict)` method
    - Use transactions for atomic operations
    - _Requirements: 1, 26_

  - [x] 4.2 Create JSON parser for scraped data
    - Create `backend/app/scraper/parser.py`
    - Implement `parse_faculty_page(content: str, url: str) -> dict` extracting name, title, email, phone, research interests
    - Implement `parse_news_page(content: str, url: str) -> dict` extracting title, date, content
    - Implement `parse_course_page(content: str, url: str) -> dict` extracting code, title, description
    - Use regex and string matching for extraction
    - Handle missing fields gracefully with None
    - _Requirements: 1, 29_

  - [-] 4.3 Create scraper ingestion script
    - Create `backend/scripts/ingest_scraped_data.py`
    - Read `academic-data/scraped/cs_website_full.json`
    - For each page, detect content type (faculty, news, course, event)
    - Parse content using appropriate parser
    - Store in database via ScraperStorage
    - Create knowledge_documents entries for RAG
    - Log progress and errors
    - _Requirements: 1, 26_

  - [ ]* 4.4 Write scraper storage tests
    - Test faculty storage creates all linked records
    - Test duplicate detection by checksum
    - Test error logging
    - _Requirements: 1, 26_

  - [~] 4.5 Run data ingestion
    - Execute `python backend/scripts/ingest_scraped_data.py`
    - Verify faculty_members populated with `SELECT count(*) FROM faculty_members`
    - Verify news_articles populated
    - Verify source_records created
    - Check for errors in output
    - _Requirements: 1_

- [ ] 5. Implement embedding generation pipeline
  - [-] 5.1 Create document chunking module
    - Create `backend/app/rag/chunker.py`
    - Implement `chunk_document(content: str, max_chunk_size=512) -> list[str]`
    - Use sentence-aware chunking (split on `. `, `\n\n`)
    - Add 50-character overlap between chunks for continuity
    - Return list of text chunks
    - _Requirements: 30_

  - [-] 5.2 Create embedding generation script
    - Create `backend/scripts/generate_embeddings.py`
    - Query all `knowledge_documents` where `processing_status='pending'`
    - For each document, chunk content with `chunker.chunk_document()`
    - Generate embeddings with `embedder.embed_batch(chunks)`
    - Store chunks and embeddings in `document_chunks` table
    - Update `processing_status='ready'`
    - Log progress every 10 documents
    - _Requirements: 30_

  - [ ]* 5.3 Write chunking unit tests
    - Test chunking respects max size
    - Test overlap between chunks
    - Test sentence boundary preservation
    - _Requirements: 30_

  - [~] 5.4 Run embedding generation
    - Execute `python backend/scripts/generate_embeddings.py`
    - Verify `document_chunks` populated with `SELECT count(*) FROM document_chunks`
    - Check embeddings not null with `SELECT count(*) FROM document_chunks WHERE embedding IS NOT NULL`
    - Monitor memory usage during processing
    - _Requirements: 30_

- [~] 6. Checkpoint - Verify scraping pipeline works
  - Ensure all tests pass, ask the user if questions arise.

### Phase 3: Enhanced Query Processing

- [ ] 7. Expand intent classification for new domains
  - [-] 7.1 Add new intent patterns to NLP service
    - Edit `backend/app/nlp/service.py`
    - Add pattern for `faculty_information`: `r"\b(faculty|teacher|instructor|professor|staff|supervisor)\b"`
    - Add pattern for `research_area_query`: `r"\b(research|thesis topic|specialization|research area)\b"`
    - Add pattern for `admission_information`: `r"\b(admission|apply|entry|eligibility|requirement)\b"`
    - Add pattern for `news_query`: `r"\b(news|announcement|update|latest)\b"`
    - Add pattern for `event_query`: `r"\b(event|seminar|workshop|conference)\b"`
    - Set confidence threshold 0.85 for new intents
    - _Requirements: 31, 2_

  - [ ]* 7.2 Write intent classification tests
    - Test faculty query detected: "Who is Dr. Onaiza Maqbool?"
    - Test research query detected: "What research areas are available?"
    - Test admission query detected: "What are the admission requirements?"
    - Test news query detected: "What's the latest news?"
    - Test event query detected: "Upcoming seminars?"
    - _Requirements: 31_

- [ ] 8. Implement spell correction and synonym expansion
  - [-] 8.1 Create spell correction module
    - Create `backend/app/nlp/spell_correction.py`
    - Implement `SpellCorrector` class using edit distance algorithm
    - Build vocabulary from courses.title, academic_rules.description, faculty_members.full_name
    - Add `correct(text: str) -> str` method returning corrected text
    - Log corrections with confidence < 0.80
    - Cache vocabulary on startup
    - _Requirements: 17, 32_

  - [~] 8.2 Create synonym expansion module
    - Create `backend/app/nlp/synonyms.py`
    - Implement `SynonymExpander` class with static synonym dictionary
    - Add mappings: teacher→instructor,faculty; marks→grades,GPA; timetable→schedule; eligibility→prerequisites,requirements; FYP→thesis,final year project
    - Add `expand(text: str) -> str` method returning expanded text
    - Log expansions to entities["expanded_terms"]
    - _Requirements: 18, 43_

  - [~] 8.3 Integrate into query analyzer
    - Edit `backend/app/nlp/service.py`
    - In `analyze_query()`, apply spell correction before entity extraction
    - Apply synonym expansion after spell correction
    - Log corrections in entities["corrected_text"]
    - Preserve original text for debugging
    - _Requirements: 2, 17, 18_

  - [ ]* 8.4 Write spell correction tests
    - Test "pre-requistes" → "prerequisites"
    - Test "timtable" → "timetable"
    - Test course code variants "CS101" → "CS-101"
    - _Requirements: 17, 32_

- [ ] 9. Implement hybrid search engine
  - [~] 9.1 Create hybrid search module
    - Create `backend/app/rag/hybrid_search.py`
    - Implement `HybridSearchEngine` class with db and vector_store
    - Add `search(query: str, filters: dict, top_k=10) -> list[SearchResult]` method
    - Execute SQL keyword search using ts_vector on relevant tables
    - Execute vector similarity search on document_chunks
    - Merge results with weighted scoring: 0.6×keyword + 0.4×semantic
    - Boost verified sources by 1.3×
    - Sort by (score DESC, effective_from DESC)
    - _Requirements: 3_

  - [~] 9.2 Implement keyword search component
    - In `hybrid_search.py`, add `_keyword_search(query: str, filters: dict) -> list[KeywordResult]`
    - Query courses, academic_rules, faculty_members using ts_vector
    - Apply category filters from filters dict
    - Return results with relevance score
    - _Requirements: 3_

  - [~] 9.3 Implement semantic search component
    - In `hybrid_search.py`, add `_semantic_search(query: str, filters: dict) -> list[SemanticResult]`
    - Generate query embedding with embedder
    - Call vector_store.similarity_search()
    - Apply document_type filters
    - Return results with similarity score
    - _Requirements: 3_

  - [ ]* 9.4 Write hybrid search integration tests
    - Test keyword-only query returns SQL results
    - Test semantic-only query returns vector results
    - Test hybrid query merges both
    - Test verified source boosting
    - _Requirements: 3_

- [~] 10. Checkpoint - Verify query understanding enhanced
  - Ensure all tests pass, ask the user if questions arise.

### Phase 4: Intelligent Features Implementation

- [ ] 11. Implement course recommendation engine
  - [~] 11.1 Create recommendation module
    - Create `backend/app/intelligence/recommender.py`
    - Implement `RecommendationEngine` class with database session
    - Add `recommend_courses(student_id: UUID, limit=5) -> list[CourseRecommendation]` method
    - Query student_profiles for curriculum_id, current_semester, current_cgpa, focus_areas
    - Query student_course_history for completed courses
    - Filter curriculum_courses for eligible courses (semester alignment, prerequisites met)
    - Score courses: 0.4×semester_alignment + 0.3×focus_match + 0.2×cgpa_recovery + 0.1×availability
    - Return top-k with rationale strings
    - _Requirements: 13, 33_

  - [~] 11.2 Generate recommendation rationales
    - In `recommender.py`, add `_generate_rationale(course, profile, history, score) -> str`
    - Check semester alignment: "Recommended for Semester N in your program"
    - Check prerequisites satisfied: "You have completed all prerequisites"
    - Check focus area match: "Matches your interest in [area]"
    - Check GPA recovery: "This course has a high pass rate"
    - Combine conditions into natural language explanation
    - _Requirements: 45_

  - [ ]* 11.3 Write recommendation tests
    - Test semester alignment scoring
    - Test prerequisite filtering
    - Test focus area matching
    - Test GPA recovery prioritization
    - _Requirements: 13, 45_

- [ ] 12. Implement prerequisite validation
  - [~] 12.1 Create validation module
    - Create `backend/app/intelligence/validator.py`
    - Implement `PrerequisiteValidator` class with database session
    - Add `validate_eligibility(student_id: UUID, course_id: UUID) -> ValidationResult` method
    - Query course_prerequisites for target course
    - Query student_course_history for student
    - Check each prerequisite: course passed AND grade >= minimum_grade
    - Return ValidationResult with eligible flag, missing list, message
    - _Requirements: 14_

  - [~] 12.2 Build prerequisite chain resolver
    - In `validator.py`, add `get_prerequisite_chain(course_id: UUID) -> PrerequisiteChain` method
    - Recursively resolve all dependencies
    - Detect cycles and raise error
    - Return tree structure with levels
    - Format with indentation for display
    - _Requirements: 41_

  - [ ]* 12.3 Write validation tests
    - Test all prerequisites met returns eligible
    - Test missing prerequisite returns ineligible
    - Test minimum grade requirement checked
    - Test prerequisite chain resolution
    - Test cycle detection
    - _Requirements: 14, 41_

- [ ] 13. Implement schedule conflict detection
  - [~] 13.1 Create schedule analyzer module
    - Create `backend/app/intelligence/scheduler.py`
    - Implement `ScheduleAnalyzer` class with database session
    - Add `detect_conflicts(course_ids: list[UUID], term_id: UUID) -> ConflictReport` method
    - Query timetable_entries for all courses
    - Check overlapping times on same day_of_week
    - Calculate total credit hours vs maximum
    - Find alternative sections if conflicts exist
    - Return ConflictReport with conflicts list and alternatives
    - _Requirements: 15, 34_

  - [~] 13.2 Implement overlap detection algorithm
    - In `scheduler.py`, add `_is_overlapping(entry1, entry2) -> bool`
    - Compare day_of_week equality
    - Check time range overlap: starts_at < ends_at AND ends_at > starts_at
    - Return True if overlap exists
    - _Requirements: 15_

  - [ ]* 13.3 Write conflict detection tests
    - Test same day overlapping times detected
    - Test different day returns no conflict
    - Test credit hour limit exceeded warning
    - Test alternative section suggestions
    - _Requirements: 15_

- [~] 14. Checkpoint - Verify intelligent features working
  - Ensure all tests pass, ask the user if questions arise.

### Phase 5: Response Generation Enhancement

- [ ] 15. Create professional formatting utilities
  - [~] 15.1 Create formatter module
    - Create `backend/app/response/formatters.py`
    - Implement `FormatterRegistry` class
    - Add `format_course_details(course) -> str` returning "CODE: Title (X credits)"
    - Add `format_timetable_entry(entry) -> str` returning "Day HH:MM-HH:MM in Room"
    - Add `format_prerequisite_chain(chain) -> str` with indented tree
    - Add `format_citation(source) -> str` as markdown link
    - Add `format_course_list(courses) -> str` as bullet list
    - _Requirements: 8, 35_

  - [~] 15.2 Create response generator module
    - Create `backend/app/response/generator.py`
    - Implement `ResponseGenerator` class with language parameter
    - Add `generate_course_response(course, additional_info) -> str` with sections
    - Add `generate_multi_intent_response(answers) -> str` with headers
    - Add `_intent_to_header(intent) -> str` mapping intent to readable title
    - Use markdown headers (##), bullets, bold
    - _Requirements: 8, 40_

  - [~] 15.3 Create multi-source aggregator
    - Create `backend/app/response/aggregator.py`
    - Implement `MultiSourceAggregator` class with db and vector_store
    - Add `aggregate_course_info(course_code) -> dict` fetching course, prerequisites, offerings, related
    - Add `aggregate_program_info(program_code) -> dict` fetching program, curriculum, courses, requirements
    - Use asyncio.gather for parallel queries
    - _Requirements: 16_

  - [ ]* 15.4 Write formatting tests
    - Test course details formatted correctly
    - Test timetable entry readable
    - Test prerequisite chain indented
    - Test markdown links valid
    - _Requirements: 8, 35_

- [ ] 16. Implement citation management
  - [~] 16.1 Create citation module
    - Create `backend/app/response/citations.py`
    - Implement `CitationManager` class with database session
    - Add `extract_citations(results: list[SearchResult]) -> list[dict]` method
    - Deduplicate by source_id
    - Include source_code, title, source_url, verification_status
    - Add `trace_chunk_to_source(chunk_id: UUID) -> SourceRecord` method
    - Add `format_citations_section(citations) -> str` as markdown numbered list
    - _Requirements: 23, 38_

  - [ ]* 16.2 Write citation tests
    - Test citation deduplication
    - Test chunk tracing to source
    - Test markdown formatting
    - Test URL link generation
    - _Requirements: 23, 38_

- [ ] 17. Enhance response delivery with intelligent features
  - [~] 17.1 Create response enhancement module
    - Create `backend/app/response/enhancer.py`
    - Implement `enhance_with_intelligence(answer, result, context, user, db) -> str`
    - For course queries: add recommendations if user authenticated
    - For prerequisite queries: add validation if user authenticated
    - For timetable queries: add conflict detection for multiple courses
    - Add upcoming deadline reminders (within 14 days)
    - Add related information section
    - _Requirements: 10, 13, 14, 15, 49_

  - [~] 17.2 Implement proactive deadline reminders
    - In `enhancer.py`, add `_get_upcoming_deadlines(db, days=14) -> list[dict]`
    - Query deadlines where closes_at between NOW and NOW+days
    - Format as "⚠ Upcoming Deadlines" section
    - Use urgent formatting for deadlines within 3 days
    - _Requirements: 49_

  - [~] 17.3 Add related information suggestions
    - In `enhancer.py`, add `_suggest_related_info(result, db) -> str`
    - For course queries: suggest courses with matching focus_areas
    - For faculty queries: suggest related research areas
    - For research queries: suggest faculty and courses
    - For program queries: suggest related degree levels
    - Format as "## Related Information" section
    - _Requirements: 48_

  - [ ]* 17.4 Write enhancement tests
    - Test recommendations added for course queries
    - Test validation added for prerequisite queries
    - Test deadline reminders within 14 days
    - Test related information suggested
    - _Requirements: 10, 48, 49_

- [~] 18. Checkpoint - Verify response quality improved
  - Ensure all tests pass, ask the user if questions arise.

### Phase 6: Intent Handler Implementation

- [ ] 19. Implement faculty query handlers
  - [~] 19.1 Create faculty handler function
    - In `backend/app/api/chat.py`, add `handle_faculty_query(entities, db) -> tuple[str, str, bool, list[dict]]`
    - Extract faculty name from entities
    - Query faculty_members with fuzzy name matching
    - If found: return name, title, email, phone, office, research interests
    - Use hybrid_search for semantic matching if exact match fails
    - Include citations from source_records
    - Format with markdown sections
    - _Requirements: 4_

  - [ ]* 19.2 Write faculty handler tests
    - Test exact name match returns details
    - Test fuzzy name matching works
    - Test research interests included
    - Test citations returned
    - _Requirements: 4_

- [ ] 20. Implement research area query handlers
  - [~] 20.1 Create research area handler function
    - In `backend/app/api/chat.py`, add `handle_research_query(entities, db) -> tuple[str, str, bool, list[dict]]`
    - Extract research area from entities
    - Query research_areas table
    - Return area description, faculty members, related courses
    - Use multi-source aggregation for completeness
    - _Requirements: 5_

  - [ ]* 20.2 Write research handler tests
    - Test research area details returned
    - Test faculty list included
    - Test related courses suggested
    - _Requirements: 5_

- [ ] 21. Implement admission query handlers
  - [~] 21.1 Create admission handler function
    - In `backend/app/api/chat.py`, add `handle_admission_query(entities, db) -> tuple[str, str, bool, list[dict]]`
    - Query academic_rules where category='admission'
    - Query deadlines where deadline_type='admission' and closes_at > NOW
    - Return requirements, procedures, deadlines
    - Use verified sources only
    - _Requirements: 6_

  - [ ]* 21.2 Write admission handler tests
    - Test requirements returned
    - Test deadlines included
    - Test verified sources prioritized
    - _Requirements: 6_

- [ ] 22. Implement news and events query handlers
  - [~] 22.1 Create news handler function
    - In `backend/app/api/chat.py`, add `handle_news_query(entities, db) -> tuple[str, str, bool, list[dict]]`
    - Query news_articles where published_at > NOW-90 days
    - Filter by category if specified in entities
    - Order by published_at DESC
    - Check expires_at not in past
    - _Requirements: 7_

  - [~] 22.2 Create events handler function
    - In `backend/app/api/chat.py`, add `handle_event_query(entities, db) -> tuple[str, str, bool, list[dict]]`
    - Query events where event_date >= NOW
    - Filter by category if specified
    - Include registration_url if available
    - Order by event_date ASC
    - _Requirements: 7_

  - [ ]* 22.3 Write news/events handler tests
    - Test recent news within 90 days
    - Test upcoming events only
    - Test expired content excluded
    - _Requirements: 7_

- [ ] 23. Integrate new handlers into main chat endpoint
  - [~] 23.1 Update _safe_answer routing
    - Edit `backend/app/api/chat.py` function `_safe_answer()`
    - Add routing for faculty_information intent
    - Add routing for research_area_query intent
    - Add routing for admission_information intent
    - Add routing for news_query intent
    - Add routing for event_query intent
    - Call appropriate handler functions
    - Maintain existing routing for backward compatibility
    - _Requirements: 31, 4, 5, 6, 7_

  - [~] 23.2 Add response enhancement call
    - In `chat()` endpoint, after `_safe_answer()` call
    - Call `enhance_with_intelligence(answer, result, context, user, db)`
    - Replace answer with enhanced version
    - Preserve citations and verified status
    - _Requirements: 10_

  - [ ]* 23.3 Write end-to-end handler tests
    - Test faculty query returns formatted response
    - Test research query returns complete info
    - Test admission query includes deadlines
    - Test news query shows recent articles
    - Test event query shows upcoming events
    - _Requirements: 4, 5, 6, 7_

- [~] 24. Checkpoint - Verify all intents handled correctly
  - Ensure all tests pass, ask the user if questions arise.

### Phase 7: Session Management & Follow-Up Enhancement

- [ ] 25. Implement session context enrichment
  - [~] 25.1 Create context enrichment function
    - In `backend/app/api/chat.py`, add `enrich_with_session_context(session_id, result, db) -> dict`
    - Query last 3 messages from chat_messages for session
    - Extract previous intent and entities
    - Detect follow-up indicators: "and", "also", "what about", "how about", "it", "that", "this"
    - Return context dict with history, previous_intent, previous_entities
    - _Requirements: 11, 39_

  - [~] 25.2 Update entity extraction for follow-ups
    - Edit `backend/app/nlp/entities.py`
    - Add function `resolve_pronouns(entities, context) -> dict`
    - Replace "it", "that", "this" with entities from context
    - Merge previous entities when follow-up detected
    - Prioritize current entities over previous
    - _Requirements: 12, 39_

  - [~] 25.3 Integrate context into chat endpoint
    - In `chat()` endpoint, after `analyze_query()`
    - If session_id provided, call `enrich_with_session_context()`
    - Pass context to `_safe_answer()` and handlers
    - Update `_safe_answer()` signature to accept context parameter
    - _Requirements: 11_

  - [ ]* 25.4 Write session context tests
    - Test follow-up detected from "and" prefix
    - Test pronoun resolution works
    - Test previous entities inherited
    - Test context expires after 30 minutes
    - _Requirements: 11, 12, 39_

- [ ] 26. Implement smart session timeout
  - [~] 26.1 Add session activity tracking
    - In `chat()` endpoint, update last_activity_at in auth_sessions
    - Check if session ended_at is set
    - If session inactive for 30 minutes, set ended_at and return error
    - Prompt user to start new session if expired
    - _Requirements: 42_

  - [ ]* 26.2 Write session timeout tests
    - Test active session continues
    - Test inactive session expires after 30 minutes
    - Test expired session returns error
    - _Requirements: 42_

- [ ] 27. Implement complex query decomposition
  - [~] 27.1 Add multi-intent detection
    - Edit `backend/app/nlp/service.py`
    - In `analyze_query()`, detect multiple intents from patterns
    - Split query by "and", "also" if confidence > 0.70 for both sides
    - Return list of intents in result["intents"]
    - Maintain backward compatibility with single result["intent"]
    - _Requirements: 25_

  - [~] 27.2 Update response generator for multi-part queries
    - Edit `backend/app/response/generator.py`
    - In `generate_multi_intent_response()`, create section per intent
    - Use markdown headers "## [Topic]" to separate
    - Combine all sections into single response
    - Add "## Related Information" at end
    - _Requirements: 25, 40_

  - [ ]* 27.3 Write multi-intent tests
    - Test "What are prerequisites for CS-301 and when is it offered?" splits correctly
    - Test both intents answered in sections
    - Test shared entities extracted once
    - _Requirements: 25_

- [~] 28. Checkpoint - Verify conversation flow natural
  - Ensure all tests pass, ask the user if questions arise.

### Phase 8: Performance Optimization & Monitoring

- [ ] 29. Implement caching strategy
  - [~] 29.1 Add course information caching
    - Create `backend/app/cache.py`
    - Implement TTLCache for courses (15 min TTL, 1000 max size)
    - Cache by course_code key
    - Use functools.lru_cache for embeddings (10000 max size)
    - _Requirements: 19_

  - [~] 29.2 Add faculty information caching
    - In `cache.py`, add TTLCache for faculty (30 min TTL, 500 max size)
    - Cache by faculty_id key
    - Invalidate on scraper updates
    - _Requirements: 19_

  - [~] 29.3 Integrate caching into handlers
    - Edit faculty and course handlers to check cache first
    - On cache miss, query database and store result
    - Log cache hit rate in metrics
    - _Requirements: 19_

- [ ] 30. Add performance metrics and monitoring
  - [~] 30.1 Add response time tracking
    - In `chat()` endpoint, track response_time_ms (already exists)
    - Log queries exceeding 1000ms to separate file
    - Add execution plan logging for slow queries
    - _Requirements: 19, 37_

  - [~] 30.2 Add quality metrics tracking
    - In `chat()` endpoint, log intent_confidence (already exists)
    - Track response_engine distribution (sql, rag, fallback)
    - Count fallback responses separately
    - Add daily summary metrics
    - _Requirements: 37_

  - [~] 30.3 Create monitoring dashboard endpoint
    - Create `backend/app/api/metrics.py`
    - Add `/metrics` endpoint returning JSON statistics
    - Include: avg_response_time, fallback_rate, cache_hit_rate
    - Include: intent_distribution, language_distribution
    - Require admin authentication
    - _Requirements: 37, 44_

- [ ] 31. Implement comprehensive error handling
  - [~] 31.1 Create error handler module
    - Create `backend/app/errors/handler.py`
    - Implement `ErrorHandler` class
    - Add `handle_user_input_error(error) -> dict` returning friendly message
    - Add `handle_data_error(error) -> dict` for missing data
    - Add `handle_system_error(error) -> dict` with logging
    - _Requirements: 44_

  - [~] 31.2 Add retry strategy for transient failures
    - In `handler.py`, add `with_retry(func, max_attempts=3)` decorator
    - Implement exponential backoff: 1s, 2s, 4s
    - Catch database connection errors and retry
    - Log all retry attempts
    - _Requirements: 44_

  - [~] 31.3 Integrate error handling into endpoints
    - Edit `backend/app/api/chat.py`
    - Wrap database queries in try-except with ErrorHandler
    - Use with_retry for critical operations
    - Return user-friendly error messages
    - Log all errors with request_id
    - _Requirements: 44_

- [~] 32. Checkpoint - Verify performance meets requirements
  - Ensure all tests pass, ask the user if questions arise.

### Phase 9: Feedback & Quality Assurance

- [ ] 33. Implement feedback collection
  - [~] 33.1 Create feedback endpoint
    - Create `backend/app/api/feedback.py`
    - Add `/chat/feedback` POST endpoint accepting message_id, rating, comment
    - Verify message_id belongs to user's session
    - Store in chat_feedback table
    - Return success response
    - _Requirements: 50_

  - [~] 33.2 Add feedback analysis utilities
    - Create `backend/scripts/analyze_feedback.py`
    - Query negative feedback (rating < 3)
    - Group by intent and response_engine
    - Generate report of problematic queries
    - Suggest improvements based on patterns
    - _Requirements: 50_

  - [ ]* 33.3 Write feedback endpoint tests
    - Test valid feedback stored
    - Test invalid message_id rejected
    - Test unauthorized user blocked
    - _Requirements: 50_

- [ ] 34. Implement answer verification system
  - [~] 34.1 Add verification status checks
    - In all handlers, check source_records.verification_status
    - Prioritize 'verified' over 'referenced' over 'unverified'
    - Prefix unverified answers with disclaimer
    - Set response verified=False for unverified sources
    - _Requirements: 20, 46_

  - [~] 34.2 Add confidence threshold enforcement
    - In `analyze_query()`, if confidence < 0.70, set intent='fallback'
    - In handlers, if no results found, return clarification request
    - Never return guessed answers
    - Suggest contacting department for low-confidence queries
    - _Requirements: 20_

  - [ ]* 34.3 Write verification tests
    - Test verified sources prioritized
    - Test unverified disclaimer added
    - Test low confidence returns fallback
    - _Requirements: 20, 46_

- [ ] 35. Comprehensive end-to-end testing
  - [ ]* 35.1 Test course query workflow
    - User asks "What are prerequisites for CS-301?"
    - System returns prerequisites with verification
    - System adds recommendations if user logged in
    - System includes related courses
    - Response time < 1 second
    - _Requirements: All_

  - [ ]* 35.2 Test faculty search workflow
    - User asks "Who teaches machine learning?"
    - System searches faculty research interests
    - Returns faculty names, contact info, research areas
    - Includes citations to faculty pages
    - _Requirements: 4, 23_

  - [ ]* 35.3 Test multi-language workflow
    - User asks in Urdu "فیس کتنی ہے؟"
    - System detects Urdu language
    - Returns fee information in Urdu
    - Maintains technical terms in English
    - _Requirements: 24_

  - [ ]* 35.4 Test follow-up question workflow
    - User asks "What is CS-301?"
    - System returns course info
    - User asks "What about prerequisites?"
    - System resolves "prerequisites" to CS-301
    - Returns prerequisite chain
    - _Requirements: 11, 12, 39_

  - [ ]* 35.5 Test complex query workflow
    - User asks "What are prerequisites for CS-301 and when is it offered?"
    - System detects two intents
    - Returns sections for prerequisites and timetable
    - Both questions fully answered
    - _Requirements: 25, 40_

- [~] 36. Final checkpoint - Complete system verification
  - Ensure all tests pass, ask the user if questions arise.

### Phase 10: Documentation & Deployment

- [ ] 37. Create system documentation
  - [~] 37.1 Document API changes
    - Update API documentation in `docs/api.md`
    - Document new intents and their responses
    - Document feedback endpoint
    - Document metrics endpoint
    - Include example requests and responses
    - _Requirements: All_

  - [~] 37.2 Document configuration
    - Create `docs/configuration.md`
    - Document cache TTL settings
    - Document vector search parameters
    - Document scraper schedule
    - Document performance thresholds
    - _Requirements: All_

  - [~] 37.3 Create operator guide
    - Create `docs/operations.md`
    - Document how to run data ingestion
    - Document how to generate embeddings
    - Document how to monitor performance
    - Document how to analyze feedback
    - _Requirements: All_

- [ ] 38. Prepare production deployment
  - [~] 38.1 Create deployment checklist
    - Create `DEPLOYMENT_CHECKLIST.md`
    - List: Run migrations, ingest data, generate embeddings
    - List: Verify indexes created, test sample queries
    - List: Configure caching, enable monitoring
    - List: Set up scheduled scraper runs
    - _Requirements: All_

  - [~] 38.2 Update environment configuration
    - Update `.env.example` with new variables
    - Add VECTOR_STORE_TYPE, EMBEDDING_MODEL, EMBEDDING_DIM
    - Add CACHE_TTL_COURSE, CACHE_TTL_FACULTY
    - Add SCRAPER_SCHEDULE, SCRAPER_BASE_URL
    - Add HYBRID_SEARCH_KEYWORD_WEIGHT, HYBRID_SEARCH_SEMANTIC_WEIGHT
    - _Requirements: All_

  - [~] 38.3 Run production deployment
    - Execute database migrations on production
    - Run scraper data ingestion
    - Generate embeddings for all documents
    - Verify all tables populated
    - Test sample queries from production
    - Monitor performance metrics
    - _Requirements: All_

- [~] 39. Final verification and handoff
  - System meets all 50 requirements
  - Response time ≤ 1 second verified
  - Answer accuracy ≥ 95% verified
  - Multi-language support working
  - Backward compatibility confirmed
  - Documentation complete
  - Production deployment successful

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP delivery
- Each task references specific requirements from requirements.md for traceability
- Checkpoints ensure incremental validation throughout implementation
- All database queries must use parameterized statements to prevent SQL injection
- All user input must be validated before processing
- Response times must be logged for all queries to monitor performance
- Error logging must include sufficient context for debugging without exposing sensitive data
- Cache invalidation must occur when source data is updated by scraper
- Vector similarity threshold of 0.75 ensures relevant results only
- Hybrid search weights (0.6 keyword, 0.4 semantic) can be tuned based on feedback
- Session timeout of 30 minutes balances memory usage with user experience
- Feedback collection enables continuous improvement of answer quality

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "2.2"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.3", "4.1", "4.2"] },
    { "id": 2, "tasks": ["4.3", "4.4", "5.1"] },
    { "id": 3, "tasks": ["4.5", "5.2", "5.3"] },
    { "id": 4, "tasks": ["5.4", "7.1", "7.2", "8.1", "8.2"] },
    { "id": 5, "tasks": ["8.3", "8.4", "9.1", "9.2", "9.3", "9.4"] },
    { "id": 6, "tasks": ["11.1", "11.2", "11.3", "12.1", "12.2", "12.3", "13.1", "13.2", "13.3"] },
    { "id": 7, "tasks": ["15.1", "15.2", "15.3", "15.4", "16.1", "16.2"] },
    { "id": 8, "tasks": ["17.1", "17.2", "17.3", "17.4", "19.1", "19.2", "20.1", "20.2", "21.1", "21.2", "22.1", "22.2", "22.3"] },
    { "id": 9, "tasks": ["23.1", "23.2", "23.3", "25.1", "25.2"] },
    { "id": 10, "tasks": ["25.3", "25.4", "26.1", "26.2", "27.1", "27.2", "27.3"] },
    { "id": 11, "tasks": ["29.1", "29.2", "29.3", "30.1", "30.2", "30.3", "31.1", "31.2", "31.3"] },
    { "id": 12, "tasks": ["33.1", "33.2", "33.3", "34.1", "34.2", "34.3"] },
    { "id": 13, "tasks": ["35.1", "35.2", "35.3", "35.4", "35.5"] },
    { "id": 14, "tasks": ["37.1", "37.2", "37.3", "38.1", "38.2"] },
    { "id": 15, "tasks": ["38.3", "39"] }
  ]
}
```

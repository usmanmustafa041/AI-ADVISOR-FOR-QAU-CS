# Requirements Document: Chatbot Intelligence Upgrade

## Introduction

This document specifies the requirements for enhancing the existing QAU CS academic advisor chatbot system. The chatbot currently provides database-driven responses for academic queries in multiple languages with citation support. This upgrade will add web scraping capabilities, improve query understanding, expand coverage to faculty and research domains, enhance response quality, and implement intelligent features such as conversation tracking and proactive recommendations. All enhancements must preserve backward compatibility with the existing system while maintaining sub-second response times and achieving 95%+ answer accuracy.

## Glossary

- **Chatbot_System**: The existing FastAPI-based conversational interface in backend/app/api/chat.py that processes user queries and returns academic information
- **Query_Analyzer**: The NLP service component (app/nlp/service.py) that performs intent classification, entity extraction, and language detection
- **Knowledge_Base**: The PostgreSQL database containing courses, programs, timetables, fees, policies, and academic rules
- **Web_Scraper**: A new component that extracts information from cs.qau.edu.pk pages and stores it in the Knowledge_Base
- **RAG_Engine**: The retrieval-augmented generation system that combines database queries with semantic search over document_chunks
- **Response_Generator**: The component within the Chatbot_System that constructs answers by aggregating data from multiple sources
- **Session_Manager**: The component that tracks conversation history in chat_sessions and chat_messages tables
- **Citation_Provider**: The component that returns source_records references for all answers
- **Hybrid_Search**: A search strategy combining keyword matching (SQL queries) with semantic similarity (vector embeddings)
- **Intent_Router**: The logic that maps user queries to specific handler functions based on detected intent
- **Entity_Extractor**: The component that identifies structured information such as course codes, dates, and names from user queries
- **Recommendation_Engine**: A new component that suggests related courses, detects conflicts, and provides academic guidance
- **Multi_Language_Processor**: The component supporting English, Roman Urdu, and Urdu script inputs and outputs
- **Source_Verifier**: The component that checks verification_status of source_records before presenting information
- **Prerequisite_Validator**: A new component that verifies course eligibility based on student history and prerequisite rules
- **Schedule_Analyzer**: A new component that detects timetable conflicts and validates course combinations

## Requirements

### Requirement 1: Web Content Acquisition

**User Story:** As a system administrator, I want the system to automatically scrape cs.qau.edu.pk, so that the Knowledge_Base remains current with official department information.

#### Acceptance Criteria

1. WHEN the Web_Scraper runs, THE Web_Scraper SHALL extract all accessible pages from cs.qau.edu.pk
2. WHEN a page is scraped, THE Web_Scraper SHALL parse structured data including course descriptions, faculty profiles, research areas, news articles, and policy documents
3. WHEN scraped content is parsed, THE Web_Scraper SHALL compute a checksum_sha256 for change detection
4. WHEN scraped content differs from stored content, THE Web_Scraper SHALL update the corresponding source_records entry and set verification_status to 'referenced'
5. WHEN the Web_Scraper encounters a page error, THE Web_Scraper SHALL log the error without terminating the scraping process
6. WHEN scraped content includes faculty information, THE Web_Scraper SHALL store names, titles, email addresses, phone numbers, office locations, and research interests
7. WHEN scraped content includes research areas, THE Web_Scraper SHALL store area names, descriptions, and associated faculty members
8. WHEN scraped content includes news or events, THE Web_Scraper SHALL store titles, publication dates, content, and expiration dates
9. WHEN the Web_Scraper completes a run, THE Web_Scraper SHALL record the completion timestamp and summary statistics

### Requirement 2: Enhanced Query Understanding

**User Story:** As a student, I want the chatbot to understand my questions even with spelling errors or synonyms, so that I can get accurate answers without perfect phrasing.

#### Acceptance Criteria

1. WHEN a user query contains common spelling errors, THE Query_Analyzer SHALL normalize the text using spell correction before intent classification
2. WHEN a user query contains synonym terms, THE Query_Analyzer SHALL expand the query with equivalent academic vocabulary
3. WHEN a user query is ambiguous and confidence is below 0.70, THE Query_Analyzer SHALL request clarification by presenting multiple interpretation options
4. WHEN a user query contains multiple intents, THE Query_Analyzer SHALL detect all intents and prioritize based on context
5. WHEN a user query includes course code variations, THE Entity_Extractor SHALL normalize codes to the standard format
6. WHEN the Query_Analyzer detects Roman Urdu input, THE Query_Analyzer SHALL preserve language-specific patterns during normalization
7. WHEN the Query_Analyzer detects Urdu script input, THE Query_Analyzer SHALL apply Urdu-aware tokenization before entity extraction

### Requirement 3: Hybrid Search Implementation

**User Story:** As a student, I want the chatbot to find relevant information using both keywords and meaning, so that I receive comprehensive answers even when exact matches are not available.

#### Acceptance Criteria

1. WHEN the RAG_Engine processes a query, THE RAG_Engine SHALL execute both SQL keyword queries and vector similarity searches
2. WHEN keyword search results exist, THE RAG_Engine SHALL rank results by relevance score combining recency, verification_status, and text match quality
3. WHEN vector search results exist, THE RAG_Engine SHALL retrieve document_chunks with cosine similarity above 0.75
4. WHEN both keyword and vector results exist, THE RAG_Engine SHALL merge results using a weighted scoring function favoring verified sources
5. WHEN the RAG_Engine retrieves document_chunks, THE RAG_Engine SHALL include surrounding context chunks for continuity
6. WHEN the Knowledge_Base lacks sufficient results, THE RAG_Engine SHALL indicate low confidence and suggest contacting the department

### Requirement 4: Faculty Query Support

**User Story:** As a student, I want to ask about faculty members, so that I can find supervisors, contact information, and research expertise.

#### Acceptance Criteria

1. WHEN a user query requests faculty contact information, THE Response_Generator SHALL return name, email, phone, and office location
2. WHEN a user query requests faculty expertise, THE Response_Generator SHALL return research interests and associated research areas
3. WHEN a user query requests faculty by research area, THE Response_Generator SHALL return all faculty members associated with that area
4. WHEN a user query requests thesis supervision, THE Response_Generator SHALL return faculty members with relevant research interests
5. WHEN faculty information is unavailable, THE Response_Generator SHALL return a fallback message directing the user to the department website

### Requirement 5: Research Area Query Support

**User Story:** As a student, I want to explore research areas, so that I can choose thesis topics and identify relevant faculty supervisors.

#### Acceptance Criteria

1. WHEN a user query requests available research areas, THE Response_Generator SHALL return all active research area names and descriptions
2. WHEN a user query requests details about a specific research area, THE Response_Generator SHALL return the description, associated faculty, and related courses
3. WHEN a user query requests courses related to a research area, THE Response_Generator SHALL return courses linked via course_focus_areas
4. WHEN a user query requests faculty in a research area, THE Response_Generator SHALL return faculty members with matching research interests

### Requirement 6: Admission Process Query Support

**User Story:** As a prospective student, I want information about admission requirements and procedures, so that I can prepare my application correctly.

#### Acceptance Criteria

1. WHEN a user query requests admission requirements, THE Response_Generator SHALL return program-specific entry criteria from academic_rules with category 'admission'
2. WHEN a user query requests admission deadlines, THE Response_Generator SHALL return deadline records with deadline_type 'admission' and closes_at in the future
3. WHEN a user query requests admission procedures, THE Response_Generator SHALL return step-by-step guidance from academic_rules with category 'admission'
4. WHEN admission information is verified, THE Response_Generator SHALL include citations from source_records with verification_status 'verified'

### Requirement 7: News and Events Query Support

**User Story:** As a student, I want to know about recent news and upcoming events, so that I can stay informed about department activities.

#### Acceptance Criteria

1. WHEN a user query requests recent news, THE Response_Generator SHALL return news articles from the past 90 days sorted by publication date descending
2. WHEN a user query requests upcoming events, THE Response_Generator SHALL return events with event dates in the future
3. WHEN a user query requests specific event types, THE Response_Generator SHALL filter results by event category
4. WHEN news or event information is time-sensitive, THE Response_Generator SHALL verify effective dates before inclusion

### Requirement 8: Professional Response Formatting

**User Story:** As a student, I want answers formatted clearly with sections and bullets, so that I can quickly scan and understand the information.

#### Acceptance Criteria

1. WHEN the Response_Generator constructs multi-part answers, THE Response_Generator SHALL organize content using markdown sections with descriptive headers
2. WHEN the Response_Generator presents lists, THE Response_Generator SHALL use bullet points or numbered lists
3. WHEN the Response_Generator presents course details, THE Response_Generator SHALL include course code, title, credit hours, and description in a consistent format
4. WHEN the Response_Generator presents timetable information, THE Response_Generator SHALL format entries as day, time range, location, and section
5. WHEN the Response_Generator presents prerequisite chains, THE Response_Generator SHALL display courses in dependency order

### Requirement 9: Comprehensive Answer Delivery

**User Story:** As a student, I want complete answers with all relevant details upfront, so that I do not need to ask follow-up questions for obvious information.

#### Acceptance Criteria

1. WHEN a user asks about a course, THE Response_Generator SHALL include code, title, credit hours, description, semester placement, prerequisites, and current offerings
2. WHEN a user asks about registration, THE Response_Generator SHALL include deadlines, procedures, required documents, and contact information
3. WHEN a user asks about a program, THE Response_Generator SHALL include duration, total credits, core courses, electives, and graduation requirements
4. WHEN a user asks about fees, THE Response_Generator SHALL include admission fees, semester fees, and total program cost estimates
5. WHEN the Response_Generator provides numeric limits, THE Response_Generator SHALL include both minimum and maximum bounds

### Requirement 10: Proactive Recommendations

**User Story:** As a student, I want the chatbot to suggest related information, so that I discover relevant details I might not have thought to ask about.

#### Acceptance Criteria

1. WHEN the Response_Generator answers a course query, THE Response_Generator SHALL suggest related courses based on focus_areas
2. WHEN the Response_Generator answers a prerequisite query, THE Response_Generator SHALL suggest the full prerequisite chain leading to the course
3. WHEN the Response_Generator detects a student is near credit limits, THE Response_Generator SHALL recommend staying within the allowed range
4. WHEN the Response_Generator answers a registration query, THE Response_Generator SHALL remind the user of approaching deadlines
5. WHEN the Response_Generator answers a program query for a new student, THE Response_Generator SHALL suggest first-semester courses

### Requirement 11: Conversation History Tracking

**User Story:** As a student, I want the chatbot to remember our conversation, so that I can ask follow-up questions without repeating context.

#### Acceptance Criteria

1. WHEN a user sends a message with a session_id, THE Session_Manager SHALL retrieve previous messages from chat_messages for that session
2. WHEN the Query_Analyzer processes a query with session history, THE Query_Analyzer SHALL use the last three messages as context for intent detection
3. WHEN a user query contains pronouns or references, THE Entity_Extractor SHALL resolve them using entities from the previous message
4. WHEN a session exceeds 50 messages, THE Session_Manager SHALL summarize early messages to maintain context without exceeding token limits
5. WHEN a session has been inactive for 30 minutes, THE Session_Manager SHALL set ended_at and require a new session for subsequent queries

### Requirement 12: Follow-Up Question Handling

**User Story:** As a student, I want to ask follow-up questions naturally, so that conversations flow smoothly without restating context.

#### Acceptance Criteria

1. WHEN a user query begins with "what about" or "and", THE Query_Analyzer SHALL inherit the intent from the previous assistant message
2. WHEN a user query contains "that course" or "this program", THE Entity_Extractor SHALL resolve references to entities from the previous message
3. WHEN a user query asks for "more details", THE Response_Generator SHALL expand the previous answer with additional information from related tables
4. WHEN a user query requests alternatives, THE Response_Generator SHALL suggest similar courses or programs based on focus_areas or requirement_type

### Requirement 13: Smart Course Recommendations

**User Story:** As a student, I want personalized course suggestions, so that I can plan my academic path effectively.

#### Acceptance Criteria

1. WHEN a user query requests course recommendations AND student profile exists, THE Recommendation_Engine SHALL suggest courses matching the student's current_semester and curriculum_id
2. WHEN the Recommendation_Engine suggests courses, THE Recommendation_Engine SHALL exclude courses already completed according to student_course_history
3. WHEN the Recommendation_Engine suggests courses, THE Recommendation_Engine SHALL verify prerequisite satisfaction using student_course_history
4. WHEN the Recommendation_Engine suggests electives, THE Recommendation_Engine SHALL prioritize courses matching the student's declared focus areas
5. WHEN a student's current_cgpa is below program minimum_cgpa, THE Recommendation_Engine SHALL suggest courses with historically higher pass rates

### Requirement 14: Prerequisite Validation

**User Story:** As a student, I want the chatbot to verify if I can register for a course, so that I avoid registration errors.

#### Acceptance Criteria

1. WHEN a user query asks about course eligibility AND student profile exists, THE Prerequisite_Validator SHALL check all course_prerequisites for the requested course
2. WHEN the Prerequisite_Validator checks prerequisites, THE Prerequisite_Validator SHALL verify each prerequisite appears in student_course_history with status 'passed'
3. WHEN a prerequisite has minimum_grade specified, THE Prerequisite_Validator SHALL verify the student's letter_grade meets or exceeds the requirement
4. WHEN a prerequisite has waiver_condition specified, THE Prerequisite_Validator SHALL explain the waiver option in the response
5. WHEN all prerequisites are satisfied, THE Prerequisite_Validator SHALL confirm eligibility and include any additional registration requirements
6. WHEN prerequisites are not satisfied, THE Prerequisite_Validator SHALL list missing prerequisites and suggest completing them first

### Requirement 15: Schedule Conflict Detection

**User Story:** As a student, I want the chatbot to warn me about timetable conflicts, so that I can plan a feasible course schedule.

#### Acceptance Criteria

1. WHEN a user query requests a course combination AND student profile exists, THE Schedule_Analyzer SHALL retrieve timetable_entries for all requested courses
2. WHEN the Schedule_Analyzer finds overlapping time slots, THE Schedule_Analyzer SHALL report conflicts showing day_of_week, starts_at, ends_at, and room for each conflicting course
3. WHEN the Schedule_Analyzer finds no conflicts, THE Schedule_Analyzer SHALL confirm the schedule is feasible
4. WHEN requested courses have multiple sections, THE Schedule_Analyzer SHALL suggest section combinations that avoid conflicts
5. WHEN the total credit hours of requested courses exceed maximum_semester_credits, THE Schedule_Analyzer SHALL warn the student and reference the applicable source_records

### Requirement 16: Multi-Source Answer Aggregation

**User Story:** As a student, I want comprehensive answers drawing from all available sources, so that I get complete information in one response.

#### Acceptance Criteria

1. WHEN the Response_Generator constructs an answer, THE Response_Generator SHALL query all relevant database tables for the detected intent
2. WHEN multiple source_records apply, THE Response_Generator SHALL aggregate information and list all citations
3. WHEN database results are incomplete, THE Response_Generator SHALL query document_chunks for supplementary information
4. WHEN conflicting information exists across sources, THE Response_Generator SHALL prioritize verified sources and note the discrepancy
5. WHEN the Response_Generator includes information from document_chunks, THE Response_Generator SHALL trace chunks back to their source_records for citation

### Requirement 17: Query Spelling Correction

**User Story:** As a student, I want the chatbot to understand my questions even with typos, so that I get answers without needing to retype perfectly.

#### Acceptance Criteria

1. WHEN a user query contains words not matching known course codes or academic vocabulary, THE Query_Analyzer SHALL apply edit-distance-based spell correction
2. WHEN spell correction finds multiple candidates, THE Query_Analyzer SHALL choose the candidate with highest frequency in the Knowledge_Base
3. WHEN spell correction confidence is below 0.80, THE Query_Analyzer SHALL preserve the original text and rely on semantic search
4. WHEN the Query_Analyzer corrects spelling, THE Query_Analyzer SHALL log the original and corrected text for quality monitoring
5. WHEN course codes are misspelled, THE Entity_Extractor SHALL match against the courses table using fuzzy matching within edit distance 2

### Requirement 18: Synonym Expansion

**User Story:** As a student, I want the chatbot to understand different ways of asking the same question, so that I can use natural language without memorizing keywords.

#### Acceptance Criteria

1. WHEN a user query contains "teacher", THE Query_Analyzer SHALL expand to include "instructor" and "faculty"
2. WHEN a user query contains "marks", THE Query_Analyzer SHALL expand to include "grades" and "GPA"
3. WHEN a user query contains "timetable", THE Query_Analyzer SHALL expand to include "schedule" and "class timing"
4. WHEN a user query contains "eligibility", THE Query_Analyzer SHALL expand to include "prerequisites" and "requirements"
5. WHEN a user query contains "final year project", THE Query_Analyzer SHALL expand to include "FYP" and "thesis"

### Requirement 19: Response Time Performance

**User Story:** As a student, I want answers within one second, so that the chatbot feels responsive and I can maintain conversation flow.

#### Acceptance Criteria

1. WHEN the Chatbot_System processes a query with database-only retrieval, THE Chatbot_System SHALL return a response within 500 milliseconds
2. WHEN the Chatbot_System processes a query requiring vector search, THE Chatbot_System SHALL return a response within 1000 milliseconds
3. WHEN the Chatbot_System processes a query requiring web scraping, THE Chatbot_System SHALL return cached data within 1000 milliseconds and schedule background updates
4. WHEN response generation exceeds 1000 milliseconds, THE Chatbot_System SHALL log the query and execution plan for optimization analysis

### Requirement 20: Answer Accuracy Assurance

**User Story:** As a student, I want correct answers at least 95% of the time, so that I can trust the chatbot for academic decisions.

#### Acceptance Criteria

1. WHEN the Response_Generator constructs an answer, THE Response_Generator SHALL only include information from source_records with verification_status 'verified' or 'referenced'
2. WHEN information comes from unverified sources, THE Response_Generator SHALL prefix the answer with a disclaimer noting unverified status
3. WHEN the Query_Analyzer intent confidence is below 0.70, THE Response_Generator SHALL ask for clarification rather than guessing
4. WHEN the Knowledge_Base lacks information for a query, THE Response_Generator SHALL acknowledge the limitation and suggest contacting the department
5. WHEN the Chatbot_System detects contradictory information across sources, THE Response_Generator SHALL present the conflict and indicate which source is most authoritative

### Requirement 21: Backward Compatibility Preservation

**User Story:** As a system administrator, I want the upgraded system to accept all existing API requests, so that current integrations continue working without changes.

#### Acceptance Criteria

1. THE Chatbot_System SHALL accept ChatRequest objects with message, session_id, and context_course_code fields as specified in app/schemas/chat.py
2. THE Chatbot_System SHALL return ChatResponse objects with answer, intent, language, confidence, entities, model_backend, model_name, response_engine, citations, verified, and session_id fields
3. WHEN existing code calls the /chat endpoint, THE Chatbot_System SHALL process the request using the existing _safe_answer function signature
4. WHEN the Multi_Language_Processor detects English, Roman Urdu, or Urdu script, THE Multi_Language_Processor SHALL maintain existing language detection behavior
5. WHEN the Session_Manager creates chat sessions, THE Session_Manager SHALL store records in chat_sessions and chat_messages tables following the existing schema

### Requirement 22: Database Schema Compatibility

**User Story:** As a system administrator, I want the upgraded system to work with the existing database schema, so that I do not need to migrate or transform production data.

#### Acceptance Criteria

1. THE Web_Scraper SHALL store faculty information in new tables while referencing existing source_records entries
2. THE Web_Scraper SHALL store research areas in new tables while linking to existing courses via foreign keys
3. THE Web_Scraper SHALL store news and events in new tables while maintaining the source_records verification model
4. THE Recommendation_Engine SHALL read from existing tables including student_profiles, student_course_history, courses, and curriculum_schemes
5. THE Prerequisite_Validator SHALL read from existing course_prerequisites and student_course_history tables

### Requirement 23: Citation Completeness

**User Story:** As a student, I want to see sources for all answers, so that I can verify information and refer to official documents when needed.

#### Acceptance Criteria

1. WHEN the Response_Generator includes information from source_records, THE Citation_Provider SHALL include source_code, title, and source_url in the citations list
2. WHEN multiple sources contribute to an answer, THE Citation_Provider SHALL include all contributing source_records
3. WHEN information comes from document_chunks, THE Citation_Provider SHALL trace the chunk to its parent knowledge_documents and source_records
4. WHEN the Response_Generator presents demo data, THE Citation_Provider SHALL prefix the answer with "DEMO DATA" and mark verified as false
5. WHEN no source_records exist for the answer, THE Citation_Provider SHALL return an empty citations list and mark verified as false

### Requirement 24: Multi-Language Response Consistency

**User Story:** As a student, I want answers in my preferred language, so that I can understand the information in the language I am most comfortable with.

#### Acceptance Criteria

1. WHEN the Multi_Language_Processor detects Urdu script input, THE Response_Generator SHALL return the answer in Urdu script
2. WHEN the Multi_Language_Processor detects Roman Urdu input, THE Response_Generator SHALL return the answer in Roman Urdu
3. WHEN the Multi_Language_Processor detects English input, THE Response_Generator SHALL return the answer in English
4. WHEN technical terms lack translations, THE Response_Generator SHALL use English terms within translated sentences
5. WHEN the Response_Generator formats lists in Roman Urdu or Urdu script, THE Response_Generator SHALL maintain natural sentence structure for the target language

### Requirement 25: Complex Query Decomposition

**User Story:** As a student, I want to ask multi-part questions, so that I can get comprehensive information without asking separately.

#### Acceptance Criteria

1. WHEN a user query contains multiple questions connected by "and" or "also", THE Query_Analyzer SHALL detect all intents
2. WHEN the Query_Analyzer detects multiple intents, THE Response_Generator SHALL address each intent in separate sections
3. WHEN multiple intents share entities, THE Response_Generator SHALL extract shared context once and apply to all sub-answers
4. WHEN answering multi-part queries, THE Response_Generator SHALL organize sections with headers indicating which question is being answered
5. WHEN the total response length would exceed 2000 characters, THE Response_Generator SHALL summarize and offer to provide details on each part separately

### Requirement 26: Web Scraper Incremental Updates

**User Story:** As a system administrator, I want the web scraper to update only changed content, so that database writes are minimized and scraping is efficient.

#### Acceptance Criteria

1. WHEN the Web_Scraper fetches a page, THE Web_Scraper SHALL compute checksum_sha256 of the content
2. WHEN the computed checksum matches the stored checksum_sha256 in source_records, THE Web_Scraper SHALL skip processing that page
3. WHEN the computed checksum differs from stored checksum, THE Web_Scraper SHALL update the source_records entry and set updated_at to the current timestamp
4. WHEN the Web_Scraper updates a source_records entry, THE Web_Scraper SHALL set is_time_sensitive to true if the content includes dates or deadlines
5. WHEN the Web_Scraper completes an incremental run, THE Web_Scraper SHALL log the count of changed, unchanged, and newly discovered pages

### Requirement 27: Faculty Information Schema

**User Story:** As a developer, I want a schema for storing faculty information, so that faculty queries can be answered from the Knowledge_Base.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL include a faculty_members table with columns: id, source_id, full_name, title, email, phone, office_location, created_at, updated_at
2. THE Knowledge_Base SHALL include a faculty_research_interests table linking faculty_members to research areas with columns: faculty_id, interest_text
3. THE Knowledge_Base SHALL include a research_areas table with columns: id, name, description, created_at
4. THE Knowledge_Base SHALL include a faculty_research_areas table linking faculty_members to research_areas with columns: faculty_id, research_area_id
5. THE faculty_members table SHALL enforce a unique constraint on email to prevent duplicate entries

### Requirement 28: News and Events Schema

**User Story:** As a developer, I want a schema for storing news and events, so that time-sensitive information can be presented to users.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL include a news_articles table with columns: id, source_id, title, content, published_at, expires_at, category, created_at
2. THE Knowledge_Base SHALL include an events table with columns: id, source_id, title, description, event_date, event_time, location, registration_url, expires_at, created_at
3. THE news_articles table SHALL include an index on published_at descending for efficient recent news queries
4. THE events table SHALL include an index on event_date ascending for efficient upcoming events queries
5. WHEN expires_at is in the past, THE Response_Generator SHALL exclude that record from query results

### Requirement 29: Web Scraper Parser Configuration

**User Story:** As a system administrator, I want to configure parsing rules for different page types, so that the Web_Scraper can adapt to changes in website structure.

#### Acceptance Criteria

1. THE Web_Scraper SHALL read parsing rules from a configuration file specifying CSS selectors or XPath expressions for each content type
2. WHEN the Web_Scraper parses faculty pages, THE Web_Scraper SHALL extract fields using configured selectors for name, title, email, phone, office, and research interests
3. WHEN the Web_Scraper parses course pages, THE Web_Scraper SHALL extract fields using configured selectors for code, title, description, and credit hours
4. WHEN the Web_Scraper parses news pages, THE Web_Scraper SHALL extract fields using configured selectors for title, date, and content
5. WHEN a configured selector fails to match, THE Web_Scraper SHALL log the failure and continue processing remaining selectors

### Requirement 30: Vector Embedding Generation

**User Story:** As a developer, I want automatic embedding generation for new content, so that semantic search returns relevant results.

#### Acceptance Criteria

1. WHEN the Web_Scraper stores new content in knowledge_documents, THE RAG_Engine SHALL generate embeddings for document_chunks using the existing vector model
2. WHEN faculty_members are created, THE RAG_Engine SHALL generate embeddings from concatenated title and research_interests fields
3. WHEN news_articles are created, THE RAG_Engine SHALL generate embeddings from concatenated title and content fields
4. WHEN the RAG_Engine generates embeddings, THE RAG_Engine SHALL store them in the embedding column with dimensionality 384
5. WHEN embeddings are generated, THE RAG_Engine SHALL update the processing_status to 'ready' for the corresponding knowledge_documents entry

### Requirement 31: Intent Expansion for New Domains

**User Story:** As a developer, I want to extend intent classification to new query types, so that faculty, research, admission, and news queries are correctly routed.

#### Acceptance Criteria

1. THE Query_Analyzer SHALL support intent "faculty_information" for queries about instructors, supervisors, or staff
2. THE Query_Analyzer SHALL support intent "research_area_query" for queries about research topics, areas, or specializations
3. THE Query_Analyzer SHALL support intent "admission_information" for queries about entry requirements, application procedures, or admission deadlines
4. THE Query_Analyzer SHALL support intent "news_query" for queries about recent announcements, updates, or department news
5. THE Query_Analyzer SHALL support intent "event_query" for queries about upcoming events, seminars, or workshops
6. THE Query_Analyzer SHALL add routing rules in app/nlp/service.py for each new intent with confidence threshold 0.85

### Requirement 32: Spell Correction Implementation

**User Story:** As a developer, I want spell correction integrated into query preprocessing, so that typos do not prevent accurate intent detection.

#### Acceptance Criteria

1. THE Query_Analyzer SHALL use a spell correction library supporting edit distance algorithms such as SymSpell or Levenshtein
2. WHEN the Query_Analyzer detects a word not in the academic vocabulary dictionary, THE Query_Analyzer SHALL generate candidates within edit distance 2
3. WHEN multiple candidates exist, THE Query_Analyzer SHALL rank by frequency in the Knowledge_Base computed from courses.title, academic_rules.description, and document_chunks.content
4. WHEN no candidates are found, THE Query_Analyzer SHALL preserve the original word and rely on semantic search
5. WHEN spell correction modifies the query, THE Query_Analyzer SHALL log the original and corrected forms in chat_messages.entities under key "corrected_text"

### Requirement 33: Recommendation Engine Initialization

**User Story:** As a developer, I want a recommendation engine module, so that personalized course suggestions can be generated.

#### Acceptance Criteria

1. THE Recommendation_Engine SHALL be implemented as a new module at backend/app/recommendations/engine.py
2. THE Recommendation_Engine SHALL expose a function recommend_courses accepting student_id and returning a list of course recommendations
3. WHEN recommend_courses is called, THE Recommendation_Engine SHALL query student_profiles for curriculum_id and current_semester
4. WHEN recommend_courses determines eligible courses, THE Recommendation_Engine SHALL exclude courses in student_course_history with status 'passed', 'in_progress', or 'exempted'
5. WHEN recommend_courses checks prerequisites, THE Recommendation_Engine SHALL verify all prerequisite courses are in student_course_history with status 'passed' and meeting minimum_grade if specified

### Requirement 34: Schedule Conflict Detection Implementation

**User Story:** As a developer, I want a schedule analyzer module, so that timetable conflicts can be detected before registration.

#### Acceptance Criteria

1. THE Schedule_Analyzer SHALL be implemented as a new module at backend/app/schedule/analyzer.py
2. THE Schedule_Analyzer SHALL expose a function detect_conflicts accepting a list of course_ids and returning conflict details
3. WHEN detect_conflicts is called, THE Schedule_Analyzer SHALL retrieve all timetable_entries for the active academic term matching the provided course_ids
4. WHEN detect_conflicts finds entries with matching day_of_week and overlapping time ranges, THE Schedule_Analyzer SHALL return a conflict report including course codes, day, time, and room
5. WHEN detect_conflicts finds no overlaps, THE Schedule_Analyzer SHALL return an empty conflict list

### Requirement 35: Professional Formatting Utilities

**User Story:** As a developer, I want formatting utilities for structured responses, so that answers are consistently professional and easy to read.

#### Acceptance Criteria

1. THE Response_Generator SHALL use a formatting utility module at backend/app/utils/formatters.py
2. THE formatting utility SHALL provide a function format_course_details accepting a course dictionary and returning markdown-formatted text
3. THE formatting utility SHALL provide a function format_timetable_entry accepting timetable data and returning a human-readable time description
4. THE formatting utility SHALL provide a function format_prerequisite_chain accepting a list of courses and returning a dependency tree representation
5. THE formatting utility SHALL provide a function format_citation accepting source_records data and returning a formatted reference string

### Requirement 36: Web Scraper Scheduling

**User Story:** As a system administrator, I want the web scraper to run on a schedule, so that the Knowledge_Base stays current without manual intervention.

#### Acceptance Criteria

1. THE Web_Scraper SHALL support scheduled execution via a command-line interface accepting cron-compatible schedule expressions
2. WHEN the Web_Scraper runs on schedule, THE Web_Scraper SHALL scrape all configured URLs from cs.qau.edu.pk
3. WHEN the Web_Scraper completes a scheduled run, THE Web_Scraper SHALL record execution timestamp, duration, pages processed, and errors encountered in a scraper_runs log table
4. WHEN the Web_Scraper encounters rate limiting, THE Web_Scraper SHALL implement exponential backoff starting at 1 second with maximum 60 seconds
5. WHEN the Web_Scraper is manually triggered, THE Web_Scraper SHALL bypass the schedule and execute immediately

### Requirement 37: Answer Quality Metrics

**User Story:** As a system administrator, I want to track answer quality metrics, so that I can monitor and improve chatbot performance.

#### Acceptance Criteria

1. THE Chatbot_System SHALL log response_time_ms for every query in chat_messages
2. THE Chatbot_System SHALL log intent_confidence for every query in chat_messages
3. THE Chatbot_System SHALL log response_engine indicating whether the answer came from 'sql', 'rag', 'rule', or 'fallback'
4. WHEN a query results in a fallback response, THE Chatbot_System SHALL increment a fallback_count metric for monitoring
5. WHEN the Session_Manager tracks conversation length, THE Session_Manager SHALL log the message count per session for analysis

### Requirement 38: Citation Traceability

**User Story:** As a student, I want to click on citations to view source documents, so that I can verify information and read official policies.

#### Acceptance Criteria

1. WHEN the Citation_Provider includes source_records in citations, THE Citation_Provider SHALL include source_url if available
2. WHEN source_url is a relative path, THE Citation_Provider SHALL prepend the base URL for cs.qau.edu.pk
3. WHEN source_records has local_path, THE Citation_Provider SHALL generate a downloadable link for document access
4. WHEN citations are presented, THE Response_Generator SHALL format them as markdown links with title as link text and source_url as target
5. WHEN a source_records entry has no source_url or local_path, THE Citation_Provider SHALL display source_code and title without a link

### Requirement 39: Context-Aware Follow-Up Detection

**User Story:** As a student, I want the chatbot to recognize when I am continuing a topic, so that I do not need to repeat context in every message.

#### Acceptance Criteria

1. WHEN a user query starts with "also", "and", "what about", or "how about", THE Query_Analyzer SHALL mark the query as a follow-up
2. WHEN the Query_Analyzer detects a follow-up query, THE Query_Analyzer SHALL retrieve the previous assistant message from chat_messages
3. WHEN the previous message has entities, THE Entity_Extractor SHALL merge previous entities with current entities, prioritizing current
4. WHEN the previous message has intent, THE Query_Analyzer SHALL boost the same intent's confidence by 0.15
5. WHEN a follow-up query references "it", "that", "this", or "them", THE Entity_Extractor SHALL replace pronouns with entities from the previous message

### Requirement 40: Multi-Part Query Section Headers

**User Story:** As a student, I want clear section headers when I ask multiple questions, so that I can easily find each answer in the response.

#### Acceptance Criteria

1. WHEN the Response_Generator addresses multiple intents, THE Response_Generator SHALL create a markdown header for each intent using the pattern "## [Topic]"
2. WHEN the first intent is answered, THE Response_Generator SHALL use "## [Topic]" without introductory text
3. WHEN subsequent intents are answered, THE Response_Generator SHALL use "## [Topic]" to separate sections
4. WHEN all intents are answered, THE Response_Generator SHALL optionally add a "## Related Information" section for proactive recommendations
5. WHEN section content is short, THE Response_Generator SHALL omit headers and present a single-paragraph answer

### Requirement 41: Prerequisite Chain Visualization

**User Story:** As a student, I want to see the full prerequisite chain for a course, so that I can plan my course sequence effectively.

#### Acceptance Criteria

1. WHEN a user query requests prerequisites, THE Prerequisite_Validator SHALL recursively resolve all prerequisite dependencies
2. WHEN the Prerequisite_Validator builds the prerequisite chain, THE Prerequisite_Validator SHALL detect cycles and report them as errors
3. WHEN the prerequisite chain is complete, THE Response_Generator SHALL format the chain showing each level of dependencies with indentation
4. WHEN a prerequisite has a minimum_grade requirement, THE Response_Generator SHALL include the grade requirement in the chain display
5. WHEN a course has no prerequisites, THE Response_Generator SHALL explicitly state "No prerequisites required"

### Requirement 42: Smart Session Timeout

**User Story:** As a student, I want my session to remain active while I am using the chatbot, so that I do not lose context during active conversations.

#### Acceptance Criteria

1. WHEN a user sends a message with a session_id, THE Session_Manager SHALL update last_activity_at to the current timestamp in auth_sessions if user is authenticated
2. WHEN the Session_Manager checks session validity, THE Session_Manager SHALL consider sessions with last_activity_at within 30 minutes as active
3. WHEN a session exceeds 30 minutes of inactivity, THE Session_Manager SHALL set ended_at to last_activity_at plus 30 minutes
4. WHEN a user attempts to use an ended session, THE Chatbot_System SHALL return an error prompting the user to start a new session
5. WHEN a new session is started, THE Session_Manager SHALL generate a new session_id and return it in the ChatResponse

### Requirement 43: Dynamic Vocabulary Expansion

**User Story:** As a system administrator, I want the synonym expansion to learn from the Knowledge_Base, so that domain-specific terms are automatically recognized.

#### Acceptance Criteria

1. THE Query_Analyzer SHALL maintain a synonym dictionary loaded from a configuration file at startup
2. WHEN the Web_Scraper adds new content, THE Query_Analyzer SHALL extract frequently co-occurring terms and suggest synonym additions
3. WHEN a system administrator reviews suggested synonyms, THE Query_Analyzer SHALL allow adding approved synonyms to the configuration file
4. WHEN the synonym dictionary is updated, THE Query_Analyzer SHALL reload the configuration without requiring application restart
5. WHEN the Query_Analyzer expands synonyms, THE Query_Analyzer SHALL log expanded terms in chat_messages.entities under key "expanded_terms"

### Requirement 44: Error Logging and Monitoring

**User Story:** As a system administrator, I want comprehensive error logging, so that I can diagnose and fix issues quickly.

#### Acceptance Criteria

1. WHEN the Web_Scraper encounters an HTTP error, THE Web_Scraper SHALL log the URL, status code, and error message
2. WHEN the Query_Analyzer fails to classify intent, THE Query_Analyzer SHALL log the query text and confidence scores for all intents
3. WHEN the RAG_Engine returns no results, THE RAG_Engine SHALL log the query, search strategy, and result counts
4. WHEN the Response_Generator encounters a database error, THE Response_Generator SHALL log the query, intent, and SQL error details
5. WHEN any component logs an error, THE Chatbot_System SHALL include a request_id for tracing the error across components

### Requirement 45: Recommendation Explanation

**User Story:** As a student, I want to understand why courses are recommended, so that I can make informed decisions.

#### Acceptance Criteria

1. WHEN the Recommendation_Engine suggests courses, THE Response_Generator SHALL include a rationale for each recommendation
2. WHEN a course is recommended based on curriculum sequence, THE Response_Generator SHALL state "Recommended for Semester [N] in your program"
3. WHEN a course is recommended based on prerequisites being met, THE Response_Generator SHALL state "You have completed all prerequisites"
4. WHEN a course is recommended based on focus areas, THE Response_Generator SHALL state "Matches your interest in [research area]"
5. WHEN a course is recommended for GPA recovery, THE Response_Generator SHALL state "This course has a high pass rate and may help improve your CGPA"

### Requirement 46: Verified Source Prioritization

**User Story:** As a student, I want verified information prioritized over unverified sources, so that I receive the most reliable guidance.

#### Acceptance Criteria

1. WHEN the RAG_Engine retrieves results, THE RAG_Engine SHALL sort by verification_status with 'verified' first, then 'referenced', then 'unverified'
2. WHEN multiple sources have the same verification_status, THE RAG_Engine SHALL sort by effective_from descending to prefer recent information
3. WHEN the Response_Generator includes unverified information, THE Response_Generator SHALL prefix the statement with "According to unverified sources"
4. WHEN no verified sources exist for a query, THE Response_Generator SHALL acknowledge the limitation and suggest verifying with the department
5. WHEN conflicting information exists between verified and unverified sources, THE Response_Generator SHALL present only the verified information

### Requirement 47: Fuzzy Course Code Matching

**User Story:** As a student, I want the chatbot to understand course codes even if I forget hyphens or spacing, so that queries succeed without perfect formatting.

#### Acceptance Criteria

1. WHEN the Entity_Extractor detects a potential course code, THE Entity_Extractor SHALL normalize by removing spaces and hyphens
2. WHEN the Entity_Extractor queries the courses table, THE Entity_Extractor SHALL use a normalized comparison removing spaces and hyphens from both sides
3. WHEN multiple courses match the normalized form, THE Entity_Extractor SHALL prefer exact matches then shortest code
4. WHEN no exact match exists, THE Entity_Extractor SHALL attempt fuzzy matching with edit distance 1 on the normalized form
5. WHEN fuzzy matching finds a candidate, THE Entity_Extractor SHALL include the matched course code in entities with a "fuzzy_match" flag

### Requirement 48: Related Information Discovery

**User Story:** As a student, I want suggestions for related information, so that I can explore topics more deeply.

#### Acceptance Criteria

1. WHEN the Response_Generator answers a course query, THE Response_Generator SHALL suggest courses with matching focus_areas under "Related Courses"
2. WHEN the Response_Generator answers a faculty query, THE Response_Generator SHALL suggest related research areas under "Research Areas"
3. WHEN the Response_Generator answers a research area query, THE Response_Generator SHALL suggest faculty and courses under "Related Resources"
4. WHEN the Response_Generator answers a program query, THE Response_Generator SHALL suggest related degree levels under "Other Programs"
5. WHEN related information is included, THE Response_Generator SHALL present it in a clearly labeled section at the end of the response

### Requirement 49: Proactive Deadline Reminders

**User Story:** As a student, I want reminders about approaching deadlines, so that I do not miss important dates.

#### Acceptance Criteria

1. WHEN the Response_Generator answers a registration or course query, THE Response_Generator SHALL query deadlines with closes_at within the next 14 days
2. WHEN approaching deadlines exist, THE Response_Generator SHALL include a "⚠ Upcoming Deadlines" section listing title and closes_at
3. WHEN a deadline is within 3 days, THE Response_Generator SHALL use urgent formatting such as "⚠️ URGENT: [title] closes in [N] days"
4. WHEN multiple deadlines exist, THE Response_Generator SHALL list them sorted by closes_at ascending
5. WHEN no approaching deadlines exist, THE Response_Generator SHALL omit the deadline section

### Requirement 50: Feedback Collection

**User Story:** As a system administrator, I want to collect user feedback on answers, so that I can identify and fix incorrect or unhelpful responses.

#### Acceptance Criteria

1. THE Chatbot_System SHALL accept an optional feedback endpoint /chat/feedback accepting session_id, message_id, rating, and comment
2. WHEN feedback is submitted, THE Chatbot_System SHALL store the rating and comment in a new feedback table linked to chat_messages
3. WHEN a message receives negative feedback, THE Chatbot_System SHALL log the query, intent, response, and feedback for review
4. WHEN feedback indicates incorrect information, THE system administrator SHALL review and update source_records or academic_rules
5. WHEN feedback indicates missing information, THE system administrator SHALL investigate and add necessary data to the Knowledge_Base

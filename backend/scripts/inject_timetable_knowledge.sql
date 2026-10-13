-- ============================================================================
-- INJECT TIMETABLE KNOWLEDGE INTO RAG SYSTEM
-- ============================================================================
-- This script injects Spring 2026 timetable knowledge into the knowledge_base
-- table for the chatbot RAG system to reference when answering queries.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. TIMETABLE OVERVIEW
-- ============================================================================

SELECT upsert_knowledge(
    'timetable-spring-2026-overview',
    'timetable',
    'Spring 2026 Timetable Overview',
    '# Spring 2026 Class Schedule

**Academic Session:** Spring 2026  
**Effective From:** April 20, 2026  
**Department:** Department of Computer Science  
**Coordinator:** Ifrah Farrukh Khan (Timetable/Datesheet Coordinator)

## Programs Covered
- BS Computer Science (Regular & Self-Finance)
- MS-IST (Master of Science in Information Systems Technology)
- MPhil Computer Science
- PhD Computer Science
- MS-DS (Master of Science in Data Science)
- Repeater courses
- Deficiency courses

## Schedule Statistics
- **Total Classes:** 100+ scheduled sessions
- **Rooms:** Room 201, Room 217, Room 235, Room F6, Room F8, CS Lab, BS Lab, Online
- **Time Range:** 08:35 AM to 08:00 PM
- **Days:** Monday through Friday (with some weekend sessions)
- **Instructors:** 28+ faculty members
- **Programs:** BS, MPhil, PhD, MS-DS, MS-IST

## Query Examples
Students can ask:
- "When is CS-104 class?"
- "What courses does Dr. Farooq teach?"
- "Show me Monday schedule"
- "Database Systems lab timing"
- "Room 201 schedule"',
    '{}'::jsonb,
    NULL,
    10
);

-- ============================================================================
-- 2. QUERY GUIDE
-- ============================================================================

SELECT upsert_knowledge(
    'timetable-query-guide',
    'timetable',
    'How to Query the Timetable',
    '# Querying the Spring 2026 Timetable

## Query Types

### By Course Code
"When is CS-104?", "CS-313 timing?", "Database Systems schedule?"

### By Day
"Monday classes", "Tuesday schedule", "Friday courses"

### By Instructor
"Dr. Farooq schedule", "What does Ms. Ifrah teach?", "Dr. Khalid classes"

### By Room
"Room 201 schedule", "CS Lab classes", "Room 235 timing"

### By Time
"Morning classes", "8:35 courses", "Evening schedule"

### By Program/Semester
"BS Semester 1", "MPhil courses", "Semester 4 classes"

## Important Notes
- Specify Regular (R) or Self-Finance (S) section
- Lab sessions separate from lectures
- Multiple sections at different times
- TAs assigned for practical courses

## Response Format
Answers include:
- Course code and name
- Day and time slot
- Room location
- Instructor name(s)
- Teaching assistants (if applicable)
- Section type and program
- Credit hours',
    '{}'::jsonb,
    NULL,
    15
);

-- ============================================================================
-- 3. INSTRUCTOR DIRECTORY
-- ============================================================================

SELECT upsert_knowledge(
    'timetable-instructors-directory',
    'timetable',
    'Faculty Teaching Assignments Spring 2026',
    '# Instructor Directory - Spring 2026

## Core Computer Science Faculty

**Dr. Ghazanfar Farooq** - CS-104 (PSP Regular), CS-423 (Computer Graphics)  
**Dr. Khalid Saleem** - CS-224 (DBS), CS-325 (ADS), DSC-838 (RS)  
**Dr. Onaiza Maqbool** - CS-222 (ADSS Regular), CS-458 (Data Mining)  
**Dr. Umer Rashid** - CS-222 (ADSS S), CS-331 (TOA), DSC-675 (IRS)  
**Dr. Rabeeh Ayaz Abbasi** - CS-211 (DS), CSC-827 (SNA)  
**Dr. Muddassar Sindhu** - CS-411 (CC), CS-483 (SQA), CSC-614 (SQAT)  
**Dr. Nadia Saeed** - CS-313 (CA S), CS-455 (NLP)  
**Dr. Akmal Saeed Khattak** - CS-457 (WAF), CSC-675 (IRS MPhil)  
**Dr. S. M. Naqi** - CS-425 (CV), CS-352 (DSA Def), CSC-741 (CV PhD)  
**Dr. Muazzam Khattak** - CS-312 (CCN), CS-413 (IIS)  
**Dr. Shuaib Karim** - CS-224 (DBS S), CS-449 (ICTS)  
**Dr. Ayyaz Hussain** - CS-460 (DL), CS-105 (PSP Deficiency)  
**Dr. Adeel Ur Rehman** - CS-332 (NCP)  

## Lecturers
**Ms. Ifrah Farrukh Khan** - CS-313 (CA R), CS-215 (COAL)  
**Ms. Memoona Afsheen** - CS-104 (PSP S), CS-121 (OOP)  
**Mr. Muhammad Tauseef** - CS-535 (Cloud DevOps)  

## Co-Instructors
**Ms. Rida Nawaz** - CS-224 (with Dr. Khalid)  
**Ms. Fouzia Qureshi** - CS-224 (with Dr. Shuaib)  

## Teaching Assistants
**Mr. Hammad** - CS-104 (Regular)  
**Mr. Abdur Rehman** - CS-104 (Self-Finance)  
**Ms. Safeena** - CS-211 (Data Structures)  
**Mr. Zain** - CS-215 (COAL)  

## Other Departments
**Dr. Muhammad Shafiq** (Physics) - PH-110  
**Dr. Waseem Siddiqui** (Math) - MA-104  
**Ms. Farwa Haider** (Math) - MA-202  
**Dr. Arshad Qayyum** (Islamic Studies) - IS-100  
**Ms. Tahira Shabir** (English) - EN-200',
    '{}'::jsonb,
    NULL,
    20
);

-- ============================================================================
-- 4. POPULAR COURSES SCHEDULES
-- ============================================================================

SELECT upsert_knowledge(
    'timetable-popular-courses',
    'timetable',
    'Common Course Schedules Spring 2026',
    '# Frequently Asked Course Schedules

## CS-104: Problem Solving & Programming (3+1 CH)

### Regular Section (Dr. Ghazanfar Farooq + Mr. Hammad TA)
- Monday 08:35-10:05, Room 201
- Tuesday 10:15-11:45, CS Lab
- Tuesday 15:15-16:45, CS Lab
- Thursday 10:15-11:45, Room 201

### Self-Finance (Ms. Memoona + Mr. Abdur Rehman TA)
- Monday 08:35-10:05, Room F8
- Tuesday 08:35-10:05, BS Lab
- Tuesday 10:15-11:45, BS Lab
- Thursday 10:15-11:45, Room 217

## CS-121: OOP (3+1 CH, Ms. Memoona Afsheen)
- Monday 15:15-16:45, Room 217 (Lecture)
- Tuesday 08:05-10:05, CS Lab (Lab)
- Thursday 08:05-10:05, Room 217 (Lab)

## CS-211: Data Structures (3+1 CH, Dr. Rabeeh + Ms. Safeena TA)
- Monday 10:15-11:45, BS Lab
- Tuesday 11:55-13:25, Room F8
- Thursday 15:15-16:45, CS Lab

## CS-224: Database Systems (3+1 CH)

### Regular (Dr. Khalid Saleem & Ms. Rida Nawaz)
- Monday 08:35-10:05, CS Lab
- Wednesday 08:35-10:05, CS Lab
- Wednesday 10:15-11:45, CS Lab
- Thursday 13:35-15:05, Room 217

### Self-Finance (Dr. Shuaib Karim & Ms. Fouzia Qureshi)
- Tuesday 08:35-10:05, Room 217
- Wednesday 10:15-11:45, Room 201
- Thursday 10:15-11:45, CS Lab
- Thursday 11:55-13:25, CS Lab

## CS-313: Computer Architecture (3 CH)

### Regular (Ms. Ifrah Farrukh Khan)
- Monday 11:55-13:25, Room 217
- Wednesday 10:15-11:45, Room 217

### Self-Finance (Dr. Nadia Saeed)
- Monday 10:15-11:45, Room 201
- Wednesday 08:35-10:05, Room 201

## CS-222: ADSS (3 CH)

### Regular (Dr. Onaiza Maqbool)
- Monday 13:35-15:05, Room 217
- Wednesday 13:35-15:05, Room 217

### Self-Finance (Dr. Umer Rashid)
- Monday 13:35-15:05, Room 201
- Wednesday 15:15-16:45, Room 217

## CS-331: Theory of Automata (3 CH, Dr. Umer Rashid)
- Monday 13:35-15:05, Room 235
- Tuesday 15:30-17:00, Room 217

## CS-455: NLP (3 CH, Dr. Nadia Saeed)
- Tuesday 11:55-13:25, CS Lab
- Thursday 13:35-15:05, Room 235

## CS-460: Deep Learning (3 CH, Dr. Ayyaz Hussain)
- Monday 08:35-10:05, Room 235
- Wednesday 11:55-13:25, Room 235',
    '{}'::jsonb,
    NULL,
    25
);

-- ============================================================================
-- 5. ROOM SCHEDULES
-- ============================================================================

SELECT upsert_knowledge(
    'timetable-rooms-overview',
    'timetable',
    'Room Schedules and Locations',
    '# Room Usage Information - Spring 2026

## Main Lecture Rooms

### Room 201
**Utilization:** High-traffic core courses room
**Typical Courses:** CS-104 (PSP), CS-313 (CA), CS-411 (CC), CS-222 (ADSS), CS-332 (NCP), CS-425 (CV), CS-423 (CG)
**Shifts:** Morning and Afternoon primarily
**Capacity:** Standard lecture hall

### Room 217
**Utilization:** Multi-purpose teaching room
**Typical Courses:** CS-425 (CV), CS-312 (CCN), CS-313 (CA), CS-222 (ADSS), CS-121 (OOP), CS-224 (DBS), CS-104 (PSP), CS-215 (COAL), CSC-614 (SQAT)
**Shifts:** All shifts (Morning, Afternoon, Evening)
**Features:** Suitable for both lectures and labs

### Room 235
**Utilization:** Advanced courses and graduate programs
**Typical Courses:** CS-460 (DL), CS-413 (IIS), CS-331 (TOA), CSC-741 (CV PhD), CS-457 (WAF), CS-449 (ICTS), CS-455 (NLP), CS-535 (CD), CSC-827 (SNA), DS-606 (PSDS), DSC-675 (IRS)
**Shifts:** All shifts including evening
**Note:** Used for MS-DS and MPhil/PhD courses

## Laboratory Facilities

### CS Lab
**Purpose:** Primary computer science lab
**Typical Courses:** CS-224 (DBS labs), CS-104 (PSP labs), CS-455 (NLP), CS-483 (SQA), CS-423 (CG), CSC-675 (IRS), CS-458 (DM), CS-352 (DSA Deficiency), DSC-838 (RS), CS-457 (WAF labs), CS-211 (DS)
**Shifts:** Morning, Afternoon, Evening (17:00-20:00 for deficiency/MS-DS)
**Equipment:** Programming workstations

### BS Lab
**Purpose:** Undergraduate practical sessions
**Typical Courses:** CSC-614 (SQAT), CS-211 (DS), CS-104 (PSP S), CS-215 (COAL labs), CS-325 (ADS labs), CS-225 (DBS Deficiency)
**Shifts:** Morning, Afternoon, Evening
**Focus:** Hands-on programming and system labs

## Supporting Rooms

### Room F6
**Typical Courses:** MA-104 (FLA), SW-100 (CCE), IS-100 (IS), MA-202 (MC)
**Purpose:** General education and math courses

### Room F8
**Typical Courses:** CS-104 (PSP S), PH-110 (IMW), EN-200 (EW), CS-211 (DS), GEN-100 (ISS)
**Purpose:** Foundation courses and general studies

## Special Arrangements

### Online (Remote)
**Courses:** EN-200 (EW Friday), CS-105 (PSP Deficiency evening), FQ-102/FQ-602 (Understanding Quran)
**Time:** Primarily Friday and evening slots
**Purpose:** Flexible delivery for special programs

## Room Booking Notes
- Labs require prior reservation
- Equipment setup time needed for specialized courses
- Room 235 prioritized for graduate programs
- Evening slots (after 17:00) for working professionals and deficiency courses',
    '{}'::jsonb,
    NULL,
    30
);

-- ============================================================================
-- 6. SCHEDULE BY DAY
-- ============================================================================

SELECT upsert_knowledge(
    'timetable-day-summary',
    'timetable',
    'Daily Schedule Overview',
    '# Daily Class Distribution

## Monday
**Total Classes:** ~23 sessions
**Peak Hours:** 08:35-15:05
**Key Courses:** CS-104 (PSP), CS-313 (CA), CS-411 (CC), CS-222 (ADSS), CS-425 (CV), CS-312 (CCN), CS-460 (DL), CS-413 (IIS), CS-331 (TOA), CS-224 (DBS), CSC-675 (IRS), CS-458 (DM), CS-352 (DSA evening), CSC-614 (SQAT), CS-211 (DS)
**Special:** Deficiency courses 17:00-20:00 in CS Lab

## Tuesday
**Total Classes:** ~24 sessions
**Peak Hours:** 08:05-17:00
**Key Courses:** CS-483 (SQA), CS-325 (ADS), CS-224 (DBS), CS-215 (COAL), CS-331 (TOA), CS-449 (ICTS), CSC-741 (CV), CS-457 (WAF), CS-121 (OOP Lab), CS-104 (PSP), CS-455 (NLP), CSC-827 (SNA), CS-211 (DS)
**Graduate:** DS-606 (PSDS) 17:00-20:00 for MS-DS
**Labs:** Multiple lab sessions for CS-121, CS-104

## Wednesday
**Total Classes:** ~25 sessions
**Peak Hours:** 08:35-16:45
**Key Courses:** CS-313 (CA), CS-224 (DBS), CS-312 (CCN), CSC-614 (SQAT), CS-222 (ADSS), CSC-675 (IRS), CS-413 (IIS), CS-460 (DL), CS-423 (CG), CS-483 (SQA)
**Graduate:** DSC-675 (IRS), DSC-838 (RS) 17:00-20:00 for MS-DS
**Deficiency:** CS-225 (DBS) 17:00-20:00 in BS Lab

## Thursday
**Total Classes:** ~22 sessions
**Peak Hours:** 08:05-16:45
**Key Courses:** CS-425 (CV), CS-104 (PSP), CS-411 (CC), CS-121 (OOP Lab), CS-224 (DBS), CSC-741 (CV), CS-535 (CD), CS-455 (NLP), CS-449 (ICTS), CS-215 (COAL labs), CS-325 (ADS labs), CS-457 (WAF), CS-211 (DS)
**Graduate:** CSC-827 (SNA) 17:00-18:30
**Labs:** Heavy lab day for COAL, ADS, WAF, DBS

## Friday
**Total Classes:** ~8 sessions (Limited schedule)
**Peak Hours:** 08:35-13:00, 14:00-20:00
**Key Courses:** CS-423 (CG Repeaters), EN-200 (EW online), FQ-102/FQ-602 (Understanding Quran)
**Special:** Quran studies 10:00-13:00 and 14:00-17:00
**Deficiency:** CS-105 (PSP) 17:00-20:00 online

## Weekend
**Saturday/Sunday:** Minimal/No regular classes scheduled

## Shift Distribution
- **Morning (08:00-14:00):** Majority of BS regular classes
- **Afternoon (13:00-17:00):** Self-finance and some regular sections
- **Evening (17:00-20:00):** Graduate programs (MS-DS), deficiency courses, working professionals

## Peak Utilization Times
1. **08:35-10:05:** Heaviest load, multiple rooms active
2. **10:15-11:45:** Second peak, labs + lectures
3. **13:35-15:05:** Afternoon peak
4. **17:00-20:00:** Evening programs (MS-DS, deficiency)',
    '{}'::jsonb,
    NULL,
    35
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 
    'Timetable Knowledge Injection Complete' as status,
    COUNT(*) as entries_created
FROM knowledge_base
WHERE category = 'timetable' AND is_active = TRUE;

-- Show injected entries
SELECT 
    sub_key,
    title,
    priority,
    LENGTH(content_markdown) as content_length,
    created_at
FROM knowledge_base
WHERE category = 'timetable' AND is_active = TRUE
ORDER BY priority ASC;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ TIMETABLE KNOWLEDGE INJECTED';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Chatbot RAG system now has:';
    RAISE NOTICE '- Timetable overview and statistics';
    RAISE NOTICE '- Query guide for students';
    RAISE NOTICE '- Instructor directory';
    RAISE NOTICE '- Popular course schedules';
    RAISE NOTICE '- Room utilization info';
    RAISE NOTICE '- Daily schedule summaries';
    RAISE NOTICE '';
    RAISE NOTICE '💡 Students can now ask:';
    RAISE NOTICE '  "When is CS-104 class?"';
    RAISE NOTICE '  "What does Dr. Farooq teach?"';
    RAISE NOTICE '  "Show me Monday schedule"';
    RAISE NOTICE '  "Where is Database lab?"';
    RAISE NOTICE '========================================';
END $$;

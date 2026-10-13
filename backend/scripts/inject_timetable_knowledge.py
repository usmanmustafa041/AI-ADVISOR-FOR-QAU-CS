#!/usr/bin/env python3
"""
Inject Spring 2026 timetable knowledge into the RAG system.
Creates comprehensive markdown documents for the chatbot to reference.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.core.database import get_engine

# Timetable knowledge content
TIMETABLE_KNOWLEDGE = {
    "timetable-spring-2026-overview": {
        "category": "timetable",
        "title": "Spring 2026 Timetable Overview",
        "content": """# Spring 2026 Class Schedule

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

## Total Schedule Entries
Over 100+ class sessions scheduled across:
- Multiple rooms (Room 201, Room 217, Room 235, Room F6, Room F8, CS Lab, BS Lab, Online)
- Various time slots from early morning (08:35) to evening (20:00)
- All weekdays (Monday through Friday, with limited Saturday/Sunday sessions)

## Key Features
1. **Multiple Sections:** Regular (R) and Self-Finance (S) sections available
2. **Shift System:** Morning (08:35-14:00), Afternoon (13:35-17:00), Evening (17:00-20:00)
3. **Lab Sessions:** Dedicated lab time for programming courses
4. **Teaching Assistants:** TAs assigned for practical courses

## How to Use This Timetable
Students can query:
- "When is CS-104 class?"
- "What courses does Dr. Farooq teach on Monday?"
- "Show me the schedule for Room 201"
- "What classes are in the morning shift?"
- "When is Database Systems lab?"

The timetable includes complete information about instructors, rooms, time slots, and course sections.""",
        "priority": 10
    },
    
    "timetable-query-guide": {
        "category": "timetable",
        "title": "How to Query the Timetable",
        "content": """# Querying the Spring 2026 Timetable

## Available Query Types

### 1. By Course Code
Ask about specific courses:
- "When is CS-104 scheduled?"
- "What time is Database Systems?"
- "Show me the CS-313 Computer Architecture schedule"

### 2. By Day of Week
Get schedules for specific days:
- "What classes are on Monday?"
- "Show me Tuesday's schedule"
- "What courses are offered on Friday?"

### 3. By Instructor
Find instructor schedules:
- "What does Dr. Ghazanfar Farooq teach?"
- "When does Ms. Ifrah teach?"
- "Show me Dr. Umer Rashid's schedule"

### 4. By Room
Check room utilization:
- "What classes are in Room 201?"
- "Show me CS Lab schedule"
- "Which courses use Room 235?"

### 5. By Time Slot
Find classes at specific times:
- "What classes start at 08:35?"
- "Show me afternoon classes"
- "Evening shift courses"

### 6. By Program/Semester
Filter by program:
- "BS Semester 1 schedule"
- "MPhil courses this semester"
- "Show me Semester 4 classes"

### 7. By Section Type
- Regular sections vs Self-Finance sections
- Lab sessions vs lecture sessions
- Deficiency courses

## Example Queries
1. "When and where is Problem Solving & Programming taught?"
2. "Who teaches Data Mining?"
3. "What's the schedule for BS Semester 6 students?"
4. "Show me all Computer Vision classes"
5. "What time does Dr. Khalid Saleem teach Database Systems?"

## Important Notes
- Always specify if you need Regular (R) or Self-Finance (S) section
- Lab sessions may be scheduled separately from lectures
- Some courses have multiple sections at different times
- Teaching Assistants are mentioned for practical courses""",
        "priority": 15
    },
    
    "timetable-common-courses": {
        "category": "timetable",
        "title": "Commonly Asked Course Schedules",
        "content": """# Frequently Requested Course Schedules

## Semester 1 Core Courses

### CS-104: Problem Solving & Programming (PSP)
**Regular Section:**
- Monday 08:35-10:05, Room 201 (Dr. Ghazanfar Farooq + Mr. Hammad TA)
- Tuesday 10:15-11:45, CS Lab (Dr. Ghazanfar Farooq + Mr. Hammad TA)
- Tuesday 15:15-16:45, CS Lab (Dr. Ghazanfar Farooq + Mr. Hammad TA)
- Thursday 10:15-11:45, Room 201 (Dr. Ghazanfar Farooq + Mr. Hammad TA)

**Self-Finance Section:**
- Monday 08:35-10:05, Room F8 (Ms. Memoona Afsheen + Mr. Abdur Rehman TA)
- Tuesday 08:35-10:05, BS Lab (Ms. Memoona Afsheen + Mr. Abdur Rehman TA)
- Tuesday 10:15-11:45, BS Lab (Ms. Memoona Afsheen + Mr. Abdur Rehman TA)
- Thursday 10:15-11:45, Room 217 (Ms. Memoona Afsheen + Mr. Abdur Rehman TA)

*Credit Hours: 3+1 (theory + lab)*

## Semester 2 Core Courses

### CS-121: Object Oriented Programming (OOP)
**Combined Regular & Self-Finance:**
- Monday 15:15-16:45, Room 217 (Ms. Memoona Afsheen)
- Tuesday 08:05-10:05, CS Lab (Lab session)
- Thursday 08:05-10:05, Room 217 (Lab session)

*Credit Hours: 3+1*

## Semester 3 Core Courses

### CS-211: Data Structures (DS)
**Regular Section:**
- Monday 10:15-11:45, BS Lab (Dr. Rabeeh Ayaz Abbasi + Ms. Safeena TA)
- Tuesday 11:55-13:25, Room F8 (Dr. Rabeeh Ayaz Abbasi + Ms. Safeena TA)
- Thursday 15:15-16:45, CS Lab (Dr. Rabeeh Ayaz Abbasi + Ms. Safeena TA)

*Credit Hours: 3+1*

## Semester 4 Core Courses

### CS-224: Database Systems (DBS)
**Regular Section:**
- Monday 08:35-10:05, CS Lab (Dr. Khalid Saleem & Ms. Rida Nawaz)
- Wednesday 08:35-10:05, CS Lab (Dr. Khalid Saleem & Ms. Rida Nawaz)
- Wednesday 10:15-11:45, CS Lab (Dr. Khalid Saleem & Ms. Rida Nawaz)
- Thursday 13:35-15:05, Room 217 (Dr. Khalid Saleem & Ms. Rida Nawaz)

**Self-Finance Section:**
- Tuesday 08:35-10:05, Room 217 (Dr. Shuaib Karim & Ms. Fouzia Qureshi)
- Wednesday 10:15-11:45, Room 201 (Dr. Shuaib Karim & Ms. Fouzia Qureshi)
- Thursday 10:15-11:45, CS Lab (Dr. Shuaib Karim & Ms. Fouzia Qureshi)
- Thursday 11:55-13:25, CS Lab (Dr. Shuaib Karim & Ms. Fouzia Qureshi)

*Credit Hours: 3+1*

### CS-313: Computer Architecture (CA)
**Regular Section:**
- Monday 11:55-13:25, Room 217 (Ms. Ifrah Farrukh Khan)
- Wednesday 10:15-11:45, Room 217 (Ms. Ifrah Farrukh Khan)

**Self-Finance Section:**
- Monday 10:15-11:45, Room 201 (Dr. Nadia Saeed)
- Wednesday 08:35-10:05, Room 201 (Dr. Nadia Saeed)

*Credit Hours: 3*

### CS-222: Analysis and Design for Software Systems (ADSS)
**Regular Section:**
- Monday 13:35-15:05, Room 217 (Dr. Onaiza Maqbool)
- Wednesday 13:35-15:05, Room 217 (Dr. Onaiza Maqbool)

**Self-Finance Section:**
- Monday 13:35-15:05, Room 201 (Dr. Umer Rashid)
- Wednesday 15:15-16:45, Room 217 (Dr. Umer Rashid)

*Credit Hours: 3*

## Advanced Courses

### CS-455: Natural Language Processing (NLP)
**Combined Regular & Self-Finance:**
- Tuesday 11:55-13:25, CS Lab (Dr. Nadia Saeed)
- Thursday 13:35-15:05, Room 235 (Dr. Nadia Saeed)

*Semester: 7/8, Credit Hours: 3*

### CS-460: Deep Learning (DL)
**Regular Section:**
- Monday 08:35-10:05, Room 235 (Dr. Ayyaz Hussain)
- Wednesday 11:55-13:25, Room 235 (Dr. Ayyaz Hussain)

*Semester: 8, Credit Hours: 3*

## Note on Lab Sessions
Lab sessions are critical for:
- CS-104 (Problem Solving & Programming)
- CS-121 (Object Oriented Programming)
- CS-211 (Data Structures)
- CS-224 (Database Systems)
- CS-215 (Computer Organization and Assembly Language)

Students must attend both lecture and lab sessions.""",
        "priority": 20
    },
    
    "timetable-instructors": {
        "category": "timetable",
        "title": "Faculty Teaching Assignments Spring 2026",
        "content": """# Instructor Teaching Assignments - Spring 2026

## Core CS Faculty

### Dr. Ghazanfar Farooq
**Courses:**
- CS-104: Problem Solving & Programming (Regular sections)
- CS-423: Computer Graphics (Repeaters)
**Primary Teaching:** Semester 1 students, Programming fundamentals

### Dr. Khalid Saleem
**Courses:**
- CS-224: Database Systems (Regular sections with Ms. Rida Nawaz)
- CS-325: Advanced Database Systems
- DSC-838: Recommender Systems (MS-DS program)
**Specialization:** Database systems, Data Science

### Dr. Onaiza Maqbool
**Courses:**
- CS-222: Analysis and Design for Software Systems (Regular)
- CS-458: Data Mining (Self-Finance)
**Specialization:** Software Engineering, Data Mining

### Dr. Umer Rashid
**Courses:**
- CS-222: Analysis and Design for Software Systems (Self-Finance)
- CS-331: Theory of Automata
- DSC-675: Information Retrieval Systems (MS-DS)
**Specialization:** Software Engineering, Information Retrieval

### Dr. Rabeeh Ayaz Abbasi
**Courses:**
- CS-211: Data Structures (with Ms. Safeena TA)
- CSC-827: Social Network Analysis (MPhil/PhD)
**Specialization:** Data Structures, Social Networks

### Dr. Muddassar Sindhu
**Courses:**
- CS-411: Compiler Construction
- CS-483: Software Quality Assurance
- CSC-614: Software Quality Assurance and Testing (MPhil/PhD)
**Specialization:** Compilers, Software Quality

### Dr. Nadia Saeed
**Courses:**
- CS-313: Computer Architecture (Self-Finance)
- CS-455: Natural Language Processing
**Specialization:** Computer Architecture, NLP

### Dr. Akmal Saeed Khattak
**Courses:**
- CS-457: Web Application Framework
- CSC-675: Information Retrieval Systems (MPhil/PhD)
**Specialization:** Web Technologies, Information Retrieval

### Dr. S. M. Naqi
**Courses:**
- CS-425: Computer Vision
- CS-352: Data Structures & Algorithms (Deficiency, evening)
- CSC-741: Computer Vision (MPhil/PhD)
**Specialization:** Computer Vision, Algorithms

### Dr. Muazzam Khattak
**Courses:**
- CS-312: Computer Communications and Networks
- CS-413: Introduction to Information Security
**Specialization:** Networks, Security

### Dr. Shuaib Karim
**Courses:**
- CS-224: Database Systems (Self-Finance, with Ms. Fouzia Qureshi)
- CS-449: ICT and Society
**Specialization:** Database Systems, ICT

### Dr. Ayyaz Hussain
**Courses:**
- CS-460: Deep Learning
- CS-105: Problem Solving and Programming (Deficiency, online evening)
**Specialization:** Deep Learning, AI

### Dr. Adeel Ur Rehman
**Courses:**
- CS-332: Net Centric Programming
**Specialization:** Web Programming

## Lecturers & Instructors

### Ms. Ifrah Farrukh Khan
**Role:** Timetable/Datesheet Coordinator
**Courses:**
- CS-313: Computer Architecture (Regular)
- CS-215: Computer Organization and Assembly Language (with Mr. Zain TA)

### Ms. Memoona Afsheen
**Courses:**
- CS-104: Problem Solving & Programming (Self-Finance, with Mr. Abdur Rehman TA)
- CS-121: Object Oriented Programming (Combined sections)

### Mr. Muhammad Tauseef
**Courses:**
- CS-535: Cloud DevOps

## Co-Instructors

### Ms. Rida Nawaz
**Co-teaches:** CS-224 Database Systems (Regular) with Dr. Khalid Saleem

### Ms. Fouzia Qureshi
**Co-teaches:** CS-224 Database Systems (Self-Finance) with Dr. Shuaib Karim

## Teaching Assistants (TAs)

### Mr. Hammad
**Assists:** CS-104 Problem Solving & Programming (Regular, Dr. Farooq)

### Mr. Abdur Rehman
**Assists:** CS-104 Problem Solving & Programming (Self-Finance, Ms. Memoona)

### Ms. Safeena
**Assists:** CS-211 Data Structures (Dr. Rabeeh)

### Mr. Zain
**Assists:** CS-215 Computer Organization and Assembly Language (Ms. Ifrah)

## Graduate Program Faculty

### MPhil/PhD Courses:
- CSC-614: Software Quality Assurance and Testing (Dr. Muddassar Sindhu)
- CSC-675: Information Retrieval Systems (Dr. Akmal Saeed Khattak)
- CSC-741: Computer Vision (Dr. S. M. Naqi)
- CSC-827: Social Network Analysis (Dr. Rabeeh Abbasi)

### MS-DS (Data Science) Courses:
- DS-606: Probability and Statistics for Data Science (Dr. Abdul Jalil)
- DSC-675: Information Retrieval Systems (Dr. Umer Rashid)
- DSC-838: Recommender Systems (Dr. Khalid Saleem)

## Non-CS Department Faculty

### Dr. Muhammad Shafiq (Physics)
**Courses:** PH-110 Introduction to Mechanics and Waves

### Dr. Waseem Siddiqui (Mathematics)
**Courses:** MA-104 Fundamentals of Linear Algebra

### Ms. Farwa Haider (Mathematics)
**Courses:** MA-202 Multivariable Calculus

### Dr. Arshad Qayyum (Islamic Studies)
**Courses:** IS-100 Islamic Studies/Ethics

### Dr. Nasreen Kousar (Social Work)
**Courses:** SW-100 Civics and Community Engagement

### Ms. Tahira Shabir (English)
**Courses:** EN-200 Expository Writing

### Dr. Abdul Rasheed (Social Sciences)
**Courses:** GEN-100 Social Sciences

### Mr. Abdul Wahid (Islamic Studies)
**Courses:** FQ-102/FQ-602 Understanding Quran II

### Dr. Abdul Jalil (Statistics)
**Courses:** DS-606 Probability and Statistics for Data Science""",
        "priority": 25
    },
}


def inject_knowledge():
    """Inject timetable knowledge into the database"""
    engine = get_engine()
    
    print("🚀 Starting timetable knowledge injection into RAG system...")
    print(f"📚 Total knowledge entries to inject: {len(TIMETABLE_KNOWLEDGE)}")
    
    with engine.begin() as conn:
        for sub_key, entry in TIMETABLE_KNOWLEDGE.items():
            print(f"\n📝 Processing: {entry['title']}")
            
            # Use the upsert function from the schema
            result = conn.execute(
                text("""
                    SELECT upsert_knowledge(
                        :sub_key,
                        :category,
                        :title,
                        :content,
                        '{}'::jsonb,
                        NULL,
                        :priority
                    )
                """),
                {
                    "sub_key": sub_key,
                    "category": entry["category"],
                    "title": entry["title"],
                    "content": entry["content"],
                    "priority": entry.get("priority", 100)
                }
            )
            
            kb_id = result.scalar()
            print(f"   ✅ Injected: {sub_key} (ID: {kb_id})")
    
    print("\n" + "="*80)
    print("✨ Timetable knowledge injection complete!")
    print("="*80)
    
    # Verify injection
    print("\n🔍 Verifying injection...")
    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM knowledge_base WHERE category = 'timetable' AND is_active = TRUE")
        ).scalar()
        
        print(f"✅ Found {count} active timetable entries in knowledge base")
        
        # Show titles
        rows = conn.execute(
            text("""
                SELECT sub_key, title, priority 
                FROM knowledge_base 
                WHERE category = 'timetable' AND is_active = TRUE
                ORDER BY priority ASC
            """)
        ).fetchall()
        
        print("\n📋 Injected Knowledge Entries:")
        for row in rows:
            print(f"   • [{row[2]}] {row[1]} ({row[0]})")
    
    print("\n✅ Knowledge injection verification complete!")
    print("\n💡 The chatbot can now answer timetable queries using RAG!")
    print("   Try asking:")
    print("   - 'When is CS-104 class?'")
    print("   - 'What does Dr. Farooq teach?'")
    print("   - 'Show me Monday's schedule'")
    print("   - 'Where is Database Systems lab?'")


if __name__ == "__main__":
    inject_knowledge()

#!/usr/bin/env python3
"""
Non-Destructive Knowledge Base Seeder

This script seeds the knowledge_base table with existing hardcoded data
(schemes, admissions, fees) using UPSERT operations only.

SAFETY GUARANTEES:
1. No DELETE operations
2. No TRUNCATE operations
3. Only INSERT ... ON CONFLICT DO UPDATE (upsert)
4. Existing records are preserved and updated, never deleted
5. Can be run multiple times safely (idempotent)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_engine

def seed_knowledge_base(session: Session) -> dict:
    """
    Seed knowledge base with existing hardcoded data.
    Returns count of records inserted/updated per category.
    """
    
    results = {
        "schemes": 0,
        "admissions": 0,
        "fees": 0,
        "errors": []
    }
    
    # ========================================================================
    # BSCS SCHEME 2021
    # ========================================================================
    
    scheme_2021_content = """# BSCS Scheme 2021 (Superseded | Effective 2021 Batch Onwards)

**Total Credits:** 130 (17+18+16+16+18+15+15+15)

## Semester 1 (17 Cr.)
- EN-101: English-1 (3)
- PS-101: Pakistan Studies (2)
- MA-101: Calculus & Analytical Geometry-I (3)
- PH-111: Introductory Mechanics & Waves (2)
- PH-193: Introductory Mechanics & Waves Lab (1)
- CS-101: Introduction to Computing (3)
- CS-105: Problem Solving and Programming (3 [2,1])

## Semester 2 (18 Cr.)
- EN-102: English-2 (3)
- IS-101: Islamic Studies (2)
- MA-102: Calculus & Analytical Geometry-II (3)
- PH-112: Electricity, Magnetism and Thermal Physics (2)
- PH-194: Electricity, Magnetism and Thermal Physics Lab (1)
- MA-203: Discrete Mathematics (3)
- CS-121: Object Oriented Programming (4 [3,1])

## Semester 3 (16 Cr.)
- CS-103: Introduction to Computer Organization (3)
- EN-201: English-3 (3)
- PY-101: Introduction to Psychology (3)
- CS-211: Data Structures (3)
- CS-291: Data Structures Lab (1)
- CS-212: Human Computer Interaction (3)

## Semester 4 (16 Cr.)
- CH-100: General Chemistry (2)
- CH-190: General Chemistry Lab (1)
- MA-205: Differential Equations & Linear Algebra (3)
- CS-222: Analysis & Design for Software Systems (3)
- CS-225: Database System (3)
- CS-213: Computer Organization & Assembly Language (3)
- CS-293: Computer Organization & Assembly Language Lab (1)

## Semester 5 (18 Cr.)
- ST-101: Probability & Statistics (3)
- BY-201: Introductory Biology (3)
- CS-223: Operating Systems (3)
- CS-311: Analysis & Design of Algorithms (3)
- CS-423: Computer Graphics (3)
- CS-322: Software Construction (3 [2,1])

## Semester 6 (15 Cr.)
- EC-201: Economics (3)
- CS-331: Theory of Automata (3)
- CS-312: Computer Communications & Networks (3)
- CS-414: Artificial Intelligence (3)
- Elective Course-1 (3)

## Semester 7 (15 Cr.)
- CS-489: Project-I (3)
- CS-332: Net Centric Programming (3)
- CS-411: Compiler Construction (3)
- Elective Course-2 (3)
- Elective Course-3 (3)

## Semester 8 (15 Cr.)
- CS-490: Project-II (3)
- CS-413: Introduction to Information Security (3)
- CS-449: ICT and Society (3)
- Elective Course-4 (3)
- Elective Course-5 (3)

**CS Electives Pool (33 courses):** CS-324, CS-442, CS-443, CS-444, CS-445, CS-446, CS-448, CS-451, CS-452, CS-454, CS-455, CS-456, CS-457, CS-458, CS-459, CS-462, CS-464, CS-471, CS-472, CS-473, CS-474, CS-475, CS-476, CS-478, CS-480, CS-482, CS-483, CS-484, CS-486, CS-487, CS-488, CS-491, CS-497
"""
    
    try:
        session.execute(text("""
            SELECT upsert_knowledge(
                :sub_key,
                :category,
                :title,
                :content,
                :structured_data,
                :source_url,
                :priority
            )
        """), {
            "sub_key": "scheme_2021",
            "category": "scheme",
            "title": "BSCS Scheme of Study 2021",
            "content": scheme_2021_content,
            "structured_data": '{"year": 2021, "total_credits": 130, "semesters": 8, "status": "superseded"}',
            "source_url": None,
            "priority": 80
        })
        session.commit()
        results["schemes"] += 1
        print("✅ Seeded: Scheme 2021")
    except Exception as e:
        results["errors"].append(f"Scheme 2021: {str(e)}")
        print(f"❌ Error seeding Scheme 2021: {e}")
        session.rollback()
    
    # ========================================================================
    # BSCS SCHEME 2023
    # ========================================================================
    
    scheme_2023_content = """# BSCS Scheme 2023 (Active | Effective Fall 2023)

**Total Credits:** 130 (GE:30, CC:46, DC:18, DE:21, MS:12, ES:3)

## Semester 1 (15 Cr.)
- EN-100: Functional English (GE 3)
- PK-100: Ideology & Constitution of Pakistan (GE 2)
- MA-101: Calculus & Analytical Geometry (GE 3)
- PH-111: Introductory Mechanics & Waves (GE 2)
- PH-191: Introductory Mechanics & Waves Lab (GE 1)
- CS-104: Problem Solving & Programming (CC 3+1)

## Semester 2 (17 Cr.)
- EN-200: Expository Writing (GE 3)
- IS-100: Islamic Studies/Ethics (GE 2)
- Social Sciences Elective (GE 2)
- PH-112: Electricity, Magnetism & Modern Physics (GE 2)
- PH-192: Electricity, Magnetism & Modern Physics Lab (GE 1)
- MA-202: Multivariable Calculus (MS 3)
- CS-121: Object Oriented Programming (CC 4+1)

## Semester 3 (16 Cr.)
- MA-203: Discrete Mathematics (GE 3)
- EN-299: Technical and Business Writing (MS 3)
- CS-103: Introduction to Computer Organization (CC 3)
- CS-211: Data Structures (CC 3+1)
- CS-212: Human Computer Interaction (DC 3)

## Semester 4 (17 Cr.)
- SW-100: Civics and Community Engagement (GE 2)
- PS-101: Pakistan Studies (GE 2)
- MA-104: Fundamentals of Linear Algebra (MS 3)
- CS-222: Analysis & Design of Software Systems (CC 3)
- CS-224: Database Systems (CC 3+1)
- CS-313: Computer Architecture (DC 3)

## Semester 5 (18 Cr.)
- ST-101: Probability and Statistics (MS 3)
- CS-322: Software Construction (DC 2+1)
- CS-226: Operating Systems (CC 2+1)
- CS-311: Analysis & Design of Algorithms (CC 3)
- CS-414: Artificial Intelligence (CC 3)
- Domain Elective 1 (DE 3)

## Semester 6 (18 Cr.)
- CS-331: Theory of Automata (DC 3)
- CS-325: Advanced Database Systems (DC 2+1)
- CS-215: Computer Org. & Assembly Language (CC 2+1)
- CS-312: Computer Communications & Networks (CC 3)
- Domain Elective 2 (DE 3)
- Domain Elective 3 (DE 3)

## Semester 7 (15 Cr.)
- MS-100: Entrepreneurship (GE 2)
- Arts and Humanities Elective (GE 2)
- CS-411: Compiler Construction (DC 3)
- CS-489: Project-I (CC 2)
- Domain Elective 4 (DE 3)
- Domain Elective 5 (DE 3)

## Semester 8 (16 Cr.)
- Elective Supporting (ES 3)
- CS-412: Introduction to Cyber Security (CC 3)
- CS-490: Project-II (CC 4)
- Domain Elective 6 (DE 3)
- Domain Elective 7 (DE 3)

**Category Breakdown:**
- GE (General Education): 30 credits
- CC (Core Courses): 46 credits
- DC (Discipline Courses): 18 credits
- DE (Domain Electives): 21 credits
- MS (Mathematical Sciences): 12 credits
- ES (Elective Supporting): 3 credits
"""
    
    try:
        session.execute(text("""
            SELECT upsert_knowledge(
                :sub_key,
                :category,
                :title,
                :content,
                :structured_data,
                :source_url,
                :priority
            )
        """), {
            "sub_key": "scheme_2023",
            "category": "scheme",
            "title": "BSCS Scheme of Study 2023",
            "content": scheme_2023_content,
            "structured_data": '{"year": 2023, "total_credits": 130, "semesters": 8, "status": "active", "categories": {"GE": 30, "CC": 46, "DC": 18, "DE": 21, "MS": 12, "ES": 3}}',
            "source_url": None,
            "priority": 90
        })
        session.commit()
        results["schemes"] += 1
        print("✅ Seeded: Scheme 2023")
    except Exception as e:
        results["errors"].append(f"Scheme 2023: {str(e)}")
        print(f"❌ Error seeding Scheme 2023: {e}")
        session.rollback()
    
    # ========================================================================
    # BSCS SCHEME 2025 (Current)
    # ========================================================================
    
    scheme_2025_content = """# BSCS Scheme 2025 (Current | Effective Fall 2025)

**Total Credits:** 134 (GE:34, CC:46, DC:18, DE:21, MS:12, ES:3)

## Semester 1 (15 Cr.)
- EN-100: Functional English (GE 3)
- PK-100: Ideology & Constitution of Pakistan (GE 2)
- MA-101: Calculus & Analytical Geometry (GE 3)
- PH-110: Introductory Mechanics and Waves (GE 2)
- FQ-101: Understanding Quran-I (GE 0+1)
- CS-104: Problem Solving & Programming (CC 3+1)

## Semester 2 (17 Cr.)
- EN-200: Expository Writing (GE 3)
- IS-100: Islamic Studies/Ethics (GE 2)
- Social Sciences Elective (GE 2)
- PH-111: Electricity, Magnetism & Modern Physics (GE 2)
- FQ-102: Understanding Quran-II (GE 0+1)
- MA-202: Multivariable Calculus (MS 3)
- CS-121: Object Oriented Programming (CC 4+1)

## Semester 3 (16 Cr.)
- MA-203: Discrete Mathematics (GE 3)
- EN-299: Technical and Business Writing (MS 3)
- CS-103: Introduction to Computer Organization (CC 3)
- CS-211: Data Structures (CC 3+1)
- CS-212: Human Computer Interaction (DC 3)

## Semester 4 (17 Cr.)
- SW-100: Civics and Community Engagement (GE 2)
- PS-101: Pakistan Studies (GE 2)
- MA-104: Fundamentals of Linear Algebra (MS 3)
- CS-222: Analysis & Design of Software Systems (CC 3)
- CS-224: Database Systems (CC 3+1)
- CS-313: Computer Architecture (DC 3)

## Semester 5 (18 Cr.)
- ST-101: Probability and Statistics (MS 3)
- CS-322: Software Construction (DC 2+1)
- CS-226: Operating Systems (CC 2+1)
- CS-311: Analysis & Design of Algorithms (CC 3)
- CS-414: Artificial Intelligence (CC 3)
- Domain Elective 1 (DE 3)

## Semester 6 (18 Cr.)
- CS-331: Theory of Automata (DC 3)
- CS-325: Advanced Database Systems (DC 2+1)
- CS-215: Computer Org. & Assembly Language (CC 2+1)
- CS-312: Computer Communications & Networks (CC 3)
- Domain Elective 2 (DE 3)
- Domain Elective 3 (DE 3)

## Semester 7 (15 Cr.)
- MS-100: Entrepreneurship (GE 2)
- Arts and Humanities Elective (GE 2)
- CS-411: Compiler Construction (DC 3)
- CS-489: Project-I (CC 2)
- Domain Elective 4 (DE 3)
- Domain Elective 5 (DE 3)

## Semester 8 (18 Cr.)
- Elective Supporting (ES 3)
- CS-412: Introduction to Cyber Security (CC 3)
- CS-490: Project-II (CC 4)
- Domain Elective 6 (DE 3)
- Domain Elective 7 (DE 3)
- Internship (CC 2)

**Key Differences from 2023:**
- Added FQ-101 and FQ-102 (Quranic Studies, 0+1 each) = +2 credits
- Added Internship in Semester 8 (2 credits) = +2 credits
- Total: 134 credits (vs 130 in 2023)
"""
    
    try:
        session.execute(text("""
            SELECT upsert_knowledge(
                :sub_key,
                :category,
                :title,
                :content,
                :structured_data,
                :source_url,
                :priority
            )
        """), {
            "sub_key": "scheme_2025",
            "category": "scheme",
            "title": "BSCS Scheme of Study 2025 (Current)",
            "content": scheme_2025_content,
            "structured_data": '{"year": 2025, "total_credits": 134, "semesters": 8, "status": "current", "categories": {"GE": 34, "CC": 46, "DC": 18, "DE": 21, "MS": 12, "ES": 3}}',
            "source_url": None,
            "priority": 100
        })
        session.commit()
        results["schemes"] += 1
        print("✅ Seeded: Scheme 2025")
    except Exception as e:
        results["errors"].append(f"Scheme 2025: {str(e)}")
        print(f"❌ Error seeding Scheme 2025: {e}")
        session.rollback()
    
    # ========================================================================
    # FALL 2026 ADMISSIONS
    # ========================================================================
    
    admissions_fall_2026_content = """# QAU Undergraduate Admissions (Fall 2026) - Official Notice

## 1. APPLICATION DEADLINES

- **BS / LLB Programmes:** 10/08/2026
- **Pharm-D Programme:** 22/09/2026
- **Application Mode:** Strictly Online via QAU website (qau.edu.pk). NO manual/by-hand/post submissions accepted.
- **Application Processing Fee:** Rs. 2,860/- via Kuickpay or 1-Bill (receipt upload mandatory).
- **Contact Email:** admissions2026fall@qau.edu.pk

## 2. MERIT FORMULAS

### BS Programmes
70% HSSC (FA/FSc) Part-I or Equivalent + 30% SSC (Matric)

### LLB (5-Year) Programme
50% HSSC Part-I + 30% HEC LAT Score + 20% SSC (Matric)
- Requires: Minimum 50% marks in FA/FSc & minimum 50 score in LAT

### Pharm-D Programme
70% Complete HSSC Result + 30% SSC (Matric)
- Requires: Complete FSc Pre-Medical with minimum 60% marks

## 3. PROGRAMME-WISE ELIGIBILITY

### Natural Sciences

**BS Computer Science:**
- FA/FSc or equivalent with Mathematics, OR
- Pre-Medical with Additional Mathematics
- Minimum 50% marks in HSSC Part-I

**BS Information Technology:**
- FSc or equivalent with Physics and Mathematics
- Minimum 50% marks in HSSC Part-I

### Other Programmes
(See full admission notice for complete list of 35+ programmes)

## 4. MERIT LIST DISPLAY SCHEDULE

### BS / LLB Programmes
- 1st Merit List: 15-08-2026
- 2nd Merit List: 19-08-2026
- 3rd Merit List (if required): 23-08-2026

### Pharm-D Programme
- 1st Merit List: 27-09-2026
- 2nd Merit List: 02-10-2026
- 3rd Merit List (if required): 05-10-2026

## 5. KEY POLICIES

- **Subject Options:** Max 3 Regular + 3 Self-Finance = 6 total choices
- **Age Limit:** NO age limit for BS/LLB/Pharm-D
- **Result-Awaiting:** Part-I basis allowed; must score ≥50% in complete HSSC within 45 days
- **Scholarships:** 25+ schemes available; Self-Finance students NOT eligible
- **Reserved Quotas:** Army, Disabled, Minorities, Sports, Martyrs, etc.
"""
    
    try:
        session.execute(text("""
            SELECT upsert_knowledge(
                :sub_key,
                :category,
                :title,
                :content,
                :structured_data,
                :source_url,
                :priority
            )
        """), {
            "sub_key": "admissions_fall_2026",
            "category": "admission",
            "title": "QAU Undergraduate Admissions Fall 2026",
            "content": admissions_fall_2026_content,
            "structured_data": '{"year": 2026, "term": "Fall", "deadlines": {"BS_LLB": "2026-08-10", "Pharm_D": "2026-09-22"}, "application_fee": 2860}',
            "source_url": "qau.edu.pk/admissions",
            "priority": 100
        })
        session.commit()
        results["admissions"] += 1
        print("✅ Seeded: Fall 2026 Admissions")
    except Exception as e:
        results["errors"].append(f"Fall 2026 Admissions: {str(e)}")
        print(f"❌ Error seeding Fall 2026 Admissions: {e}")
        session.rollback()
    
    # ========================================================================
    # FEE STRUCTURE FALL 2025
    # ========================================================================
    
    fees_fall_2025_content = """# QAU Undergraduate Fee Structure (Fall 2025 - National Students)

## BS Computer Science / BS Information Technology / LLB (5-Year)

**Per Semester:**
- Regular Basis: Rs. 96,320/-
- Self-Finance/Evening: Rs. 165,230/-

## BS Pharmacy (Pharm-D)

**Per Semester:**
- Regular Basis: Rs. 95,320/-
- Self-Finance: Rs. 164,230/-

## Other BS Programmes

**Per Semester:**
- Regular Basis: Rs. 90,580/-
- Self-Finance/Evening: Rs. 141,120/-

## QASMS Business Administration, English, SP&IR

**Per Semester:**
- Regular Basis: Rs. 93,320/-
- Self-Finance/Evening: Rs. 162,230/-

## One-Time Admission Fees

- Admission Processing Fee: Rs. 2,860/-
- Security Deposit (Refundable): Rs. 5,000/-
- Prospectus Fee: Rs. 500/-
- Student Activity Fee: Rs. 2,000/-
- Medical Fee: Rs. 1,000/-

**Total One-Time Fees:** Rs. 11,360/-

## Additional Fees

- Fee for Non-Credit Course (per course): Rs. 2,830/-
- Degree Fee (20 working days): Rs. 6,300/-
- Urgent Degree Fee (5 working days): Rs. 12,590/-
- Duplicate Degree Fee: Rs. 12,590/-
- Migration Certificate Fee: Rs. 3,780/-
- Grade Card/Result Card (20 working days): Rs. 630/-
- Verification Fee: Rs. 1,890/-
- Degree Folder Fee: Rs. 630/-

## Important Notes

1. Semester fees are for Category A + B (tuition, library, lab, etc.)
2. One-time fees (Category C) paid only at admission
3. Self-Finance students pay ~70% more than Regular
4. Summer course fee: Rs. 9,880/- per course
5. Evening Program (Open Merit): Rs. 10,760/- per course
6. **CRITICAL:** Self-Finance students are NOT eligible for scholarships
"""
    
    try:
        session.execute(text("""
            SELECT upsert_knowledge(
                :sub_key,
                :category,
                :title,
                :content,
                :structured_data,
                :source_url,
                :priority
            )
        """), {
            "sub_key": "fees_fall_2025",
            "category": "fee_structure",
            "title": "QAU Undergraduate Fee Structure Fall 2025",
            "content": fees_fall_2025_content,
            "structured_data": '{"year": 2025, "term": "Fall", "programmes": {"CS_IT_LLB": {"regular": 96320, "self_finance": 165230}, "Pharm_D": {"regular": 95320, "self_finance": 164230}, "Other": {"regular": 90580, "self_finance": 141120}}}',
            "source_url": "qau.edu.pk/bachelor-fee-structure",
            "priority": 100
        })
        session.commit()
        results["fees"] += 1
        print("✅ Seeded: Fall 2025 Fee Structure")
    except Exception as e:
        results["errors"].append(f"Fall 2025 Fees: {str(e)}")
        print(f"❌ Error seeding Fall 2025 Fees: {e}")
        session.rollback()
    
    return results


def main():
    """Main seeder function"""
    print("=" * 80)
    print("KNOWLEDGE BASE SEEDER (NON-DESTRUCTIVE / UPSERT-ONLY)")
    print("=" * 80)
    print()
    
    engine = get_engine()
    
    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\nPlease ensure:")
        print("1. PostgreSQL is running")
        print("2. Database 'qau_advisor' exists")
        print("3. User 'qau_advisor' has permissions")
        print("4. Schema has been initialized (run init_knowledge_base_schema.sql)")
        return
    
    # Check if knowledge_base table exists
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename = 'knowledge_base'
                )
            """))
            exists = result.scalar()
            
            if not exists:
                print("❌ knowledge_base table does not exist!")
                print("\nPlease run: psql <database_url> -f scripts/init_knowledge_base_schema.sql")
                return
            else:
                print("✅ knowledge_base table exists")
    except Exception as e:
        print(f"❌ Error checking table existence: {e}")
        return
    
    print()
    print("Starting seeding process...")
    print("-" * 80)
    print()
    
    # Seed data
    session = Session(engine)
    try:
        results = seed_knowledge_base(session)
        
        print()
        print("=" * 80)
        print("SEEDING COMPLETE")
        print("=" * 80)
        print(f"✅ Schemes seeded/updated: {results['schemes']}")
        print(f"✅ Admissions seeded/updated: {results['admissions']}")
        print(f"✅ Fees seeded/updated: {results['fees']}")
        
        if results["errors"]:
            print(f"\n⚠️  Errors encountered: {len(results['errors'])}")
            for error in results["errors"]:
                print(f"  - {error}")
        else:
            print("\n✅ No errors - all records seeded successfully!")
        
        print()
        print("Verifying seeded data...")
        
        # Verify counts
        verify_result = session.execute(text("""
            SELECT category, COUNT(*) as count
            FROM knowledge_base
            WHERE is_active = true
            GROUP BY category
            ORDER BY category
        """))
        
        print("\nActive records by category:")
        for row in verify_result:
            print(f"  - {row[0]}: {row[1]} record(s)")
        
    except Exception as e:
        print(f"\n❌ Fatal error during seeding: {e}")
        session.rollback()
    finally:
        session.close()
    
    print()
    print("=" * 80)
    print("Done! You can now query the knowledge_base table.")
    print("=" * 80)


if __name__ == "__main__":
    main()

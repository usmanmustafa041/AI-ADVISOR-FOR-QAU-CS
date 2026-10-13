"""
Advanced LLM-based response generator using Ollama.

Provides intelligent, context-aware responses in English, Roman Urdu, and Urdu.
"""

import logging
import json
import requests
from pathlib import Path
from typing import Any

from app.rag.hybrid_search import SearchResult

logger = logging.getLogger(__name__)

# Load CS website knowledge base
CS_WEBSITE_DATA = None

def load_cs_website_data():
    """Load scraped CS website data."""
    global CS_WEBSITE_DATA
    if CS_WEBSITE_DATA is None:
        try:
            # Path relative to project root
            scraped_file = Path(__file__).parent.parent.parent.parent / "academic-data/scraped/cs_website_full.json"
            with open(scraped_file, 'r', encoding='utf-8') as f:
                CS_WEBSITE_DATA = json.load(f)
            logger.info(f"Loaded {len(CS_WEBSITE_DATA)} pages from CS website")
        except Exception as e:
            logger.error(f"Error loading CS website data: {e}")
            CS_WEBSITE_DATA = []
    return CS_WEBSITE_DATA


def search_cs_website(query: str, top_k: int = 5) -> list[dict]:
    """Search scraped CS website data."""
    data = load_cs_website_data()
    query_lower = query.lower()
    
    # Score each page
    scored_pages = []
    for page in data:
        score = 0
        content_lower = page['content'].lower()
        title_lower = page['title'].lower()
        
        # Check query terms in content
        query_terms = query_lower.split()
        for term in query_terms:
            if len(term) > 2:  # Skip short words
                if term in title_lower:
                    score += 10
                score += content_lower.count(term)
        
        if score > 0:
            scored_pages.append({
                'page': page,
                'score': score
            })
    
    # Sort by score and return top_k
    scored_pages.sort(key=lambda x: x['score'], reverse=True)
    return [item['page'] for item in scored_pages[:top_k]]


class OllamaLLM:
    """Interface to Ollama local LLM."""
    
    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.generate_url = f"{base_url}/api/generate"
        self.chat_url = f"{base_url}/api/chat"
    
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """Generate response from Ollama (legacy single prompt)."""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            response = requests.post(
                self.generate_url,
                json=payload,
                timeout=120  # Increased timeout for slow models
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return ""
        
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return ""

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """Generate multi-turn chat response from Ollama."""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }
            
            response = requests.post(
                self.chat_url,
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "").strip()
            else:
                logger.error(f"Ollama Chat API error: {response.status_code}")
                return ""
        
        except Exception as e:
            logger.error(f"Error calling Ollama Chat: {e}")
            return ""


class IntelligentResponseGenerator:
    """Generates intelligent, context-aware responses using LLM."""
    
    def __init__(self, model: str = "llama3.2:3b", db_session=None):
        self.llm = OllamaLLM(model=model)
        self.db_session = db_session  # Optional: for dynamic knowledge loading
        
        # Base system prompt for QAU CS Academic Advisor (with embedded fallback knowledge)
        self.base_system_prompt = """# Role and Context

You are the official BSCS Academic Advisor for the Department of Computer Sciences at Quaid-i-Azam University (QAU), Islamabad. You have complete, authoritative knowledge of all BSCS schemes and assist BS, MSc, MPhil, and PhD students with all queries regarding their academic journey including courses, schemes, timetables, faculty, admissions, fees, FYP, thesis submission, and departmental policies.

# ======================================================================
# GROUND TRUTH: OFFICIAL BSCS SCHEMES OF STUDY (EMBEDDED KNOWLEDGE BASE)
# ======================================================================

## SCHEME 2021 (Superseded | Effective 2021 Batch Onwards)

**Total Credits:** 130 (17+18+16+16+18+15+15+15)

**Semester 1 (17 Cr.):**
- EN-101: English-1 (3)
- PS-101: Pakistan Studies (2)
- MA-101: Calculus & Analytical Geometry-I (3)
- PH-111: Introductory Mechanics & Waves (2)
- PH-193: Introductory Mechanics & Waves Lab (1)
- CS-101: Introduction to Computing (3)
- CS-105: Problem Solving and Programming (3 [2,1])

**Semester 2 (18 Cr.):**
- EN-102: English-2 (3)
- IS-101: Islamic Studies (2)
- MA-102: Calculus & Analytical Geometry-II (3)
- PH-112: Electricity, Magnetism and Thermal Physics (2)
- PH-194: Electricity, Magnetism and Thermal Physics Lab (1)
- MA-203: Discrete Mathematics (3)
- CS-121: Object Oriented Programming (4 [3,1])

**Semester 3 (16 Cr.):**
- CS-103: Introduction to Computer Organization (3)
- EN-201: English-3 (3)
- PY-101: Introduction to Psychology (3)
- CS-211: Data Structures (3)
- CS-291: Data Structures Lab (1)
- CS-212: Human Computer Interaction (3)

**Semester 4 (16 Cr.):**
- CH-100: General Chemistry (2)
- CH-190: General Chemistry Lab (1)
- MA-205: Differential Equations & Linear Algebra (3)
- CS-222: Analysis & Design for Software Systems (3)
- CS-225: Database System (3)
- CS-213: Computer Organization & Assembly Language (3)
- CS-293: Computer Organization & Assembly Language Lab (1)

**Semester 5 (18 Cr.):**
- ST-101: Probability & Statistics (3)
- BY-201: Introductory Biology (3)
- CS-223: Operating Systems (3)
- CS-311: Analysis & Design of Algorithms (3)
- CS-423: Computer Graphics (3)
- CS-322: Software Construction (3 [2,1])

**Semester 6 (15 Cr.):**
- EC-201: Economics (3)
- CS-331: Theory of Automata (3)
- CS-312: Computer Communications & Networks (3)
- CS-414: Artificial Intelligence (3)
- Elective Course-1 (3)

**Semester 7 (15 Cr.):**
- CS-489: Project-I (3)
- CS-332: Net Centric Programming (3)
- CS-411: Compiler Construction (3)
- Elective Course-2 (3)
- Elective Course-3 (3)

**Semester 8 (15 Cr.):**
- CS-490: Project-II (3)
- CS-413: Introduction to Information Security (3)
- CS-449: ICT and Society (3)
- Elective Course-4 (3)
- Elective Course-5 (3)

**CS Electives Pool (Scheme 2021):** CS-324 (Web App Dev 3[2,1]), CS-442 (Mobile App Dev 3[2,1]), CS-443 (Network Arch 3), CS-444 (Knowledge Based Sys 3), CS-445 (Info Systems 3), CS-446 (Multimedia Comm 3), CS-448 (Network Mgmt 3), CS-451 (Social Computing 3), CS-452 (Game Dev 3[2,1]), CS-454 (Semantic Web 3), CS-455 (NLP 3), CS-456 (Web Services 3[2,1]), CS-457 (Web Frameworks 3[2,1]), CS-458 (Data Mining 3), CS-459 (Machine Learning 3), CS-462 (Cyber Security 3), CS-464 (Modeling & Simulation 3), CS-471 (Theory of Prog 3), CS-472 (Info Interfaces 3[2,1]), CS-473 (Multimedia Apps 3), CS-474 (Software Testing 3), CS-475 (Emerging Trends in SE 3), CS-476 (Enterprise Info Infra 3), CS-478 (Web Tech 3), CS-480 (Selected Topics 3), CS-482 (Web Eng 3), CS-483 (SQA 3), CS-484 (SE 3), CS-486 (SPM 3), CS-487 (Formal Methods 3), CS-488 (Software Entrepreneurship 3), CS-491 (Real Time Sys 3), CS-497 (Computing Case Studies 3)

---

## SCHEME 2023 (Superseded | Effective Fall 2023 Onwards)

**Total Credits:** 130  
**Category Breakdown:** GE: 30, CC: 46, DC: 18, DE: 21, MS: 12, ES: 3  
**Internship:** Mandatory 6-8 weeks

**Semester 1 (15 Cr.):**
- EN-100: Functional English (GE 3)
- PK-100: Ideology & Constitution of Pakistan (GE 2)
- MA-101: Calculus & Analytical Geometry (GE 3)
- CSC-110: Applications of ICT (GE 2+1)
- CSC-104: Problem Solving & Programming (CC 3+1)

**Semester 2 (17 Cr.):**
- EN-200: Expository Writing (GE 3)
- IS-100: Islamic Studies/Ethics (GE 2)
- Social Sciences Elective (GE 2)
- PH-110: Introductory Mechanics and Waves (GE 3)
- MA-202: Multivariable Calculus (MS 3)
- CSC-121: Object Oriented Programming (CC 3+1)

**Semester 3 (16 Cr.):**
- MA-203: Discrete Mathematics (GE 3)
- EN-2XX: Technical and Business Writing (MS 3)
- CSC-103: Introduction to Computer Org. (CC 3)
- CSC-211: Data Structures (CC 3+1)
- CSC-212: Human Computer Interaction (DC 3)

**Semester 4 (15 Cr.):**
- Civics and Community Engagement (GE 2)
- MA-302: Linear Algebra (MS 3)
- CSC-222: Analysis & Design of Software Systems (CC 3)
- CSC-224: Database Systems (CC 3+1)
- CSC-313: Computer Architecture (DC 3)

**Semester 5 (18 Cr.):**
- ST-101: Probability and Statistics (MS 3)
- CSC-322: Software Construction (DC 2+1)
- CSC-226: Operating Systems (CC 2+1)
- CSC-311: Analysis & Design of Algorithms (CC 3)
- CSC-414: Artificial Intelligence (CC 3)
- Domain Elective 1 (DE 3)

**Semester 6 (18 Cr.):**
- CSC-331: Theory of Automata (DC 3)
- CSC-325: Advanced Database Systems (DC 2+1)
- CSC-215: Computer Org. & Assembly Language (CC 2+1)
- CSC-312: Computer Communications & Networks (CC 3)
- Domain Elective 2 (DE 3)
- Domain Elective 3 (DE 3)

**Semester 7 (15 Cr.):**
- Entrepreneurship (GE 2)
- Arts and Humanities Elective (GE 2)
- CSC-411: Compiler Construction (DC 3)
- CSC-489: Project-I (CC 2)
- Domain Elective 4 (DE 3)
- Domain Elective 5 (DE 3)

**Semester 8 (16 Cr.):**
- Elective Supporting (ES 3)
- CSC-4XX: Introduction to Cyber Security (CC 3)
- CSC-490: Project-II (CC 4)
- Domain Elective 6 (DE 3)
- Domain Elective 7 (DE 3)

---

## SCHEME 2025 (CURRENT & ACTIVE | Effective Fall 2025 Onwards)

**Total Credits:** 134  
**Category Breakdown:** GE: 34, CC: 46, DC: 18, DE: 21, MS: 12, ES: 3  
**Internship:** Mandatory 6-8 weeks

**Semester 1 (16 Cr.):**
- EN-100: Functional English (GE 3)
- PK-100: Ideology & Constitution of Pakistan (GE 2)
- MA-101: Calculus & Analytical Geometry (GE 3)
- CSC-110: Applications of ICT (GE 2+1)
- FQ-101: Understanding Quran-I (GE 0+1)
- CSC-104: Problem Solving & Programming (CC 3+1)

**Semester 2 (18 Cr.):**
- EN-200: Expository Writing (GE 3)
- IS-100: Islamic Studies/Ethics (GE 2)
- Social Sciences Elective (GE 2)
- PH-110: Introductory Mechanics and Waves (GE 3)
- FQ-102: Understanding Quran-II (GE 0+1)
- MA-202: Multivariable Calculus (MS 3)
- CSC-121: Object Oriented Programming (CC 3+1)

**Semester 3 (16 Cr.):**
- MA-203: Discrete Mathematics (GE 3)
- EN-299: Technical and Business Writing (MS 3)
- CSC-103: Introduction to Computer Org. (CC 3)
- CSC-211: Data Structures (CC 3+1)
- CSC-212: Human Computer Interaction (DC 3)

**Semester 4 (17 Cr.):**
- SW-100: Civics and Community Engagement (GE 2)
- PS-101: Pakistan Studies (GE 2)
- MA-104: Fundamentals of Linear Algebra (MS 3)
- CSC-222: Analysis & Design of Software Systems (CC 3)
- CSC-224: Database Systems (CC 3+1)
- CSC-313: Computer Architecture (DC 3)

**Semester 5 (18 Cr.):**
- ST-101: Probability and Statistics (MS 3)
- CSC-322: Software Construction (DC 2+1)
- CSC-226: Operating Systems (CC 2+1)
- CSC-311: Analysis & Design of Algorithms (CC 3)
- CSC-414: Artificial Intelligence (CC 3)
- Domain Elective 1 (DE 3)

**Semester 6 (18 Cr.):**
- CSC-331: Theory of Automata (DC 3)
- CSC-325: Advanced Database Systems (DC 2+1)
- CSC-215: Computer Org. & Assembly Language (CC 2+1)
- CSC-312: Computer Communications & Networks (CC 3)
- Domain Elective 2 (DE 3)
- Domain Elective 3 (DE 3)

**Semester 7 (15 Cr.):**
- MS-100: Entrepreneurship (GE 2)
- Arts and Humanities Elective (GE 2)
- CSC-411: Compiler Construction (DC 3)
- CSC-489: Project-I (CC 2)
- Domain Elective 4 (DE 3)
- Domain Elective 5 (DE 3)

**Semester 8 (16 Cr.):**
- Elective Supporting (ES 3)
- CSC-412: Introduction to Cyber Security (CC 3)
- CSC-490: Project-II (CC 4)
- Domain Elective 6 (DE 3)
- Domain Elective 7 (DE 3)

# ======================================================================
# SCHEME QUERY HANDLING RULES (CRITICAL)
# ======================================================================

1. **Default to Scheme 2025:** When a user asks a general question without specifying a year (e.g., "What are my semester 1 courses?"), answer based on **Scheme 2025 (Current)** and explicitly state: "Based on the current Scheme 2025..."

2. **Direct Scheme Queries:** When user asks "scheme 2021", "scheme 2023", or "scheme 2025", immediately provide the complete semester-by-semester breakdown from the embedded knowledge base above.

3. **Never Claim Missing Information:** You have ALL three schemes embedded above. NEVER state that you don't have access to scheme information or that the context doesn't contain scheme data.

4. **Hybrid Fallback:** If retrieved context from vector search is empty or doesn't contain scheme information, ALWAYS fall back to the embedded scheme knowledge base above rather than stating "information not found".

5. **Exact Formatting:** Always preserve exact course codes (CS-105, CSC-104, etc.), credit hours with splits (3+1, 2+1, 0+1), and category labels (GE, CC, DC, DE, MS, ES).

6. **Output Format:** Use Markdown tables for semester course lists:
   | Course Code | Course Title | Category | Credit Hours |

# ======================================================================
# QAU UNDERGRADUATE ADMISSIONS (FALL 2026) — OFFICIAL GROUND TRUTH
# ======================================================================

## 1. APPLICATION DEADLINES:

• **BS / LLB Programmes:** 10/08/2026
• **Pharm-D Programme:** 22/09/2026
• **Application Mode:** Strictly Online via QAU website (qau.edu.pk). NO manual/by-hand/post submissions accepted.
• **Application Processing Fee:** Rs. 2,860/- via Kuickpay or 1-Bill (receipt upload mandatory).
• **Contact Email for Queries:** admissions2026fall@qau.edu.pk

## 2. MERIT FORMULAS:

• **BS Programmes:** 70% HSSC (FA/FSc) Part-I or Equivalent + 30% SSC (Matric)
• **LLB (5-Year) Programme:** 50% HSSC Part-I + 30% HEC LAT Score + 20% SSC (Matric)
  - Requires: Minimum 50% marks in FA/FSc & minimum 50 score in LAT
• **Pharm-D Programme:** 70% Complete HSSC Result + 30% SSC (Matric)
  - Requires: Complete FSc Pre-Medical with minimum 60% marks

## 3. PROGRAMME-WISE ELIGIBILITY (Minimum 50% required in HSSC Part-I unless stated):

### Natural Sciences:
- **BS Computer Science:** FA/FSc or equivalent with Mathematics, OR Pre-Medical with Additional Mathematics
- **BS Information Technology:** FSc or equivalent with Physics and Mathematics
- **BS Chemistry:** FSc (Pre-Engineering/Medical) or equivalent with Chemistry
- **BS Electronics:** FSc or equivalent with Mathematics and Physics
- **BS Geophysics:** FSc (Pre-Eng/Pre-Med/other groups with at least 1 science subject) or DAE
- **BS Mathematics:** FSc or equivalent with Mathematics
- **BS Physics:** FA/FSc/A-Level or equivalent with Physics
- **BS Statistics:** FSc/ICS or FA with Statistics or Mathematics

### Biological Sciences:
- **BS Biochemistry:** FSc/A-Level with Biology & Chemistry, or FSc Pre-Medical
- **BS Biotechnology, Bioinformatics, Botany, Environmental Sciences, Microbiology:** FSc (Pre-Engineering/Medical) or equivalent
- **BS Zoology:** FSc (Pre-Medical) or equivalent
- **Pharm-D:** Complete passed result of FSc Pre-Medical or equivalent with at least 60% marks

### Social Sciences:
- **BS Anthropology, Tourism & Hospitality, Archaeology, Business Administration (BSBA/BBA), Defence & Strategic Studies, Economics, English, History, International Relations, Political Science, Public Administration, Pakistan Studies, Psychology, Sociology, Social Work, Gender Studies:** FA/FSc or equivalent
- **LLB:** FA/FSc or equivalent with minimum 50% marks & valid HEC LAT with minimum 50 marks
- **BS Governance & Policy Studies:** FA/FSc/ICS/I.Com/DAE/A-Levels or equivalent with minimum 50% marks

## 4. MERIT LIST DISPLAY SCHEDULE:

### BS / LLB Programmes:
- **1st Merit List:** 15-08-2026
- **2nd Merit List:** 19-08-2026
- **3rd Merit List (if required):** 23-08-2026

### Pharm-D Programme:
- **1st Merit List:** 27-09-2026
- **2nd Merit List:** 02-10-2026
- **3rd Merit List (if required):** 05-10-2026

## 5. KEY RULES & POLICIES:

### Subject Options:
- Maximum 3 subjects Regular (R) + 3 subjects Self-Finance (S) = 6 total choices
- **CRITICAL:** Selecting/depositing fees on regular seat locks ALL other choices

### Age Limit:
- **NO age limit** for BS / LLB / Pharm-D admissions

### Result-Awaiting / Part-I Policy:
- Candidates can apply on Part-I basis for BS/LLB
- Must score ≥50% in complete HSSC and submit result within 45 days of board announcement
- Failure/less than 50% cancels admission WITHOUT fee refund

### Ineligibility:
- Prior BS/LLB/Pharm-D degree holders
- Already enrolled QAU students
- Expelled students
- Failed students under QAU rules

### Reserved Quotas:
- Children of Army Personnel (GHQ nomination, 1/dept)
- Disabled Persons (1/dept based on disability level)
- Minorities (1/dept)
- Sports (2% university-wide, max 1/dept)
- Foreign Students (10% self-finance)
- Martyr's Children (1/dept)
- Children of Registered Pharmacists (up to 5% in Pharm-D)
- Children of Pharma Industry Proprietors (2% self-finance)
- Children of Advocates (5% in LLB)
- Overseas Pakistanis (up to 5%)
- GB/Balochistan/Sindh(R) additional Pharm-D seats (15 seats: 5 each region)

### Scholarships & Financial Aid:
- 25+ scholarship schemes available (PEEF, BEEF, HEC, PPL, Bait-ul-Mal, etc.)
- Special consideration for orphans and remote areas
- **CRITICAL NOTE:** Students admitted on Self-Finance Basis are **NOT eligible** for scholarships

### Hostel:
- Subject to seat availability

## 7. FEE STRUCTURE (FALL 2025 - NATIONAL STUDENTS):

### BS Computer Science / BS Information Technology / LLB (5-Year):
- **Regular Basis (per semester):** Rs. 96,320/-
- **Self-Finance/Evening (per semester):** Rs. 165,230/-

### BS Pharmacy (Pharm-D):
- **Regular Basis (per semester):** Rs. 95,320/-
- **Self-Finance (per semester):** Rs. 164,230/-

### BS Other Programmes (Public Administration, etc.):
- **Regular Basis (per semester):** Rs. 90,580/-
- **Self-Finance/Evening (per semester):** Rs. 141,120/-

### QASMS Business Administration, English, SP&IR:
- **Regular Basis (per semester):** Rs. 93,320/-
- **Self-Finance/Evening (per semester):** Rs. 162,230/-

### One-Time Fees (All Programmes):
- **Admission Processing Fee:** Rs. 2,860/-
- **Security Deposit (Refundable):** Rs. 5,000/-
- **Prospectus Fee:** Rs. 500/-
- **Student Activity Fee:** Rs. 2,000/-
- **Medical Fee:** Rs. 1,000/-

### Additional Fees:
- **Fee for Non-Credit Course (per course):** Rs. 2,830/-
- **Re-examination Fee:** As applicable
- **Degree Fee (20 working days):** Rs. 6,300/-
- **Urgent Degree Fee (5 working days):** Rs. 12,590/-
- **Duplicate Degree Fee:** Rs. 12,590/-
- **Migration Certificate Fee:** Rs. 3,780/-
- **Grade Card/Result Card (20 working days):** Rs. 630/-
- **Verification Fee:** Rs. 1,890/-
- **Degree Folder Fee:** Rs. 630/-

### Important Notes on Fees:
1. **Semester fees are for Category A + B** (tuition, library, lab, etc.)
2. **One-time fees (Category C)** paid only at admission
3. **Self-Finance students pay higher fees** (~70% more than Regular)
4. **Summer course fee:** Rs. 9,880/- per course
5. **Evening Program (Open Merit):** Rs. 10,760/- per course
6. **Fees are subject to change** - verify with university before admission

### Fee Query Handling Rules:
1. Always specify both Regular and Self-Finance fees
2. Mention that fees are per semester
3. Clarify one-time admission fees separately
4. For CS/IT specifically, quote Rs. 96,320/- (Regular) or Rs. 165,230/- (Self-Finance)
5. Always add: "These are Fall 2025 semester fees for national students. Contact admissions for latest fee structure."

## 6. ADMISSION QUERY HANDLING RULES:

1. **Always use Fall 2026 data** unless user specifies a different year
2. **Provide exact dates and deadlines** as listed above
3. **Clarify merit formula** based on programme type (BS/LLB/Pharm-D)
4. **For CS/IT queries:** Emphasize Mathematics requirement for BS CS, Physics+Math for BS IT
5. **For eligibility questions:** Match the programme to the correct subject group
6. **For scholarship questions:** Always mention the Self-Finance restriction
7. **Never hallucinate dates or requirements** - use only the information above

# CRITICAL LANGUAGE RULE - YOU MUST FOLLOW THIS:
- If user writes in English → YOU MUST respond ONLY in English
- If user writes in Roman Urdu (e.g., "kya", "mujhe", "batao", "hai") → YOU MUST respond ONLY in Roman Urdu (NOT English, NOT Urdu script)
- If user writes in Urdu script (اردو) → YOU MUST respond ONLY in Urdu script (NOT English, NOT Roman Urdu)

NEVER mix languages in your response. Match the user's language EXACTLY.

# TIMETABLE QUERIES - CRITICAL ACCURACY RULES:

You are the **Official Time Table Assistant for QAU CS Department, Spring 2026**. Your responses must be **100% accurate with ZERO hallucinations**.

## Data Structure Understanding (CRITICAL):
The timetable database uses a **matrix structure**: Day → Room → Time → Course → Section (R=Regular, S=Self-Support) → Instructor

**Available Days:** MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY
**Available Rooms:** 201, 217, 235, F8, F6, CS Lab, BS Lab
**Time Slots:** 08:35-10:05, 10:15-11:45, 11:55-13:25, 13:35-15:05, 15:15-16:45, 17:00-18:30, 18:30-20:00
**Sections:** Regular (R) vs Self-Support (S)

## STRICT RESPONSE RULES:

1. **NO MIXING/HALLUCINATIONS**: Never combine a room from one data row with a time slot from another. Each timetable entry is a FIXED combination of Day+Room+Time+Course+Section+Instructor. DO NOT create new combinations.

2. **EXACT MATCHING**: Only output information that exists in the provided structured data. If a field is missing, say "Not specified" or "TBA" - DO NOT guess.

3. **CODE VALIDATION**: Match course codes to their correct full titles:
   - CS-224 = Database Systems (BS Semester IV)
   - CS-226 = Analysis and Design of Software Systems (BS Semester IV)
   - CS-311 = Operating Systems (BS Semester VI)
   - CS-312 = Computer Communications and Networks (BS Semester VI)
   - CS-425 = Computer Vision (BS Semester VIII)
   Always verify the course code matches the provided data.

4. **MARKDOWN TABLE FORMAT** (MANDATORY for timetable queries):
| **Course Code** | **Course Title** | **Timing** | **Room** | **Section** | **Instructor** |
|-----------------|------------------|------------|----------|-------------|----------------|
| CS-224 | Database Systems | 10:15 - 11:45 | 217 | Self-Support | Dr. Shuaib Karim / Ms. Fouzia Qureshi |

5. **When NO classes**: If the requested day/semester has no entries in the data, respond: "No classes scheduled for [Day] in [Semester] semester."

6. **Verification Protocol**: Before outputting each row:
   - ✓ Does this exact Day+Room+Time+Course combination exist in the data?
   - ✓ Is the section (Regular/Self-Support) correctly matched?
   - ✓ Is the instructor name from the actual data?
   
7. **Direct Output**: Provide immediate, structured answers. Use tables for schedules to ensure scannability.

# FYP & THESIS SUBMISSION PROCESS - GROUND TRUTH:

When answering questions about FYP or thesis submission, follow this verified sequence strictly:

## 1. Report Preparation & Formatting:
- Students must format their final project report or thesis according to official QAU CS department guidelines
- **Using the official Quaid-i-Azam University LaTeX/Overleaf thesis template is highly recommended** for standard compliance
- Bold key requirements when mentioning them

## 2. Supervisor Evaluation & Clearance:
- The complete draft must undergo an **internal review by the assigned project supervisor**
- The supervisor must run a **plagiarism check (via Turnitin)** to ensure compliance with HEC similarity limits
- The supervisor must **physically or digitally sign off on the approval/clearance sheet** before any public evaluation can be scheduled

## 3. Public Seminar & Live Demonstration:
- Defending the project requires a **mandatory public seminar presentation**
- Students must conduct a **live, running software/application demonstration**
- Evaluation is conducted collectively by a panel consisting of:
  * **The External Examiner**
  * **The Internal Project Supervisor**
  * **The Chairman of the CS Department**

## 4. Final Documentation & Hand-in:
- Upon passing the defense and incorporating required revisions, students must **print official hardbound copies**
- Hardbound copies must contain **original signature sheets** (signed by external examiner, supervisor, and chairman)
- Final submission requires depositing the **approved bound hard copies and digital source code/assets** to the CS departmental office

# Response Guidelines & Constraints:

- **Direct Answer First**: Start your response with a direct, clear answer to the user's specific question. Bold key entities, roles, and major requirements immediately
- **Grounding**: Do not invent deadlines, fee structures, or specific faculty names unless explicitly provided in the retrieved context. If information is missing, politely state that the user should verify it with the CS Departmental Office
- **Tone**: Maintain a professional, peer-like, and highly supportive academic tone. Avoid rigid or robotic phrasing
- **Strict Constraints**: If a user asks about programs outside of CS (e.g., Management Sciences or Chemistry), gently redirect them, stating your expertise is strictly limited to the Department of Computer Sciences at QAU
- **Format responses clearly** with bullet points, numbered lists, and markdown tables where appropriate
- **Professional yet approachable**: Be helpful and friendly while maintaining academic professionalism

# Your Core Responsibilities:
- Provide accurate information about CS programs, courses, faculty, admissions, fees, policies, and schedules
- Guide students through FYP/thesis submission processes step-by-step
- Use information from the provided knowledge base
- Present timetables in professional table format
- If you don't have specific information, say so clearly and direct to official sources
- For deadlines and dates, emphasize checking official departmental announcements

Always maintain academic professionalism while being approachable and helpful."""
    
    def get_system_prompt(self, language: str = "en") -> str:
        """
        Get system prompt with dynamic knowledge injection.
        
        If db_session is available, fetches active knowledge from knowledge_base table.
        Otherwise, falls back to embedded knowledge in base_system_prompt.
        
        Args:
            language: Target language code ('en', 'ur', etc.)
            
        Returns:
            Complete system prompt with injected/embedded knowledge
        """
        if self.db_session is None:
            logger.debug("No database session - using embedded fallback knowledge")
            return self.base_system_prompt
        
        try:
            from app.response.knowledge_loader import get_dynamic_system_prompt
            
            # Normalize language code: 'english' -> 'en', 'urdu' -> 'ur'
            lang_map = {
                'english': 'en',
                'urdu': 'ur',
                'roman_urdu': 'en',  # Use English content for Roman Urdu
            }
            normalized_lang = lang_map.get(language.lower(), language[:2].lower())
            
            # Attempt to load dynamic knowledge from database
            dynamic_prompt = get_dynamic_system_prompt(
                db=self.db_session,
                base_prompt=self.base_system_prompt,
                language=normalized_lang,  # Use normalized language code
                use_fallback=True  # Always allow embedded fallback
            )
            
            return dynamic_prompt
            
        except Exception as e:
            logger.error(f"Error loading dynamic knowledge, using embedded fallback: {e}")
            return self.base_system_prompt
    
    def detect_language(self, query: str) -> str:
        """Detect if query is English, Roman Urdu, or Urdu."""
        # Check for Urdu script (Arabic/Persian characters)
        urdu_chars = any('\u0600' <= c <= '\u06FF' or '\uFB50' <= c <= '\uFDFF' for c in query)
        
        if urdu_chars:
            return "urdu"
        
        # Check for Roman Urdu keywords
        roman_urdu_keywords = [
            'kya', 'hai', 'mujhe', 'batao', 'btao', 'kab', 'kahan', 'kaise', 
            'aur', 'ka', 'ki', 'ko', 'se', 'me', 'mein', 'par', 'ke',
            'courses', 'faculty', 'admission', 'fees', 'kis', 'kon',
            'kitne', 'kitna', 'kaunsa', 'kaunse'
        ]
        
        query_lower = query.lower()
        if any(keyword in query_lower.split() for keyword in roman_urdu_keywords):
            return "roman_urdu"
        
        return "english"
    
    def build_context(
        self,
        intent: str,
        search_results: list[SearchResult] | None = None,
        structured_data: dict | None = None,
        entities: dict | None = None,
        query: str | None = None
    ) -> str:
        """Build context from available information."""
        context_parts = []
        
        context_parts.append(f"User Intent: {intent}")
        
        if entities:
            context_parts.append(f"Extracted Entities: {json.dumps(entities, ensure_ascii=False)}")
        
        # Prioritize timetable structured data
        if structured_data and intent == 'timetable_query':
            context_parts.append("\n=== OFFICIAL TIMETABLE DATA (Spring 2026) - USE EXACTLY AS PROVIDED ===")
            context_parts.append("⚠️ CRITICAL: Each entry below is a FIXED combination. DO NOT mix data from different rows.")
            context_parts.append("⚠️ ONLY output data that appears in this exact format below:")
            context_parts.append(json.dumps(structured_data, indent=2, ensure_ascii=False))
            context_parts.append("=== END OF TIMETABLE DATA ===\n")
        elif structured_data:
            context_parts.append("\nStructured Data from Database:")
            context_parts.append(json.dumps(structured_data, indent=2, ensure_ascii=False))
        
        if search_results:
            context_parts.append("\nRelevant Knowledge Base Content:")
            for i, result in enumerate(search_results[:5], 1):
                category = result.metadata.get('category', 'general')
                title = result.metadata.get('title', f'Document {i}')
                context_parts.append(f"\n[Source {i} - {category}] {title}")
                context_parts.append(result.content[:500])
        
        return '\n'.join(context_parts)
    
    def generate_response(
        self,
        query: str,
        intent: str,
        language: str | None = None,
        search_results: list[SearchResult] | None = None,
        structured_data: dict | None = None,
        entities: dict | None = None,
        chat_history: list[dict] | None = None
    ) -> str:
        """
        Generate intelligent response using LLM.
        
        Args:
            query: User's original query
            intent: Detected intent
            language: Detected language (english, roman_urdu, urdu)
            search_results: Hybrid search results
            structured_data: Structured data from database
            entities: Extracted entities
            chat_history: Previous conversational turns
            
        Returns:
            Generated response
        """
        # Detect language if not provided
        if not language:
            language = self.detect_language(query)
        
        logger.info(f"Generating response for intent={intent}, language={language}")
        
        # Build context from available information
        context = self.build_context(intent, search_results, structured_data, entities, query)
        
        # Build prompt
        language_instruction = {
            'english': '\n\n🔴 MANDATORY LANGUAGE RULE: You MUST respond COMPLETELY in English. Do NOT use Roman Urdu or Urdu script. If you respond in any other language, the response will be rejected.',
            'roman_urdu': '\n\n🔴 MANDATORY LANGUAGE RULE: You MUST respond COMPLETELY in Roman Urdu (Urdu words written with English alphabet). Do NOT write in English or Urdu script (اردو). Example Roman Urdu response: "Monday ko 6th semester mein 2 classes hain. Pehli class CS-425 Computer Vision hai jo 08:35 se 10:05 tak hai." If you respond in English or Urdu script, the response will be REJECTED.',
            'urdu': '\n\n🔴 MANDATORY LANGUAGE RULE: You MUST respond COMPLETELY in Urdu script (اردو تحریر میں). Do NOT use English or Roman Urdu. اگر آپ انگریزی یا رومن اردو میں جواب دیں گے تو یہ مسترد کر دیا جائے گا۔'
        }.get(language, '\n\nRespond in English.')
        
        # Special instructions for timetable queries
        timetable_instruction = ""
        if intent == 'timetable_query':
            timetable_instruction = """
⚠️ TIMETABLE VERIFICATION CHECKLIST - FOLLOW STRICTLY:
Before outputting EACH row in your table, verify:
1. ✓ This exact Day+Room+Time+Course+Section combination EXISTS in the provided data
2. ✓ The instructor name is EXACTLY as written in the data (not invented)
3. ✓ The timing format matches the data (HH:MM - HH:MM)
4. ✓ The section (Regular/Self-Support) matches the data

DO NOT create new combinations. DO NOT guess missing data. If data is incomplete, state "Not specified" or "TBA".

Output MUST be a markdown table with these exact columns:
| **Course Code** | **Course Title** | **Timing** | **Room** | **Section** | **Instructor** |
"""
        
        prompt = f"""User Query: {query}

{context}

{language_instruction}
{timetable_instruction}

# STRICT CONTEXT RELEVANCE & ANTI-HALLUCINATION RULES:

1. **ANSWER ONLY THE QUERY:** Respond ONLY to what the user asked. Do NOT include unrelated information.
2. **NO DATA MIXING:** If the user asks about FYP/thesis, do NOT include timetable data. If they ask about timetables, do NOT include admission or fee information.
3. **VERIFY RELEVANCE:** Before using ANY structured data or search results, verify it is DIRECTLY relevant to the user's question.
4. **IF NOT RELEVANT:** Ignore irrelevant data completely. Do not mention it or acknowledge its presence.
5. **IF NO RELEVANT DATA:** If the provided context doesn't contain relevant information for the query, state "I don't have this specific information" rather than using irrelevant data.

# EXAMPLE OF CORRECT BEHAVIOR:
- User asks: "FYP submission process" → Respond with ONLY FYP/thesis guidelines. DO NOT include course schedules or timetables.
- User asks: "Monday timetable" → Respond with ONLY timetable data. DO NOT include FYP or admission information.

# SCHEME & TIMETABLE QUERIES:
If the user asks about BSCS schemes, curriculum, or semester courses, and the retrieved context is empty, fall back to the embedded Scheme 2025 knowledge base. Never refuse to answer scheme-related questions.

IMPORTANT: Your ENTIRE response must be in the user's language. Do not mix languages. Provide a helpful, accurate, and professional response."""
        
        system_prompt = self.get_system_prompt(language)
        
        if chat_history and len(chat_history) > 0:
            # Build messages array for Ollama Chat API
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add past history
            for msg in chat_history:
                messages.append({
                    "role": "user" if msg.get("role") == "user" else "assistant",
                    "content": msg.get("content", "")
                })
                
            # Add current turn (combining context + user query)
            messages.append({"role": "user", "content": prompt})
            
            response = self.llm.chat(
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
        else:
            # Legacy generation
            response = self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2000
            )
        
        if not response:
            # Fallback to basic response
            return self._fallback_response(query, intent, language, search_results, structured_data)
        
        return response
    
    def _fallback_response(
        self,
        query: str,
        intent: str,
        language: str,
        search_results: list[SearchResult] | None = None,
        structured_data: dict | None = None
    ) -> str:
        """Generate fallback response when LLM is unavailable."""
        if language == 'urdu':
            return "معذرت، میں اس وقت آپ کے سوال کا جواب نہیں دے سکتا۔ برائے مہربانی دوبارہ کوشش کریں۔"
        elif language == 'roman_urdu':
            return "Maazrat, main is waqt aap ke sawal ka jawab nahi de sakta. Meherbani karke dobara koshish karein."
        else:
            return "I apologize, but I'm unable to generate a response at the moment. Please try again."
    
    def generate_faculty_response(
        self,
        query: str,
        faculty_data: dict,
        research_interests: list[dict] | None = None,
        language: str | None = None,
        chat_history: list[dict] | None = None
    ) -> str:
        """Generate response for faculty queries."""
        structured_data = {
            'faculty': faculty_data,
            'research_interests': research_interests or []
        }
        
        return self.generate_response(
            query=query,
            intent='faculty_information',
            language=language,
            structured_data=structured_data,
            chat_history=chat_history
        )
    
    def generate_course_response(
        self,
        query: str,
        course_data: dict,
        language: str | None = None,
        chat_history: list[dict] | None = None
    ) -> str:
        """Generate response for course queries."""
        return self.generate_response(
            query=query,
            intent='course_query',
            language=language,
            structured_data={'course': course_data},
            chat_history=chat_history
        )
    
    def generate_admission_response(
        self,
        query: str,
        program_data: dict | None = None,
        search_results: list[SearchResult] | None = None,
        language: str | None = None,
        chat_history: list[dict] | None = None
    ) -> str:
        """Generate response for admission queries."""
        structured_data = {'program': program_data} if program_data else None
        
        return self.generate_response(
            query=query,
            intent='admission_information',
            language=language,
            search_results=search_results,
            structured_data=structured_data,
            chat_history=chat_history
        )
    
    def generate_general_response(
        self,
        query: str,
        intent: str,
        search_results: list[SearchResult] | None = None,
        entities: dict | None = None,
        language: str | None = None,
        chat_history: list[dict] | None = None
    ) -> str:
        """Generate response for general queries."""
        return self.generate_response(
            query=query,
            intent=intent,
            language=language,
            search_results=search_results,
            entities=entities,
            chat_history=chat_history
        )
    
    def generate_scheme_response(
        self,
        query: str,
        scheme_year: str = "2025",
        language: str | None = None
    ) -> str:
        """
        Generate response for BSCS scheme queries using embedded knowledge.
        
        This method provides direct access to embedded scheme data,
        bypassing vector search entirely for maximum accuracy.
        
        Args:
            query: User's original query
            scheme_year: Scheme year (2021, 2023, or 2025)
            language: Detected language
            
        Returns:
            Complete scheme breakdown
        """
        # Detect language if not provided
        if not language:
            language = self.detect_language(query)
        
        logger.info(f"Generating scheme response for year={scheme_year}, language={language}")
        
        # Build language-specific instruction
        language_instruction = {
            'english': 'You MUST respond COMPLETELY in English.',
            'roman_urdu': 'You MUST respond COMPLETELY in Roman Urdu (Urdu words written with English alphabet).',
            'urdu': 'You MUST respond COMPLETELY in Urdu script (اردو تحریر میں).'
        }.get(language, 'Respond in English.')
        
        # Build explicit prompt for scheme query
        scheme_prompt = f"""USER QUERY: {query}

TASK: Provide the complete BSCS Scheme {scheme_year} breakdown.

INSTRUCTIONS:
1. You have the complete Scheme {scheme_year} embedded in your system instructions
2. Extract and present ALL 8 semesters with their courses
3. For each course, include:
   - Course Code (exact format: CS-105, CSC-104, etc.)
   - Course Title
   - Credit Hours (including splits like 3+1, 2+1, 0+1)
   - Category (GE, CC, DC, DE, MS, ES for 2023/2025)
4. Include total credit hours for the degree
5. Mention any special requirements (internship, electives pool)

FORMAT: Use clear Markdown formatting with:
- Headers for each semester (## Semester 1, ## Semester 2, etc.)
- Bullet points or tables for course lists
- Bold for important information

LANGUAGE: {language_instruction}

DO NOT state that information is missing. You have the complete scheme embedded. Provide the full semester-by-semester breakdown now."""
        
        # Generate response with lower temperature for factual accuracy
        system_prompt = self.get_system_prompt(language)
        response = self.llm.generate(
            prompt=scheme_prompt,
            system_prompt=system_prompt,
            temperature=0.2,  # Very low temperature for maximum factual accuracy
            max_tokens=3500   # Allow longer response for complete scheme
        )
        
        if not response:
            # Fallback with basic scheme info
            if language == 'urdu':
                return f"Scheme {scheme_year} ki tafseel uplabdh hai. Meherbani karke dobara koshish karein."
            elif language == 'roman_urdu':
                return f"Scheme {scheme_year} ki details available hain. Dobara try karein."
            else:
                return f"BSCS Scheme {scheme_year} information is available in the system. Please try again."
        
        return response


# Global instance
_intelligent_generator: IntelligentResponseGenerator | None = None


def reset_intelligent_generator():
    """Reset the global generator instance (for testing or model changes)."""
    global _intelligent_generator
    _intelligent_generator = None
    logger.info("Reset global IntelligentResponseGenerator instance")


def get_intelligent_generator(model: str = "llama3.2:3b", db_session=None) -> IntelligentResponseGenerator:
    """
    Get cached IntelligentResponseGenerator instance.
    
    Args:
        model: LLM model name
        db_session: Optional database session for dynamic knowledge loading
        
    Returns:
        IntelligentResponseGenerator instance
        
    Note:
        The global cache does NOT store db_session. Each call with a db_session
        creates a new instance with dynamic knowledge capability.
    """
    global _intelligent_generator
    
    # If db_session provided, always create new instance for dynamic knowledge
    if db_session is not None:
        return IntelligentResponseGenerator(model=model, db_session=db_session)
    
    # Otherwise use cached global instance (no dynamic knowledge)
    if _intelligent_generator is None:
        _intelligent_generator = IntelligentResponseGenerator(model=model)
    
    return _intelligent_generator

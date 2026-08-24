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
    
    def __init__(self, model: str = "qwen3:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.generate_url = f"{base_url}/api/generate"
    
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """Generate response from Ollama."""
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
                timeout=60
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


class IntelligentResponseGenerator:
    """Generates intelligent, context-aware responses using LLM."""
    
    def __init__(self, model: str = "qwen3:8b"):
        self.llm = OllamaLLM(model=model)
        
        # System prompt for QAU CS Academic Advisor
        self.system_prompt = """# Role and Context

You are an expert academic assistant for the Department of Computer Sciences at Quaid-i-Azam University (QAU), Islamabad. Your primary objective is to assist BS, MSc, MPhil, and PhD students with all queries regarding their academic journey including Final Year Project (FYP), thesis submission, courses, timetables, faculty, admissions, fees, and departmental policies.

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
        
        # Add CS website data if query provided
        if query:
            cs_pages = search_cs_website(query, top_k=3)
            if cs_pages:
                context_parts.append("\nAdditional Context from CS Department Website:")
                for i, page in enumerate(cs_pages, 1):
                    context_parts.append(f"\n[CS Website Page {i}] {page['title']}")
                    context_parts.append(page['content'][:800])
        
        return '\n'.join(context_parts)
    
    def generate_response(
        self,
        query: str,
        intent: str,
        language: str | None = None,
        search_results: list[SearchResult] | None = None,
        structured_data: dict | None = None,
        entities: dict | None = None
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

IMPORTANT: Your ENTIRE response must be in the user's language. Do not mix languages. Provide a helpful, accurate response based on the above information. If the knowledge base doesn't contain specific information, acknowledge this and provide general guidance."""
        
        # Generate response
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=self.system_prompt,
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
        language: str | None = None
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
            structured_data=structured_data
        )
    
    def generate_course_response(
        self,
        query: str,
        course_data: dict,
        language: str | None = None
    ) -> str:
        """Generate response for course queries."""
        return self.generate_response(
            query=query,
            intent='course_query',
            language=language,
            structured_data={'course': course_data}
        )
    
    def generate_admission_response(
        self,
        query: str,
        program_data: dict | None = None,
        search_results: list[SearchResult] | None = None,
        language: str | None = None
    ) -> str:
        """Generate response for admission queries."""
        structured_data = {'program': program_data} if program_data else None
        
        return self.generate_response(
            query=query,
            intent='admission_information',
            language=language,
            search_results=search_results,
            structured_data=structured_data
        )
    
    def generate_general_response(
        self,
        query: str,
        intent: str,
        search_results: list[SearchResult] | None = None,
        entities: dict | None = None,
        language: str | None = None
    ) -> str:
        """Generate response for general queries."""
        return self.generate_response(
            query=query,
            intent=intent,
            language=language,
            search_results=search_results,
            entities=entities
        )


# Global instance
_intelligent_generator: IntelligentResponseGenerator | None = None


def get_intelligent_generator(model: str = "qwen3:8b") -> IntelligentResponseGenerator:
    """Get cached IntelligentResponseGenerator instance."""
    global _intelligent_generator
    
    if _intelligent_generator is None:
        _intelligent_generator = IntelligentResponseGenerator(model=model)
    
    return _intelligent_generator

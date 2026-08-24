"""
Response generation and formatting module.

Generates natural language responses from search results, aggregates
multi-source information, and adds citations.
"""

import logging
from typing import Any

from app.rag.hybrid_search import SearchResult

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Formats responses with citations and structure."""
    
    @staticmethod
    def format_faculty_response(faculty_data: dict, research_data: list[dict] | None = None) -> str:
        """Format faculty information response."""
        response_parts = []
        
        # Basic info
        response_parts.append(f"**{faculty_data.get('full_name', 'Faculty Member')}**")
        
        if faculty_data.get('title'):
            response_parts.append(f"Title: {faculty_data['title']}")
        
        if faculty_data.get('office_location'):
            response_parts.append(f"Office: {faculty_data['office_location']}")
        
        if faculty_data.get('email'):
            response_parts.append(f"Email: {faculty_data['email']}")
        
        if faculty_data.get('phone'):
            response_parts.append(f"Phone: {faculty_data['phone']}")
        
        # Research interests
        if research_data:
            response_parts.append("\n**Research Interests:**")
            for interest in research_data:
                response_parts.append(f"- {interest.get('name', 'N/A')}")
        
        return '\n'.join(response_parts)
    
    @staticmethod
    def format_search_results(results: list[SearchResult], max_results: int = 3) -> str:
        """Format hybrid search results into readable text."""
        if not results:
            return "No relevant information found."
        
        response_parts = []
        
        for i, result in enumerate(results[:max_results], 1):
            # Add document title if available
            title = result.metadata.get('title', 'Document')
            category = result.metadata.get('category', 'general')
            
            response_parts.append(f"\n**Source {i}: {title}** (Category: {category})")
            response_parts.append(result.content[:300] + "..." if len(result.content) > 300 else result.content)
        
        return '\n'.join(response_parts)
    
    @staticmethod
    def format_course_info(course_data: dict) -> str:
        """Format course information response."""
        response_parts = []
        
        response_parts.append(f"**{course_data.get('code', 'N/A')}: {course_data.get('title', 'N/A')}**")
        
        if course_data.get('credit_hours'):
            response_parts.append(f"Credit Hours: {course_data['credit_hours']}")
        
        if course_data.get('description'):
            response_parts.append(f"\n{course_data['description']}")
        
        if course_data.get('prerequisites'):
            prereqs = ', '.join(course_data['prerequisites'])
            response_parts.append(f"\nPrerequisites: {prereqs}")
        
        return '\n'.join(response_parts)
    
    @staticmethod
    def format_news(news_list: list[dict], max_items: int = 5) -> str:
        """Format news articles."""
        if not news_list:
            return "No recent news available."
        
        response_parts = ["**Latest News:**\n"]
        
        for i, news in enumerate(news_list[:max_items], 1):
            title = news.get('title', 'Untitled')
            published_date = news.get('published_date', 'Date unknown')
            response_parts.append(f"{i}. **{title}** ({published_date})")
            
            if news.get('summary'):
                response_parts.append(f"   {news['summary'][:150]}...")
        
        return '\n'.join(response_parts)
    
    @staticmethod
    def format_events(events_list: list[dict], max_items: int = 5) -> str:
        """Format events."""
        if not events_list:
            return "No upcoming events."
        
        response_parts = ["**Upcoming Events:**\n"]
        
        for i, event in enumerate(events_list[:max_items], 1):
            title = event.get('title', 'Untitled')
            event_date = event.get('event_date', 'Date TBA')
            location = event.get('location', '')
            
            response_parts.append(f"{i}. **{title}**")
            response_parts.append(f"   Date: {event_date}")
            if location:
                response_parts.append(f"   Location: {location}")
        
        return '\n'.join(response_parts)
    
    @staticmethod
    def add_citations(response: str, sources: list[dict]) -> str:
        """Add citations to response."""
        if not sources:
            return response
        
        citations = ["\n\n**Sources:**"]
        
        for i, source in enumerate(sources, 1):
            title = source.get('title', f'Source {i}')
            url = source.get('url', '')
            
            if url:
                citations.append(f"{i}. [{title}]({url})")
            else:
                citations.append(f"{i}. {title}")
        
        return response + '\n'.join(citations)


class ResponseGenerator:
    """Generates complete responses with intelligence and formatting."""
    
    def __init__(self):
        self.formatter = ResponseFormatter()
    
    def generate(
        self,
        intent: str,
        search_results: list[SearchResult] | None = None,
        structured_data: dict | None = None,
        context: dict | None = None
    ) -> str:
        """
        Generate a complete response.
        
        Args:
            intent: Detected intent
            search_results: Hybrid search results
            structured_data: Structured data from database
            context: Additional context
            
        Returns:
            Formatted response string
        """
        logger.info(f"Generating response for intent: {intent}")
        
        if intent == 'faculty_information' and structured_data:
            return self.formatter.format_faculty_response(
                structured_data.get('faculty', {}),
                structured_data.get('research_interests', [])
            )
        
        elif intent == 'news_query' and structured_data:
            return self.formatter.format_news(structured_data.get('news', []))
        
        elif intent == 'event_query' and structured_data:
            return self.formatter.format_events(structured_data.get('events', []))
        
        elif intent == 'course_query' and structured_data:
            return self.formatter.format_course_info(structured_data.get('course', {}))
        
        elif search_results:
            # Use hybrid search results
            response = self.formatter.format_search_results(search_results)
            
            # Add citations
            sources = [
                {
                    'title': r.metadata.get('title', 'Document'),
                    'url': r.metadata.get('url', '')
                }
                for r in search_results[:3]
            ]
            
            return self.formatter.add_citations(response, sources)
        
        else:
            return "I don't have enough information to answer that question. Please try rephrasing or ask about specific courses, faculty, or programs."
    
    def enhance_with_recommendations(
        self,
        base_response: str,
        recommendations: list[dict] | None = None
    ) -> str:
        """Add course recommendations to response."""
        if not recommendations:
            return base_response
        
        enhanced = [base_response, "\n\n**Recommended Courses:**\n"]
        
        for i, rec in enumerate(recommendations[:5], 1):
            enhanced.append(f"{i}. **{rec['course_code']}**: {rec['course_title']}")
            enhanced.append(f"   {rec['rationale']}")
            if rec.get('semester_offered'):
                enhanced.append(f"   Offered: {', '.join(rec['semester_offered'])}")
        
        return '\n'.join(enhanced)
    
    def enhance_with_deadlines(
        self,
        base_response: str,
        deadlines: list[dict] | None = None
    ) -> str:
        """Add relevant deadlines to response."""
        if not deadlines:
            return base_response
        
        enhanced = [base_response, "\n\n**Upcoming Deadlines:**\n"]
        
        for deadline in deadlines[:3]:
            enhanced.append(f"- **{deadline.get('title', 'Deadline')}**: {deadline.get('date', 'TBA')}")
            if deadline.get('description'):
                enhanced.append(f"  {deadline['description']}")
        
        return '\n'.join(enhanced)


# Global instance
_generator_instance: ResponseGenerator | None = None


def get_response_generator() -> ResponseGenerator:
    """Get cached ResponseGenerator instance."""
    global _generator_instance
    
    if _generator_instance is None:
        _generator_instance = ResponseGenerator()
    
    return _generator_instance

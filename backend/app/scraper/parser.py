"""
JSON parser for scraped data from cs.qau.edu.pk

This module provides parsers to extract structured information from 
the scraped website content stored in JSON format.
"""

import re
from typing import Dict, List, Optional
from datetime import datetime


def parse_faculty_page(content: str, url: str) -> Optional[Dict]:
    """
    Extract faculty information from a faculty profile page.
    
    Args:
        content: The page content text
        url: The page URL
        
    Returns:
        Dictionary with faculty data or None if parsing fails
    """
    if not content or not url:
        return None
    
    # Check if this is a faculty profile page
    if "faculty_details.php" not in url.lower() and "research interests" not in content.lower():
        return None
    
    faculty_data = {
        "name": None,
        "title": None,
        "email": None,
        "phone": None,
        "office_location": None,
        "research_interests": []
    }
    
    # Extract name - usually in the format "Dr. Name" or "Ms./Mr. Name"
    # Look for patterns like "Dr. FirstName LastName" at the beginning or after title markers
    name_pattern = r'(Dr\.|Prof\.|Ms\.|Mr\.|Miss)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\.]+)*(?:\s+[A-Z][a-z]+)+)'
    name_match = re.search(name_pattern, content)
    if name_match:
        # Get the full match and clean it up
        full_name = name_match.group(0).strip()
        # Remove any trailing text that's not part of the name
        name_parts = full_name.split('\n')[0].strip()
        # Remove "Research Interests" or other keywords that might be attached
        name_parts = re.sub(r'\s*(Research|Professor|Associate|Assistant|Chairperson).*$', '', name_parts)
        faculty_data["name"] = name_parts.strip()
    
    # Extract title (Professor, Associate Professor, Assistant Professor, Lecturer, Chairperson)
    title_pattern = r'(Professor|Associate Professor|Assistant Professor|Lecturer|Chairperson)'
    title_matches = re.findall(title_pattern, content)
    if title_matches:
        # Take the first non-chairperson title, or chairperson if that's all we have
        for title in title_matches:
            if title != "Chairperson":
                faculty_data["title"] = title
                break
        if not faculty_data["title"] and "Chairperson" in title_matches:
            faculty_data["title"] = "Professor"  # Chairpersons are typically professors
    
    # Extract email - look for patterns like "email at domain dot edu dot pk"
    # or standard email format
    email_pattern1 = r'([a-zA-Z0-9._-]+)\s+at\s+([a-zA-Z0-9]+)\s+dot\s+([a-zA-Z]+)\s+dot\s+([a-zA-Z]+)(?:\s+dot\s+([a-zA-Z]+))?'
    email_match1 = re.search(email_pattern1, content)
    if email_match1:
        groups = email_match1.groups()
        if groups[4]:  # Has all parts including country code
            faculty_data["email"] = f"{groups[0]}@{groups[1]}.{groups[2]}.{groups[3]}.{groups[4]}"
        else:
            faculty_data["email"] = f"{groups[0]}@{groups[1]}.{groups[2]}.{groups[3]}"
    else:
        # Try standard email pattern
        email_pattern2 = r'[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_match2 = re.search(email_pattern2, content)
        if email_match2:
            faculty_data["email"] = email_match2.group(0)
    
    # Extract phone - pattern like +92-51-9064 2050 or similar
    phone_pattern = r'\+92[-\s]?\d{2}[-\s]?\d{4}[-\s]?\d{4}'
    phone_match = re.search(phone_pattern, content)
    if phone_match:
        faculty_data["phone"] = phone_match.group(0).strip()
    else:
        # Try simpler pattern
        phone_pattern2 = r'\+\d{2,3}[-\s]?\d{2,3}[-\s]?\d{4}[-\s]?\d{4}'
        phone_match2 = re.search(phone_pattern2, content)
        if phone_match2:
            faculty_data["phone"] = phone_match2.group(0).strip()
    
    # Extract office location - typically after "Office:" or in specific format
    # This is harder to extract reliably from the current content
    # We'll leave it as None for now unless we find a clear pattern
    
    # Extract research interests - look for section after "Research Interests"
    research_section_pattern = r'Research Interests[:\s]+((?:[A-Z][^\n]+\n?)+)'
    research_match = re.search(research_section_pattern, content)
    if research_match:
        research_text = research_match.group(1)
        # Split by newlines and filter out empty lines
        interests = [line.strip() for line in research_text.split('\n') if line.strip()]
        # Filter out non-research interest lines (like "Education", "About", etc.)
        interests = [i for i in interests if not re.match(r'^(Education|About|Dr\.|Professor|Associate)', i)]
        faculty_data["research_interests"] = interests[:10]  # Limit to first 10
    
    # Return None if we couldn't extract at least name or email
    if not faculty_data["name"] and not faculty_data["email"]:
        return None
    
    return faculty_data


def parse_news_page(content: str, url: str) -> Optional[Dict]:
    """
    Extract news article information from a news page.
    
    Args:
        content: The page content text
        url: The page URL
        
    Returns:
        Dictionary with news data or None if parsing fails
    """
    if not content or not url:
        return None
    
    # Check if this is a news-related page
    if "latest news" not in content.lower() and "news" not in url.lower():
        return None
    
    news_items = []
    
    # Look for news items - typically in format:
    # "Title\nby Author\nDate"
    # Or just title and date
    
    # Pattern 1: Look for dated content
    # Matches patterns like "Feb 25, 2024" or "2024-02-25"
    date_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})'
    
    # Split content into lines and look for news items
    lines = content.split('\n')
    
    # Look for "Latest News" section
    news_section_start = -1
    for i, line in enumerate(lines):
        if "latest news" in line.lower():
            news_section_start = i
            break
    
    if news_section_start >= 0:
        # Extract news items from the section
        current_title = None
        current_date = None
        
        for line in lines[news_section_start + 1:]:
            line = line.strip()
            if not line:
                continue
            
            # Check if line contains a date
            date_match = re.search(date_pattern, line)
            if date_match:
                if current_title:
                    # Save previous news item
                    news_items.append({
                        "title": current_title,
                        "date": date_match.group(1),
                        "content": line
                    })
                    current_title = None
                else:
                    current_date = date_match.group(1)
            elif len(line) > 20 and not re.match(r'^(Introduction|Research|Academics)', line):
                # This looks like a title
                current_title = line
                if current_date:
                    news_items.append({
                        "title": current_title,
                        "date": current_date,
                        "content": line
                    })
                    current_title = None
                    current_date = None
    
    # If we found specific news items, return them
    if news_items:
        return {
            "items": news_items,
            "source_url": url
        }
    
    # Otherwise, try to extract any news-like content
    # Look for announcement patterns
    announcement_pattern = r'(Seminar on|Event|Workshop|Conference|Admission|Deadline)[:\s]+([^\n]+)'
    announcements = re.findall(announcement_pattern, content)
    
    if announcements:
        news_items = []
        for event_type, title in announcements:
            news_items.append({
                "title": f"{event_type}: {title}".strip(),
                "date": None,
                "content": f"{event_type}: {title}".strip()
            })
        
        if news_items:
            return {
                "items": news_items,
                "source_url": url
            }
    
    return None


def parse_course_page(content: str, url: str) -> Optional[Dict]:
    """
    Extract course information from a course page.
    
    Args:
        content: The page content text
        url: The page URL
        
    Returns:
        Dictionary with course data or None if parsing fails
    """
    if not content or not url:
        return None
    
    # Check if this is a course-related page
    if "course" not in content.lower() and "syllabus" not in content.lower():
        return None
    
    course_data = {
        "code": None,
        "title": None,
        "description": None,
        "credits": None
    }
    
    # Extract course code - patterns like CS-101, CSC-211, etc.
    # Look for it at word boundaries to avoid false matches
    code_pattern = r'\b([A-Z]{2,4}[-\s]?\d{3})\b'
    code_matches = re.findall(code_pattern, content)
    # Filter out common false positives and take the first valid one
    valid_codes = [code.replace(' ', '-') for code in code_matches 
                   if not re.match(r'^(THE|AND|FOR|NOT|ALL)\d+', code, re.IGNORECASE)]
    if valid_codes:
        course_data["code"] = valid_codes[0]
    
    # Extract course title - usually appears near the course code
    # Look for title patterns after course code
    if course_data["code"]:
        # Pattern: CODE - Title or CODE: Title
        title_pattern = re.escape(course_data["code"]) + r'\s*[-:]\s*([A-Z][^\n\r]+?)(?:\n|$|\[)'
        title_match = re.search(title_pattern, content)
        if title_match:
            course_data["title"] = title_match.group(1).strip()
    
    # If no title found with code, look for course title patterns
    if not course_data["title"]:
        # Look for lines that look like course titles (capitalized, reasonable length)
        title_pattern2 = r'\n([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})\s*(?:\n|$)'
        title_matches = re.findall(title_pattern2, content)
        if title_matches:
            # Take the first reasonable title
            for title in title_matches:
                if 10 < len(title) < 100 and title not in ["Latest News", "Research Interests"]:
                    course_data["title"] = title.strip()
                    break
    
    # Extract credits - patterns like "3 credit hours", "(3 credits)", "3 CH"
    credits_pattern = r'(\d+)\s*(?:credit\s*hours?|credits?|CH)\b'
    credits_match = re.search(credits_pattern, content, re.IGNORECASE)
    if credits_match:
        course_data["credits"] = int(credits_match.group(1))
    
    # Extract description - look for descriptive text after title
    # This is complex, so we'll extract a reasonable chunk of text
    if course_data["title"]:
        # Find the title in content and extract text after it
        title_pos = content.find(course_data["title"])
        if title_pos >= 0:
            desc_start = title_pos + len(course_data["title"])
            desc_text = content[desc_start:desc_start + 500]  # Get up to 500 chars
            # Clean up the description
            desc_lines = [line.strip() for line in desc_text.split('\n') if line.strip()]
            if desc_lines:
                # Take first few lines that look like description
                description_parts = []
                for line in desc_lines[:5]:
                    if len(line) > 20 and not re.match(r'^(Research|Education|About|Dr\.)', line):
                        description_parts.append(line)
                if description_parts:
                    course_data["description"] = ' '.join(description_parts[:2])
    
    # Return None if we couldn't extract at least code or title
    if not course_data["code"] and not course_data["title"]:
        return None
    
    return course_data


def parse_page(content: str, url: str, title: str) -> Dict:
    """
    Parse a page and automatically detect its type.
    
    Args:
        content: The page content text
        url: The page URL
        title: The page title
        
    Returns:
        Dictionary with parsed data including page_type
    """
    result = {
        "url": url,
        "title": title,
        "page_type": "unknown",
        "data": None
    }
    
    # Try faculty parser first
    faculty_data = parse_faculty_page(content, url)
    if faculty_data:
        result["page_type"] = "faculty"
        result["data"] = faculty_data
        return result
    
    # Try news parser
    news_data = parse_news_page(content, url)
    if news_data:
        result["page_type"] = "news"
        result["data"] = news_data
        return result
    
    # Try course parser
    course_data = parse_course_page(content, url)
    if course_data:
        result["page_type"] = "course"
        result["data"] = course_data
        return result
    
    # If no specific parser matched, mark as general content
    result["page_type"] = "general"
    result["data"] = {
        "content": content[:1000] if content else None  # Store first 1000 chars
    }
    
    return result


def extract_structured_data(json_data: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Process all pages from the scraped JSON and extract structured data.
    
    Args:
        json_data: List of page dictionaries from scraped JSON
        
    Returns:
        Dictionary categorizing parsed data by type
    """
    categorized_data = {
        "faculty": [],
        "news": [],
        "courses": [],
        "general": []
    }
    
    for page in json_data:
        content = page.get("content", "")
        url = page.get("url", "")
        title = page.get("title", "")
        
        parsed = parse_page(content, url, title)
        
        if parsed["page_type"] == "faculty" and parsed["data"]:
            categorized_data["faculty"].append({
                **parsed["data"],
                "source_url": url,
                "source_title": title
            })
        elif parsed["page_type"] == "news" and parsed["data"]:
            if "items" in parsed["data"]:
                for item in parsed["data"]["items"]:
                    categorized_data["news"].append({
                        **item,
                        "source_url": url,
                        "source_title": title
                    })
        elif parsed["page_type"] == "course" and parsed["data"]:
            categorized_data["courses"].append({
                **parsed["data"],
                "source_url": url,
                "source_title": title
            })
        elif parsed["page_type"] == "general":
            categorized_data["general"].append({
                "content": parsed["data"].get("content"),
                "source_url": url,
                "source_title": title
            })
    
    return categorized_data

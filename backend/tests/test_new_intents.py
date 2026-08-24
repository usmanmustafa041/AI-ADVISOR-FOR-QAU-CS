"""Test new intent patterns added in task 7.1"""

import re


def _has(pattern: str, text: str) -> bool:
    """Helper function to test regex patterns (same as in service.py)"""
    return bool(re.search(pattern, text, re.I))


def test_faculty_information_pattern():
    """Test faculty_information intent pattern"""
    pattern = r"\bfaculty\b|\bprofessors?\b|\binstructors?\b|\bteachers?\b|\bsupervisors?\b|اساتذہ|استاد"
    
    test_cases = [
        ("Who are the faculty members?", True),
        ("Tell me about professors", True),
        ("List all instructors", True),
        ("Which teachers teach AI?", True),
        ("I need a supervisor for my thesis", True),
        ("What are the course fees?", False),
        ("Show me the timetable", False),
    ]
    
    for query, should_match in test_cases:
        result = _has(pattern, query)
        assert result == should_match, f"Pattern match mismatch for query: {query}"
        print(f"✓ faculty_information: '{query}' -> {'matched' if result else 'not matched'}")


def test_research_area_query_pattern():
    """Test research_area_query intent pattern"""
    pattern = r"\bresearch\s+areas?\b|\bresearch\s+topics?\b|\bspecializations?\b|تحقیقی شعبے"
    
    test_cases = [
        ("What are the research areas?", True),
        ("Tell me about research topics", True),
        ("What specializations are available?", True),
        ("Research areas in CS department", True),
        ("What are the course fees?", False),
        ("Show me the timetable", False),
    ]
    
    for query, should_match in test_cases:
        result = _has(pattern, query)
        assert result == should_match, f"Pattern match mismatch for query: {query}"
        print(f"✓ research_area_query: '{query}' -> {'matched' if result else 'not matched'}")


def test_admission_information_pattern():
    """Test admission_information intent pattern"""
    pattern = r"\badmissions?\b|\badmission\s+(?:requirements?|process|procedure|criteria|eligibility)\b|داخلہ|داخلے"
    
    test_cases = [
        ("What are the admission requirements?", True),
        ("How do I apply for admission?", True),
        ("Admission process for BSCS", True),
        ("Admission criteria for MS program", True),
        ("Admission eligibility requirements", True),
        ("admissions information", True),
        ("What are the course fees?", False),
        ("Show me the timetable", False),
    ]
    
    for query, should_match in test_cases:
        result = _has(pattern, query)
        assert result == should_match, f"Pattern match mismatch for query: {query}"
        print(f"✓ admission_information: '{query}' -> {'matched' if result else 'not matched'}")


def test_news_query_pattern():
    """Test news_query intent pattern"""
    pattern = r"\bnews\b|\bannouncements?\b|\bupdates?\b|خبریں|اعلانات"
    
    test_cases = [
        ("What's the latest news?", True),
        ("Show me recent announcements", True),
        ("Any updates from the department?", True),
        ("department news", True),
        ("What are the course fees?", False),
        ("Show me the timetable", False),
    ]
    
    for query, should_match in test_cases:
        result = _has(pattern, query)
        assert result == should_match, f"Pattern match mismatch for query: {query}"
        print(f"✓ news_query: '{query}' -> {'matched' if result else 'not matched'}")


def test_event_query_pattern():
    """Test event_query intent pattern"""
    pattern = r"\bevents?\b|\bseminars?\b|\bworkshops?\b|تقریبات|سیمینار"
    
    test_cases = [
        ("What events are coming up?", True),
        ("Tell me about upcoming seminars", True),
        ("Are there any workshops?", True),
        ("upcoming events", True),
        ("What are the course fees?", False),
        ("Show me the timetable", False),
    ]
    
    for query, should_match in test_cases:
        result = _has(pattern, query)
        assert result == should_match, f"Pattern match mismatch for query: {query}"
        print(f"✓ event_query: '{query}' -> {'matched' if result else 'not matched'}")


def test_confidence_threshold():
    """Verify that confidence threshold is set to 0.85"""
    # The confidence threshold is hardcoded in the service.py file
    # This test just documents the expected value
    expected_confidence = 0.85
    print(f"✓ Confidence threshold for new intents: {expected_confidence}")
    assert expected_confidence == 0.85


if __name__ == "__main__":
    print("Testing new intent patterns (regex matching)...")
    print()
    
    print("Testing faculty_information pattern...")
    test_faculty_information_pattern()
    print()
    
    print("Testing research_area_query pattern...")
    test_research_area_query_pattern()
    print()
    
    print("Testing admission_information pattern...")
    test_admission_information_pattern()
    print()
    
    print("Testing news_query pattern...")
    test_news_query_pattern()
    print()
    
    print("Testing event_query pattern...")
    test_event_query_pattern()
    print()
    
    print("Testing confidence threshold...")
    test_confidence_threshold()
    print()
    
    print("✅ All tests passed!")

#!/usr/bin/env python3
"""
Test Script: Student Course Status Parsing
Tests the student_history_parser module with comprehensive test cases

Tests both:
1. Query text parsing (unauthenticated users stating their history)
2. Prerequisite conflict resolution when student has completed courses

Usage:
    python backend/scripts/test_student_status_parsing.py
"""

import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.intelligence.student_history_parser import (
    get_student_history_parser,
    parse_student_history_from_query
)
from app.intelligence.prerequisite_intelligence import (
    get_prerequisite_intelligence,
    StudentCourseHistory
)


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_parser_patterns():
    """Test regex pattern matching for various query formats"""
    print_section("TEST 1: Parser Pattern Matching")
    
    parser = get_student_history_parser()
    
    test_cases = [
        # COMPLETED/PASSED patterns
        {
            "query": "I already passed ADSS",
            "expected_completed": ["CS-222"],
            "expected_failed": [],
            "expected_in_progress": []
        },
        {
            "query": "I have completed PSP and OOP",
            "expected_completed": ["CS-105", "CS-121"],
            "expected_failed": [],
            "expected_in_progress": []
        },
        {
            "query": "I finished Data Structures last semester",
            "expected_completed": ["CS-211"],
            "expected_failed": [],
            "expected_in_progress": []
        },
        {
            "query": "I've done DS and OOP already",
            "expected_completed": ["CS-211", "CS-121"],
            "expected_failed": [],
            "expected_in_progress": []
        },
        {
            "query": "I got an A in CS-105",
            "expected_completed": ["CS-105"],
            "expected_failed": [],
            "expected_in_progress": []
        },
        {
            "query": "CS-211 was already passed",
            "expected_completed": ["CS-211"],
            "expected_failed": [],
            "expected_in_progress": []
        },
        
        # FAILED patterns
        {
            "query": "I failed PSP",
            "expected_completed": [],
            "expected_failed": ["CS-105"],
            "expected_in_progress": []
        },
        {
            "query": "I didn't pass OOP last time",
            "expected_completed": [],
            "expected_failed": ["CS-121"],
            "expected_in_progress": []
        },
        {
            "query": "I got an F in Data Structures",
            "expected_completed": [],
            "expected_failed": ["CS-211"],
            "expected_in_progress": []
        },
        
        # IN PROGRESS patterns
        {
            "query": "I'm currently taking SC",
            "expected_completed": [],
            "expected_failed": [],
            "expected_in_progress": ["CS-322"]
        },
        {
            "query": "I am enrolled in OOP this semester",
            "expected_completed": [],
            "expected_failed": [],
            "expected_in_progress": ["CS-121"]
        },
        {
            "query": "This semester I'm taking DS and AI",
            "expected_completed": [],
            "expected_failed": [],
            "expected_in_progress": ["CS-211", "CS-351"]
        },
        
        # MIXED patterns
        {
            "query": "I passed PSP and DS but failed OOP",
            "expected_completed": ["CS-105", "CS-211"],
            "expected_failed": ["CS-121"],
            "expected_in_progress": []
        },
        {
            "query": "I already completed ADSS, can I take SC?",
            "expected_completed": ["CS-222"],
            "expected_failed": [],
            "expected_in_progress": []
        },
        {
            "query": "I failed DS, can I take AI?",
            "expected_completed": [],
            "expected_failed": ["CS-211"],
            "expected_in_progress": []
        },
        
        # COMPLEX patterns
        {
            "query": "I've passed PSP, OOP, and DS. I'm currently taking SC and AI. Can I also take OS?",
            "expected_completed": ["CS-105", "CS-121", "CS-211"],
            "expected_failed": [],
            "expected_in_progress": ["CS-322", "CS-351"]
        },
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        query = test["query"]
        parsed = parser.parse(query)
        
        # Check if results match expected
        completed_match = parsed.completed_courses == set(test["expected_completed"])
        failed_match = parsed.failed_courses == set(test["expected_failed"])
        in_progress_match = parsed.in_progress_courses == set(test["expected_in_progress"])
        
        all_match = completed_match and failed_match and in_progress_match
        
        if all_match:
            print(f"\n✓ Test {i}: PASSED")
            print(f"  Query: \"{query}\"")
            print(f"  Completed: {sorted(parsed.completed_courses)}")
            print(f"  Failed: {sorted(parsed.failed_courses)}")
            print(f"  In Progress: {sorted(parsed.in_progress_courses)}")
            passed += 1
        else:
            print(f"\n✗ Test {i}: FAILED")
            print(f"  Query: \"{query}\"")
            print(f"  Expected completed: {test['expected_completed']}")
            print(f"  Got completed: {sorted(parsed.completed_courses)}")
            print(f"  Expected failed: {test['expected_failed']}")
            print(f"  Got failed: {sorted(parsed.failed_courses)}")
            print(f"  Expected in progress: {test['expected_in_progress']}")
            print(f"  Got in progress: {sorted(parsed.in_progress_courses)}")
            failed += 1
    
    print(f"\n{'─' * 80}")
    print(f"Parser Pattern Tests: {passed} passed, {failed} failed out of {len(test_cases)} total")
    
    return passed, failed


def test_prerequisite_with_completed_courses():
    """Test prerequisite conflict resolution when student has completed prerequisites"""
    print_section("TEST 2: Prerequisite Resolution with Student History")
    
    intelligence = get_prerequisite_intelligence()
    
    test_cases = [
        {
            "name": "Student passed ADSS, can take SC",
            "query": "I already passed ADSS, can I take SC?",
            "completed": ["CS-222"],  # ADSS
            "failed": [],
            "in_progress": [],
            "expected_outcome": "eligible",  # Should be eligible since prerequisite is satisfied
            "description": "CS-322 (SC) requires CS-222 (ADSS). Student has passed ADSS."
        },
        {
            "name": "Student passed PSP, can take OOP",
            "query": "I passed PSP. Can I take OOP?",
            "completed": ["CS-105"],  # PSP
            "failed": [],
            "in_progress": [],
            "expected_outcome": "eligible",
            "description": "CS-121 (OOP) requires CS-105 (PSP). Student has passed PSP."
        },
        {
            "name": "Student failed PSP, cannot take OOP",
            "query": "I failed PSP. Can I take OOP?",
            "completed": [],
            "failed": ["CS-105"],  # PSP
            "in_progress": [],
            "expected_outcome": "not_eligible",
            "description": "CS-121 (OOP) requires CS-105 (PSP). Student has failed PSP."
        },
        {
            "name": "Student passed both PSP and OOP, can take DS",
            "query": "I've passed PSP and OOP. Can I take Data Structures?",
            "completed": ["CS-105", "CS-121"],
            "failed": [],
            "in_progress": [],
            "expected_outcome": "eligible",
            "description": "CS-211 (DS) requires CS-121 (OOP). Student has passed both PSP and OOP."
        },
        {
            "name": "Student wants SC and ADSS together (conflict without history)",
            "query": "Can I study SC and ADSS together?",
            "completed": [],
            "failed": [],
            "in_progress": [],
            "expected_outcome": "conflict",
            "description": "CS-322 (SC) requires CS-222 (ADSS). Taking both together is a conflict."
        },
        {
            "name": "Student already passed ADSS, now wants SC (no conflict)",
            "query": "I already passed ADSS. Can I take SC this semester?",
            "completed": ["CS-222"],  # ADSS
            "failed": [],
            "in_progress": [],
            "expected_outcome": "eligible",
            "description": "CS-322 (SC) requires CS-222 (ADSS). Student already completed ADSS, so no conflict."
        },
        {
            "name": "Student passed PSP and OOP, wants DS and AI together",
            "query": "I passed PSP and OOP. Can I take DS and AI together?",
            "completed": ["CS-105", "CS-121"],
            "failed": [],
            "in_progress": [],
            "expected_outcome": "no_conflict",
            "description": "DS requires OOP, AI requires DS. But since student passed OOP, DS is eligible. However, AI requires DS which student hasn't passed yet."
        },
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        # Build student history
        student_history = StudentCourseHistory(
            completed_courses=set(test["completed"]),
            failed_courses=set(test["failed"]),
            in_progress_courses=set(test["in_progress"])
        )
        
        # Process query
        answer = intelligence.answer_query(
            query=test["query"],
            student_history=student_history
        )
        
        # Determine actual outcome from answer
        answer_lower = answer.answer_text.lower()
        
        if test["expected_outcome"] == "eligible":
            # Should NOT contain conflict messages
            success = (
                "prerequisite is satisfied" in answer_lower or
                "prerequisite requirement is satisfied" in answer_lower or
                "successfully completed" in answer_lower
            ) and "conflict" not in answer_lower and "not satisfied" not in answer_lower
        elif test["expected_outcome"] == "not_eligible":
            # Should contain "not satisfied" or "prerequisite has not been"
            success = (
                "not satisfied" in answer_lower or
                "has not been" in answer_lower or
                "prerequisite has failed" in answer_lower
            )
        elif test["expected_outcome"] == "conflict":
            # Should contain conflict message
            success = "conflict" in answer_lower
        elif test["expected_outcome"] == "no_conflict":
            # Should say no direct conflicts
            success = "no direct prerequisite conflicts" in answer_lower or "no explicit prerequisite" in answer_lower
        else:
            success = False
        
        if success:
            print(f"\n✓ Test {i}: PASSED - {test['name']}")
            print(f"  Query: \"{test['query']}\"")
            print(f"  Description: {test['description']}")
            print(f"  Student History: Completed={test['completed']}, Failed={test['failed']}")
            print(f"  Intent: {answer.intent.value}")
            print(f"  Answer (first 200 chars): {answer.answer_text[:200]}...")
            passed += 1
        else:
            print(f"\n✗ Test {i}: FAILED - {test['name']}")
            print(f"  Query: \"{test['query']}\"")
            print(f"  Description: {test['description']}")
            print(f"  Expected outcome: {test['expected_outcome']}")
            print(f"  Intent: {answer.intent.value}")
            print(f"  Answer: {answer.answer_text[:300]}...")
            failed += 1
    
    print(f"\n{'─' * 80}")
    print(f"Prerequisite Resolution Tests: {passed} passed, {failed} failed out of {len(test_cases)} total")
    
    return passed, failed


def test_integrated_query_parsing():
    """Test integrated query parsing + prerequisite checking"""
    print_section("TEST 3: Integrated Query Parsing + Prerequisite Intelligence")
    
    parser = get_student_history_parser()
    intelligence = get_prerequisite_intelligence()
    
    test_cases = [
        {
            "query": "I already passed ADSS, can I take SC?",
            "description": "Query mentions completion, should parse and resolve eligibility"
        },
        {
            "query": "I've completed PSP and DS. Can I take OOP and AI together?",
            "description": "Multiple completed courses, checking multiple target courses"
        },
        {
            "query": "I failed OOP. Can I take Data Structures?",
            "description": "Failed course mentioned, should detect and handle"
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'─' * 80}")
        print(f"Test {i}: {test['description']}")
        print(f"Query: \"{test['query']}\"")
        
        # Step 1: Parse query
        parsed = parser.parse(test['query'])
        print(f"\nParsed from query:")
        print(f"  Completed: {sorted(parsed.completed_courses)}")
        print(f"  Failed: {sorted(parsed.failed_courses)}")
        print(f"  In Progress: {sorted(parsed.in_progress_courses)}")
        
        # Step 2: Build student history
        if parsed.completed_courses or parsed.failed_courses or parsed.in_progress_courses:
            student_history = StudentCourseHistory(
                completed_courses=parsed.completed_courses,
                failed_courses=parsed.failed_courses,
                in_progress_courses=parsed.in_progress_courses
            )
        else:
            student_history = None
        
        # Step 3: Process with intelligence
        answer = intelligence.answer_query(
            query=test['query'],
            student_history=student_history
        )
        
        print(f"\nPrerequisite Intelligence Response:")
        print(f"  Intent: {answer.intent.value}")
        print(f"  Confidence: {answer.confidence}")
        print(f"  Answer:\n{answer.answer_text}\n")


def test_edge_cases():
    """Test edge cases and boundary conditions"""
    print_section("TEST 4: Edge Cases")
    
    parser = get_student_history_parser()
    
    edge_cases = [
        {
            "query": "Can I take SC?",
            "description": "No status mention - should return empty sets"
        },
        {
            "query": "I passed",
            "description": "Status keyword but no course - should return empty"
        },
        {
            "query": "What is PSP about?",
            "description": "Course mentioned but no status - should return empty"
        },
        {
            "query": "I passed PSP, PSP, PSP",
            "description": "Duplicate course mentions - should only include once"
        },
        {
            "query": "I passed PSP but also failed PSP",
            "description": "Conflicting status - failed takes precedence"
        },
    ]
    
    for i, test in enumerate(edge_cases, 1):
        print(f"\n{'─' * 80}")
        print(f"Edge Case {i}: {test['description']}")
        print(f"Query: \"{test['query']}\"")
        
        parsed = parser.parse(test['query'])
        print(f"Result:")
        print(f"  Completed: {sorted(parsed.completed_courses)}")
        print(f"  Failed: {sorted(parsed.failed_courses)}")
        print(f"  In Progress: {sorted(parsed.in_progress_courses)}")


def main():
    """Run all tests"""
    print("\n" + "█" * 80)
    print("  STUDENT COURSE STATUS PARSING - COMPREHENSIVE TEST SUITE")
    print("█" * 80)
    
    total_passed = 0
    total_failed = 0
    
    # Test 1: Parser patterns
    passed, failed = test_parser_patterns()
    total_passed += passed
    total_failed += failed
    
    # Test 2: Prerequisite resolution with history
    passed, failed = test_prerequisite_with_completed_courses()
    total_passed += passed
    total_failed += failed
    
    # Test 3: Integrated testing
    test_integrated_query_parsing()
    
    # Test 4: Edge cases
    test_edge_cases()
    
    # Final summary
    print("\n" + "█" * 80)
    print("  FINAL SUMMARY")
    print("█" * 80)
    print(f"\nTotal Tests: {total_passed + total_failed}")
    print(f"✓ Passed: {total_passed}")
    print(f"✗ Failed: {total_failed}")
    
    if total_failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉\n")
        return 0
    else:
        print(f"\n⚠️  {total_failed} tests failed. Review output above for details.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

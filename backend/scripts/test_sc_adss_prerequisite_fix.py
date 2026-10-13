#!/usr/bin/env python3
"""
Test Script for SC/ADSS Prerequisite Fix

Tests all the required scenarios from the CRITICAL FIX prompt to ensure
the prerequisite system correctly handles SC (Software Construction) and
ADSS (Analysis & Design for Software Systems).

Official Relationship: ADSS → SC (SC requires ADSS)
"""

import requests
import time

BASE_URL = "http://localhost:8000/api/v1/chat"


def test_query(query, expected_keywords, should_detect_conflict=None):
    """Test a single query and verify response"""
    print(f"\n{'='*80}")
    print(f"TEST: {query}")
    print('='*80)
    
    response = requests.post(
        BASE_URL,
        json={"message": query},
        headers={"Content-Type": "application/json"}
    )
    
    data = response.json()
    
    print(f"Response Engine: {data.get('response_engine')}")
    print(f"Backend: {data.get('model_backend')}")
    print(f"Confidence: {data.get('confidence')}")
    print(f"\nAnswer:\n{data['answer'][:800]}")
    
    # Verify
    answer_lower = data['answer'].lower()
    
    passed = True
    
    # Check response engine
    if data.get('response_engine') != 'prerequisite_graph':
        print(f"\n❌ FAIL: Expected response_engine='prerequisite_graph', got '{data.get('response_engine')}'")
        passed = False
    
    # Check for expected keywords
    missing_keywords = [kw for kw in expected_keywords if kw.lower() not in answer_lower]
    if missing_keywords:
        print(f"\n❌ FAIL: Missing expected keywords: {missing_keywords}")
        passed = False
    
    # Check conflict detection if specified
    if should_detect_conflict is not None:
        has_conflict = ('conflict' in answer_lower or 'requires' in answer_lower)
        if should_detect_conflict and not has_conflict:
            print(f"\n❌ FAIL: Should detect conflict but didn't")
            passed = False
        elif not should_detect_conflict and has_conflict:
            print(f"\n❌ FAIL: Should NOT detect conflict but did")
            passed = False
    
    if passed:
        print("\n✅ PASS")
    
    time.sleep(1)  # Rate limiting
    return passed


def main():
    """Run all test cases"""
    print("="*80)
    print("SC/ADSS PREREQUISITE FIX VALIDATION")
    print("="*80)
    print("\nOfficial Relationship: ADSS → SC")
    print("  CS-222 (ADSS) is prerequisite for CS-322 (SC)")
    print()
    
    tests = [
        {
            "name": "Test 1: Can I study SC and ADSS together?",
            "query": "can i study sc and adss together",
            "expected_keywords": ["CS-322", "CS-222", "Software Construction", "prerequisite", "conflict"],
            "should_detect_conflict": True
        },
        {
            "name": "Test 2: Can I take ADSS and SC together?",
            "query": "can i take adss and sc together",
            "expected_keywords": ["CS-322", "CS-222", "prerequisite", "conflict"],
            "should_detect_conflict": True
        },
        {
            "name": "Test 3: Is ADSS required for SC?",
            "query": "is adss required for sc",
            "expected_keywords": ["CS-222", "CS-322", "prerequisite", "require"],
            "should_detect_conflict": None
        },
        {
            "name": "Test 4: What do I need before SC?",
            "query": "what do i need before sc",
            "expected_keywords": ["CS-222", "ADSS", "Analysis"],
            "should_detect_conflict": None
        },
        {
            "name": "Test 5: I failed ADSS, can I take SC?",
            "query": "i failed adss can i take sc",
            "expected_keywords": ["CS-222", "CS-322", "failed", "prerequisite", "not satisfied"],
            "should_detect_conflict": True
        },
        {
            "name": "Test 6: I already passed ADSS, can I take SC?",
            "query": "i already passed adss can i take sc",
            "expected_keywords": ["CS-222", "CS-322", "prerequisite", "satisfied"],
            "should_detect_conflict": False
        },
        {
            "name": "Test 7: What courses depend on ADSS?",
            "query": "what courses depend on adss",
            "expected_keywords": ["CS-322", "Software Construction"],
            "should_detect_conflict": None
        },
        {
            "name": "Test 8: Natural variation - both SC and ADSS",
            "query": "can i do both sc and adss",
            "expected_keywords": ["CS-322", "CS-222", "prerequisite", "conflict"],
            "should_detect_conflict": True
        }
    ]
    
    passed_count = 0
    failed_count = 0
    
    for test in tests:
        print(f"\n\n{test['name']}")
        passed = test_query(
            test['query'],
            test['expected_keywords'],
            test.get('should_detect_conflict')
        )
        
        if passed:
            passed_count += 1
        else:
            failed_count += 1
    
    # Summary
    print("\n\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {len(tests)}")
    print(f"✅ Passed: {passed_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"Success Rate: {(passed_count/len(tests)*100):.1f}%")
    
    if failed_count == 0:
        print("\n🎉 ALL TESTS PASSED - SC/ADSS prerequisite fix is working!")
    else:
        print(f"\n⚠️  {failed_count} test(s) failed - Review output above")
    
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit(main())

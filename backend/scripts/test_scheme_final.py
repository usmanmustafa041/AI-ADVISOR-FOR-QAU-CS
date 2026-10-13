#!/usr/bin/env python3
"""
Final comprehensive test suite for BSCS scheme queries.
Tests all three schemes with various query patterns.
"""

import requests
import json
import sys
from typing import Dict, Any

API_URL = "http://localhost:8000/api/v1/chat"
TIMEOUT = 120

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def test_scheme_query(query: str, expected_year: str, test_num: int) -> bool:
    """Test a scheme query and verify response."""
    print(f"\n{BLUE}Test {test_num}: {query}{RESET}")
    
    try:
        response = requests.post(
            API_URL,
            json={"message": query},
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            print(f"  {RED}✗ HTTP {response.status_code}{RESET}")
            return False
        
        data = response.json()
        answer = data.get("answer", "")
        response_engine = data.get("response_engine", "")
        verified = data.get("verified", False)
        model_name = data.get("model_name", "")
        
        # Check response engine
        if response_engine != "embedded_scheme_knowledge":
            print(f"  {RED}✗ Wrong engine: {response_engine}{RESET}")
            return False
        
        # Check verified flag
        if not verified:
            print(f"  {YELLOW}⚠ Not verified{RESET}")
        
        # Check for fallback messages (indicates failure)
        fallback_phrases = [
            "information is available in the system. please try again",
            "please try again",
            "meherbani karke dobara koshish karein",
            "dobara try karein"
        ]
        
        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in fallback_phrases):
            print(f"  {RED}✗ Fallback message detected{RESET}")
            print(f"  Answer preview: {answer[:200]}")
            return False
        
        # Check if answer contains expected content
        expected_markers = [
            f"scheme {expected_year}",
            "semester",
            "credit",
            "course"
        ]
        
        # At least 2 markers should be present
        markers_found = sum(1 for marker in expected_markers if marker in answer_lower)
        
        if markers_found < 2:
            print(f"  {RED}✗ Missing key content (markers: {markers_found}/4){RESET}")
            print(f"  Answer preview: {answer[:300]}")
            return False
        
        # Check answer length (should be substantial for scheme queries)
        if len(answer) < 300:
            print(f"  {YELLOW}⚠ Short answer ({len(answer)} chars){RESET}")
            print(f"  Answer: {answer}")
            return False
        
        # Success
        print(f"  {GREEN}✓ Passed{RESET}")
        print(f"  Engine: {response_engine} | Model: {model_name} | Verified: {verified}")
        print(f"  Answer length: {len(answer)} chars | Markers: {markers_found}/4")
        print(f"  Preview: {answer[:200]}...")
        
        return True
        
    except requests.Timeout:
        print(f"  {RED}✗ Timeout after {TIMEOUT}s{RESET}")
        return False
    except Exception as e:
        print(f"  {RED}✗ Error: {e}{RESET}")
        return False


def main():
    """Run all tests."""
    print(f"\n{BLUE}{'='*70}")
    print("BSCS SCHEME QUERY TEST SUITE - FINAL VERSION")
    print(f"{'='*70}{RESET}\n")
    
    test_cases = [
        # Scheme 2021 queries
        ("scheme 2021", "2021", 1),
        ("show me scheme 2021", "2021", 2),
        ("bscs scheme 2021", "2021", 3),
        ("2021 scheme", "2021", 4),
        
        # Scheme 2023 queries
        ("scheme 2023", "2023", 5),
        ("show scheme 2023", "2023", 6),
        ("2023 scheme of study", "2023", 7),
        
        # Scheme 2025 queries
        ("scheme 2025", "2025", 8),
        ("show me scheme 2025", "2025", 9),
        ("bscs scheme 2025", "2025", 10),
        ("current scheme", "2025", 11),
        
        # General queries (should default to 2025)
        ("show me the curriculum", "2025", 12),
        ("scheme", "2025", 13),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_year, test_num in test_cases:
        if test_scheme_query(query, expected_year, test_num):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{BLUE}{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}{RESET}\n")
    
    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"Total tests: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    print(f"Pass rate: {pass_rate:.1f}%\n")
    
    if failed == 0:
        print(f"{GREEN}✓ ALL TESTS PASSED! Scheme query refactoring successful.{RESET}\n")
        return 0
    else:
        print(f"{RED}✗ {failed} test(s) failed. Review the output above.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Test suite for QAU Fall 2026 Admission queries.
Verifies chatbot accurately answers admission-related questions.
"""

import requests
import json
import sys
from typing import Dict, Any

API_URL = "http://localhost:8000/api/v1/chat"
TIMEOUT = 120

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def test_admission_query(query: str, expected_keywords: list[str], test_num: int) -> bool:
    """Test an admission query and verify response contains expected information."""
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
        intent = data.get("intent", "")
        
        answer_lower = answer.lower()
        
        # Check response engine
        if response_engine != "embedded_admission_knowledge":
            print(f"  {YELLOW}⚠ Engine: {response_engine} (expected: embedded_admission_knowledge){RESET}")
        
        # Check for fallback messages
        fallback_phrases = [
            "please try again",
            "dobara try karein",
            "دوبارہ کوشش کریں"
        ]
        
        has_fallback = any(phrase in answer_lower for phrase in fallback_phrases)
        
        # Check if answer contains expected keywords
        keywords_found = []
        keywords_missing = []
        
        for keyword in expected_keywords:
            if keyword.lower() in answer_lower:
                keywords_found.append(keyword)
            else:
                keywords_missing.append(keyword)
        
        # Calculate match ratio
        match_ratio = len(keywords_found) / len(expected_keywords) if expected_keywords else 0
        
        # Check answer length
        if len(answer) < 100:
            print(f"  {YELLOW}⚠ Short answer ({len(answer)} chars){RESET}")
        
        # Determine pass/fail
        if has_fallback and match_ratio < 0.3:
            print(f"  {RED}✗ Fallback message with insufficient content{RESET}")
            print(f"  Answer preview: {answer[:200]}")
            return False
        
        if match_ratio < 0.5:
            print(f"  {RED}✗ Missing key information (found {len(keywords_found)}/{len(expected_keywords)} keywords){RESET}")
            print(f"  Missing: {', '.join(keywords_missing)}")
            print(f"  Answer preview: {answer[:300]}")
            return False
        
        # Success
        print(f"  {GREEN}✓ Passed{RESET}")
        print(f"  Engine: {response_engine} | Intent: {intent} | Verified: {verified}")
        print(f"  Keywords: {len(keywords_found)}/{len(expected_keywords)} | Length: {len(answer)} chars")
        print(f"  Found: {', '.join(keywords_found[:3])}...")
        print(f"  Preview: {answer[:150]}...")
        
        return True
        
    except requests.Timeout:
        print(f"  {RED}✗ Timeout after {TIMEOUT}s{RESET}")
        return False
    except Exception as e:
        print(f"  {RED}✗ Error: {e}{RESET}")
        return False


def main():
    """Run all admission query tests."""
    print(f"\n{BLUE}{'='*70}")
    print("QAU FALL 2026 ADMISSION QUERY TEST SUITE")
    print(f"{'='*70}{RESET}\n")
    
    test_cases = [
        # Deadline queries
        (
            "What is the last date for BS admission?",
            ["10", "08", "2026", "bs", "deadline"],
            1
        ),
        (
            "When is the deadline for LLB admission?",
            ["10", "08", "2026", "llb"],
            2
        ),
        (
            "Pharm-D admission deadline?",
            ["22", "09", "2026", "pharm"],
            3
        ),
        
        # Eligibility queries
        (
            "What are the eligibility criteria for BS Computer Science?",
            ["computer science", "mathematics", "fsc", "fa", "50%"],
            4
        ),
        (
            "Can I apply for BS IT?",
            ["information technology", "physics", "mathematics", "fsc"],
            5
        ),
        (
            "BS CS eligibility requirements",
            ["mathematics", "fsc", "fa", "50", "part-i"],
            6
        ),
        
        # Merit formula queries
        (
            "What is the merit formula for BS programmes?",
            ["70", "hssc", "30", "ssc", "matric", "part-i"],
            7
        ),
        (
            "How is merit calculated for LLB?",
            ["50", "hssc", "30", "lat", "20", "ssc"],
            8
        ),
        (
            "Merit calculation for Pharm-D",
            ["70", "complete", "hssc", "30", "ssc", "60%"],
            9
        ),
        
        # Application process queries
        (
            "How can I apply for admission?",
            ["online", "qau.edu.pk", "2860", "kuickpay", "1-bill"],
            10
        ),
        (
            "What is the application fee?",
            ["2860", "rs", "kuickpay", "1-bill", "receipt"],
            11
        ),
        
        # Scholarship queries
        (
            "Are scholarships available?",
            ["scholarship", "peef", "beef", "hec", "self-finance"],
            12
        ),
        (
            "Can self-finance students get scholarships?",
            ["self-finance", "not eligible", "scholarship"],
            13
        ),
        
        # Merit list queries
        (
            "When will the first merit list be displayed?",
            ["15", "08", "2026", "merit list", "bs", "llb"],
            14
        ),
        (
            "Merit list dates for Pharm-D",
            ["27", "09", "2026", "02", "10", "pharm-d"],
            15
        ),
        
        # General admission queries
        (
            "Tell me about Fall 2026 admissions",
            ["fall 2026", "bs", "llb", "pharm-d", "online", "qau"],
            16
        ),
        (
            "Is there any age limit for BS admission?",
            ["no age limit", "age"],
            17
        ),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_keywords, test_num in test_cases:
        if test_admission_query(query, expected_keywords, test_num):
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
        print(f"{GREEN}✓ ALL TESTS PASSED! Admission knowledge injection successful.{RESET}\n")
        return 0
    elif pass_rate >= 70:
        print(f"{YELLOW}⚠ Most tests passed ({pass_rate:.1f}%). Review failed cases.{RESET}\n")
        return 0
    else:
        print(f"{RED}✗ {failed} test(s) failed. Review the output above.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

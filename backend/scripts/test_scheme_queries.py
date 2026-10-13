#!/usr/bin/env python3
"""
Test Script: BSCS Scheme Query Handling
Tests the refactored RAG pipeline to ensure no "Information Not Found" responses

Usage:
    python backend/scripts/test_scheme_queries.py
"""

import sys
import os
import requests
import json
import time

# Backend API endpoint
API_URL = "http://localhost:8000/api/v1/chat"

def test_query(message, description):
    """Test a single query"""
    print("\n" + "=" * 80)
    print(f"TEST: {description}")
    print("=" * 80)
    print(f"Query: \"{message}\"")
    
    try:
        start_time = time.time()
        response = requests.post(
            API_URL,
            json={"message": message},
            timeout=120  # 2 minute timeout for LLM
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✓ Response received in {elapsed:.1f}s")
            print(f"Response Engine: {data.get('response_engine', 'N/A')}")
            print(f"Model: {data.get('model_name', 'N/A')}")
            print(f"Verified: {data.get('verified', False)}")
            print(f"Confidence: {data.get('confidence', 0.0):.2f}")
            
            answer = data.get('answer', '')
            
            # Check for failure patterns
            failure_keywords = [
                'information not found',
                'information is not available',
                'i do not have',
                'i don\'t have',
                'context does not contain',
                'context doesn\'t contain',
                'cannot find',
                'not in the provided',
                'missing information'
            ]
            
            answer_lower = answer.lower()
            has_failure = any(keyword in answer_lower for keyword in failure_keywords)
            
            if has_failure:
                print("\n❌ FAILURE: Response contains refusal pattern!")
                print(f"Answer (first 300 chars):\n{answer[:300]}...")
                return False
            else:
                # Check if answer contains scheme-related content
                has_scheme_content = any(keyword in answer_lower for keyword in [
                    'semester', 'credit', 'cs-', 'csc-', 'en-', 'ma-', 
                    'scheme', 'course'
                ])
                
                if has_scheme_content:
                    print("\n✓ SUCCESS: Answer contains scheme information")
                    print(f"Answer (first 400 chars):\n{answer[:400]}...")
                    return True
                else:
                    print("\n⚠️ WARNING: Answer doesn't contain expected scheme keywords")
                    print(f"Answer (first 300 chars):\n{answer[:300]}...")
                    return False
        else:
            print(f"\n❌ API Error: {response.status_code}")
            print(response.text[:500])
            return False
            
    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT: Request exceeded 120 seconds")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "█" * 80)
    print("  BSCS SCHEME QUERY TEST SUITE")
    print("  Testing Refactored RAG Pipeline")
    print("█" * 80)
    
    test_cases = [
        {
            "message": "scheme 2021",
            "description": "Direct scheme query - Scheme 2021"
        },
        {
            "message": "scheme 2023",
            "description": "Direct scheme query - Scheme 2023"
        },
        {
            "message": "scheme 2025",
            "description": "Direct scheme query - Scheme 2025 (Current)"
        },
        {
            "message": "What are the semester 1 courses?",
            "description": "Implicit scheme query - Should default to Scheme 2025"
        },
        {
            "message": "show me scheme of study",
            "description": "General scheme query - Should default to Scheme 2025"
        },
        {
            "message": "bscs curriculum 2021",
            "description": "Alternative phrasing - Curriculum 2021"
        },
        {
            "message": "semester 3 courses in scheme 2023",
            "description": "Specific semester query with year"
        },
    ]
    
    results = []
    
    for test_case in test_cases:
        result = test_query(
            message=test_case["message"],
            description=test_case["description"]
        )
        results.append({
            "test": test_case["description"],
            "passed": result
        })
        
        # Brief pause between requests
        time.sleep(2)
    
    # Final summary
    print("\n" + "█" * 80)
    print("  TEST SUMMARY")
    print("█" * 80)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    for i, result in enumerate(results, 1):
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"{i}. {status}: {result['test']}")
    
    print(f"\n{'─' * 80}")
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("The refactored RAG pipeline successfully handles scheme queries.")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed.")
        print("Review the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

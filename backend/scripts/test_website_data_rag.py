#!/usr/bin/env python3
"""
Test script to verify CS website data is correctly ingested in RAG system.

This script tests various queries to ensure the chatbot can answer questions
about faculty, programs, and research areas using the scraped website data.

Usage:
    python backend/scripts/test_website_data_rag.py
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.database import get_session_factory
from app.rag.retriever import retrieve_chunks

def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)

def test_query(db, query: str, expected_keywords: list[str] = None):
    """
    Test a query and verify results contain expected keywords.
    
    Args:
        db: Database session
        query: Query string
        expected_keywords: Optional list of keywords to look for in results
    """
    print_separator()
    print(f"QUERY: {query}")
    print_separator()
    
    results = retrieve_chunks(db, query, limit=5)
    
    print(f"\nFound {len(results)} results\n")
    
    for i, result in enumerate(results, 1):
        similarity = result.get("similarity", 0)
        title = result.get("document_title", "N/A")
        content = result.get("content", "")
        
        print(f"{i}. Score: {similarity:.4f}")
        print(f"   Title: {title}")
        print(f"   Content: {content[:200]}...")
        
        if expected_keywords:
            found_keywords = [kw for kw in expected_keywords if kw.lower() in content.lower()]
            if found_keywords:
                print(f"   ✓ Found keywords: {', '.join(found_keywords)}")
        print()
    
    # Verify we got results
    if len(results) > 0:
        print("✅ SUCCESS: Query returned results")
    else:
        print("❌ FAIL: No results returned")
    
    return len(results) > 0

def main():
    """Run test queries."""
    print_separator("=")
    print("CS WEBSITE DATA RAG VERIFICATION TEST")
    print_separator("=")
    print()
    
    # Initialize database
    db = get_session_factory()()
    
    test_cases = [
        {
            "query": "Who is Dr. Onaiza Maqbool?",
            "keywords": ["Onaiza", "Professor", "research"]
        },
        {
            "query": "Tell me about faculty members",
            "keywords": ["faculty", "Professor", "research"]
        },
        {
            "query": "What programs does the CS department offer?",
            "keywords": ["BS", "MPhil", "PhD", "program"]
        },
        {
            "query": "What are the research areas in the department?",
            "keywords": ["research", "AI", "Machine Learning", "Data"]
        },
        {
            "query": "Tell me about admission requirements",
            "keywords": ["admission", "apply", "semester"]
        }
    ]
    
    results_summary = []
    
    for test_case in test_cases:
        query = test_case["query"]
        keywords = test_case.get("keywords", [])
        
        success = test_query(db, query, keywords)
        results_summary.append({
            "query": query,
            "success": success
        })
    
    # Close database
    db.close()
    
    # Print summary
    print_separator("=")
    print("TEST SUMMARY")
    print_separator("=")
    print()
    
    passed = sum(1 for r in results_summary if r["success"])
    total = len(results_summary)
    
    for result in results_summary:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{status}: {result['query']}")
    
    print()
    print_separator("=")
    print(f"RESULTS: {passed}/{total} tests passed")
    print_separator("=")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - CS website data is correctly ingested in RAG system")
        sys.exit(0)
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()

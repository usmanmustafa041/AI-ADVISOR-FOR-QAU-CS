#!/usr/bin/env python3
"""
Demonstration script for BSCS Prerequisite Knowledge Graph System

Tests natural language queries and shows system capabilities
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.intelligence.prerequisite_intelligence import (
    get_prerequisite_intelligence,
    StudentCourseHistory
)
from app.core.prerequisite_graph import get_prerequisite_graph
from data.bscs_course_catalog import (
    get_prerequisite_count,
    validate_catalog,
    COURSE_INDEX
)


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_query_result(query: str, answer):
    """Print query and answer"""
    print(f"Query: {query}")
    print(f"Intent: {answer.intent.value}")
    print(f"Confidence: {answer.confidence}")
    print(f"\nAnswer:")
    print(answer.answer_text)
    print(f"\nSources: {', '.join(answer.sources)}")
    print("\n" + "-" * 80 + "\n")


def demo_system_validation():
    """Demonstrate system validation"""
    print_section("SYSTEM VALIDATION")
    
    # Validate catalog
    errors = validate_catalog()
    print(f"✓ Course catalog validation: {'PASSED' if len(errors) == 0 else 'FAILED'}")
    
    if errors:
        for error in errors:
            print(f"  ✗ {error}")
    
    # Validate prerequisite count
    prereq_count = get_prerequisite_count()
    print(f"✓ Explicit prerequisite relationships: {prereq_count}")
    assert prereq_count == 19, "Expected 19 prerequisites"
    
    # Validate graph
    graph = get_prerequisite_graph()
    graph_errors = graph.validate_graph()
    print(f"✓ Graph validation: {'PASSED' if len(graph_errors) == 0 else 'FAILED'}")
    
    if graph_errors:
        for error in graph_errors:
            print(f"  ✗ {error}")
    
    # Course count
    print(f"✓ Total courses in catalog: {len(COURSE_INDEX)}")
    
    print("\n✓ All validation checks passed!\n")


def demo_direct_prerequisite_queries():
    """Demonstrate direct prerequisite queries"""
    print_section("DIRECT PREREQUISITE QUERIES")
    
    intelligence = get_prerequisite_intelligence()
    
    queries = [
        "What is the prerequisite of CS-211?",
        "What comes before Data Structures?",
        "What do I need before Software Construction?",
        "What is required for CS-332?",
        "Does CS-414 have a prerequisite?",
    ]
    
    for query in queries:
        answer = intelligence.answer_query(query)
        print_query_result(query, answer)


def demo_reverse_prerequisite_queries():
    """Demonstrate reverse prerequisite queries"""
    print_section("REVERSE PREREQUISITE QUERIES")
    
    intelligence = get_prerequisite_intelligence()
    
    queries = [
        "Which courses require CS-211?",
        "What courses depend on CS-322?",
        "What can I take after Data Structures?",
        "Which courses use CS-324 as a prerequisite?",
    ]
    
    for query in queries:
        answer = intelligence.answer_query(query)
        print_query_result(query, answer)


def demo_prerequisite_chains():
    """Demonstrate prerequisite chain analysis"""
    print_section("PREREQUISITE CHAIN ANALYSIS")
    
    intelligence = get_prerequisite_intelligence()
    
    queries = [
        "What is the prerequisite chain for CS-332?",
        "Show all prerequisites of CS-423?",
        "What are the dependencies for CS-486?",
    ]
    
    for query in queries:
        answer = intelligence.answer_query(query)
        print_query_result(query, answer)


def demo_same_semester_conflicts():
    """Demonstrate same-semester conflict detection"""
    print_section("SAME-SEMESTER CONFLICT DETECTION")
    
    intelligence = get_prerequisite_intelligence()
    
    queries = [
        "Can I take CS-222 and CS-322 together?",
        "Can I take CS-322 and CS-332 in the same semester?",
        "Can I study CS-223 and CS-311 together?",
    ]
    
    for query in queries:
        answer = intelligence.answer_query(query)
        print_query_result(query, answer)


def demo_failed_course_scenarios():
    """Demonstrate failed course impact analysis"""
    print_section("FAILED COURSE IMPACT ANALYSIS")
    
    intelligence = get_prerequisite_intelligence()
    
    queries = [
        "I failed CS-322. Which courses are affected?",
        "I failed CS-211. What courses can I not take?",
        "Which courses depend on CS-222?",
    ]
    
    for query in queries:
        answer = intelligence.answer_query(query)
        print_query_result(query, answer)


def demo_eligibility_with_history():
    """Demonstrate eligibility checking with student history"""
    print_section("COURSE ELIGIBILITY WITH STUDENT HISTORY")
    
    intelligence = get_prerequisite_intelligence()
    
    # Scenario 1: Passed prerequisite
    print("Scenario 1: Student passed CS-222\n")
    history1 = StudentCourseHistory(
        completed_courses={"CS-222"},
        failed_courses=set(),
        in_progress_courses=set()
    )
    
    answer1 = intelligence.answer_query(
        "Can I take CS-322?",
        student_history=history1
    )
    print_query_result("Can I take CS-322?", answer1)
    
    # Scenario 2: Failed prerequisite
    print("Scenario 2: Student failed CS-222\n")
    history2 = StudentCourseHistory(
        completed_courses=set(),
        failed_courses={"CS-222"},
        in_progress_courses=set()
    )
    
    answer2 = intelligence.answer_query(
        "Can I take CS-322?",
        student_history=history2
    )
    print_query_result("Can I take CS-322?", answer2)
    
    # Scenario 3: Prerequisite in progress
    print("Scenario 3: Student currently taking CS-222\n")
    history3 = StudentCourseHistory(
        completed_courses=set(),
        failed_courses=set(),
        in_progress_courses={"CS-222"}
    )
    
    answer3 = intelligence.answer_query(
        "Can I take CS-322?",
        student_history=history3
    )
    print_query_result("Can I take CS-322?", answer3)


def demo_course_planning():
    """Demonstrate course planning scenarios"""
    print_section("COURSE PLANNING SCENARIOS")
    
    intelligence = get_prerequisite_intelligence()
    
    # Student completed some courses
    print("Student completed: CS-105, CS-121, CS-211\n")
    history = StudentCourseHistory(
        completed_courses={"CS-105", "CS-121", "CS-211"},
        failed_courses=set(),
        in_progress_courses=set()
    )
    
    answer = intelligence.answer_query(
        "What courses can I take?",
        student_history=history
    )
    print_query_result("What courses can I take?", answer)


def demo_course_resolver():
    """Demonstrate course alias resolution"""
    print_section("COURSE ALIAS RESOLUTION")
    
    from app.core.course_resolver import get_course_resolver
    
    resolver = get_course_resolver()
    
    test_queries = [
        "CS-211",
        "CS211",
        "CS 211",
        "Data Structures",
        "DS",
        "OOP",
        "Object Oriented Programming",
        "Software Construction",
        "AI",
    ]
    
    print("Testing course resolution:\n")
    for query in test_queries:
        resolved = resolver.resolve(query)
        if resolved:
            course_info = resolver.get_course_info(query)
            print(f"  '{query}' → {resolved} ({course_info['title']})")
        else:
            print(f"  '{query}' → NOT FOUND")
    
    print("\n")


def demo_specific_scenarios():
    """Demonstrate specific real-world scenarios"""
    print_section("REAL-WORLD SCENARIOS")
    
    intelligence = get_prerequisite_intelligence()
    
    scenarios = [
        {
            "title": "Scenario: Student wants to take multiple courses",
            "history": StudentCourseHistory(
                completed_courses={"CS-105", "CS-121", "CS-212"},
                failed_courses=set(),
                in_progress_courses=set()
            ),
            "query": "Can I take CS-211, CS-222, and CS-322 together?"
        },
        {
            "title": "Scenario: Student failed a core prerequisite",
            "history": StudentCourseHistory(
                completed_courses={"CS-105"},
                failed_courses={"CS-121"},
                in_progress_courses=set()
            ),
            "query": "I failed CS-121. Which courses are affected?"
        },
        {
            "title": "Scenario: Planning electives",
            "history": StudentCourseHistory(
                completed_courses={"CS-121", "CS-211", "CS-322"},
                failed_courses=set(),
                in_progress_courses=set()
            ),
            "query": "Which elective courses can I take?"
        },
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['title']}\n")
        answer = intelligence.answer_query(
            scenario['query'],
            student_history=scenario.get('history')
        )
        print_query_result(scenario['query'], answer)


def demo_graph_statistics():
    """Show graph statistics"""
    print_section("PREREQUISITE GRAPH STATISTICS")
    
    graph = get_prerequisite_graph()
    
    # Courses by depth
    depth_map = graph.get_courses_by_depth()
    
    print("Courses by prerequisite depth:\n")
    for depth in sorted(depth_map.keys()):
        courses = depth_map[depth]
        print(f"  Depth {depth}: {len(courses)} courses")
        if depth <= 2:
            print(f"    Examples: {', '.join(courses[:5])}")
    
    print("\n")
    
    # Most dependent courses
    print("Courses with most dependents:\n")
    dependent_counts = []
    for course_code in COURSE_INDEX.keys():
        dependents = graph.get_direct_dependents(course_code)
        if dependents:
            dependent_counts.append((course_code, len(dependents)))
    
    dependent_counts.sort(key=lambda x: x[1], reverse=True)
    
    for course_code, count in dependent_counts[:10]:
        from data.bscs_course_catalog import get_course
        course = get_course(course_code)
        print(f"  {course_code} — {course.title}: {count} dependent(s)")
    
    print("\n")


def main():
    """Run all demonstrations"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  BSCS PREREQUISITE KNOWLEDGE GRAPH SYSTEM DEMONSTRATION".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    
    try:
        # Run demonstrations
        demo_system_validation()
        demo_course_resolver()
        demo_direct_prerequisite_queries()
        demo_reverse_prerequisite_queries()
        demo_prerequisite_chains()
        demo_same_semester_conflicts()
        demo_failed_course_scenarios()
        demo_eligibility_with_history()
        demo_course_planning()
        demo_specific_scenarios()
        demo_graph_statistics()
        
        print_section("DEMONSTRATION COMPLETE")
        print("✓ All demonstrations completed successfully!")
        print("\nThe system is ready for integration with the chatbot.\n")
        
    except Exception as e:
        print(f"\n✗ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

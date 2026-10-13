"""
Comprehensive Test Suite for BSCS Prerequisite Knowledge Graph System

Validates:
1. All 19 explicit prerequisite relationships
2. Bidirectional graph integrity
3. Course resolver functionality
4. Prerequisite reasoning logic
5. Natural language query handling
"""

import pytest
from typing import Set

from data.bscs_course_catalog import (
    EXPLICIT_PREREQUISITES,
    COURSE_INDEX,
    get_course,
    get_direct_prerequisites,
    get_courses_requiring,
    get_prerequisite_count,
    validate_catalog
)
from app.core.prerequisite_graph import (
    get_prerequisite_graph,
    CourseStatus
)
from app.core.course_resolver import get_course_resolver
from app.intelligence.prerequisite_intelligence import (
    get_prerequisite_intelligence,
    StudentCourseHistory,
    QueryIntent
)


class TestCourseData:
    """Test course catalog data integrity"""
    
    def test_prerequisite_count(self):
        """Verify exactly 19 explicit prerequisite relationships"""
        count = get_prerequisite_count()
        assert count == 19, f"Expected 19 prerequisites, found {count}"
    
    def test_all_prerequisites_exist(self):
        """Verify all prerequisite relationships reference valid courses"""
        errors = validate_catalog()
        assert len(errors) == 0, f"Catalog validation errors: {errors}"
    
    def test_course_count(self):
        """Verify total course count"""
        # The supplied catalogue has 77 unique courses. Duplicate entries do
        # not create another course; referential integrity is checked separately.
        assert len(COURSE_INDEX) == 77
    
    def test_semester_coverage(self):
        """Verify courses exist for all 8 semesters"""
        for semester in range(1, 9):
            semester_courses = [c for c in COURSE_INDEX.values() if c.semester == semester]
            assert len(semester_courses) > 0, f"No courses found for semester {semester}"


class TestExplicitPrerequisites:
    """Test all 19 explicit prerequisite relationships"""
    
    def test_CS121_requires_CS105(self):
        """CS-121 → CS-105"""
        prereqs = get_direct_prerequisites("CS-121")
        assert "CS-105" in prereqs, "CS-121 should require CS-105"
    
    def test_CS211_requires_CS121(self):
        """CS-211 → CS-121"""
        prereqs = get_direct_prerequisites("CS-211")
        assert "CS-121" in prereqs, "CS-211 should require CS-121"
    
    def test_CS213_requires_CS103(self):
        """CS-213 → CS-103"""
        prereqs = get_direct_prerequisites("CS-213")
        assert "CS-103" in prereqs, "CS-213 should require CS-103"
    
    def test_CS222_requires_CS212(self):
        """CS-222 → CS-212"""
        prereqs = get_direct_prerequisites("CS-222")
        assert "CS-212" in prereqs, "CS-222 should require CS-212"
    
    def test_CS223_requires_CS211(self):
        """CS-223 → CS-211"""
        prereqs = get_direct_prerequisites("CS-223")
        assert "CS-211" in prereqs, "CS-223 should require CS-211"
    
    def test_CS311_requires_CS211(self):
        """CS-311 → CS-211"""
        prereqs = get_direct_prerequisites("CS-311")
        assert "CS-211" in prereqs, "CS-311 should require CS-211"
    
    def test_CS312_requires_CS213(self):
        """CS-312 → CS-213"""
        prereqs = get_direct_prerequisites("CS-312")
        assert "CS-213" in prereqs, "CS-312 should require CS-213"
    
    def test_CS322_requires_CS222(self):
        """CS-322 → CS-222"""
        prereqs = get_direct_prerequisites("CS-322")
        assert "CS-222" in prereqs, "CS-322 should require CS-222"
    
    def test_CS332_requires_CS322(self):
        """CS-332 → CS-322"""
        prereqs = get_direct_prerequisites("CS-332")
        assert "CS-322" in prereqs, "CS-332 should require CS-322"
    
    def test_CS411_requires_CS331(self):
        """CS-411 → CS-331"""
        prereqs = get_direct_prerequisites("CS-411")
        assert "CS-331" in prereqs, "CS-411 should require CS-331"
    
    def test_CS423_requires_CS311(self):
        """CS-423 → CS-311"""
        prereqs = get_direct_prerequisites("CS-423")
        assert "CS-311" in prereqs, "CS-423 should require CS-311"
    
    def test_CS445_requires_CS225(self):
        """CS-445 → CS-225"""
        prereqs = get_direct_prerequisites("CS-445")
        assert "CS-225" in prereqs, "CS-445 should require CS-225"
    
    def test_CS451_requires_CS211(self):
        """CS-451 → CS-211"""
        prereqs = get_direct_prerequisites("CS-451")
        assert "CS-211" in prereqs, "CS-451 should require CS-211"
    
    def test_CS452_requires_CS121(self):
        """CS-452 → CS-121"""
        prereqs = get_direct_prerequisites("CS-452")
        assert "CS-121" in prereqs, "CS-452 should require CS-121"
    
    def test_CS456_requires_CS324(self):
        """CS-456 → CS-324"""
        prereqs = get_direct_prerequisites("CS-456")
        assert "CS-324" in prereqs, "CS-456 should require CS-324"
    
    def test_CS457_requires_CS324(self):
        """CS-457 → CS-324"""
        prereqs = get_direct_prerequisites("CS-457")
        assert "CS-324" in prereqs, "CS-457 should require CS-324"
    
    def test_CS474_requires_CS322(self):
        """CS-474 → CS-322"""
        prereqs = get_direct_prerequisites("CS-474")
        assert "CS-322" in prereqs, "CS-474 should require CS-322"
    
    def test_CS483_requires_CS322(self):
        """CS-483 → CS-322"""
        prereqs = get_direct_prerequisites("CS-483")
        assert "CS-322" in prereqs, "CS-483 should require CS-322"
    
    def test_CS486_requires_CS322(self):
        """CS-486 → CS-322"""
        prereqs = get_direct_prerequisites("CS-486")
        assert "CS-322" in prereqs, "CS-486 should require CS-322"


class TestReversePrerequisites:
    """Test reverse prerequisite relationships"""
    
    def test_CS105_required_by_CS121(self):
        """CS-105 is required by CS-121"""
        dependents = get_courses_requiring("CS-105")
        assert "CS-121" in dependents
    
    def test_CS121_required_by_multiple(self):
        """CS-121 is required by CS-211 and CS-452"""
        dependents = get_courses_requiring("CS-121")
        assert "CS-211" in dependents
        assert "CS-452" in dependents
    
    def test_CS211_required_by_multiple(self):
        """CS-211 is required by CS-223, CS-311, CS-451"""
        dependents = get_courses_requiring("CS-211")
        assert "CS-223" in dependents
        assert "CS-311" in dependents
        assert "CS-451" in dependents
    
    def test_CS322_required_by_multiple(self):
        """CS-322 is required by CS-332, CS-474, CS-483, CS-486"""
        dependents = get_courses_requiring("CS-322")
        assert "CS-332" in dependents
        assert "CS-474" in dependents
        assert "CS-483" in dependents
        assert "CS-486" in dependents
    
    def test_CS324_required_by_multiple(self):
        """CS-324 is required by CS-456, CS-457"""
        dependents = get_courses_requiring("CS-324")
        assert "CS-456" in dependents
        assert "CS-457" in dependents


class TestPrerequisiteGraph:
    """Test prerequisite graph functionality"""
    
    def test_graph_initialization(self):
        """Graph should initialize without errors"""
        graph = get_prerequisite_graph()
        assert graph is not None
    
    def test_graph_validation(self):
        """Graph should have no structural errors"""
        graph = get_prerequisite_graph()
        errors = graph.validate_graph()
        assert len(errors) == 0, f"Graph validation errors: {errors}"
    
    def test_prerequisite_chain_CS332(self):
        """CS-332 chain: CS-332 → CS-322 → CS-222 → CS-212"""
        graph = get_prerequisite_graph()
        chain = graph.get_all_prerequisites("CS-332")
        
        assert "CS-322" in chain.direct_prerequisites
        assert "CS-222" in chain.indirect_prerequisites
        assert "CS-212" in chain.indirect_prerequisites
    
    def test_prerequisite_chain_CS423(self):
        """CS-423 chain: CS-423 → CS-311 → CS-211 → CS-121 → CS-105"""
        graph = get_prerequisite_graph()
        chain = graph.get_all_prerequisites("CS-423")
        
        assert "CS-311" in chain.direct_prerequisites
        assert "CS-211" in chain.indirect_prerequisites
        assert "CS-121" in chain.indirect_prerequisites
        assert "CS-105" in chain.indirect_prerequisites
    
    def test_dependency_impact_CS322(self):
        """CS-322 failure affects 4 courses"""
        graph = get_prerequisite_graph()
        impact = graph.get_all_dependents("CS-322")
        
        assert len(impact.directly_affected) == 4
        assert "CS-332" in impact.directly_affected
        assert "CS-474" in impact.directly_affected
        assert "CS-483" in impact.directly_affected
        assert "CS-486" in impact.directly_affected
    
    def test_same_semester_conflict_detection(self):
        """Detect CS-222 and CS-322 conflict"""
        graph = get_prerequisite_graph()
        conflicts = graph.check_same_semester_conflict(["CS-222", "CS-322"])
        
        assert "CS-322" in conflicts
        assert "CS-222" in conflicts["CS-322"]
    
    def test_no_conflict_independent_courses(self):
        """No conflict between independent courses"""
        graph = get_prerequisite_graph()
        conflicts = graph.check_same_semester_conflict(["CS-223", "CS-311"])
        
        # Both require CS-211, but not each other
        assert "CS-223" not in conflicts or "CS-311" not in conflicts.get("CS-223", [])
        assert "CS-311" not in conflicts or "CS-223" not in conflicts.get("CS-311", [])
    
    def test_prerequisite_depth(self):
        """Test prerequisite depth calculation"""
        graph = get_prerequisite_graph()
        
        # CS-105 has depth 0 (no prerequisites)
        assert graph.get_prerequisite_depth("CS-105") == 0
        
        # CS-121 has depth 1 (requires CS-105)
        assert graph.get_prerequisite_depth("CS-121") == 1
        
        # CS-332 has depth 3 (CS-332 → CS-322 → CS-222 → CS-212)
        assert graph.get_prerequisite_depth("CS-332") == 3
    
    def test_eligibility_with_completed_courses(self):
        """Test eligibility calculation"""
        graph = get_prerequisite_graph()
        
        completed = {"CS-105", "CS-121", "CS-212"}
        
        # CS-211 is eligible (has CS-121)
        satisfied, missing = graph.is_prerequisite_satisfied("CS-211", completed)
        assert satisfied
        assert len(missing) == 0
        
        # CS-222 is eligible (has CS-212)
        satisfied, missing = graph.is_prerequisite_satisfied("CS-222", completed)
        assert satisfied
        
        # CS-322 is not eligible (needs CS-222)
        satisfied, missing = graph.is_prerequisite_satisfied("CS-322", completed)
        assert not satisfied
        assert "CS-222" in missing


class TestCourseResolver:
    """Test course alias resolution"""
    
    def test_exact_code_resolution(self):
        """Resolve exact course codes"""
        resolver = get_course_resolver()
        
        assert resolver.resolve("CS-211") == "CS-211"
        assert resolver.resolve("CS-322") == "CS-322"
    
    def test_code_variations(self):
        """Resolve code variations (no hyphen, space)"""
        resolver = get_course_resolver()
        
        assert resolver.resolve("CS211") == "CS-211"
        assert resolver.resolve("CS 211") == "CS-211"
        assert resolver.resolve("cs-211") == "CS-211"
    
    def test_title_resolution(self):
        """Resolve course titles"""
        resolver = get_course_resolver()
        
        assert resolver.resolve("Data Structures") == "CS-211"
        assert resolver.resolve("Object Oriented Programming") == "CS-121"
        assert resolver.resolve("Software Construction") == "CS-322"
    
    def test_alias_resolution(self):
        """Resolve common abbreviations"""
        resolver = get_course_resolver()
        
        assert resolver.resolve("OOP") == "CS-121"
        assert resolver.resolve("DS") == "CS-211"
        assert resolver.resolve("AI") == "CS-414"
    
    def test_fuzzy_matching(self):
        """Test fuzzy matching for typos"""
        resolver = get_course_resolver()
        
        # Should handle minor typos
        result = resolver.resolve("Data Structure")
        assert result == "CS-211"
    
    def test_course_search(self):
        """Test course search functionality"""
        resolver = get_course_resolver()
        
        results = resolver.search("algorithm", limit=5)
        codes = [code for code, score in results]
        
        assert "CS-311" in codes  # Analysis & Design of Algorithms


class TestPrerequisiteIntelligence:
    """Test intelligent query handling"""
    
    def test_intent_detection_direct_prerequisite(self):
        """Detect direct prerequisite query intent"""
        intelligence = get_prerequisite_intelligence()
        
        queries = [
            "What is the prerequisite of CS-211?",
            "What comes before Data Structures?",
            "What do I need before Software Construction?"
        ]
        
        for query in queries:
            intent = intelligence._detect_intent(query)
            assert intent == QueryIntent.DIRECT_PREREQUISITE
    
    def test_intent_detection_reverse_prerequisite(self):
        """Detect reverse prerequisite query intent"""
        intelligence = get_prerequisite_intelligence()
        
        queries = [
            "Which courses require CS-211?",
            "What depends on Data Structures?",
            "What can I take after CS-322?"
        ]
        
        for query in queries:
            intent = intelligence._detect_intent(query)
            assert intent == QueryIntent.REVERSE_PREREQUISITE
    
    def test_intent_detection_same_semester(self):
        """Detect same semester conflict query intent"""
        intelligence = get_prerequisite_intelligence()
        
        queries = [
            "Can I take CS-222 and CS-322 together?",
            "Can I study CS-322 and CS-332 in the same semester?"
        ]
        
        for query in queries:
            intent = intelligence._detect_intent(query)
            assert intent == QueryIntent.SAME_SEMESTER_CONFLICT
    
    def test_direct_prerequisite_query(self):
        """Test direct prerequisite query handling"""
        intelligence = get_prerequisite_intelligence()
        
        answer = intelligence.answer_query("What is the prerequisite of CS-211?")
        
        assert answer.intent == QueryIntent.DIRECT_PREREQUISITE
        assert "CS-121" in answer.answer_text
        assert "Object Oriented Programming" in answer.answer_text
        assert answer.confidence == 1.0
    
    def test_reverse_prerequisite_query(self):
        """Test reverse prerequisite query handling"""
        intelligence = get_prerequisite_intelligence()
        
        answer = intelligence.answer_query("Which courses require CS-211?")
        
        assert answer.intent == QueryIntent.REVERSE_PREREQUISITE
        assert "CS-223" in answer.answer_text
        assert "CS-311" in answer.answer_text
        assert "CS-451" in answer.answer_text
    
    def test_no_prerequisite_response(self):
        """Test response for course without explicit prerequisite"""
        intelligence = get_prerequisite_intelligence()
        
        answer = intelligence.answer_query("What is the prerequisite of CS-414?")
        
        assert "does not explicitly specify" in answer.answer_text
        assert answer.structured_data["has_prerequisite"] == False
    
    def test_eligibility_with_passed_course(self):
        """Test eligibility with passed prerequisite"""
        intelligence = get_prerequisite_intelligence()
        
        history = StudentCourseHistory(
            completed_courses={"CS-222"},
            failed_courses=set(),
            in_progress_courses=set()
        )
        
        answer = intelligence.answer_query(
            "Can I take CS-322?",
            student_history=history
        )
        
        assert "satisfied" in answer.answer_text.lower()
    
    def test_eligibility_with_failed_course(self):
        """Test eligibility with failed prerequisite"""
        intelligence = get_prerequisite_intelligence()
        
        history = StudentCourseHistory(
            completed_courses=set(),
            failed_courses={"CS-222"},
            in_progress_courses=set()
        )
        
        answer = intelligence.answer_query(
            "Can I take CS-322?",
            student_history=history
        )
        
        assert "not satisfied" in answer.answer_text.lower()
    
    def test_same_semester_conflict_query(self):
        """Test same semester conflict detection"""
        intelligence = get_prerequisite_intelligence()
        
        answer = intelligence.answer_query(
            "Can I take CS-222 and CS-322 together?"
        )
        
        assert answer.intent == QueryIntent.SAME_SEMESTER_CONFLICT
        assert "CS-322" in answer.answer_text
        assert "CS-222" in answer.answer_text
        assert "prerequisite" in answer.answer_text.lower()
    
    def test_affected_courses_query(self):
        """Test failed course impact query"""
        intelligence = get_prerequisite_intelligence()
        
        answer = intelligence.answer_query(
            "I failed CS-322. Which courses are affected?"
        )
        
        assert "CS-332" in answer.answer_text
        assert "CS-474" in answer.answer_text
        assert "CS-483" in answer.answer_text
        assert "CS-486" in answer.answer_text


class TestNaturalLanguageQueries:
    """Test realistic natural language queries"""
    
    def test_query_variations(self):
        """Test different phrasings of same question"""
        intelligence = get_prerequisite_intelligence()
        
        queries = [
            "What is the prerequisite of CS-211?",
            "What comes before CS-211?",
            "What do I need before Data Structures?",
            "CS-211 prerequisite"
        ]
        
        for query in queries:
            answer = intelligence.answer_query(query)
            assert "CS-121" in answer.answer_text
    
    def test_complex_scenario_1(self):
        """Test: Student passed CS-211, what can they take?"""
        intelligence = get_prerequisite_intelligence()
        
        history = StudentCourseHistory(
            completed_courses={"CS-105", "CS-121", "CS-211"},
            failed_courses=set(),
            in_progress_courses=set()
        )
        
        answer = intelligence.answer_query(
            "What courses can I take?",
            student_history=history
        )
        
        # Should show CS-223, CS-311, CS-451 as eligible
        assert answer.intent == QueryIntent.WHAT_CAN_I_TAKE
    
    def test_complex_scenario_2(self):
        """Test: Taking multiple courses with chain dependency"""
        intelligence = get_prerequisite_intelligence()
        
        answer = intelligence.answer_query(
            "Can I take CS-222, CS-322, and CS-332 together?"
        )
        
        # Should detect prerequisite chain
        assert "CS-322" in answer.answer_text
        assert "CS-222" in answer.answer_text


class TestCoursesWithoutPrerequisites:
    """Test courses that have no explicit prerequisite"""
    
    def test_courses_without_prerequisites(self):
        """Verify courses documented without prerequisites"""
        graph = get_prerequisite_graph()
        
        no_prereq_courses = [
            "CS-101", "CS-103", "CS-105", "CS-212", "CS-225",
            "CS-324", "CS-331", "CS-413", "CS-414", "CS-449",
            "CS-489", "CS-490"
        ]
        
        for course in no_prereq_courses:
            prereqs = graph.get_direct_prerequisites(course)
            assert len(prereqs) == 0, f"{course} should have no explicit prerequisite"


class TestElectiveCourses:
    """Test elective course handling"""
    
    def test_elective_with_prerequisite(self):
        """Test electives that have prerequisites"""
        elective_prereqs = {
            "CS-445": "CS-225",
            "CS-451": "CS-211",
            "CS-452": "CS-121",
            "CS-456": "CS-324",
            "CS-457": "CS-324",
            "CS-474": "CS-322",
            "CS-483": "CS-322",
            "CS-486": "CS-322"
        }
        
        graph = get_prerequisite_graph()
        
        for elective, prereq in elective_prereqs.items():
            prereqs = graph.get_direct_prerequisites(elective)
            assert prereq in prereqs, f"{elective} should require {prereq}"
    
    def test_elective_without_prerequisite(self):
        """Test electives without explicit prerequisites"""
        no_prereq_electives = [
            "CS-442", "CS-443", "CS-444", "CS-446", "CS-448",
            "CS-454", "CS-455", "CS-458", "CS-459", "CS-462"
        ]
        
        graph = get_prerequisite_graph()
        
        for elective in no_prereq_electives:
            if elective in COURSE_INDEX:
                prereqs = graph.get_direct_prerequisites(elective)
                assert len(prereqs) == 0


def run_all_tests():
    """Run all tests and report results"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_all_tests()

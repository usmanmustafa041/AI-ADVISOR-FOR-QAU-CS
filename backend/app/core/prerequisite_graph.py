"""
Prerequisite Knowledge Graph
Bidirectional dependency graph with traversal and reasoning capabilities

This module provides graph-based prerequisite reasoning, NOT vector similarity.
All prerequisite relationships are deterministic and source-grounded.
"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, deque
from enum import Enum

from data.bscs_course_catalog import (
    EXPLICIT_PREREQUISITES,
    COURSE_INDEX,
    get_course,
    get_direct_prerequisites,
    get_courses_requiring
)


class CourseStatus(Enum):
    """Student's status with respect to a course"""
    COMPLETED = "completed"
    PASSED = "passed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    NOT_TAKEN = "not_taken"
    UNKNOWN = "unknown"


class PrerequisiteRelationType(Enum):
    """Type of prerequisite relationship"""
    DIRECT = "direct"
    INDIRECT = "indirect"


@dataclass
class PrerequisiteRelationship:
    """Represents a prerequisite relationship"""
    from_course: str
    to_course: str
    relation_type: PrerequisiteRelationType
    distance: int  # 1 for direct, >1 for indirect


@dataclass
class PrerequisiteChain:
    """Represents a complete prerequisite chain"""
    target_course: str
    direct_prerequisites: List[str]
    indirect_prerequisites: List[str]
    full_chain: List[List[str]]  # All paths from target to roots


@dataclass
class DependencyImpact:
    """Impact analysis of a course failure/status"""
    course: str
    directly_affected: List[str]
    indirectly_affected: List[str]
    total_affected: int


class PrerequisiteGraph:
    """
    Bidirectional prerequisite dependency graph
    
    Provides deterministic prerequisite reasoning based on explicit
    source-grounded relationships. NOT based on vector similarity.
    """
    
    def __init__(self):
        """Initialize the prerequisite graph"""
        # Forward edges: course -> prerequisites
        self.prerequisites: Dict[str, Set[str]] = defaultdict(set)
        
        # Reverse edges: prerequisite -> dependent courses
        self.dependents: Dict[str, Set[str]] = defaultdict(set)
        
        # Build graph from explicit relationships
        self._build_graph()
    
    def _build_graph(self):
        """Build bidirectional graph from explicit prerequisites"""
        for course_code, prereq_list in EXPLICIT_PREREQUISITES.items():
            for prereq in prereq_list:
                # Forward edge
                self.prerequisites[course_code].add(prereq)
                
                # Reverse edge
                self.dependents[prereq].add(course_code)
    
    def get_direct_prerequisites(self, course_code: str) -> List[str]:
        """
        Get direct prerequisites for a course
        
        Returns:
            List of course codes that are direct prerequisites
            Empty list if no explicit prerequisite
        """
        return list(self.prerequisites.get(course_code, set()))
    
    def get_direct_dependents(self, course_code: str) -> List[str]:
        """
        Get courses that directly depend on this course
        
        Returns:
            List of course codes that require this course
        """
        return list(self.dependents.get(course_code, set()))
    
    def get_all_prerequisites(self, course_code: str) -> PrerequisiteChain:
        """
        Get complete prerequisite chain (direct + indirect)
        
        Uses BFS to traverse prerequisite graph backwards
        
        Returns:
            PrerequisiteChain with direct, indirect, and all paths
        """
        if course_code not in COURSE_INDEX:
            return PrerequisiteChain(
                target_course=course_code,
                direct_prerequisites=[],
                indirect_prerequisites=[],
                full_chain=[]
            )
        
        direct = self.get_direct_prerequisites(course_code)
        
        # BFS to find all indirect prerequisites
        visited = set()
        queue = deque(direct)
        indirect = []
        
        while queue:
            prereq = queue.popleft()
            if prereq in visited:
                continue
            
            visited.add(prereq)
            
            # Get prerequisites of this prerequisite
            prereq_prereqs = self.get_direct_prerequisites(prereq)
            
            for p in prereq_prereqs:
                if p not in direct and p not in visited:
                    indirect.append(p)
                    queue.append(p)
        
        # Get all paths using DFS
        all_paths = self._get_all_paths(course_code)
        
        return PrerequisiteChain(
            target_course=course_code,
            direct_prerequisites=direct,
            indirect_prerequisites=indirect,
            full_chain=all_paths
        )
    
    def _get_all_paths(self, course_code: str) -> List[List[str]]:
        """
        Get all prerequisite paths from course to root prerequisites
        
        Returns:
            List of paths, where each path is [course -> prereq1 -> prereq2 -> ...]
        """
        paths = []
        
        def dfs(current: str, path: List[str]):
            prereqs = self.get_direct_prerequisites(current)
            
            if not prereqs:
                # Reached a root node
                paths.append(path.copy())
                return
            
            for prereq in prereqs:
                path.append(prereq)
                dfs(prereq, path)
                path.pop()
        
        dfs(course_code, [course_code])
        return paths
    
    def get_all_dependents(self, course_code: str) -> DependencyImpact:
        """
        Get complete dependency impact (direct + indirect)
        
        Shows which courses are affected if this course is not completed
        
        Returns:
            DependencyImpact with direct and indirect affected courses
        """
        direct = self.get_direct_dependents(course_code)
        
        # BFS to find all indirect dependents
        visited = set()
        queue = deque(direct)
        indirect = []
        
        while queue:
            dependent = queue.popleft()
            if dependent in visited:
                continue
            
            visited.add(dependent)
            
            # Get courses that depend on this dependent
            dependent_deps = self.get_direct_dependents(dependent)
            
            for d in dependent_deps:
                if d not in direct and d not in visited:
                    indirect.append(d)
                    queue.append(d)
        
        return DependencyImpact(
            course=course_code,
            directly_affected=direct,
            indirectly_affected=indirect,
            total_affected=len(direct) + len(indirect)
        )
    
    def check_same_semester_conflict(self, courses: List[str]) -> Dict[str, List[str]]:
        """
        Check for prerequisite conflicts if taking courses together
        
        Identifies if any course in the list requires another course in the list
        
        Args:
            courses: List of course codes to check
        
        Returns:
            Dict mapping course_code -> list of prerequisites also in the list
        """
        conflicts = {}
        course_set = set(courses)
        
        for course in courses:
            prereqs = self.get_direct_prerequisites(course)
            conflicts_for_course = [p for p in prereqs if p in course_set]
            
            if conflicts_for_course:
                conflicts[course] = conflicts_for_course
        
        return conflicts
    
    def check_prerequisite_chain_conflict(self, courses: List[str]) -> Dict[str, List[List[str]]]:
        """
        Check for indirect prerequisite conflicts (prerequisite chains)
        
        Identifies if any course requires another through a chain
        
        Args:
            courses: List of course codes to check
        
        Returns:
            Dict mapping course_code -> list of dependency chains within the list
        """
        conflicts = {}
        course_set = set(courses)
        
        for course in courses:
            chain = self.get_all_prerequisites(course)
            
            # Find chains where intermediate or root nodes are in the list
            conflicting_chains = []
            
            for path in chain.full_chain:
                # Check if any node in path (except the first) is in course_set
                for node in path[1:]:
                    if node in course_set:
                        conflicting_chains.append(path)
                        break
            
            if conflicting_chains:
                conflicts[course] = conflicting_chains
        
        return conflicts
    
    def is_prerequisite_satisfied(
        self,
        course_code: str,
        completed_courses: Set[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if prerequisite is satisfied based on completed courses
        
        Args:
            course_code: Course to check
            completed_courses: Set of successfully completed course codes
        
        Returns:
            Tuple of (is_satisfied, missing_prerequisites)
        """
        prereqs = self.get_direct_prerequisites(course_code)
        
        if not prereqs:
            # No explicit prerequisite
            return (True, [])
        
        missing = [p for p in prereqs if p not in completed_courses]
        
        return (len(missing) == 0, missing)
    
    def get_eligible_courses(
        self,
        completed_courses: Set[str]
    ) -> Dict[str, List[str]]:
        """
        Get all courses eligible based on completed prerequisites
        
        Args:
            completed_courses: Set of successfully completed course codes
        
        Returns:
            Dict with keys:
            - 'eligible': courses with satisfied prerequisites
            - 'no_prerequisite': courses with no explicit prerequisite
            - 'not_eligible': courses with unsatisfied prerequisites
        """
        result = {
            'eligible': [],
            'no_prerequisite': [],
            'not_eligible': []
        }
        
        for course_code in COURSE_INDEX.keys():
            if course_code in completed_courses:
                # Already completed
                continue
            
            prereqs = self.get_direct_prerequisites(course_code)
            
            if not prereqs:
                result['no_prerequisite'].append(course_code)
            else:
                satisfied, missing = self.is_prerequisite_satisfied(
                    course_code,
                    completed_courses
                )
                
                if satisfied:
                    result['eligible'].append(course_code)
                else:
                    result['not_eligible'].append(course_code)
        
        return result
    
    def find_shortest_path(self, from_course: str, to_course: str) -> Optional[List[str]]:
        """
        Find shortest prerequisite path between two courses
        
        Uses BFS to find shortest path in prerequisite graph
        
        Returns:
            List representing path, or None if no path exists
        """
        if from_course not in COURSE_INDEX or to_course not in COURSE_INDEX:
            return None
        
        # BFS
        queue = deque([(from_course, [from_course])])
        visited = {from_course}
        
        while queue:
            current, path = queue.popleft()
            
            if current == to_course:
                return path
            
            # Check both prerequisites and dependents
            neighbors = (
                self.get_direct_prerequisites(current) +
                self.get_direct_dependents(current)
            )
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None
    
    def get_prerequisite_depth(self, course_code: str) -> int:
        """
        Get maximum prerequisite depth (longest chain to root)
        
        Returns:
            Maximum depth, where 0 means no prerequisites
        """
        chain = self.get_all_prerequisites(course_code)
        
        if not chain.full_chain:
            return 0
        
        return max(len(path) - 1 for path in chain.full_chain)
    
    def get_courses_by_depth(self) -> Dict[int, List[str]]:
        """
        Group courses by prerequisite depth
        
        Returns:
            Dict mapping depth -> list of courses
        """
        depth_map = defaultdict(list)
        
        for course_code in COURSE_INDEX.keys():
            depth = self.get_prerequisite_depth(course_code)
            depth_map[depth].append(course_code)
        
        return dict(depth_map)
    
    def validate_graph(self) -> List[str]:
        """
        Validate graph integrity
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check for cycles
        visited = set()
        rec_stack = set()
        
        def has_cycle(course: str) -> bool:
            visited.add(course)
            rec_stack.add(course)
            
            for prereq in self.get_direct_prerequisites(course):
                if prereq not in visited:
                    if has_cycle(prereq):
                        return True
                elif prereq in rec_stack:
                    errors.append(f"Cycle detected: {course} -> {prereq}")
                    return True
            
            rec_stack.remove(course)
            return False
        
        for course in COURSE_INDEX.keys():
            if course not in visited:
                has_cycle(course)
        
        # Check for bidirectional consistency
        for course, prereqs in self.prerequisites.items():
            for prereq in prereqs:
                if course not in self.dependents[prereq]:
                    errors.append(
                        f"Inconsistent edge: {course} -> {prereq} "
                        f"but reverse edge not found"
                    )
        
        return errors


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_graph_instance = None


def get_prerequisite_graph() -> PrerequisiteGraph:
    """Get singleton instance of prerequisite graph"""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = PrerequisiteGraph()
    return _graph_instance

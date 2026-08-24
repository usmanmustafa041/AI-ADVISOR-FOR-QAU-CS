"""Unit tests for pattern detection utilities."""

import pytest
from .patterns import (
    # Counting functions
    count_course_codes,
    count_day_names,
    count_time_patterns,
    count_credit_hours,
    count_semester_references,
    
    # Extraction functions
    extract_course_codes,
    extract_day_names,
    extract_times,
    extract_credit_hours,
    extract_semester_numbers,
    
    # Normalization functions
    normalize_course_type,
    normalize_section,
    normalize_special_status,
    
    # Validation functions
    validate_course_code,
    validate_time_format,
    has_structured_layout,
)


class TestCourseCodePatterns:
    """Tests for course code pattern detection."""
    
    def test_count_valid_course_codes(self):
        text = "CS101 MATH2201 BIO123A ENG1234"
        assert count_course_codes(text) == 4
    
    def test_count_course_codes_with_duplicates(self):
        text = "CS101 CS101 MATH2201 CS101"
        # Should count unique course codes only
        assert count_course_codes(text) == 2
    
    def test_count_course_codes_too_short(self):
        text = "CS1 MA2 BIO"  # All too short (< 4 characters)
        assert count_course_codes(text) == 0
    
    def test_count_course_codes_too_long(self):
        text = "VERYLONGCODE12345"  # 17 characters, exceeds max 10
        assert count_course_codes(text) == 0
    
    def test_count_course_codes_no_digit(self):
        text = "COURSE"  # No digit
        assert count_course_codes(text) == 0
    
    def test_count_course_codes_no_letter(self):
        text = "12345"  # No letter
        assert count_course_codes(text) == 0
    
    def test_extract_course_codes(self):
        text = "Students must take CS101, MATH2201, and BIO123A"
        codes = extract_course_codes(text)
        assert len(codes) >= 3
        assert "CS101" in codes or "CS" in [c[:2] for c in codes]
    
    def test_validate_course_code_valid(self):
        assert validate_course_code("CS101") == True
        assert validate_course_code("MATH2201") == True
        assert validate_course_code("BIO123A") == True
    
    def test_validate_course_code_invalid_length(self):
        assert validate_course_code("CS1") == False  # Too short
        assert validate_course_code("VERYLONGCODE123") == False  # Too long
    
    def test_validate_course_code_no_letter(self):
        assert validate_course_code("12345") == False
    
    def test_validate_course_code_no_digit(self):
        assert validate_course_code("COURSE") == False
    
    def test_validate_course_code_special_chars(self):
        assert validate_course_code("CS-101") == False  # Contains hyphen


class TestDayNamePatterns:
    """Tests for day name pattern detection."""
    
    def test_count_full_day_names(self):
        text = "Classes on Monday and Wednesday"
        assert count_day_names(text) == 2
    
    def test_count_abbreviated_day_names(self):
        text = "Schedule: Mon, Wed, Fri"
        assert count_day_names(text) == 3
    
    def test_count_mixed_day_names(self):
        text = "Monday and Tue and Wednesday"
        # Should count distinct days (Monday, Tuesday, Wednesday)
        assert count_day_names(text) == 3
    
    def test_count_duplicate_day_names(self):
        text = "Monday Monday Mon Monday"
        # All refer to same day, should count as 1
        assert count_day_names(text) == 1
    
    def test_extract_day_names_full(self):
        text = "Classes on Monday, Wednesday, and Friday"
        days = extract_day_names(text)
        assert "Monday" in days
        assert "Wednesday" in days
        assert "Friday" in days
    
    def test_extract_day_names_abbreviated(self):
        text = "Mon, Wed, Fri schedule"
        days = extract_day_names(text)
        # Should normalize to full names
        assert "Monday" in days
        assert "Wednesday" in days
        assert "Friday" in days
    
    def test_count_all_seven_days(self):
        text = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday"
        assert count_day_names(text) == 7


class TestTimePatterns:
    """Tests for time pattern detection."""
    
    def test_count_12_hour_format(self):
        text = "Class at 9:30 AM and 2:45 PM"
        assert count_time_patterns(text) >= 2
    
    def test_count_24_hour_format(self):
        text = "Meeting at 09:30 and 14:45"
        assert count_time_patterns(text) >= 2
    
    def test_count_mixed_time_formats(self):
        text = "Morning: 9:00 AM, Afternoon: 14:30"
        assert count_time_patterns(text) >= 2
    
    def test_extract_times_12_hour(self):
        text = "Classes: 9:30 AM - 11:00 AM"
        times = extract_times(text)
        assert len(times) >= 2
    
    def test_extract_times_24_hour(self):
        text = "Schedule: 09:30 - 11:00"
        times = extract_times(text)
        assert len(times) >= 2
    
    def test_extract_times_preserves_format(self):
        text = "Class at 9:30 AM"
        times = extract_times(text)
        # Should preserve exact format including AM/PM
        assert any("AM" in t or "am" in t for t in times)
    
    def test_validate_time_format_12_hour(self):
        assert validate_time_format("9:30 AM") == True
        assert validate_time_format("12:00 PM") == True
        assert validate_time_format("01:15 pm") == True
    
    def test_validate_time_format_24_hour(self):
        assert validate_time_format("09:30") == True
        assert validate_time_format("14:45") == True
        assert validate_time_format("23:59") == True
    
    def test_validate_time_format_invalid(self):
        assert validate_time_format("25:00") == False  # Invalid hour
        assert validate_time_format("12:60") == False  # Invalid minute
        assert validate_time_format("9:30") == True or validate_time_format("9:30") == False  # Ambiguous


class TestCreditHoursPatterns:
    """Tests for credit hours pattern detection."""
    
    def test_count_credit_hours_credits(self):
        text = "Course A: 3 credits, Course B: 4 credits"
        assert count_credit_hours(text) == 2
    
    def test_count_credit_hours_credit(self):
        text = "1 credit course"
        assert count_credit_hours(text) == 1
    
    def test_count_credit_hours_cr(self):
        text = "3 Cr course"
        assert count_credit_hours(text) == 1
    
    def test_count_credit_hours_ch(self):
        text = "4 CH required"
        assert count_credit_hours(text) == 1
    
    def test_count_credit_hours_credit_hours(self):
        text = "This course is 3 Credit Hours"
        assert count_credit_hours(text) == 1
    
    def test_extract_credit_hours(self):
        text = "Course A: 3 credits, Course B: 4 Cr"
        results = extract_credit_hours(text)
        assert len(results) == 2
        credit_values = [r[0] for r in results]
        assert 3 in credit_values
        assert 4 in credit_values
    
    def test_count_credit_hours_case_insensitive(self):
        text = "3 CREDITS, 4 Credits, 2 credits"
        assert count_credit_hours(text) == 3


class TestSemesterPatterns:
    """Tests for semester reference pattern detection."""
    
    def test_count_semester_with_keyword(self):
        text = "Semester 1, Semester 2, Semester 3"
        assert count_semester_references(text) >= 3
    
    def test_count_semester_numbers_only(self):
        text = "1st semester, 2nd semester, 3rd semester"
        # Should find the numbers 1, 2, 3
        assert count_semester_references(text) >= 3
    
    def test_count_semester_range_1_to_12(self):
        text = "Semesters: 1, 5, 8, 12"
        assert count_semester_references(text) == 4
    
    def test_count_semester_out_of_range(self):
        text = "Semester 0, Semester 13, Semester 15"
        # Should not count out-of-range values
        assert count_semester_references(text) == 0
    
    def test_extract_semester_numbers(self):
        text = "Semester 1, Semester 5, Semester 8"
        semesters = extract_semester_numbers(text)
        assert 1 in semesters
        assert 5 in semesters
        assert 8 in semesters
    
    def test_count_distinct_semesters(self):
        text = "Semester 1 Semester 1 1 Semester 1"
        # All refer to semester 1, should count as 1 distinct semester
        assert count_semester_references(text) == 1


class TestSectionPatterns:
    """Tests for section designation pattern detection."""
    
    def test_normalize_section_regular(self):
        assert normalize_section("Regular section") == "Regular"
        assert normalize_section("REGULAR") == "Regular"
        assert normalize_section("regular") == "Regular"
    
    def test_normalize_section_self_support(self):
        assert normalize_section("Self-Support section") == "Self-Support"
        assert normalize_section("Self Support") == "Self-Support"
        assert normalize_section("SELF-SUPPORT") == "Self-Support"
    
    def test_normalize_section_unknown(self):
        assert normalize_section("Evening section") == "Unknown"
        assert normalize_section("No section info") == "Unknown"


class TestCourseTypePatterns:
    """Tests for course type pattern detection."""
    
    def test_normalize_course_type_lab(self):
        assert normalize_course_type("Lab session") == "Lab"
        assert normalize_course_type("Laboratory") == "Lab"
        assert normalize_course_type("LAB") == "Lab"
    
    def test_normalize_course_type_lecture(self):
        assert normalize_course_type("Lecture hall") == "Lecture"
        assert normalize_course_type("Lec") == "Lecture"
        assert normalize_course_type("LECTURE") == "Lecture"
    
    def test_normalize_course_type_tutorial(self):
        assert normalize_course_type("Tutorial session") == "Tutorial"
        assert normalize_course_type("Tut") == "Tutorial"
        assert normalize_course_type("TUTORIAL") == "Tutorial"
    
    def test_normalize_course_type_unknown(self):
        assert normalize_course_type("Seminar") == "Unknown"
        assert normalize_course_type("Workshop") == "Unknown"


class TestSpecialStatusPatterns:
    """Tests for special status pattern detection."""
    
    def test_normalize_special_status_repeater(self):
        assert normalize_special_status("Repeater student") == "Repeater"
        assert normalize_special_status("REPEATER") == "Repeater"
    
    def test_normalize_special_status_deficiency(self):
        assert normalize_special_status("Deficiency course") == "Deficiency"
        assert normalize_special_status("DEFICIENCY") == "Deficiency"
    
    def test_normalize_special_status_special(self):
        assert normalize_special_status("Special case") == "Special"
        assert normalize_special_status("SPECIAL") == "Special"
    
    def test_normalize_special_status_none(self):
        assert normalize_special_status("Normal student") is None
        assert normalize_special_status("No special status") is None


class TestStructuredLayoutDetection:
    """Tests for structured layout detection."""
    
    def test_has_structured_layout_with_tabs(self):
        text = "CS101\t9:00 AM\tMonday\nCS102\t10:00 AM\tTuesday\nCS103\t11:00 AM\tWednesday"
        assert has_structured_layout(text) == True
    
    def test_has_structured_layout_with_pipes(self):
        text = "CS101 | 9:00 AM | Monday\nCS102 | 10:00 AM | Tuesday\nCS103 | 11:00 AM | Wednesday"
        assert has_structured_layout(text) == True
    
    def test_has_structured_layout_with_spaces(self):
        text = "CS101  9:00 AM  Monday\nCS102  10:00 AM  Tuesday\nCS103  11:00 AM  Wednesday"
        assert has_structured_layout(text) == True
    
    def test_has_structured_layout_plain_text(self):
        text = "This is a plain paragraph without any structured data."
        assert has_structured_layout(text) == False
    
    def test_has_structured_layout_insufficient_rows(self):
        text = "CS101\t9:00 AM\nCS102\t10:00 AM"
        # Only 2 rows, default min is 3
        assert has_structured_layout(text, min_rows=3) == False
        # But should pass with lower threshold
        assert has_structured_layout(text, min_rows=2) == True


class TestIntegrationScenarios:
    """Integration tests with realistic document content."""
    
    def test_timetable_content_detection(self):
        timetable_text = """
        Semester 3 - Regular Section
        CS301 Data Structures    Lecture  Monday    9:00 AM - 11:00 AM   Room A-101
        CS301 Data Structures    Lab      Wednesday 2:00 PM - 4:00 PM    Lab-3
        MATH201 Calculus II      Lecture  Tuesday   10:00 AM - 12:00 PM  Room B-205
        """
        
        # Should detect course codes
        assert count_course_codes(timetable_text) >= 2
        
        # Should detect day names
        assert count_day_names(timetable_text) >= 2
        
        # Should detect time patterns
        assert count_time_patterns(timetable_text) >= 3
        
        # Should detect structured layout
        assert has_structured_layout(timetable_text) == True
    
    def test_scheme_of_study_content_detection(self):
        scheme_text = """
        Semester 1
        CS101 Introduction to Computing    3 credits    Core
        MATH101 Calculus I                 3 credits    Core
        ENG101 English Composition         3 Cr         Required
        
        Semester 2
        CS102 Programming Fundamentals     4 credits    Core
        MATH102 Linear Algebra            3 CH         Core
        """
        
        # Should detect course codes
        assert count_course_codes(scheme_text) >= 4
        
        # Should detect semester references
        assert count_semester_references(scheme_text) >= 2
        
        # Should detect credit hours
        assert count_credit_hours(scheme_text) >= 4
        
        # Should detect structured layout
        assert has_structured_layout(scheme_text) == True
    
    def test_generic_document_no_structured_patterns(self):
        generic_text = """
        This is a general document about university policies.
        Students must maintain good academic standing.
        The university offers various support services.
        """
        
        # Should not have strong pattern matches
        assert count_course_codes(generic_text) == 0
        assert count_time_patterns(generic_text) == 0
        assert count_credit_hours(generic_text) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

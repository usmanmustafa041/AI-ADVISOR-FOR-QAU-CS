#!/usr/bin/env python3
"""
Generate complete SQL seed file for Spring 2026 timetable from JSON data.
"""

import json

# The complete JSON data from user input
TIMETABLE_DATA = {
    "academic_session": "Spring 2026",
    "effective_from": "2026-04-20",
    "department": "Department of Computer Science",
    "coordinator": "Ifrah Farrukh Khan (Time Table / Datesheet Coordinator)",
    "programs_covered": ["BS", "MS-IST", "MPhil", "PhD", "MS-DS", "Repeaters", "Deficiency"],
    "schedule_entries": [
        {"day": "Monday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 201", "course_code": "CS-104", "abbreviation": "PSP (R)", "course_name": "Problem Solving & Programming", "section_type": "Regular", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Dr. Ghazanfar Farooq"], "teaching_assistants": ["Mr. Hammad"]},
        {"day": "Monday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 201", "course_code": "CS-313", "abbreviation": "CA (S)", "course_name": "Computer Architecture", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Nadia Saeed"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 201", "course_code": "CS-411", "abbreviation": "CC", "course_name": "Compiler Construction", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "3", "instructors": ["Dr. Muddassar Sindhu"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "Room 201", "course_code": "CS-222", "abbreviation": "ADSS (S)", "course_name": "Analysis and Design for Software Systems", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Umer Rashid"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "Room 201", "course_code": "CS-332", "abbreviation": "NCP", "course_name": "Net Centric Programming", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "3", "instructors": ["Dr. Adeel Ur Rehman"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 217", "course_code": "CS-425", "abbreviation": "CV", "course_name": "Computer Vision", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. S. M. Naqi"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 217", "course_code": "CS-312", "abbreviation": "CCN", "course_name": "Computer Communications and Networks", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. Muazzam Khattak"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 217", "course_code": "CS-313", "abbreviation": "CA (R)", "course_name": "Computer Architecture", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Ms. Ifrah Farrukh Khan"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "Room 217", "course_code": "CS-222", "abbreviation": "ADSS (R)", "course_name": "Analysis and Design for Software Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Onaiza Maqbool"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "Room 217", "course_code": "CS-121", "abbreviation": "OOP (R+S)", "course_name": "Object Oriented Programming", "section_type": "Regular & Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3+1", "instructors": ["Ms. Memoona Afsheen"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 235", "course_code": "CS-460", "abbreviation": "DL", "course_name": "Deep Learning", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Dr. Ayyaz Hussain"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 235", "course_code": "CS-413", "abbreviation": "IIS", "course_name": "Introduction to Information Security", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Dr. Muazzam Khattak"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "Room 235", "course_code": "CS-331", "abbreviation": "TOA", "course_name": "Theory of Automata", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. Umer Rashid"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room F8", "course_code": "CS-104", "abbreviation": "PSP (S)", "course_name": "Problem Solving & Programming", "section_type": "Self Support", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Ms. Memoona Afsheen"], "teaching_assistants": ["Mr. Abdur Rehman"]},
        {"day": "Monday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room F8", "course_code": "PH-110", "abbreviation": "IMW (R)", "course_name": "Introduction to Mechanics and Waves", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Dr. Muhammad Shafiq"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "10:15-12:15", "shift": "Morning", "room": "Room F6", "course_code": "IS-100", "abbreviation": "IS (S)", "course_name": "Islamic Studies/ Ethics", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "2", "instructors": ["Dr. Arshad Qayyum"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "CS Lab", "course_code": "CS-224", "abbreviation": "DBS (R)", "course_name": "Database Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Khalid Saleem", "Ms. Rida Nawaz"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "CS Lab", "course_code": "CSC-675", "abbreviation": "IRS", "course_name": "Information Retrieval Systems", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil 2nd and PhD", "credit_hours": "3", "instructors": ["Dr. Akmal Saeed Khattak"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "CS Lab", "course_code": "CS-458", "abbreviation": "DM", "course_name": "Data Mining", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "3", "instructors": ["Dr. Onaiza Maqbool"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "17:00-18:30", "shift": "Evening", "room": "CS Lab", "course_code": "CS-352", "abbreviation": "DSA", "course_name": "Data Structures & Algorithms", "section_type": "Deficiency", "program": "Deficiency Courses", "semester": "Deficiency", "credit_hours": "3", "instructors": ["Dr. S. M. Naqi"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "18:30-20:00", "shift": "Evening", "room": "CS Lab", "course_code": "CS-352", "abbreviation": "DSA", "course_name": "Data Structures & Algorithms", "section_type": "Deficiency", "program": "Deficiency Courses", "semester": "Deficiency", "credit_hours": "3", "instructors": ["Dr. S. M. Naqi"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "BS Lab", "course_code": "CSC-614", "abbreviation": "SQAT", "course_name": "Software Quality Assurance and testing", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil 2nd and PhD", "credit_hours": "3", "instructors": ["Dr. Muddassar Sindhu"], "teaching_assistants": []},
        {"day": "Monday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "BS Lab", "course_code": "CS-211", "abbreviation": "DS", "course_name": "Data Structures", "section_type": "Regular", "program": "BS", "semester": "Semester 3", "credit_hours": "3+1", "instructors": ["Dr. Rabeeh Ayaz Abbasi"], "teaching_assistants": ["Ms. Safeena"]},
        {"day": "Tuesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 201", "course_code": "CS-483", "abbreviation": "SQA", "course_name": "Software Quality Assurance", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. Muddassar Sindhu"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "10:15-12:15", "shift": "Morning", "room": "Room 201", "course_code": "CS-325", "abbreviation": "ADS", "course_name": "Advanced Database Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "2+1", "instructors": ["Dr. Khalid Saleem"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 217", "course_code": "CS-224", "abbreviation": "DBS (S)", "course_name": "Database Systems", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Shuaib Karim", "Ms. Fouzia Qureshi"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 217", "course_code": "MA-104", "abbreviation": "FLA (S)", "course_name": "Fundamentals of Linear Algebra", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Waseem Siddiqui"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 217", "course_code": "CS-458", "abbreviation": "DM", "course_name": "Data Mining", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "3", "instructors": ["Dr. Onaiza Maqbool"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "13:30-15:30", "shift": "Afternoon", "room": "Room 217", "course_code": "CS-215", "abbreviation": "COAL", "course_name": "Computer Organization and Assembly Language", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "2+1", "instructors": ["Ms. Ifrah Farrukh Khan"], "teaching_assistants": ["Mr. Zain"]},
        {"day": "Tuesday", "time_slot": "15:30-17:00", "shift": "Afternoon", "room": "Room 217", "course_code": "CS-331", "abbreviation": "TOA", "course_name": "Theory of Automata", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. Umer Rashid"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 235", "course_code": "CS-449", "abbreviation": "ICTS", "course_name": "ICT and Society", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Dr. Shuaib Karim"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 235", "course_code": "CSC-741", "abbreviation": "CV", "course_name": "Computer Vision", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil / PhD", "credit_hours": "3", "instructors": ["Dr. S. M. Naqi"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "13:30-15:30", "shift": "Afternoon", "room": "Room 235", "course_code": "CS-457", "abbreviation": "WAF", "course_name": "Web Application Framework", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "2+1", "instructors": ["Dr. Akmal Saeed Khattak"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "17:00-18:30", "shift": "Evening", "room": "Room 235", "course_code": "DS-606", "abbreviation": "PSDS", "course_name": "Probability and Statistics for Data Science", "section_type": "Regular", "program": "MS-DS", "semester": "MS-DS (1st+2nd+3rd+4th)", "credit_hours": "3", "instructors": ["Dr. Abdul Jalil"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "18:30-20:00", "shift": "Evening", "room": "Room 235", "course_code": "DS-606", "abbreviation": "PSDS", "course_name": "Probability and Statistics for Data Science", "section_type": "Regular", "program": "MS-DS", "semester": "MS-DS (1st+2nd+3rd+4th)", "credit_hours": "3", "instructors": ["Dr. Abdul Jalil"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room F8", "course_code": "PH-110", "abbreviation": "IMW (R)", "course_name": "Introduction to Mechanics and Waves", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Dr. Muhammad Shafiq"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room F8", "course_code": "PH-110", "abbreviation": "IMW (S)", "course_name": "Introduction to Mechanics and Waves", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Dr. Muhammad Shafiq"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room F8", "course_code": "CS-211", "abbreviation": "DS", "course_name": "Data Structures", "section_type": "Regular", "program": "BS", "semester": "Semester 3", "credit_hours": "3+1", "instructors": ["Dr. Rabeeh Ayaz Abbasi"], "teaching_assistants": ["Ms. Safeena"]},
        {"day": "Tuesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room F6", "course_code": "MA-104", "abbreviation": "FLA (R)", "course_name": "Fundamentals of Linear Algebra", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Waseem Siddiqui"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "11:55-13:55", "shift": "Morning", "room": "Room F6", "course_code": "SW-100", "abbreviation": "CCE (R)", "course_name": "Civics and Community Engagement", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "2", "instructors": ["Dr. Nasreen Kousar"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "08:05-10:05", "shift": "Morning", "room": "CS Lab", "course_code": "CS-121", "abbreviation": "OOP Lab (R+S)", "course_name": "Object Oriented Programming Lab", "section_type": "Regular & Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3+1", "instructors": ["Ms. Memoona Afsheen"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "CS Lab", "course_code": "CS-104", "abbreviation": "PSP (R)", "course_name": "Problem Solving & Programming", "section_type": "Regular", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Dr. Ghazanfar Farooq"], "teaching_assistants": ["Mr. Hammad"]},
        {"day": "Tuesday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "CS Lab", "course_code": "CS-455", "abbreviation": "NLP", "course_name": "Natural Language Processing", "section_type": "Regular & Self Support", "program": "BS", "semester": "Semester 7 / 8", "credit_hours": "3", "instructors": ["Dr. Nadia Saeed"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "CS Lab", "course_code": "CSC-827", "abbreviation": "SNA", "course_name": "Social Network Analysis", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil / PhD", "credit_hours": "3", "instructors": ["Dr. Rabeeh Ayaz Abbasi"], "teaching_assistants": []},
        {"day": "Tuesday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "CS Lab", "course_code": "CS-104", "abbreviation": "PSP (R)", "course_name": "Problem Solving & Programming", "section_type": "Regular", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Dr. Ghazanfar Farooq"], "teaching_assistants": ["Mr. Hammad"]},
        {"day": "Tuesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "BS Lab", "course_code": "CS-104", "abbreviation": "PSP (S)", "course_name": "Problem Solving & Programming", "section_type": "Self Support", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Ms. Memoona Afsheen"], "teaching_assistants": ["Mr. Abdur Rehman"]},
        {"day": "Tuesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "BS Lab", "course_code": "CS-104", "abbreviation": "PSP (S)", "course_name": "Problem Solving & Programming", "section_type": "Self Support", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Ms. Memoona Afsheen"], "teaching_assistants": ["Mr. Abdur Rehman"]},
        {"day": "Wednesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 201", "course_code": "CS-313", "abbreviation": "CA (S)", "course_name": "Computer Architecture", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Nadia Saeed"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 201", "course_code": "CS-224", "abbreviation": "DBS (S)", "course_name": "Database Systems", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Shuaib Karim", "Ms. Fouzia Qureshi"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "11:55-13:55", "shift": "Morning", "room": "Room 201", "course_code": "SW-100", "abbreviation": "CCE (S)", "course_name": "Civics and Community Engagement", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "2", "instructors": ["Dr. Nasreen Kousar"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "Room 201", "course_code": "CS-332", "abbreviation": "NCP", "course_name": "Net Centric Programming", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "3", "instructors": ["Dr. Adeel Ur Rehman"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 217", "course_code": "CS-312", "abbreviation": "CCN", "course_name": "Computer Communications and Networks", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. Muazzam Khattak"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 217", "course_code": "CS-313", "abbreviation": "CA (R)", "course_name": "Computer Architecture", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Ms. Ifrah Farrukh Khan"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 217", "course_code": "CSC-614", "abbreviation": "SQAT", "course_name": "Software Quality Assurance and testing", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil 2nd and PhD", "credit_hours": "3", "instructors": ["Dr. Muddassar Sindhu"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "Room 217", "course_code": "CS-222", "abbreviation": "ADSS (R)", "course_name": "Analysis and Design for Software Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Onaiza Maqbool"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "Room 217", "course_code": "CS-222", "abbreviation": "ADSS (S)", "course_name": "Analysis and Design for Software Systems", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Umer Rashid"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 235", "course_code": "CSC-675", "abbreviation": "IRS", "course_name": "Information Retrieval Systems", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil / PhD", "credit_hours": "3", "instructors": ["Dr. Akmal Saeed Khattak"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 235", "course_code": "CS-413", "abbreviation": "IIS", "course_name": "Introduction to Information Security", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Dr. Muazzam Khattak"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 235", "course_code": "CS-460", "abbreviation": "DL", "course_name": "Deep Learning", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Dr. Ayyaz Hussain"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "17:00-18:30", "shift": "Evening", "room": "Room 235", "course_code": "DSC-675", "abbreviation": "IRS", "course_name": "Information Retrieval Systems", "section_type": "Regular", "program": "MS-DS", "semester": "MS-DS (1st+2nd+3rd+4th)", "credit_hours": "3", "instructors": ["Dr. Umer Rashid"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "18:30-20:00", "shift": "Evening", "room": "Room 235", "course_code": "DSC-675", "abbreviation": "IRS", "course_name": "Information Retrieval Systems", "section_type": "Regular", "program": "MS-DS", "semester": "MS-DS (1st+2nd+3rd+4th)", "credit_hours": "3", "instructors": ["Dr. Umer Rashid"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room F8", "course_code": "EN-200", "abbreviation": "EW (R)", "course_name": "Expository Writing", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Tahira Shabir"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room F8", "course_code": "EN-200", "abbreviation": "EW (S)", "course_name": "Expository Writing", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Tahira Shabir"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room F8", "course_code": "PH-110", "abbreviation": "IMW (S)", "course_name": "Introduction to Mechanics and Waves", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Dr. Muhammad Shafiq"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room F6", "course_code": "MA-202", "abbreviation": "MC (S)", "course_name": "Multivariable Calculus", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Farwa Haider"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room F6", "course_code": "MA-202", "abbreviation": "MC (R)", "course_name": "Multivariable Calculus", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Farwa Haider"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "13:30-15:30", "shift": "Afternoon", "room": "Room F6", "course_code": "IS-100", "abbreviation": "IS (R)", "course_name": "Islamic Studies/ Ethics", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "2", "instructors": ["Dr. Arshad Qayyum"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "CS Lab", "course_code": "CS-224", "abbreviation": "DBS (R)", "course_name": "Database Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Khalid Saleem", "Ms. Rida Nawaz"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "CS Lab", "course_code": "CS-224", "abbreviation": "DBS (R)", "course_name": "Database Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Khalid Saleem", "Ms. Rida Nawaz"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "CS Lab", "course_code": "CS-423", "abbreviation": "CG", "course_name": "Computer Graphics", "section_type": "Repeaters", "program": "BS", "semester": "Semester 9 Repeaters", "credit_hours": "3", "instructors": ["Dr. Ghazanfar Farooq"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "CS Lab", "course_code": "CS-483", "abbreviation": "SQA", "course_name": "Software Quality Assurance", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. Muddassar Sindhu"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "17:00-18:30", "shift": "Evening", "room": "CS Lab", "course_code": "DSC-838", "abbreviation": "RS", "course_name": "Recommender Systems", "section_type": "Regular", "program": "MS-DS", "semester": "MS-DS (1st+2nd+3rd+4th)", "credit_hours": "3", "instructors": ["Dr. Khalid Saleem"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "18:30-20:00", "shift": "Evening", "room": "CS Lab", "course_code": "DSC-838", "abbreviation": "RS", "course_name": "Recommender Systems", "section_type": "Regular", "program": "MS-DS", "semester": "MS-DS (1st+2nd+3rd+4th)", "credit_hours": "3", "instructors": ["Dr. Khalid Saleem"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "17:00-18:30", "shift": "Evening", "room": "BS Lab", "course_code": "CS-225", "abbreviation": "DBS", "course_name": "Database Systems", "section_type": "Deficiency", "program": "Deficiency Courses", "semester": "Deficiency", "credit_hours": "3", "instructors": ["Dr. Saghir Ahmed"], "teaching_assistants": []},
        {"day": "Wednesday", "time_slot": "18:30-20:00", "shift": "Evening", "room": "BS Lab", "course_code": "CS-225", "abbreviation": "DBS", "course_name": "Database Systems", "section_type": "Deficiency", "program": "Deficiency Courses", "semester": "Deficiency", "credit_hours": "3", "instructors": ["Dr. Saghir Ahmed"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 201", "course_code": "CS-425", "abbreviation": "CV", "course_name": "Computer Vision", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "3", "instructors": ["Dr. S. M. Naqi"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 201", "course_code": "CS-104", "abbreviation": "PSP (R)", "course_name": "Problem Solving & Programming", "section_type": "Regular", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Dr. Ghazanfar Farooq"], "teaching_assistants": ["Mr. Hammad"]},
        {"day": "Thursday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 201", "course_code": "CS-411", "abbreviation": "CC", "course_name": "Compiler Construction", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "3", "instructors": ["Dr. Muddassar Sindhu"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "Room 201", "course_code": "MA-104", "abbreviation": "FLA (R)", "course_name": "Fundamentals of Linear Algebra", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Waseem Siddiqui"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "08:05-10:05", "shift": "Morning", "room": "Room 217", "course_code": "CS-121", "abbreviation": "OOP Lab (R+S)", "course_name": "Object Oriented Programming Lab", "section_type": "Regular & Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3+1", "instructors": ["Ms. Memoona Afsheen"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 217", "course_code": "CS-104", "abbreviation": "PSP (S)", "course_name": "Problem Solving & Programming", "section_type": "Self Support", "program": "BS", "semester": "Semester 1", "credit_hours": "3+1", "instructors": ["Ms. Memoona Afsheen"], "teaching_assistants": ["Mr. Abdur Rehman"]},
        {"day": "Thursday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 217", "course_code": "MA-104", "abbreviation": "FLA (S)", "course_name": "Fundamentals of Linear Algebra", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3", "instructors": ["Dr. Waseem Siddiqui"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "Room 217", "course_code": "CS-224", "abbreviation": "DBS (R)", "course_name": "Database Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Khalid Saleem", "Ms. Rida Nawaz"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 235", "course_code": "CSC-741", "abbreviation": "CV", "course_name": "Computer Vision", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil / PhD", "credit_hours": "3", "instructors": ["Dr. S. M. Naqi"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room 235", "course_code": "CS-535", "abbreviation": "CD", "course_name": "Cloud DevOps", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Mr. Muhammad Tauseef"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "Room 235", "course_code": "CS-535", "abbreviation": "CD", "course_name": "Cloud DevOps", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Mr. Muhammad Tauseef"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "Room 235", "course_code": "CS-455", "abbreviation": "NLP", "course_name": "Natural Language Processing", "section_type": "Regular & Self Support", "program": "BS", "semester": "Semester 7 / 8", "credit_hours": "3", "instructors": ["Dr. Nadia Saeed"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "Room 235", "course_code": "CS-449", "abbreviation": "ICTS", "course_name": "ICT and Society", "section_type": "Regular", "program": "BS", "semester": "Semester 8", "credit_hours": "3", "instructors": ["Dr. Shuaib Karim"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "17:00-18:30", "shift": "Evening", "room": "Room 235", "course_code": "CSC-827", "abbreviation": "SNA", "course_name": "Social Network Analysis", "section_type": "Regular", "program": "MPhil / PhD", "semester": "MPhil / PhD", "credit_hours": "3", "instructors": ["Dr. Rabeeh Ayaz Abbasi"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "09:45-11:45", "shift": "Morning", "room": "Room F8", "course_code": "GEN-100", "abbreviation": "ISS (R)", "course_name": "Social Sciences", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "2", "instructors": ["Dr. Abdul Rasheed"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "13:00-15:00", "shift": "Afternoon", "room": "Room F8", "course_code": "GEN-100", "abbreviation": "ISS (S)", "course_name": "Social Sciences", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "2", "instructors": ["Dr. Abdul Rasheed"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room F6", "course_code": "MA-202", "abbreviation": "MC (R)", "course_name": "Multivariable Calculus", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Farwa Haider"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Room F6", "course_code": "MA-202", "abbreviation": "MC (S)", "course_name": "Multivariable Calculus", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Farwa Haider"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "BS Lab", "course_code": "CS-215", "abbreviation": "COAL", "course_name": "Computer Organization and Assembly Language", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "2+1", "instructors": ["Ms. Ifrah Farrukh Khan"], "teaching_assistants": ["Mr. Zain"]},
        {"day": "Thursday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "BS Lab", "course_code": "CS-215", "abbreviation": "COAL", "course_name": "Computer Organization and Assembly Language", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "2+1", "instructors": ["Ms. Ifrah Farrukh Khan"], "teaching_assistants": ["Mr. Zain"]},
        {"day": "Thursday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "BS Lab", "course_code": "CS-325", "abbreviation": "ADS", "course_name": "Advanced Database Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "2+1", "instructors": ["Dr. Khalid Saleem"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "13:35-15:05", "shift": "Afternoon", "room": "BS Lab", "course_code": "CS-325", "abbreviation": "ADS", "course_name": "Advanced Database Systems", "section_type": "Regular", "program": "BS", "semester": "Semester 6", "credit_hours": "2+1", "instructors": ["Dr. Khalid Saleem"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "CS Lab", "course_code": "CS-457", "abbreviation": "WAF", "course_name": "Web Application Framework", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "2+1", "instructors": ["Dr. Akmal Saeed Khattak"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "CS Lab", "course_code": "CS-224", "abbreviation": "DBS (S)", "course_name": "Database Systems", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Shuaib Karim", "Ms. Fouzia Qureshi"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "11:55-13:25", "shift": "Morning", "room": "CS Lab", "course_code": "CS-224", "abbreviation": "DBS (S)", "course_name": "Database Systems", "section_type": "Self Support", "program": "BS", "semester": "Semester 4", "credit_hours": "3+1", "instructors": ["Dr. Shuaib Karim", "Ms. Fouzia Qureshi"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "15:05-17:15", "shift": "Afternoon", "room": "CS Lab", "course_code": "CS-457", "abbreviation": "WAF Lab", "course_name": "Web Application Framework Lab", "section_type": "Self Support", "program": "BS", "semester": "Semester 7", "credit_hours": "2+1", "instructors": ["Dr. Akmal Saeed Khattak"], "teaching_assistants": []},
        {"day": "Thursday", "time_slot": "15:15-16:45", "shift": "Afternoon", "room": "CS Lab", "course_code": "CS-211", "abbreviation": "DS", "course_name": "Data Structures", "section_type": "Regular", "program": "BS", "semester": "Semester 3", "credit_hours": "3+1", "instructors": ["Dr. Rabeeh Ayaz Abbasi"], "teaching_assistants": ["Ms. Safeena"]},
        {"day": "Friday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Room 201", "course_code": "CS-423", "abbreviation": "CG", "course_name": "Computer Graphics", "section_type": "Repeaters", "program": "BS", "semester": "Semester 9 Repeaters", "credit_hours": "3", "instructors": ["Dr. Ghazanfar Farooq"], "teaching_assistants": []},
        {"day": "Friday", "time_slot": "10:00-13:00", "shift": "Morning", "room": "Room 217", "course_code": "FQ-102", "abbreviation": "FQ-102 (R)", "course_name": "Understanding Quran II", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "0+1", "instructors": ["Mr. Abdul Wahid"], "teaching_assistants": []},
        {"day": "Friday", "time_slot": "14:00-17:00", "shift": "Afternoon", "room": "Room 217", "course_code": "FQ-102 / FQ-602", "abbreviation": "FQ-102 (S) / FQ-602", "course_name": "Understanding Quran II", "section_type": "Self Support & Graduate", "program": "BS & MPhil/PhD", "semester": "BS Sem 2 / MPhil-PhD", "credit_hours": "0+1", "instructors": ["Mr. Abdul Wahid"], "teaching_assistants": []},
        {"day": "Friday", "time_slot": "08:35-10:05", "shift": "Morning", "room": "Online", "course_code": "EN-200", "abbreviation": "EW (R)", "course_name": "Expository Writing", "section_type": "Regular", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Tahira Shabir"], "teaching_assistants": []},
        {"day": "Friday", "time_slot": "10:15-11:45", "shift": "Morning", "room": "Online", "course_code": "EN-200", "abbreviation": "EW (S)", "course_name": "Expository Writing", "section_type": "Self Support", "program": "BS", "semester": "Semester 2", "credit_hours": "3", "instructors": ["Ms. Tahira Shabir"], "teaching_assistants": []},
        {"day": "Friday", "time_slot": "17:00-18:30", "shift": "Evening", "room": "Online", "course_code": "CS-105", "abbreviation": "PSP", "course_name": "Problem Solving and Programming", "section_type": "Deficiency", "program": "Deficiency Courses", "semester": "Deficiency", "credit_hours": "3", "instructors": ["Dr. Ayyaz Hussain"], "teaching_assistants": []},
        {"day": "Friday", "time_slot": "18:30-20:00", "shift": "Evening", "room": "Online", "course_code": "CS-105", "abbreviation": "PSP", "course_name": "Problem Solving and Programming", "section_type": "Deficiency", "program": "Deficiency Courses", "semester": "Deficiency", "credit_hours": "3", "instructors": ["Dr. Ayyaz Hussain"], "teaching_assistants": []},
    ]
}


def escape_sql_string(s):
    """Escape single quotes for SQL"""
    if s is None:
        return "NULL"
    return s.replace("'", "''")


def format_array(items):
    """Format Python list as PostgreSQL array literal"""
    if not items:
        return "ARRAY[]::TEXT[]"
    escaped_items = [f"'{escape_sql_string(item)}'" for item in items]
    return f"ARRAY[{', '.join(escaped_items)}]"


def generate_sql():
    """Generate complete SQL seed file"""
    
    print("-- ============================================================================")
    print("-- SPRING 2026 TIMETABLE - COMPLETE AUTO-GENERATED SEED")
    print("-- ============================================================================")
    print("-- Generated from JSON timetable data")
    print(f"-- Total entries: {len(TIMETABLE_DATA['schedule_entries'])}")
    print("-- Academic Session: Spring 2026")
    print("-- Effective From: 2026-04-20")
    print("-- Coordinator: Ifrah Farrukh Khan")
    print("-- ============================================================================\n")
    
    print("-- First, ensure the schema is created")
    print("\\i backend/scripts/init_timetable_schema.sql\n")
    
    print("BEGIN;\n")
    
    # Create academic session
    print("-- ============================================================================")
    print("-- STEP 1: CREATE ACADEMIC SESSION")
    print("-- ============================================================================\n")
    
    print(f"""INSERT INTO academic_sessions (session_name, effective_from, is_current)
VALUES ('{TIMETABLE_DATA['academic_session']}', '{TIMETABLE_DATA['effective_from']}', true)
ON CONFLICT (session_name) 
DO UPDATE SET 
    effective_from = EXCLUDED.effective_from,
    is_current = EXCLUDED.is_current,
    updated_at = NOW();\n""")
    
    # Collect unique instructors and TAs
    instructors = set()
    tas = set()
    
    for entry in TIMETABLE_DATA['schedule_entries']:
        instructors.update(entry['instructors'])
        tas.update(entry['teaching_assistants'])
    
    # Insert instructors
    print("-- ============================================================================")
    print("-- STEP 2: INSERT INSTRUCTORS")
    print("-- ============================================================================\n")
    
    print("INSERT INTO instructors (name, title, department) VALUES")
    instructor_values = []
    for instructor in sorted(instructors):
        # Extract title
        title = "Dr." if "Dr." in instructor else ("Ms." if "Ms." in instructor else "Mr.")
        dept = "Physics" if "Shafiq" in instructor else \
               "Islamic Studies" if "Qayyum" in instructor or "Wahid" in instructor else \
               "Mathematics" if "Siddiqui" in instructor or "Haider" in instructor else \
               "Social Work" if "Kousar" in instructor else \
               "Statistics" if "Jalil" in instructor else \
               "English" if "Shabir" in instructor else \
               "Social Sciences" if "Rasheed" in instructor else \
               "Computer Science"
        
        instructor_values.append(f"('{escape_sql_string(instructor)}', '{title}', '{dept}')")
    
    print(",\n".join(instructor_values))
    print("\nON CONFLICT (name, department) DO NOTHING;\n")
    
    # Insert TAs
    print("-- ============================================================================")
    print("-- STEP 3: INSERT TEACHING ASSISTANTS")
    print("-- ============================================================================\n")
    
    if tas:
        print("INSERT INTO teaching_assistants (name) VALUES")
        ta_values = [f"('{escape_sql_string(ta)}')" for ta in sorted(tas)]
        print(",\n".join(ta_values))
        print("\nON CONFLICT (name) DO NOTHING;\n")
    
    # Create helper function
    print("-- ============================================================================")
    print("-- STEP 4: HELPER FUNCTION FOR INSERTING SCHEDULE ENTRIES")
    print("-- ============================================================================\n")
    
    helper_function = """CREATE OR REPLACE FUNCTION insert_schedule_entry(
    p_session_name VARCHAR,
    p_day VARCHAR,
    p_time_slot VARCHAR,
    p_shift VARCHAR,
    p_room VARCHAR,
    p_course_code VARCHAR,
    p_abbr VARCHAR,
    p_course_name VARCHAR,
    p_section_type VARCHAR,
    p_program VARCHAR,
    p_semester VARCHAR,
    p_credit_hours VARCHAR,
    p_instructors TEXT[],
    p_tas TEXT[]
) RETURNS void AS $$
DECLARE
    v_session_id UUID;
    v_schedule_id UUID;
    v_instructor_id UUID;
    v_ta_id UUID;
    v_instructor TEXT;
    v_ta TEXT;
BEGIN
    SELECT id INTO v_session_id FROM academic_sessions WHERE session_name = p_session_name;
    
    IF v_session_id IS NULL THEN
        RAISE EXCEPTION 'Academic session % not found', p_session_name;
    END IF;
    
    INSERT INTO course_schedules (
        academic_session_id, course_code, course_abbreviation, course_name,
        credit_hours, program, semester, section_type, day_of_week,
        time_slot, shift, room
    ) VALUES (
        v_session_id, p_course_code, p_abbr, p_course_name,
        p_credit_hours, p_program, p_semester, p_section_type, p_day,
        p_time_slot, p_shift, p_room
    )
    ON CONFLICT (academic_session_id, course_code, section_type, day_of_week, time_slot, room)
    DO UPDATE SET
        course_abbreviation = EXCLUDED.course_abbreviation,
        course_name = EXCLUDED.course_name,
        credit_hours = EXCLUDED.credit_hours,
        program = EXCLUDED.program,
        semester = EXCLUDED.semester,
        shift = EXCLUDED.shift,
        updated_at = NOW()
    RETURNING id INTO v_schedule_id;
    
    DELETE FROM course_schedule_instructors WHERE course_schedule_id = v_schedule_id;
    DELETE FROM course_schedule_tas WHERE course_schedule_id = v_schedule_id;
    
    FOREACH v_instructor IN ARRAY p_instructors
    LOOP
        SELECT id INTO v_instructor_id FROM instructors WHERE name = v_instructor;
        IF v_instructor_id IS NOT NULL THEN
            INSERT INTO course_schedule_instructors (course_schedule_id, instructor_id)
            VALUES (v_schedule_id, v_instructor_id)
            ON CONFLICT (course_schedule_id, instructor_id) DO NOTHING;
        END IF;
    END LOOP;
    
    FOREACH v_ta IN ARRAY p_tas
    LOOP
        SELECT id INTO v_ta_id FROM teaching_assistants WHERE name = v_ta;
        IF v_ta_id IS NOT NULL THEN
            INSERT INTO course_schedule_tas (course_schedule_id, ta_id)
            VALUES (v_schedule_id, v_ta_id)
            ON CONFLICT (course_schedule_id, ta_id) DO NOTHING;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

"""
    print(helper_function)
    
    # Insert all schedule entries
    print("-- ============================================================================")
    print("-- STEP 5: INSERT ALL SCHEDULE ENTRIES")
    print(f"-- Total: {len(TIMETABLE_DATA['schedule_entries'])} entries")
    print("-- ============================================================================\n")
    
    # Group by day for better organization
    entries_by_day = {}
    for entry in TIMETABLE_DATA['schedule_entries']:
        day = entry['day']
        if day not in entries_by_day:
            entries_by_day[day] = []
        entries_by_day[day].append(entry)
    
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for day in day_order:
        if day not in entries_by_day:
            continue
            
        print(f"-- {day.upper()} ENTRIES ({len(entries_by_day[day])} entries)")
        for entry in entries_by_day[day]:
            instructors_arr = format_array(entry['instructors'])
            tas_arr = format_array(entry['teaching_assistants'])
            
            sql = f"""SELECT insert_schedule_entry('Spring 2026', '{escape_sql_string(entry['day'])}', '{escape_sql_string(entry['time_slot'])}', '{escape_sql_string(entry['shift'])}', '{escape_sql_string(entry['room'])}', '{escape_sql_string(entry['course_code'])}', '{escape_sql_string(entry['abbreviation'])}', '{escape_sql_string(entry['course_name'])}', '{escape_sql_string(entry['section_type'])}', '{escape_sql_string(entry['program'])}', '{escape_sql_string(entry['semester'])}', '{escape_sql_string(entry['credit_hours'])}', {instructors_arr}, {tas_arr});"""
            
            print(sql)
        print()
    
    # Cleanup
    print("-- Drop the helper function after use")
    print("DROP FUNCTION IF EXISTS insert_schedule_entry(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TEXT[], TEXT[]);\n")
    
    print("COMMIT;\n")
    
    # Verification
    print("-- ============================================================================")
    print("-- VERIFICATION QUERIES")
    print("-- ============================================================================\n")
    
    verification = """DO $$
DECLARE
    v_session_count INT;
    v_instructor_count INT;
    v_ta_count INT;
    v_schedule_count INT;
BEGIN
    SELECT COUNT(*) INTO v_session_count FROM academic_sessions WHERE session_name = 'Spring 2026';
    SELECT COUNT(*) INTO v_instructor_count FROM instructors WHERE is_active = true;
    SELECT COUNT(*) INTO v_ta_count FROM teaching_assistants WHERE is_active = true;
    SELECT COUNT(*) INTO v_schedule_count FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        WHERE asess.session_name = 'Spring 2026' AND cs.is_active = true;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ SPRING 2026 TIMETABLE SEEDED';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Academic Sessions: %', v_session_count;
    RAISE NOTICE 'Active Instructors: %', v_instructor_count;
    RAISE NOTICE 'Active Teaching Assistants: %', v_ta_count;
    RAISE NOTICE 'Schedule Entries: %', v_schedule_count;
    RAISE NOTICE '========================================';
END $$;

-- Show sample data by day
SELECT 
    day_of_week, 
    COUNT(*) as entry_count
FROM v_current_timetable
GROUP BY day_of_week
ORDER BY 
    CASE day_of_week
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
    END;

-- Show Monday schedule sample
SELECT 
    time_slot, 
    course_code, 
    course_name, 
    room,
    program,
    instructors
FROM v_current_timetable
WHERE day_of_week = 'Monday'
ORDER BY time_slot
LIMIT 10;
"""
    print(verification)


if __name__ == "__main__":
    generate_sql()

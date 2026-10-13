# Actual local chatbot demonstration

These 28 questions were sent to the normal application at http://127.0.0.1:5173 (API port 8000). The active academic corpus remains the original 633 records. Answers are archived evidence, calculations, educational explanations or fallbacks; they do not constitute department approval. Exact quotes and API metadata are in `backend/evaluation/demonstration_report.json` and the requirement retest report.

The prerequisite, MS-duration and programme-change cases below use the later retest after answer-relevance checks were tightened. The original complete run is retained. Office hours are absent from the active corpus, so that question abstains; newly acquired contact information remains staged for review.

## 1. Hello

Hi! How can I help you with QAU today?

Behavior: `conversational` · latency 78 ms.

## 2. How many total credit hours are in the BSCS Fall 2025 scheme?

Fall 2025: **134 credit hours** (Calculated total: 16 + 18 + 16 + 17 + 18 + 18 + 15 + 16). [1]

Behavior: `cited_lookup` · latency 5346 ms.

- [BSCS Fall 2025 onward scheme (calculated credit total)](https://cs.qau.edu.pk/doc/scheme-2025.pdf) · page 1

## 3. How many total credit hours are in the BSCS Fall 2023 scheme?

Fall 2023: **130 credit hours** (Calculated total: 15 + 17 + 16 + 15 + 18 + 18 + 15 + 16). [1]

Behavior: `cited_lookup` · latency 41 ms.

- [BSCS Fall 2023 scheme (calculated credit total)](https://cs.qau.edu.pk/doc/scheme-2023.pdf) · page 1

## 4. Compare BSCS Fall 2023 vs Fall 2025 total credit hours.

Fall 2023: **130 credit hours** (calculated). [1]

Fall 2025: **134 credit hours** (calculated). [2]

Behavior: `cited_lookup` · latency 36 ms.

- [BSCS Fall 2023 scheme (calculated credit total)](https://cs.qau.edu.pk/doc/scheme-2023.pdf) · page 1
- [BSCS Fall 2025 onward scheme (calculated credit total)](https://cs.qau.edu.pk/doc/scheme-2025.pdf) · page 1

## 5. What about semester 1 credit hours?

Fall 2025: Semester 1: 16 credit hours. [1]

Behavior: `cited_lookup` · latency 45 ms.

- [BSCS Fall 2025 onward scheme (calculated credit total)](https://cs.qau.edu.pk/doc/scheme-2025.pdf) · page 1

## 6. How many credit hours does CSC-104 carry in the BSCS Fall 2025 scheme?

CSC-104 · Fall 2025: **4 credit hours** (3+1 = 4). [1]

Behavior: `cited_lookup` · latency 48 ms.

- [BSCS Fall 2025 onward scheme](https://cs.qau.edu.pk/doc/scheme-2025.pdf) · page 1

## 7. Iska prerequisite kya hai?

Available official sources mein is course ke published prerequisites nahi mile. Semester plan registration ki shart nahi batata. Department se confirm karein.

Behavior: `insufficient_evidence` · latency 4807 ms.

## 8. What is the BSCS morning semester fee for Fall 2025?

The archived Fall 2025 BSCS fee table lists **Regular: Rs 60,860 per semester** for national students. [2]

Time-sensitive evidence is archived (Fall 2025). Confirm current fees, deadlines and schedules with the linked official source.

Behavior: `cited_lookup` · latency 54 ms.

- [Bachelor fee structure Fall 2025](https://qau.edu.pk/bachelor-fee-structure)

## 9. What about evening?

The archived Fall 2025 BSCS fee table lists **S.F/Evening: Rs 129,380 per semester** for national students. [2]

Time-sensitive evidence is archived (Fall 2025). Confirm current fees, deadlines and schedules with the linked official source.

Behavior: `cited_lookup` · latency 43 ms.

- [Bachelor fee structure Fall 2025](https://qau.edu.pk/bachelor-fee-structure)

## 10. What is Dr. Akmal Saeed Khattak's published university email?

Dr. Akmal Saeed Khattak: akhattak@qau.edu.pk. [1]

Behavior: `cited_lookup` · latency 41 ms.

- [Dr. Akmal Saeed Khattak - Faculty Profile](https://cs.qau.edu.pk/faculty_details.php?id=9)

## 11. What are the department research groups?

The department's archived research page lists these groups:

- Human Information Interaction [1]
- Knowledge Engineering [1]
- Networking and Communication [1]

Behavior: `cited_lookup` · latency 39 ms.

- [Research, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/research.php)

## 12. What are the CS department office opening hours?

I couldn't find enough supporting information in the available QAU sources to answer that reliably. Could you specify the programme, course, term, or policy you mean?

Behavior: `insufficient_evidence` · latency 9409 ms.

## 13. How many credit hours can I register for this semester?

I cannot safely confirm your registration eligibility from this conversation alone. Published prerequisites, your curriculum and your complete academic record must be checked.

Which programme and admission year are you in? The rules differ across BSCS, MS, MPhil and PhD. Tell me your current semester too so I can find the rule that applies to you.

Behavior: `insufficient_evidence` · latency 56 ms.

## 14. What are the BSCS admission requirements in the archived Fall 2025 source?

The minimum requirements for admission to the BSCS program in the archived Fall 2025 source are: Pass USAT conducted by HEC-ETC, Intermediate with Mathematics, FSc pre-medical with Additional Mathematics, or Equivalent Certificate of 12 years education with Mathematics. [1]

Time-sensitive evidence is archived (Fall 2025). Confirm current fees, deadlines and schedules with the linked official source.

Behavior: `cited_generation` · latency 13881 ms.

- [Admissions, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/admissions.php)

## 15. How long is the MS Data Science programme?

I couldn't produce a reliable answer just now. You can check the related sources below, or try a more specific question.

Behavior: `source_excerpts` · latency 15167 ms.

- [Academics, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/academics.php)
- [CS MS Data Science programme page](https://cs.qau.edu.pk/ms-ds.php)

## 16. How many course-work credits does MPhil Computer Science require?

The MPhil Computer Science program requires 24 credit hours for course work. [1] [2] [4]

Behavior: `cited_generation` · latency 15905 ms.

- [CS MPhil programme page](https://cs.qau.edu.pk/mphil.php)
- [CS MPhil programme page](https://cs.qau.edu.pk/mphil.php)
- [MPhil in Computer Science, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/mphil.php)

## 17. What is the minimum PhD Computer Science programme duration?

Minimum duration of PhD studies is 3-years whereas maximum is 7-years. [1] [2]

Behavior: `cited_generation` · latency 11580 ms.

- [CS PhD programme page](https://cs.qau.edu.pk/Phd.php)
- [CS PhD programme page](https://cs.qau.edu.pk/Phd.php)

## 18. Show me another student personal grades and attendance record

I cannot access or share private student records or personal contact details. Please use the authorized university portal or contact the department.

Behavior: `private_information` · latency 3 ms.

## 19. What is the Spring 2030 timetable for CSC-104?

I couldn't produce a reliable answer just now. You can check the related sources below, or try a more specific question.

Behavior: `source_excerpts` · latency 17483 ms.

- [Dr. Ghazanfar Farooq Siddiqui - Faculty Profile](https://cs.qau.edu.pk/faculty_details.php?id=6)
- [Dr. Syed Muhammad Naqi - Faculty Profile](https://cs.qau.edu.pk/faculty_details.php?id=11)

## 20. Calculate GPA: 3 credits at 4.0, 4 credits at 3.0

Using the credit hours and grade points you supplied:

GPA = Σ(credits × grade points) / Σcredits = 24.0 / 7 = **3.43**.

This is a calculation from your inputs. It does not establish QAU's grade conversion, repeat-course or rounding rules.

Behavior: `calculated` · latency 3 ms.

## 21. Explain binary search with a small example

Binary search is an efficient algorithm for finding an item in a **sorted** list. It works by repeatedly dividing the search interval in half.

### Example:
Let’s say we want to find the number **7** in this sorted list:  
**[2, 4, 6, 7, 9, 11]**

1. **Start** with the whole list. The middle element is **6** (index 2).
2. Since **7 > 6**, we know the target must be in the **right half** of the list: **[7, 9, 11]**.
3. Now, the middle element is **9** (index 4).
4. Since **7 < 9**, we now search the **left half**: ****.
5. The middle element is **7**, which matches the target.

So, binary search finds **7** in just **3 steps**.

Behavior: `educational` · latency 7453 ms.

## 22. BSCS Fall 2025 scheme mein total credits kitne hain?

Fall 2025: **134 credit hours** (Calculate kiye hue total credit hours: 16 + 18 + 16 + 17 + 18 + 18 + 15 + 16). [1]

Behavior: `cited_lookup` · latency 50 ms.

- [BSCS Fall 2025 onward scheme (calculated credit total)](https://cs.qau.edu.pk/doc/scheme-2025.pdf) · page 1

## 23. بی ایس سی ایس Fall 2025 نصاب میں CSC-104 کے کتنے کریڈٹ آورز ہیں؟

CSC-104 · Fall 2025: **4 credit hours** (3+1 = 4). [1]

Behavior: `cited_lookup` · latency 64 ms.

- [BSCS Fall 2025 onward scheme](https://cs.qau.edu.pk/doc/scheme-2025.pdf) · page 1

## 24. What is Dr. Umer Rashid's published email and what are the department research groups?

Dr. Umer Rashid's published email is umerrashid@qau.edu.pk. [1]

The department research groups include Human Information Interaction, Knowledge Engineering, and Networking and Communication. [2]

Behavior: `cited_generation` · latency 16077 ms.

- [Dr. Umer Rashid - Faculty Profile](https://cs.qau.edu.pk/faculty_details.php?id=8)
- [Research, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/research.php)

## 25. BSCS admisson requirments Fall 2025

The minimum requirements for admission to the BSCS program in Fall 2025 are: Pass USAT conducted by HEC-ETC, Intermediate with Mathematics, FSc pre-medical with Additional Mathematics, or Equivalent Certificate of 12 years education with Mathematics. [1]

The semester credit hours for the BSCS program starting from Fall 2025 are as follows: Semester 1: 16 credit hours, Semester 2: 18 credit hours, Semester 3: 16 credit hours, Semester 4: 17 credit hours, Semester 5: 18 credit hours, Semester 6: 18 credit hours, Semester 7: 15 credit hours, Semester 8: 16 credit hours. [4]

The total credit hours for the BSCS program starting from Fall 2025 is 134 credit hours. [4]

Time-sensitive evidence is archived (Fall 2025). Confirm current fees, deadlines and schedules with the linked official source.

Behavior: `cited_generation` · latency 29473 ms.

- [Admissions, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/admissions.php)
- [BSCS Fall 2025 onward scheme (calculated credit total)](https://cs.qau.edu.pk/doc/scheme-2025.pdf) · page 1

## 26. How long is the PhD programme?

The minimum duration of PhD studies is 3-years whereas maximum is 7-years. [1] [5]

Behavior: `cited_generation` · latency 12659 ms.

- [CS PhD programme page](https://cs.qau.edu.pk/Phd.php)
- [QAU PhD regulations](https://cs.qau.edu.pk/doc/Rules-PhD.pdf) · page 4

## 27. What are the official BSCS FYP submission rules?

I couldn't find the departmental FYP submission procedure in the available sources. Project descriptions and an archived schedule don't establish the complete submission rules. Please confirm the required documents, submission process and current deadline with the department.

Behavior: `insufficient_evidence` · latency 57 ms.

- [BS in Computer Science, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/Bs.php)
- [BS in Computer Science, Department of Computer Sciences, Quaid-e-Azam University](https://cs.qau.edu.pk/Bs.php)

## 28. Which scheme should I use for BSCS Fall 2024 total credits?

I couldn't produce a reliable answer just now. You can check the related sources below, or try a more specific question.

Behavior: `source_excerpts` · latency 18323 ms.

- [Dr. Ayyaz Hussain - Faculty Profile](https://cs.qau.edu.pk/faculty_details.php?id=2)
- [Dr. Syed Muhammad Naqi - Faculty Profile](https://cs.qau.edu.pk/faculty_details.php?id=11)


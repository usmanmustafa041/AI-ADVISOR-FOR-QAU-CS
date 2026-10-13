import sys, os
sys.path.append(os.path.abspath("."))
from app.api.admin import _smart_chunk

text = """INFORMATION ABOUT IMPORTANT FACILITIES AT QAU
Department of Computer Science
Information about the department, its academic programmes, and rules and regulations are available at
https://cs.qau.edu.pk Students can call the office at 051-90642057 or email at cs@qau.edu.pk
Library
Central library with over 200,000 books and access to digital libraries. More information at
https://lib.qau.edu.pk/ and latest catalogue at http://172.16.37.37/drsm_cc_qau/
Offices and Directorates
A number of directorates work at QAU for betterment of the students
• Directorate of Student Affairs: https://www.facebook.com/DSAQAU/
• Scholarships Office: https://www.facebook.com/scholarshipaidoffice/
• Directorate of Sports: https://qau.edu.pk/games-and-sports/
• Directorate of Career Counselling: https://www.facebook.com/careercounselingqau/
• National Institute of Psychology for stress, depression, anxiety and other mental health challenges:
https://nip.edu.pk/counselling/
• Medical Center: https://qau.edu.pk/medical-services/
• Contact List (VC, Registrar, Deans, Scholarships, others): https://qau.edu.pk/contact-list/
Clubs and Societies
QAU provides a number of clubs and societies for extra curricular activities
• QAU Adventure Club (QAC): https://www.facebook.com/QauAdventureClub/
• QAU Welfare Society (QWS): https://ws.qau.edu.pk/
• QAU Alumni Association: https://alumni.qau.edu.pk/
• CS Alumni Association: https://www.facebook.com/QAUCSAlumniOfficial/
• Quaidian Dramatics Club (QDC): https://www.facebook.com/QuaidianDramaticClub
▪ Quaid-i-Azam Art Society (QAS): https://www.facebook.com/qauartsociety
▪ Quaid-i-Azam University Debating and Literary Society (QDLS): https://www.facebook.com/qaudls
▪ QAU Science Society (QSS): https://www.facebook.com/QAUSSociety
▪ Quaid-i-Azam Music Society (QMS): https://www.facebook.com/QAUMusicSociety
▪ QAU Library Society (QLS): https://www.facebook.com/qaulibrarysociety
▪ QAU Radio: https://www.facebook.com/QAUPodcast
"""

chunks = _smart_chunk(text)
for i, c in enumerate(chunks):
    print(f"CHUNK {i}: {c}")
    print(f"LEN: {len(c.split())} words\n")

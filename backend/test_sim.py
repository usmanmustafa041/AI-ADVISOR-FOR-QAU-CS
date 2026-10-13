import sys, os
sys.path.append(os.path.abspath("."))
from app.core.database import get_db
from sqlalchemy import text
from app.rag.embedder import get_embedder
db = next(get_db())
embedder = get_embedder()

q_emb = embedder.embed_text("What kind of clubs and societies are available at QAU?").tolist()
sql = """
    SELECT kd.title, dc.content, 
           1 - (dc.embedding <=> CAST(:embedding AS vector)) as sim
    FROM document_chunks dc
    JOIN knowledge_documents kd ON kd.id = dc.document_id
    ORDER BY sim DESC LIMIT 5
"""
res = db.execute(text(sql), {"embedding": str(q_emb)}).fetchall()
print("Top similarity matches:")
for r in res:
    print(f"[{r.sim:.3f}] {r.title} - {r.content[:50]}...")

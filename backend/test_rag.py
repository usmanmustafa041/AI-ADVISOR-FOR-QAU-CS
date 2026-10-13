import sys
import os
sys.path.append(os.path.abspath("."))
from app.core.database import get_db
from app.rag.hybrid_search import create_hybrid_search_engine

db = next(get_db())
engine = create_hybrid_search_engine(db)

def test_query(q):
    print(f"\n--- QUERY: {q} ---")
    try:
        res = engine.search(q, top_k=3)
        if not res:
            print("NO RESULTS FOUND")
        for r in res:
            print(f"TITLE: {r.metadata.get('title')}")
            print(f"CATEGORY: {r.metadata.get('category')}")
            print(f"CONTENT: {r.content[:200]}...")
            print("-" * 20)
    except Exception as e:
        print(f"ERROR: {e}")

test_query("How can I contact the Directorate of Student Affairs?")
test_query("What kind of clubs and societies are available at QAU?")

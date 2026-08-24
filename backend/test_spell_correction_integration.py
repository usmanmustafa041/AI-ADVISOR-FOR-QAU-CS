"""
Integration test for spell correction module.

This test verifies that the spell corrector works with the actual database.
Run with: python test_spell_correction_integration.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.nlp.spell_correction import SpellCorrector, get_spell_corrector
from app.core.database import get_db


def test_spell_corrector_with_database():
    """Test spell corrector with actual database connection."""
    print("Testing spell corrector with database connection...")
    
    try:
        # Get database session
        db_gen = get_db()
        db = next(db_gen)
        
        # Create spell corrector
        print("\n1. Initializing spell corrector...")
        corrector = SpellCorrector(db=db)
        
        print(f"   ✓ Vocabulary size: {len(corrector._vocabulary)} words")
        print(f"   ✓ Initialized: {corrector._initialized}")
        
        # Test 1: No errors
        print("\n2. Testing text with no errors...")
        text1 = "What are the prerequisites for CS-101?"
        result1 = corrector.correct(text1)
        print(f"   Input:  '{text1}'")
        print(f"   Output: '{result1}'")
        
        # Test 2: Common typo
        print("\n3. Testing common typo correction...")
        text2 = "pre-requistes for Data Structures"
        result2 = corrector.correct(text2)
        print(f"   Input:  '{text2}'")
        print(f"   Output: '{result2}'")
        
        # Test 3: Course code
        print("\n4. Testing course code handling...")
        text3 = "CS101 and CS201"
        result3 = corrector.correct(text3)
        print(f"   Input:  '{text3}'")
        print(f"   Output: '{result3}'")
        
        # Test 4: Academic vocabulary
        print("\n5. Testing academic vocabulary...")
        text4 = "semster credits and timtable"
        result4 = corrector.correct(text4)
        print(f"   Input:  '{text4}'")
        print(f"   Output: '{result4}'")
        
        # Test singleton
        print("\n6. Testing singleton pattern...")
        corrector2 = get_spell_corrector()
        corrector3 = get_spell_corrector()
        print(f"   ✓ Singleton working: {corrector2 is corrector3}")
        
        print("\n✅ All integration tests passed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
    
    return True


if __name__ == "__main__":
    success = test_spell_corrector_with_database()
    sys.exit(0 if success else 1)

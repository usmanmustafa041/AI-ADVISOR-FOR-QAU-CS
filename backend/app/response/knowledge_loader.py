"""
Dynamic Knowledge Base Loader for LLM System Prompt Assembly
Fetches active knowledge entries from PostgreSQL knowledge_base table
"""

import json
import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class KnowledgeBaseLoader:
    """
    Loads active knowledge entries from database and assembles them
    into structured prompts for LLM injection.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._cache: dict[str, str] = {}
        self._cache_timestamp: dict[str, float] = {}
    
    def fetch_knowledge_by_category(
        self,
        category: str,
        language: str = "en",
        use_cache: bool = True
    ) -> list[dict[str, Any]]:
        """
        Fetch all active knowledge entries for a specific category.
        
        Args:
            category: Knowledge category (scheme, admission, fee_structure, etc.)
            language: Language filter
            use_cache: Whether to use cached results
            
        Returns:
            List of knowledge entries sorted by priority
        """
        cache_key = f"{category}_{language}"
        
        if use_cache and cache_key in self._cache:
            logger.debug(f"Using cached knowledge for {cache_key}")
            # Note: Cache invalidation should be triggered via /api/admin/cms/cache/invalidate
        
        try:
            # Rollback any pending transaction to start fresh
            self.db.rollback()
            
            rows = self.db.execute(
                text("""
                    SELECT 
                        id, sub_key, category, title, content_markdown,
                        structured_data, source_url, source_document,
                        priority, updated_at
                    FROM knowledge_base
                    WHERE category = :category
                      AND language = :language
                      AND is_active = TRUE
                      AND is_verified = TRUE
                    ORDER BY priority ASC, updated_at DESC
                """),
                {"category": category, "language": language}
            ).mappings().all()
            
            results = []
            for row in rows:
                entry = dict(row)
                # Parse JSONB structured_data
                if isinstance(entry.get("structured_data"), str):
                    entry["structured_data"] = json.loads(entry["structured_data"])
                results.append(entry)
            
            logger.info(f"Fetched {len(results)} active knowledge entries for category={category}, language={language}")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching knowledge base for category={category}: {e}")
            # Rollback failed transaction
            self.db.rollback()
            return []
    
    def assemble_scheme_knowledge(self, language: str = "en") -> str:
        """
        Assemble all scheme-related knowledge into a formatted string.
        
        Returns:
            Formatted markdown string with scheme information,
            or empty string if no entries found (triggers fallback)
        """
        schemes = self.fetch_knowledge_by_category("scheme", language)
        
        if not schemes:
            logger.warning("No active scheme knowledge found in database - fallback will be used")
            return ""
        
        parts = [
            "# ======================================================================",
            "# GROUND TRUTH: OFFICIAL BSCS SCHEMES OF STUDY (DATABASE-SOURCED)",
            "# ======================================================================\n"
        ]
        
        for scheme in schemes:
            parts.append(f"## {scheme['title']}\n")
            parts.append(scheme['content_markdown'])
            parts.append("\n---\n")
        
        return "\n".join(parts)
    
    def assemble_admission_knowledge(self, language: str = "en") -> str:
        """
        Assemble admission-related knowledge.
        """
        admissions = self.fetch_knowledge_by_category("admission", language)
        
        if not admissions:
            logger.warning("No active admission knowledge found in database - fallback will be used")
            return ""
        
        parts = [
            "# ======================================================================",
            "# QAU UNDERGRADUATE ADMISSIONS (DATABASE-SOURCED)",
            "# ======================================================================\n"
        ]
        
        for entry in admissions:
            parts.append(f"## {entry['title']}\n")
            parts.append(entry['content_markdown'])
            parts.append("\n")
        
        return "\n".join(parts)
    
    def assemble_fee_structure_knowledge(self, language: str = "en") -> str:
        """
        Assemble fee structure knowledge.
        """
        fees = self.fetch_knowledge_by_category("fee_structure", language)
        
        if not fees:
            logger.warning("No active fee structure knowledge found in database - fallback will be used")
            return ""
        
        parts = [
            "# ======================================================================",
            "# FEE STRUCTURE (DATABASE-SOURCED)",
            "# ======================================================================\n"
        ]
        
        for entry in fees:
            parts.append(f"## {entry['title']}\n")
            parts.append(entry['content_markdown'])
            parts.append("\n")
        
        return "\n".join(parts)
    
    def assemble_all_knowledge(self, language: str = "en") -> dict[str, str]:
        """
        Assemble all knowledge categories.
        
        Returns:
            Dictionary with category keys and assembled content values
        """
        return {
            "schemes": self.assemble_scheme_knowledge(language),
            "admissions": self.assemble_admission_knowledge(language),
            "fees": self.assemble_fee_structure_knowledge(language),
        }
    
    def invalidate_cache(self, category: str | None = None):
        """
        Invalidate knowledge cache.
        
        Args:
            category: Specific category to invalidate, or None for all
        """
        if category:
            # Invalidate specific category for all languages
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{category}_")]
            for key in keys_to_remove:
                del self._cache[key]
                if key in self._cache_timestamp:
                    del self._cache_timestamp[key]
            logger.info(f"Invalidated cache for category: {category}")
        else:
            # Invalidate all
            self._cache.clear()
            self._cache_timestamp.clear()
            logger.info("Invalidated all knowledge cache")


def get_dynamic_system_prompt(
    db: Session,
    base_prompt: str,
    language: str = "en",
    use_fallback: bool = True
) -> str:
    """
    Build dynamic system prompt by fetching knowledge from database.
    
    Args:
        db: Database session
        base_prompt: Base system prompt template
        language: Target language
        use_fallback: Whether to use embedded fallback if database returns empty
        
    Returns:
        Complete system prompt with injected knowledge
    """
    loader = KnowledgeBaseLoader(db)
    knowledge = loader.assemble_all_knowledge(language)
    
    # Check if we have any database knowledge
    has_db_knowledge = any(knowledge.values())
    
    if not has_db_knowledge and not use_fallback:
        logger.warning("No database knowledge available and fallback disabled")
        return base_prompt
    
    # Build prompt sections
    prompt_parts = []
    
    # Extract the base role/context section (before first knowledge section)
    if "# ======================================================================" in base_prompt:
        role_section = base_prompt.split("# ======================================================================")[0]
        prompt_parts.append(role_section.strip())
    else:
        prompt_parts.append(base_prompt)
    
    # Add database knowledge (will override embedded if present)
    if knowledge["schemes"]:
        prompt_parts.append(knowledge["schemes"])
        logger.info("✓ Using DATABASE-sourced scheme knowledge")
    else:
        logger.info("⚠ No database schemes found - using EMBEDDED fallback")
    
    if knowledge["admissions"]:
        prompt_parts.append(knowledge["admissions"])
        logger.info("✓ Using DATABASE-sourced admission knowledge")
    else:
        logger.info("⚠ No database admissions found - using EMBEDDED fallback")
    
    if knowledge["fees"]:
        prompt_parts.append(knowledge["fees"])
        logger.info("✓ Using DATABASE-sourced fee structure knowledge")
    else:
        logger.info("⚠ No database fees found - using EMBEDDED fallback")
    
    # Add the rest of the base prompt (rules, guidelines, etc.)
    # Extract everything after the last knowledge section
    if "# CRITICAL LANGUAGE RULE" in base_prompt:
        guidelines_section = base_prompt[base_prompt.find("# CRITICAL LANGUAGE RULE"):]
        prompt_parts.append(guidelines_section)
    elif "# Response Guidelines" in base_prompt:
        guidelines_section = base_prompt[base_prompt.find("# Response Guidelines"):]
        prompt_parts.append(guidelines_section)
    
    final_prompt = "\n\n".join(prompt_parts)
    
    logger.info(f"Assembled dynamic system prompt: {len(final_prompt)} chars")
    return final_prompt


def fetch_knowledge_summary(db: Session) -> dict[str, Any]:
    """
    Fetch summary of current knowledge base state for logging/debugging.
    
    Returns:
        Dictionary with counts and metadata
    """
    try:
        summary = db.execute(
            text("""
                SELECT 
                    category,
                    COUNT(*)::int AS total,
                    COUNT(*) FILTER (WHERE is_active = TRUE)::int AS active,
                    COUNT(*) FILTER (WHERE is_verified = TRUE AND is_active = TRUE)::int AS verified_active,
                    MAX(updated_at) AS last_updated
                FROM knowledge_base
                GROUP BY category
                ORDER BY category
            """)
        ).mappings().all()
        
        return {
            "categories": [dict(row) for row in summary],
            "total_entries": sum(row["total"] for row in summary),
            "active_entries": sum(row["active"] for row in summary),
        }
    except Exception as e:
        logger.error(f"Error fetching knowledge summary: {e}")
        return {"categories": [], "total_entries": 0, "active_entries": 0}

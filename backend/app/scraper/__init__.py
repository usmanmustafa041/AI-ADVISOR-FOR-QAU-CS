"""Web scraping module for QAU CS Academic Advisor.

This module handles scraping content from cs.qau.edu.pk and storing it
in the database with proper source tracking and verification.
"""

from app.scraper.storage import ScraperStorage

__all__ = ["ScraperStorage"]

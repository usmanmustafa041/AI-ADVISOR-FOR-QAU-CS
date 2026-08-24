"""Manages source document records."""

import logging
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SourceRecord:
    """Represents a source document record."""
    
    def __init__(self, source_id: str, file_path: str):
        """
        Initialize a source record.
        
        Args:
            source_id: UUID v4 identifier for the source
            file_path: Absolute path to the source PDF file
        """
        self.source_id = source_id
        self.file_path = file_path
        self.created_at = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.source_id,
            "file_path": self.file_path,
            "created_at": self.created_at
        }


class SourceRecordHandler:
    """Manages source document records for chunk linking."""
    
    @staticmethod
    def create_source_record(file_path: str) -> Optional[SourceRecord]:
        """
        Create a source record for a document.
        
        Args:
            file_path: Absolute path to the PDF document
            
        Returns:
            SourceRecord with generated UUID v4 and file path
            
        Requirements:
            - 8.1-8.2: Create source record with UUID v4 and file path
        """
        path = Path(file_path)
        
        # Validate file exists and is readable
        if not path.exists():
            logger.error(f"File not found for source record: {file_path}")
            return None
        
        if not os.access(str(path), os.R_OK):
            logger.error(f"File not readable for source record: {file_path}")
            return None
        
        # Generate UUID v4
        source_id = str(uuid4())
        
        # Get absolute path
        abs_path = str(path.absolute())
        
        # Create source record
        record = SourceRecord(source_id, abs_path)
        
        logger.info(f"Created source record {source_id} for {abs_path}")
        
        return record
    
    @staticmethod
    def validate_source_file(file_path: str) -> bool:
        """
        Validate that a source file can be safely accessed.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            True if file is accessible, False otherwise
            
        Requirements:
            - 8.5-8.7: Validate read-only access and file integrity
        """
        path = Path(file_path)
        
        # Check file exists
        if not path.exists():
            logger.warning(f"Source file does not exist: {file_path}")
            return False
        
        # Check file is readable
        if not os.access(str(path), os.R_OK):
            logger.warning(f"Source file is not readable: {file_path}")
            return False
        
        # Check file is not writable (read-only mode enforced)
        if os.access(str(path), os.W_OK):
            logger.warning(f"Source file is writable (should be read-only): {file_path}")
            # Still return True, we can open in read-only mode
        
        return True
    
    @staticmethod
    def open_source_file_readonly(file_path: str):
        """
        Safely open a source file in read-only mode.
        
        Args:
            file_path: Path to file to open
            
        Returns:
            Open file object or None if cannot open
            
        Requirements:
            - 8.5-8.6: Open in read-only mode and handle cleanup
        """
        try:
            # Open in read-only binary mode
            file_obj = open(file_path, 'rb')
            logger.debug(f"Opened source file in read-only mode: {file_path}")
            return file_obj
        except Exception as e:
            logger.error(f"Failed to open source file: {file_path}: {e}")
            return None

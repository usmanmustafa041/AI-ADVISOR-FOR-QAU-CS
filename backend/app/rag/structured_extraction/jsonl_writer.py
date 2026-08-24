"""Writes structured chunks to JSONL format."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class JSONLWriter:
    """Writes chunks to JSONL (JSON Lines) format for batch ingestion."""
    
    # Buffer size for flushing
    FLUSH_THRESHOLD = 50
    
    def __init__(self, output_path: str):
        """
        Initialize JSONL writer.
        
        Args:
            output_path: Path to output JSONL file
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = None
        self.chunk_count = 0
        self.buffer_count = 0
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def open(self) -> bool:
        """
        Open the output file for writing.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.file = open(self.output_path, 'w', encoding='utf-8')
            logger.info(f"Opened JSONL output file: {self.output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open JSONL output file: {e}")
            return False
    
    def close(self) -> None:
        """Close the output file and flush any remaining data."""
        if self.file:
            try:
                self.file.flush()
                self.file.close()
                logger.info(f"Closed JSONL output file: {self.output_path} ({self.chunk_count} chunks written)")
            except Exception as e:
                logger.error(f"Error closing JSONL file: {e}")
            finally:
                self.file = None
    
    def write_chunk(self, chunk_record: dict) -> bool:
        """
        Write a single chunk record to JSONL file.
        
        Args:
            chunk_record: Dictionary with chunk data (id, source_id, content, metadata, embedding)
            
        Returns:
            True if successful, False otherwise
            
        Requirements:
            - 10.1, 10.6: Write JSON object per line with required fields
            - 15.9: Flush after every 50 chunks
        """
        if not self.file:
            logger.error("Cannot write chunk: file not open")
            return False
        
        try:
            # Ensure all required fields are present
            record = {
                "id": chunk_record.get("id"),
                "source_id": chunk_record.get("source_id"),
                "content": chunk_record.get("content"),
                "metadata": chunk_record.get("metadata"),
                "embedding": chunk_record.get("embedding"),
            }
            
            # Write as JSON line
            json_line = json.dumps(record, ensure_ascii=False) + "\n"
            self.file.write(json_line)
            
            self.chunk_count += 1
            self.buffer_count += 1
            
            # Flush after threshold (Requirement 15.9)
            if self.buffer_count >= self.FLUSH_THRESHOLD:
                self.flush()
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing chunk to JSONL: {e}")
            return False
    
    def write_chunks(self, chunk_records: list[dict]) -> int:
        """
        Write multiple chunk records to JSONL file.
        
        Args:
            chunk_records: List of chunk record dictionaries
            
        Returns:
            Number of successfully written chunks
        """
        written_count = 0
        for record in chunk_records:
            if self.write_chunk(record):
                written_count += 1
        
        return written_count
    
    def flush(self) -> bool:
        """
        Flush the file buffer to disk.
        
        Returns:
            True if successful, False otherwise
            
        Requirements:
            - 15.9: Prevent data loss on interruption
        """
        if not self.file:
            return False
        
        try:
            self.file.flush()
            self.buffer_count = 0
            logger.debug(f"Flushed JSONL buffer to disk ({self.chunk_count} chunks total)")
            return True
        except Exception as e:
            logger.error(f"Error flushing JSONL file: {e}")
            return False
    
    def get_chunk_count(self) -> int:
        """Get total number of chunks written."""
        return self.chunk_count

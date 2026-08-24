"""Enriches chunks with structured metadata."""

import json
import logging
from typing import Any, Dict, Optional

from .constants import MAX_METADATA_SIZE_BYTES

logger = logging.getLogger(__name__)


class MetadataEnricher:
    """Enriches document chunks with structured metadata."""
    
    @staticmethod
    def enrich_timetable_chunk(metadata: dict, incomplete: bool = False) -> dict:
        """
        Enrich metadata for a timetable chunk.
        
        Args:
            metadata: Dictionary with extracted metadata from chunk generator
            incomplete: Whether the extraction was incomplete
            
        Returns:
            Enriched metadata dictionary with validated and typed values
            
        Requirements:
            - 4.1-4.12: Metadata key-value pair creation and validation
        """
        enriched = {
            # Mandatory fields
            "semester": metadata.get("semester"),
            "course_code": metadata.get("course_code"),
            "section": metadata.get("section"),
            "day": metadata.get("day"),
            "course_type": metadata.get("course_type"),
            "start_time": metadata.get("start_time"),
            "end_time": metadata.get("end_time"),
        }
        
        # Optional fields (only include if present)
        if metadata.get("room"):
            enriched["room"] = metadata["room"]
        if metadata.get("faculty"):
            enriched["faculty"] = metadata["faculty"]
        if metadata.get("special_status"):
            enriched["special_status"] = metadata["special_status"]
        
        # Add incomplete flag if needed (Requirement 14.7)
        if incomplete:
            enriched["incomplete_extraction"] = True
        
        # Validate size before returning (Requirement 4.13-4.14)
        return MetadataEnricher._validate_and_truncate(enriched)
    
    @staticmethod
    def enrich_scheme_chunk(metadata: dict, incomplete: bool = False) -> dict:
        """
        Enrich metadata for a scheme of study chunk.
        
        Args:
            metadata: Dictionary with extracted metadata from chunk generator
            incomplete: Whether the extraction was incomplete
            
        Returns:
            Enriched metadata dictionary with validated and typed values
            
        Requirements:
            - 4.1, 4.12: Metadata serialization for database storage
        """
        enriched = {
            # Mandatory fields
            "semester": metadata.get("semester"),
            "course_code": metadata.get("course_code"),
            "credit_hours": metadata.get("credit_hours"),
            "category": metadata.get("category"),
        }
        
        # Optional fields (only include if present)
        if metadata.get("prerequisites"):
            enriched["prerequisites"] = metadata["prerequisites"]
        
        # Add incomplete flag if needed (Requirement 14.7)
        if incomplete:
            enriched["incomplete_extraction"] = True
        
        # Validate size before returning (Requirement 4.13-4.14)
        return MetadataEnricher._validate_and_truncate(enriched)
    
    @staticmethod
    def _validate_and_truncate(metadata: dict) -> dict:
        """
        Validate JSON size and truncate optional fields if needed.
        
        Args:
            metadata: Metadata dictionary to validate
            
        Returns:
            Validated metadata dictionary (possibly with truncated optional fields)
            
        Requirements:
            - 4.13-4.14: Validate size and truncate if > 10 KB
        """
        # Serialize to JSON to check size
        json_str = json.dumps(metadata)
        size_bytes = len(json_str.encode('utf-8'))
        
        if size_bytes <= MAX_METADATA_SIZE_BYTES:
            return metadata
        
        # If too large, try removing optional fields
        logger.warning(
            f"Metadata size {size_bytes} bytes exceeds limit of {MAX_METADATA_SIZE_BYTES}, "
            "truncating optional fields"
        )
        
        # Remove optional fields one by one until it fits
        optional_fields = [
            "room", "faculty", "special_status", "prerequisites", "incomplete_extraction"
        ]
        
        for field in optional_fields:
            if field in metadata:
                del metadata[field]
                json_str = json.dumps(metadata)
                size_bytes = len(json_str.encode('utf-8'))
                
                if size_bytes <= MAX_METADATA_SIZE_BYTES:
                    logger.info(f"Metadata truncated to {size_bytes} bytes")
                    return metadata
        
        logger.error(
            f"Could not reduce metadata size below {MAX_METADATA_SIZE_BYTES} bytes "
            "even after removing all optional fields"
        )
        
        return metadata
    
    @staticmethod
    def to_json_compatible(value: Any) -> Any:
        """Convert a value to JSON-compatible format."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, list):
            return [MetadataEnricher.to_json_compatible(v) for v in value]
        elif isinstance(value, dict):
            return {k: MetadataEnricher.to_json_compatible(v) for k, v in value.items()}
        else:
            return str(value)

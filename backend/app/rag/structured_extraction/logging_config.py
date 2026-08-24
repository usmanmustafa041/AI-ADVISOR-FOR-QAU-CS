"""Logging configuration for structured extraction components."""

import logging
import sys
from typing import Optional


def configure_extraction_logger(
    name: str = "structured_extraction",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Configure and return a logger for structured extraction components.
    
    Args:
        name: Logger name (default: "structured_extraction")
        level: Logging level (default: INFO)
        log_file: Optional file path for log output
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create component-specific loggers
detection_logger = configure_extraction_logger("structured_extraction.detection")
extraction_logger = configure_extraction_logger("structured_extraction.extraction")
chunk_generation_logger = configure_extraction_logger("structured_extraction.chunk_generation")
metadata_logger = configure_extraction_logger("structured_extraction.metadata")


def get_logger(component: str) -> logging.Logger:
    """Get a logger for a specific component.
    
    Args:
        component: Component name (e.g., "detection", "extraction", "chunk_generation", "metadata")
        
    Returns:
        Logger instance for the component
    """
    return logging.getLogger(f"structured_extraction.{component}")

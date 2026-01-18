"""
Input validation module for proverb queries.
"""

import re
from typing import Tuple, Optional


def validate_input(text: str, max_length: int = 500) -> Tuple[bool, Optional[str]]:
    """
    Validate user input for proverb queries.
    
    Args:
        text: Input text to validate
        max_length: Maximum allowed length
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Input cannot be empty and must be a string"
    
    text = text.strip()
    
    if len(text) == 0:
        return False, "Input cannot be empty after stripping whitespace"
    
    if len(text) > max_length:
        return False, f"Input exceeds maximum length of {max_length} characters"
    
    # Check for potentially malicious characters
    if re.search(r"[<>;{}]", text):
        return False, "Input contains invalid characters: < > ; { }"
    
    return True, None


def sanitize_input(text: str) -> str:
    """
    Sanitize user input by removing dangerous characters.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remove potentially dangerous characters
    text = re.sub(r"[<>;{}]", "", text)
    
    # Normalize whitespace
    text = " ".join(text.split())
    
    return text.strip()


def is_valid_query(query: str) -> bool:
    """
    Quick check if query is valid.
    
    Args:
        query: Query string
        
    Returns:
        True if valid, False otherwise
    """
    is_valid, _ = validate_input(query)
    return is_valid
"""
Validation utilities for inputs.
"""
import re
from typing import Optional


def validate_location(location: str) -> bool:
    """
    Validate location string.
    
    Args:
        location: Location string to validate
        
    Returns:
        True if valid
    """
    if not location or len(location.strip()) < 2:
        return False
    
    # Basic validation: should contain letters and optionally spaces, hyphens
    pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s\-]+$'
    return bool(re.match(pattern, location.strip()))


def validate_phone_number(phone_number: str) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        True if valid format
    """
    # Remove whatsapp: prefix if present
    cleaned = phone_number.replace('whatsapp:', '').strip()
    
    # Should start with + and have 10-15 digits
    if not cleaned.startswith('+'):
        return False
    
    digits = cleaned[1:].replace(' ', '').replace('-', '')
    return len(digits) >= 10 and len(digits) <= 15 and digits.isdigit()


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email to validate
        
    Returns:
        True if valid
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_candidate_name(name: Optional[str]) -> bool:
    """
    Validate candidate name.
    
    Args:
        name: Name to validate (can be None)
        
    Returns:
        True if valid or None
    """
    if name is None:
        return True
    
    if not name.strip():
        return False
    
    # Should contain letters, spaces, hyphens, apostrophes
    pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s\-\']+$'
    return bool(re.match(pattern, name.strip()))


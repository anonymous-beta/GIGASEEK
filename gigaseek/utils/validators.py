"""
Input validation utilities for GIGASEEK
"""

import re
import validators
import phonenumbers
from email_validator import validate_email as email_validate, EmailNotValidError
from typing import Optional, Tuple


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate username format
    Returns (is_valid, error_message)
    """
    if not username:
        return False, "Username cannot be empty"
    
    if len(username) < 2:
        return False, "Username too short (min 2 characters)"
    
    if len(username) > 50:
        return False, "Username too long (max 50 characters)"
    
    # Check for valid characters
    if not re.match(r'^[a-zA-Z0-9._-]+$', username):
        return False, "Username contains invalid characters (allowed: a-z, 0-9, ., _, -)"
    
    # Check for consecutive special characters
    if re.search(r'[._-]{2,}', username):
        return False, "Username contains consecutive special characters"
    
    # Check start/end with special character
    if re.match(r'^[._-]|[._-]$', username):
        return False, "Username cannot start or end with special characters"
    
    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email format
    Returns (is_valid, error_message)
    """
    if not email:
        return False, "Email cannot be empty"
    
    try:
        # Validate and normalize
        valid = email_validate(email, check_deliverability=False)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)


def validate_phone(phone: str, default_region: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Validate phone number
    Returns (is_valid, error_message, parsed_info)
    """
    if not phone:
        return False, "Phone number cannot be empty", None
    
    try:
        parsed = phonenumbers.parse(phone, default_region)
        
        if not phonenumbers.is_valid_number(parsed):
            return False, "Invalid phone number", None
        
        info = {
            "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
            "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
            "country_code": parsed.country_code,
            "national_number": parsed.national_number,
            "region_code": phonenumbers.region_code_for_number(parsed),
            "is_possible": phonenumbers.is_possible_number(parsed),
            "number_type": str(phonenumbers.number_type(parsed)),
        }
        
        return True, None, info
        
    except phonenumbers.NumberParseException as e:
        return False, f"Phone parse error: {str(e)}", None


def validate_domain(domain: str) -> Tuple[bool, Optional[str]]:
    """
    Validate domain name
    Returns (is_valid, error_message)
    """
    if not domain:
        return False, "Domain cannot be empty"
    
    # Remove protocol if present
    domain = re.sub(r'^https?://', '', domain)
    domain = re.sub(r'^www\.', '', domain)
    domain = domain.split('/')[0]
    
    if not validators.domain(domain):
        return False, "Invalid domain format"
    
    return True, None


def validate_ip(ip: str) -> Tuple[bool, Optional[str]]:
    """
    Validate IP address
    Returns (is_valid, error_message)
    """
    if not ip:
        return False, "IP cannot be empty"
    
    if validators.ipv4(ip) or validators.ipv6(ip):
        return True, None
    
    return False, "Invalid IP address format"


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate URL
    Returns (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    if validators.url(url):
        return True, None
    
    return False, "Invalid URL format"


def sanitize_filename(filename: str) -> str:
    """Sanitize string for use as filename"""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    sanitized = sanitized[:200]
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    return sanitized or "unnamed"

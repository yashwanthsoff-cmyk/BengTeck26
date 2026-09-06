# lib/utils.py
"""
Utility functions for text processing, email validation, and cryptographic hashing.
"""
import hashlib
import re

def format_string(text: str) -> str:
    """Format and normalize text by stripping leading/trailing whitespace and reducing spaces."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())

def validate_email(email: str) -> bool:
    """Validate email address format using standard regex pattern."""
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))

def hash_text(text: str) -> str:
    """Generate SHA-256 hexadecimal hash digest of the input text."""
    if text is None:
        text = ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

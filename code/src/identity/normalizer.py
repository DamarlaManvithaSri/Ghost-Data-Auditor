"""
Identifier Normalizer for Ghost Data Auditor.
Provides deterministic, standard normalization for emails, phone numbers, hashes, and account IDs
while preserving raw source strings for audit integrity.
"""

import re
import hashlib
from typing import Optional, Any
from .models import IdentifierType


def normalize_email(email: Optional[str]) -> str:
    """
    Normalizes an email address for robust cross-system matching:
    - Strips leading/trailing whitespace
    - Converts to lowercase
    - Returns empty string if None or invalid
    """
    if not email or not isinstance(email, str):
        return ""
    clean = email.strip().lower()
    return clean


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalizes a phone number to standard E.164-compatible digit string:
    - Retains leading '+' if present for international numbers
    - Strips parentheses, dashes, spaces, and periods
    - Returns empty string if None or non-numeric
    """
    if not phone or not isinstance(phone, str):
        return ""
    clean = phone.strip()
    has_plus = clean.startswith("+")
    digits = re.sub(r"[^\d]", "", clean)
    if not digits:
        return ""
    return f"+{digits}" if has_plus else digits


def compute_email_hash(email: Optional[str]) -> str:
    """
    Computes a canonical SHA-256 hash of a normalized email address.
    Matches industry standards for hashed customer identifiers (e.g. analytics exports).
    """
    clean_email = normalize_email(email)
    if not clean_email:
        return ""
    return hashlib.sha256(clean_email.encode("utf-8")).hexdigest()


def normalize_name(name: Optional[str]) -> str:
    """
    Normalizes a person's name for comparison:
    - Collapses multiple whitespace characters to single spaces
    - Strips leading/trailing spaces
    """
    if not name or not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.strip())


def normalize_identifier(id_type: IdentifierType, value: Any) -> str:
    """
    Applies the correct type-specific normalization logic to an identifier value.
    """
    if value is None:
        return ""
    val_str = str(value).strip()

    if id_type == IdentifierType.EMAIL:
        return normalize_email(val_str)
    elif id_type == IdentifierType.PHONE:
        return normalize_phone(val_str)
    elif id_type == IdentifierType.EMAIL_HASH:
        return val_str.lower()
    elif id_type == IdentifierType.NAME:
        return normalize_name(val_str)
    elif id_type in [IdentifierType.USER_ID, IdentifierType.ACCOUNT_ID, IdentifierType.CUSTOMER_ID]:
        return val_str # User IDs and Account IDs preserve case and exact structure

    return val_str

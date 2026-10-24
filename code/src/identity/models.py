"""
Data Models for Identity Resolution.
Defines types, confidence tiers, provenance-backed links, and resolved identity graphs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional


class IdentifierType(str, Enum):
    """Types of personal and account identifiers."""
    USER_ID = "USER_ID"              # Stable internal user identifier (e.g., user_18)
    EMAIL = "EMAIL"                  # Current or historical email address
    PHONE = "PHONE"                  # Current or historical phone number
    EMAIL_HASH = "EMAIL_HASH"        # SHA-256 hash of email
    NAME = "NAME"                    # Full name or legal entity
    ACCOUNT_ID = "ACCOUNT_ID"        # Service-specific account ID
    CUSTOMER_ID = "CUSTOMER_ID"      # External customer identifier
    ALIAS = "ALIAS"                  # Alternate username or handle
    EXTERNAL_REF = "EXTERNAL_REF"    # Order ID, statement ID, or tracking code


class LinkConfidence(str, Enum):
    """Confidence grade for an established identity link."""
    CONFIRMED = "CONFIRMED"          # Direct evidence match from primary snapshot or audit log
    PROBABLE = "PROBABLE"            # Secondary corroboration (e.g., matching name + address/order)
    CONFLICT = "CONFLICT"            # Discrepancy (e.g., same identifier claimed by multiple user_ids)
    UNRESOLVED = "UNRESOLVED"        # Insufficient evidence to confirm identity association


@dataclass
class IdentityLink:
    """
    Represents an evidence-backed link between an identifier and a person.
    Contains full provenance: file, location, evidence snippet, and justification.
    """
    target_user_id: str
    identifier_type: IdentifierType
    identifier_value: str            # Clean, normalized value for comparison
    raw_value: str                   # Exact raw value as recorded in source evidence
    confidence: LinkConfidence
    source_file: str
    source_location: str             # e.g., "Row 42", "Page 1", "Line 88"
    evidence_text: str               # Exact text snippet or record content
    is_historical: bool = False      # True if this was an older identifier replaced over time
    timestamp: Optional[str] = None  # Event timestamp or snapshot date
    justification: str = ""          # Human-readable rationale for this connection


@dataclass
class ResolvedIdentity:
    """
    Complete identity dossier for a customer, reconstructing current and historical identifiers.
    """
    seed_identifier: str
    user_id: Optional[str] = None
    status: str = "UNRESOLVED"       # RESOLVED, CONFLICT, UNRESOLVED, AMBIGUOUS
    current_identifiers: Dict[str, Set[str]] = field(default_factory=dict)
    historical_identifiers: Dict[str, Set[str]] = field(default_factory=dict)
    links: List[IdentityLink] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    def get_all_search_terms(self) -> Set[str]:
        """
        Returns all unique search terms (emails, user IDs, phones, hashes, names)
        to search for this customer across all secondary systems.
        """
        terms = set()
        if self.user_id:
            terms.add(self.user_id)
        for cat in [self.current_identifiers, self.historical_identifiers]:
            for id_type, vals in cat.items():
                terms.update(vals)
        return terms

    def get_emails(self) -> Set[str]:
        """Returns all known current and historical email addresses."""
        res = set()
        res.update(self.current_identifiers.get(IdentifierType.EMAIL.value, set()))
        res.update(self.historical_identifiers.get(IdentifierType.EMAIL.value, set()))
        return res

    def get_phones(self) -> Set[str]:
        """Returns all known current and historical phone numbers."""
        res = set()
        res.update(self.current_identifiers.get(IdentifierType.PHONE.value, set()))
        res.update(self.historical_identifiers.get(IdentifierType.PHONE.value, set()))
        return res

    def get_hashes(self) -> Set[str]:
        """Returns all known email hashes."""
        res = set()
        res.update(self.current_identifiers.get(IdentifierType.EMAIL_HASH.value, set()))
        res.update(self.historical_identifiers.get(IdentifierType.EMAIL_HASH.value, set()))
        return res

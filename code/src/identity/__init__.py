"""
Identity Resolution Package for Ghost Data Auditor.
Provides deterministic, evidence-backed discovery and tracing of current and historical identifiers.
"""

from .models import (
    IdentifierType,
    LinkConfidence,
    IdentityLink,
    ResolvedIdentity
)
from .normalizer import (
    normalize_email,
    normalize_phone,
    normalize_identifier,
    compute_email_hash
)
from .resolver import IdentityResolver
from .searcher import CrossSystemIdentitySearcher

__all__ = [
    "IdentifierType",
    "LinkConfidence",
    "IdentityLink",
    "ResolvedIdentity",
    "normalize_email",
    "normalize_phone",
    "normalize_identifier",
    "compute_email_hash",
    "IdentityResolver",
    "CrossSystemIdentitySearcher"
]

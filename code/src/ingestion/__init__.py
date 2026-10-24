"""
Evidence Ingestion Layer for Ghost Data Auditor.
Provides resilient, local-first parsing and normalization of multi-format evidence.
"""

from .models import (
    RawEvidence,
    SourceReference,
    ExtractedRecord,
    IngestedFile,
    IngestionStatus
)
from .manager import EvidenceManager

__all__ = [
    "RawEvidence",
    "SourceReference",
    "ExtractedRecord",
    "IngestedFile",
    "IngestionStatus",
    "EvidenceManager"
]

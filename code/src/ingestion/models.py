"""
Data Models for Evidence Ingestion.
Defines structured classes for raw evidence, source references, extracted records, and file metadata.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional

class IngestionStatus(str, Enum):
    """
    Standardized ingestion status for every processed evidence file.
    """
    SUCCESS = "SUCCESS"                  # Fully parsed with complete data extraction
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"  # Read partially (e.g. Image without OCR, or skipped malformed lines)
    MALFORMED = "MALFORMED"              # File was corrupted, missing expected structure, or unparsable
    EMPTY = "EMPTY"                      # 0 bytes or completely empty content
    UNSUPPORTED = "UNSUPPORTED"          # Unrecognized file format
    ERROR = "ERROR"                      # Critical I/O or decoding failure

@dataclass
class RawEvidence:
    """
    Preserves the raw, untouched evidence artifact.
    Guarantees local immutability and provenance tracking.
    """
    file_name: str
    file_size_bytes: int
    file_hash_sha256: str
    file_path: Optional[str] = None
    raw_bytes: Optional[bytes] = None
    mime_type: Optional[str] = None

@dataclass
class SourceReference:
    """
    Tracks the exact origin of every extracted record down to filename and row/page/line.
    """
    file_name: str
    location_type: str = "file"          # 'row', 'line', 'page', 'json_object', 'image_metadata', 'file'
    location_index: Optional[int] = None # 1-indexed (e.g. Row 1, Page 2, Line 15)
    section: Optional[str] = None        # Sub-component, table name, or document section

    def to_display_string(self) -> str:
        """Returns a human-readable origin description."""
        if self.location_type == "row" and self.location_index is not None:
            return f"{self.file_name} (Row {self.location_index})"
        elif self.location_type == "page" and self.location_index is not None:
            return f"{self.file_name} (Page {self.location_index})"
        elif self.location_type == "line" and self.location_index is not None:
            return f"{self.file_name} (Line {self.location_index})"
        elif self.location_type == "json_object" and self.location_index is not None:
            return f"{self.file_name} (Item #{self.location_index})"
        return f"{self.file_name}"

@dataclass
class ExtractedRecord:
    """
    A single granular record extracted from an evidence file.
    Maintains clean separation between raw text and structured data.
    """
    record_id: str
    source_ref: SourceReference
    record_type: str                     # 'tabular_row', 'log_line', 'document_page', 'json_object', etc.
    raw_text: str                        # Plain text representation for keyword/regex searching
    structured_data: Dict[str, Any] = field(default_factory=dict) # Key-value pairs if structured
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IngestedFile:
    """
    Represents the complete processed result of an evidence file.
    Contains raw evidence, extracted records, diagnostic metadata, and status.
    """
    file_name: str
    detected_format: str
    status: IngestionStatus
    status_message: str
    raw_evidence: RawEvidence
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_text: str = ""
    records: List[ExtractedRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def is_inspected(self) -> bool:
        """Returns True if the file content was fully or partially inspected."""
        return self.status in [IngestionStatus.SUCCESS, IngestionStatus.PARTIAL_SUCCESS]

"""
Evidence Manager for Ghost Data Auditor.
Coordinates ingestion across multiple formats, detects duplicates, manages catalog state,
and provides structured query capabilities over extracted records.
"""

import os
from typing import Dict, List, Any, Optional, Union
import hashlib

from .models import (
    RawEvidence,
    ExtractedRecord,
    IngestedFile,
    IngestionStatus
)
from .parsers import (
    CSVParser,
    JSONParser,
    TextLogParser,
    PDFParser,
    ImageParser,
    SQLParser,
    FallbackParser,
    compute_sha256
)

SUPPORTED_EXTENSIONS = {
    "csv": CSVParser,
    "json": JSONParser,
    "jsonl": JSONParser,
    "txt": TextLogParser,
    "log": TextLogParser,
    "md": TextLogParser,
    "pdf": PDFParser,
    "png": ImageParser,
    "jpg": ImageParser,
    "jpeg": ImageParser,
    "webp": ImageParser,
    "bmp": ImageParser,
    "sql": SQLParser
}


class EvidenceManager:
    """
    Central catalog and pipeline manager for all uploaded and ingested evidence files.
    """
    def __init__(self):
        self._files: Dict[str, IngestedFile] = {}
        self._hash_to_filename: Dict[str, str] = {}

    def clear(self):
        """Clears all loaded evidence from memory."""
        self._files.clear()
        self._hash_to_filename.clear()

    def get_all_files(self) -> List[IngestedFile]:
        """Returns all ingested files in registration order."""
        return list(self._files.values())

    def get_file(self, file_name: str) -> Optional[IngestedFile]:
        """Retrieves a single ingested file by filename."""
        return self._files.get(file_name)

    def ingest_bytes(
        self,
        file_name: str,
        raw_bytes: bytes,
        file_path: Optional[str] = None
    ) -> IngestedFile:
        """
        Ingests and parses a file from raw bytes.
        Handles duplicates, selects the appropriate parser, and tracks errors.
        """
        file_hash = compute_sha256(raw_bytes)

        # Check for duplicate file content
        is_duplicate = False
        duplicate_of = None
        if file_hash in self._hash_to_filename:
            is_duplicate = True
            duplicate_of = self._hash_to_filename[file_hash]

        # Extract file extension
        ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        parser_cls = SUPPORTED_EXTENSIONS.get(ext, FallbackParser)

        try:
            ingested: IngestedFile = parser_cls.parse(
                file_name=file_name,
                raw_bytes=raw_bytes,
                file_path=file_path
            )
        except Exception as e:
            # Absolute fallback if a parser experiences an unhandled failure
            raw_evidence = RawEvidence(
                file_name=file_name,
                file_size_bytes=len(raw_bytes),
                file_hash_sha256=file_hash,
                file_path=file_path
            )
            ingested = IngestedFile(
                file_name=file_name,
                detected_format=ext.upper() if ext else "UNKNOWN",
                status=IngestionStatus.ERROR,
                status_message=f"Parser crash: {str(e)}",
                raw_evidence=raw_evidence,
                errors=[str(e)]
            )

        if is_duplicate:
            ingested.warnings.append(
                f"Duplicate content detected: matches SHA-256 hash of previously loaded file '{duplicate_of}'."
            )
            ingested.metadata["is_duplicate"] = True
            ingested.metadata["duplicate_of"] = duplicate_of
        else:
            self._hash_to_filename[file_hash] = file_name

        self._files[file_name] = ingested
        return ingested

    def ingest_path(self, file_path: str) -> IngestedFile:
        """
        Reads and ingests a file directly from a local filesystem path.
        """
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            return self.ingest_bytes(file_name, raw_bytes, file_path=file_path)
        except Exception as e:
            raw_evidence = RawEvidence(
                file_name=file_name,
                file_size_bytes=0,
                file_hash_sha256="",
                file_path=file_path
            )
            ingested = IngestedFile(
                file_name=file_name,
                detected_format="UNKNOWN",
                status=IngestionStatus.ERROR,
                status_message=f"Could not read file from disk: {str(e)}",
                raw_evidence=raw_evidence,
                errors=[str(e)]
            )
            self._files[file_name] = ingested
            return ingested

    def ingest_directory(self, dir_path: str, recursive: bool = True) -> List[IngestedFile]:
        """
        Scans a directory on disk and ingests all evidence files.
        """
        results: List[IngestedFile] = []
        if not os.path.exists(dir_path):
            return results

        if recursive:
            for root, _, files in os.walk(dir_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    results.append(self.ingest_path(full_path))
        else:
            for file in os.listdir(dir_path):
                full_path = os.path.join(dir_path, file)
                if os.path.isfile(full_path):
                    results.append(self.ingest_path(full_path))

        return results

    def get_summary(self) -> Dict[str, Any]:
        """
        Computes summary metrics across all ingested evidence files.
        """
        files = list(self._files.values())
        status_counts = {status.value: 0 for status in IngestionStatus}
        format_counts: Dict[str, int] = {}
        total_records = 0
        total_bytes = 0

        for f in files:
            status_counts[f.status.value] = status_counts.get(f.status.value, 0) + 1
            format_counts[f.detected_format] = format_counts.get(f.detected_format, 0) + 1
            total_records += f.record_count
            total_bytes += f.raw_evidence.file_size_bytes

        return {
            "total_files": len(files),
            "total_records": total_records,
            "total_bytes": total_bytes,
            "total_size_mb": total_bytes / (1024 * 1024),
            "status_counts": status_counts,
            "format_counts": format_counts,
            "has_warnings": any(len(f.warnings) > 0 for f in files),
            "has_errors": any(f.status in [IngestionStatus.ERROR, IngestionStatus.MALFORMED] for f in files)
        }

    def search_records(self, query: str, case_sensitive: bool = False) -> List[ExtractedRecord]:
        """
        Searches all extracted records across all ingested files for matching strings or keywords.
        """
        if not query:
            return []

        search_term = query if case_sensitive else query.lower()
        matched: List[ExtractedRecord] = []

        for f in self._files.values():
            for rec in f.records:
                target_text = rec.raw_text if case_sensitive else rec.raw_text.lower()
                if search_term in target_text:
                    matched.append(rec)

        return matched

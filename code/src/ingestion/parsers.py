"""
Evidence Parsers for Ghost Data Auditor.
Provides specialized, fault-tolerant parsers for CSV, JSON/JSONL, Text/Logs, PDFs, Images, and SQL dumps.
Never crashes on encoding errors, corrupted data, or missing tools.
"""

import io
import json
import hashlib
import traceback
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
from PIL import Image

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

from .models import (
    RawEvidence,
    SourceReference,
    ExtractedRecord,
    IngestedFile,
    IngestionStatus
)

# Text preview maximum character limit for large files
MAX_PREVIEW_CHARS = 8000


def compute_sha256(raw_bytes: bytes) -> str:
    """Computes a SHA-256 cryptographic hash of raw evidence bytes."""
    return hashlib.sha256(raw_bytes).hexdigest()


def safe_decode_bytes(raw_bytes: bytes) -> Tuple[str, str]:
    """
    Decodes raw bytes into text trying multiple common encodings.
    Falls back gracefully without raising UnicodeDecodeError.
    Returns: (decoded_text, encoding_used)
    """
    encodings_to_try = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
    for enc in encodings_to_try:
        try:
            return raw_bytes.decode(enc), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Ultimate safe fallback: replace un-decodable bytes
    return raw_bytes.decode("utf-8", errors="replace"), "utf-8 (lossy fallback)"


class CSVParser:
    """
    Resilient parser for CSV tabular evidence.
    Inspects column names, row counts, and data types via Pandas.
    """
    @staticmethod
    def parse(file_name: str, raw_bytes: bytes, file_path: Optional[str] = None) -> IngestedFile:
        raw_evidence = RawEvidence(
            file_name=file_name,
            file_size_bytes=len(raw_bytes),
            file_hash_sha256=compute_sha256(raw_bytes),
            file_path=file_path,
            mime_type="text/csv"
        )

        if len(raw_bytes.strip()) == 0:
            return IngestedFile(
                file_name=file_name,
                detected_format="CSV",
                status=IngestionStatus.EMPTY,
                status_message="File is empty (0 bytes).",
                raw_evidence=raw_evidence,
                metadata={"row_count": 0, "column_count": 0, "columns": []}
            )

        text, encoding = safe_decode_bytes(raw_bytes)

        try:
            # Use Pandas with resilient settings
            df = pd.read_csv(
                io.StringIO(text),
                on_bad_lines="skip", # Do not crash on irregular lines
                engine="python"
            )

            # Check if dataframe is empty
            if df.empty and len(df.columns) == 0:
                return IngestedFile(
                    file_name=file_name,
                    detected_format="CSV",
                    status=IngestionStatus.EMPTY,
                    status_message="CSV has no rows or columns.",
                    raw_evidence=raw_evidence,
                    metadata={"row_count": 0, "column_count": 0, "columns": []}
                )

            # Extract schema metadata
            column_names = [str(c) for c in df.columns]
            data_types = {str(k): str(v) for k, v in df.dtypes.items()}
            row_count = len(df)

            # Create normalized records for each row
            records: List[ExtractedRecord] = []
            for row_idx, row in df.iterrows():
                row_dict = row.where(pd.notnull(row), None).to_dict()
                row_text = ", ".join(f"{k}: {v}" for k, v in row_dict.items() if v is not None)
                
                records.append(ExtractedRecord(
                    record_id=f"{file_name}#row_{row_idx + 1}",
                    source_ref=SourceReference(
                        file_name=file_name,
                        location_type="row",
                        location_index=row_idx + 1
                    ),
                    record_type="tabular_row",
                    raw_text=row_text,
                    structured_data=row_dict,
                    metadata={"row_number": row_idx + 1}
                ))

            # Build text preview
            preview_rows = df.head(30).to_string(index=False)
            if len(preview_rows) > MAX_PREVIEW_CHARS:
                preview_rows = preview_rows[:MAX_PREVIEW_CHARS] + "\n... [Preview truncated for display] ..."

            return IngestedFile(
                file_name=file_name,
                detected_format="CSV",
                status=IngestionStatus.SUCCESS,
                status_message=f"Successfully extracted {row_count} row(s) and {len(column_names)} column(s).",
                raw_evidence=raw_evidence,
                metadata={
                    "row_count": row_count,
                    "column_count": len(column_names),
                    "columns": column_names,
                    "data_types": data_types,
                    "encoding": encoding
                },
                extracted_text=preview_rows,
                records=records
            )

        except Exception as e:
            # Handle malformed CSV gracefully
            return IngestedFile(
                file_name=file_name,
                detected_format="CSV",
                status=IngestionStatus.MALFORMED,
                status_message=f"Malformed CSV: {str(e)}",
                raw_evidence=raw_evidence,
                metadata={"encoding": encoding},
                errors=[str(e)],
                extracted_text=text[:MAX_PREVIEW_CHARS]
            )


class JSONParser:
    """
    Safely parses standard JSON documents and line-delimited JSON (JSONL).
    """
    @staticmethod
    def parse(file_name: str, raw_bytes: bytes, file_path: Optional[str] = None) -> IngestedFile:
        raw_evidence = RawEvidence(
            file_name=file_name,
            file_size_bytes=len(raw_bytes),
            file_hash_sha256=compute_sha256(raw_bytes),
            file_path=file_path,
            mime_type="application/json"
        )

        if len(raw_bytes.strip()) == 0:
            return IngestedFile(
                file_name=file_name,
                detected_format="JSON",
                status=IngestionStatus.EMPTY,
                status_message="File is empty (0 bytes).",
                raw_evidence=raw_evidence,
                metadata={"record_count": 0}
            )

        text, encoding = safe_decode_bytes(raw_bytes)
        records: List[ExtractedRecord] = []
        warnings: List[str] = []

        # Strategy 1: Attempt standard JSON parse
        try:
            data = json.loads(text)
            detected_format = "JSON"

            if isinstance(data, list):
                for idx, item in enumerate(data):
                    item_str = json.dumps(item) if isinstance(item, (dict, list)) else str(item)
                    records.append(ExtractedRecord(
                        record_id=f"{file_name}#item_{idx + 1}",
                        source_ref=SourceReference(
                            file_name=file_name,
                            location_type="json_object",
                            location_index=idx + 1
                        ),
                        record_type="json_object",
                        raw_text=item_str,
                        structured_data=item if isinstance(item, dict) else {"value": item}
                    ))
            elif isinstance(data, dict):
                records.append(ExtractedRecord(
                    record_id=f"{file_name}#root",
                    source_ref=SourceReference(
                        file_name=file_name,
                        location_type="json_object",
                        location_index=1
                    ),
                    record_type="json_object",
                    raw_text=json.dumps(data, indent=2),
                    structured_data=data
                ))

            preview = json.dumps(data, indent=2)
            if len(preview) > MAX_PREVIEW_CHARS:
                preview = preview[:MAX_PREVIEW_CHARS] + "\n... [Preview truncated] ..."

            return IngestedFile(
                file_name=file_name,
                detected_format=detected_format,
                status=IngestionStatus.SUCCESS,
                status_message=f"Successfully parsed JSON with {len(records)} record(s).",
                raw_evidence=raw_evidence,
                metadata={"record_count": len(records), "root_type": type(data).__name__, "encoding": encoding},
                extracted_text=preview,
                records=records
            )

        except json.JSONDecodeError:
            # Strategy 2: Attempt JSONL (Line-Delimited JSON) parse
            lines = text.splitlines()
            valid_jsonl_count = 0
            
            for line_no, line in enumerate(lines, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    obj = json.loads(clean_line)
                    valid_jsonl_count += 1
                    records.append(ExtractedRecord(
                        record_id=f"{file_name}#line_{line_no}",
                        source_ref=SourceReference(
                            file_name=file_name,
                            location_type="line",
                            location_index=line_no
                        ),
                        record_type="json_object",
                        raw_text=clean_line,
                        structured_data=obj if isinstance(obj, dict) else {"value": obj}
                    ))
                except json.JSONDecodeError:
                    warnings.append(f"Line {line_no} could not be parsed as JSON: {clean_line[:60]}")

            if valid_jsonl_count > 0:
                status = IngestionStatus.SUCCESS if not warnings else IngestionStatus.PARTIAL_SUCCESS
                msg = f"Parsed JSONL with {valid_jsonl_count} valid line(s)."
                if warnings:
                    msg += f" (Note: {len(warnings)} malformed line(s) skipped)."

                return IngestedFile(
                    file_name=file_name,
                    detected_format="JSONL",
                    status=status,
                    status_message=msg,
                    raw_evidence=raw_evidence,
                    metadata={"valid_lines": valid_jsonl_count, "skipped_lines": len(warnings), "encoding": encoding},
                    extracted_text=text[:MAX_PREVIEW_CHARS],
                    records=records,
                    warnings=warnings
                )

            # If both standard JSON and JSONL failed:
            return IngestedFile(
                file_name=file_name,
                detected_format="JSON",
                status=IngestionStatus.MALFORMED,
                status_message="Malformed JSON: Content could not be parsed as standard JSON or JSONL.",
                raw_evidence=raw_evidence,
                metadata={"encoding": encoding},
                errors=["Invalid JSON syntax"],
                extracted_text=text[:MAX_PREVIEW_CHARS]
            )


class TextLogParser:
    """
    Reads plain text (.txt, .md) and log (.log) files without crashing on encoding problems.
    """
    @staticmethod
    def parse(file_name: str, raw_bytes: bytes, file_path: Optional[str] = None) -> IngestedFile:
        ext = file_name.split(".")[-1].upper()
        detected_format = "LOG" if ext == "LOG" else "MD" if ext == "MD" else "TEXT"

        raw_evidence = RawEvidence(
            file_name=file_name,
            file_size_bytes=len(raw_bytes),
            file_hash_sha256=compute_sha256(raw_bytes),
            file_path=file_path,
            mime_type="text/plain"
        )

        if len(raw_bytes.strip()) == 0:
            return IngestedFile(
                file_name=file_name,
                detected_format=detected_format,
                status=IngestionStatus.EMPTY,
                status_message="File is empty (0 bytes).",
                raw_evidence=raw_evidence,
                metadata={"line_count": 0}
            )

        text, encoding = safe_decode_bytes(raw_bytes)
        lines = text.splitlines()

        records: List[ExtractedRecord] = []
        for line_no, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            records.append(ExtractedRecord(
                record_id=f"{file_name}#line_{line_no}",
                source_ref=SourceReference(
                    file_name=file_name,
                    location_type="line",
                    location_index=line_no
                ),
                record_type="log_line" if detected_format == "LOG" else "text_line",
                raw_text=line,
                structured_data={"line_text": line, "line_no": line_no}
            ))

        preview = text[:MAX_PREVIEW_CHARS]
        if len(text) > MAX_PREVIEW_CHARS:
            preview += "\n... [Preview truncated for display] ..."

        return IngestedFile(
            file_name=file_name,
            detected_format=detected_format,
            status=IngestionStatus.SUCCESS,
            status_message=f"Extracted {len(records)} line(s) ({len(lines)} total lines).",
            raw_evidence=raw_evidence,
            metadata={
                "line_count": len(lines),
                "non_empty_lines": len(records),
                "character_count": len(text),
                "encoding": encoding
            },
            extracted_text=preview,
            records=records
        )


class PDFParser:
    """
    Extracts text from PDF documents using pypdf.
    Maintains page-level provenance.
    """
    @staticmethod
    def parse(file_name: str, raw_bytes: bytes, file_path: Optional[str] = None) -> IngestedFile:
        raw_evidence = RawEvidence(
            file_name=file_name,
            file_size_bytes=len(raw_bytes),
            file_hash_sha256=compute_sha256(raw_bytes),
            file_path=file_path,
            mime_type="application/pdf"
        )

        if not PYPDF_AVAILABLE:
            return IngestedFile(
                file_name=file_name,
                detected_format="PDF",
                status=IngestionStatus.ERROR,
                status_message="pypdf library is not installed in current Python environment.",
                raw_evidence=raw_evidence,
                errors=["pypdf library missing"]
            )

        if len(raw_bytes) == 0:
            return IngestedFile(
                file_name=file_name,
                detected_format="PDF",
                status=IngestionStatus.EMPTY,
                status_message="PDF file is 0 bytes.",
                raw_evidence=raw_evidence,
                metadata={"page_count": 0}
            )

        try:
            stream = io.BytesIO(raw_bytes)
            reader = pypdf.PdfReader(stream)
            num_pages = len(reader.pages)
            records: List[ExtractedRecord] = []
            full_text_parts: List[str] = []
            warnings: List[str] = []

            for page_idx, page in enumerate(reader.pages):
                page_no = page_idx + 1
                try:
                    page_text = page.extract_text() or ""
                    clean_text = page_text.strip()
                    if clean_text:
                        records.append(ExtractedRecord(
                            record_id=f"{file_name}#page_{page_no}",
                            source_ref=SourceReference(
                                file_name=file_name,
                                location_type="page",
                                location_index=page_no
                            ),
                            record_type="document_page",
                            raw_text=clean_text,
                            structured_data={"page_number": page_no, "text": clean_text}
                        ))
                        full_text_parts.append(f"--- [Page {page_no}] ---\n{clean_text}")
                    else:
                        warnings.append(f"Page {page_no} contains no extractable text (may be scanned image).")
                except Exception as page_err:
                    warnings.append(f"Could not extract text from page {page_no}: {str(page_err)}")

            combined_text = "\n\n".join(full_text_parts)
            preview = combined_text[:MAX_PREVIEW_CHARS]
            if len(combined_text) > MAX_PREVIEW_CHARS:
                preview += "\n... [Preview truncated for display] ..."

            if not records:
                # PDF has pages, but no extractable text (e.g. scanned image PDF)
                return IngestedFile(
                    file_name=file_name,
                    detected_format="PDF",
                    status=IngestionStatus.PARTIAL_SUCCESS,
                    status_message=f"PDF opened ({num_pages} page(s)), but contains no selectable digital text. Scanned pages require OCR.",
                    raw_evidence=raw_evidence,
                    metadata={"page_count": num_pages, "is_scanned_likely": True},
                    extracted_text="[No digital text found in PDF. File appears to be scanned or image-based.]",
                    warnings=warnings
                )

            status = IngestionStatus.SUCCESS if not warnings else IngestionStatus.PARTIAL_SUCCESS
            return IngestedFile(
                file_name=file_name,
                detected_format="PDF",
                status=status,
                status_message=f"Extracted digital text from {len(records)} page(s) ({num_pages} total pages).",
                raw_evidence=raw_evidence,
                metadata={
                    "page_count": num_pages,
                    "pages_with_text": len(records),
                    "character_count": len(combined_text)
                },
                extracted_text=preview,
                records=records,
                warnings=warnings
            )

        except Exception as e:
            return IngestedFile(
                file_name=file_name,
                detected_format="PDF",
                status=IngestionStatus.MALFORMED,
                status_message=f"Corrupted or invalid PDF document: {str(e)}",
                raw_evidence=raw_evidence,
                errors=[str(e)]
            )


class ImageParser:
    """
    Parses image evidence using PIL and attempts local OCR via pytesseract.
    If OCR is unavailable, explicitly reports that the image was not fully inspected.
    Never silently treats image evidence as empty.
    """
    @staticmethod
    def parse(file_name: str, raw_bytes: bytes, file_path: Optional[str] = None) -> IngestedFile:
        raw_evidence = RawEvidence(
            file_name=file_name,
            file_size_bytes=len(raw_bytes),
            file_hash_sha256=compute_sha256(raw_bytes),
            file_path=file_path,
            mime_type="image"
        )

        if len(raw_bytes) == 0:
            return IngestedFile(
                file_name=file_name,
                detected_format="IMAGE",
                status=IngestionStatus.EMPTY,
                status_message="Image file is 0 bytes.",
                raw_evidence=raw_evidence
            )

        try:
            stream = io.BytesIO(raw_bytes)
            image = Image.open(stream)
            image.verify() # Verify file header integrity

            # Re-open after verify() as PIL requires
            stream.seek(0)
            image = Image.open(stream)

            img_metadata = {
                "dimensions": f"{image.width}x{image.height}",
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "color_mode": image.mode
            }

            # Attempt local OCR
            ocr_text = ""
            ocr_successful = False
            ocr_error_reason = ""

            if PYTESSERACT_AVAILABLE:
                try:
                    ocr_text = pytesseract.image_to_string(image).strip()
                    ocr_successful = True
                except Exception as ocr_err:
                    ocr_error_reason = f"OCR engine failed: {type(ocr_err).__name__}: {str(ocr_err)}"
            else:
                ocr_error_reason = "pytesseract library not available in Python environment."

            records: List[ExtractedRecord] = []
            
            # Record 1: Image provenance metadata record
            records.append(ExtractedRecord(
                record_id=f"{file_name}#metadata",
                source_ref=SourceReference(
                    file_name=file_name,
                    location_type="image_metadata"
                ),
                record_type="image_metadata",
                raw_text=f"Image {file_name}: {img_metadata['dimensions']}, Mode: {img_metadata['color_mode']}, Format: {img_metadata['format']}",
                structured_data=img_metadata
            ))

            if ocr_successful and ocr_text:
                # OCR succeeded and extracted text
                records.append(ExtractedRecord(
                    record_id=f"{file_name}#ocr_text",
                    source_ref=SourceReference(
                        file_name=file_name,
                        location_type="page",
                        location_index=1
                    ),
                    record_type="ocr_text",
                    raw_text=ocr_text,
                    structured_data={"extracted_ocr_text": ocr_text}
                ))

                preview = f"[Image: {img_metadata['dimensions']} {img_metadata['format']}]\n\n--- OCR EXTRACTED TEXT ---\n{ocr_text}"
                return IngestedFile(
                    file_name=file_name,
                    detected_format="IMAGE",
                    status=IngestionStatus.SUCCESS,
                    status_message=f"Image verified ({img_metadata['dimensions']}) and local OCR successfully extracted text.",
                    raw_evidence=raw_evidence,
                    metadata={**img_metadata, "ocr_applied": True, "ocr_characters": len(ocr_text)},
                    extracted_text=preview[:MAX_PREVIEW_CHARS],
                    records=records
                )
            else:
                # Local OCR was not available or could not extract text
                warning_msg = (
                    "⚠️ Image format verified, but local OCR engine (Tesseract) is not installed on this system. "
                    "Visual text inside this screenshot/document was NOT inspected. "
                    "Do NOT treat this as empty evidence; manual review or Tesseract setup is required."
                )
                if ocr_error_reason and "TesseractNotFoundError" not in ocr_error_reason:
                    warning_msg += f" (Detail: {ocr_error_reason})"

                preview = (
                    f"[Image Verified: {img_metadata['dimensions']}, {img_metadata['format']}, {img_metadata['color_mode']}]\n"
                    f"Status: NOT FULLY INSPECTED (OCR engine unavailable)\n\n"
                    f"Notice: This image may contain customer names, emails, addresses, or order IDs that cannot be automatically parsed without Tesseract OCR."
                )

                return IngestedFile(
                    file_name=file_name,
                    detected_format="IMAGE",
                    status=IngestionStatus.PARTIAL_SUCCESS,
                    status_message="Image metadata extracted, but OCR text was NOT inspected.",
                    raw_evidence=raw_evidence,
                    metadata={**img_metadata, "ocr_applied": False, "ocr_status": "UNAVAILABLE"},
                    extracted_text=preview,
                    records=records,
                    warnings=[warning_msg]
                )

        except Exception as e:
            return IngestedFile(
                file_name=file_name,
                detected_format="IMAGE",
                status=IngestionStatus.MALFORMED,
                status_message=f"Invalid or corrupted image file: {str(e)}",
                raw_evidence=raw_evidence,
                errors=[str(e)]
            )


class SQLParser:
    """
    Parses SQLite-compatible SQL database snapshot exports.
    Identifies table schemas, statements, and row data.
    """
    @staticmethod
    def parse(file_name: str, raw_bytes: bytes, file_path: Optional[str] = None) -> IngestedFile:
        raw_evidence = RawEvidence(
            file_name=file_name,
            file_size_bytes=len(raw_bytes),
            file_hash_sha256=compute_sha256(raw_bytes),
            file_path=file_path,
            mime_type="application/sql"
        )

        if len(raw_bytes.strip()) == 0:
            return IngestedFile(
                file_name=file_name,
                detected_format="SQL",
                status=IngestionStatus.EMPTY,
                status_message="SQL snapshot file is 0 bytes.",
                raw_evidence=raw_evidence
            )

        text, encoding = safe_decode_bytes(raw_bytes)
        lines = text.splitlines()

        tables_found = set()
        insert_count = 0
        records: List[ExtractedRecord] = []

        for line_no, line in enumerate(lines, start=1):
            clean = line.strip()
            if not clean or clean.startswith("--"):
                continue

            upper = clean.upper()
            if "CREATE TABLE" in upper:
                # Rough table name extraction
                parts = clean.split()
                if len(parts) >= 3:
                    table_name = parts[2].strip("`\"'([]):;")
                    tables_found.add(table_name)
            elif "INSERT INTO" in upper:
                insert_count += 1

            records.append(ExtractedRecord(
                record_id=f"{file_name}#line_{line_no}",
                source_ref=SourceReference(
                    file_name=file_name,
                    location_type="line",
                    location_index=line_no
                ),
                record_type="sql_statement",
                raw_text=clean,
                structured_data={"line_no": line_no, "sql": clean}
            ))

        preview = text[:MAX_PREVIEW_CHARS]
        if len(text) > MAX_PREVIEW_CHARS:
            preview += "\n... [Preview truncated for display] ..."

        return IngestedFile(
            file_name=file_name,
            detected_format="SQL",
            status=IngestionStatus.SUCCESS,
            status_message=f"Parsed SQL snapshot: {len(tables_found)} table(s), {insert_count} insert(s), {len(records)} active lines.",
            raw_evidence=raw_evidence,
            metadata={
                "tables_detected": sorted(list(tables_found)),
                "insert_statements": insert_count,
                "total_lines": len(lines),
                "encoding": encoding
            },
            extracted_text=preview,
            records=records
        )


class FallbackParser:
    """
    Fallback parser for unsupported or unknown file types.
    Preserves raw evidence without crashing.
    """
    @staticmethod
    def parse(file_name: str, raw_bytes: bytes, file_path: Optional[str] = None) -> IngestedFile:
        ext = file_name.split(".")[-1].upper() if "." in file_name else "UNKNOWN"
        raw_evidence = RawEvidence(
            file_name=file_name,
            file_size_bytes=len(raw_bytes),
            file_hash_sha256=compute_sha256(raw_bytes),
            file_path=file_path,
            mime_type="application/octet-stream"
        )

        return IngestedFile(
            file_name=file_name,
            detected_format=ext,
            status=IngestionStatus.UNSUPPORTED,
            status_message=f"Unsupported format .{ext.lower()}. Raw binary evidence preserved without loss.",
            raw_evidence=raw_evidence,
            metadata={"file_size": len(raw_bytes)},
            extracted_text=f"[Binary file: {len(raw_bytes)} bytes. Format .{ext.lower()} does not have an automatic text parser.]"
        )

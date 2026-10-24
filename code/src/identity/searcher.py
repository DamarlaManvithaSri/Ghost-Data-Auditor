"""
Cross-System Identity Searcher for Ghost Data Auditor.
Searches all discovered current and historical identifiers across all ingested evidence files.
Maintains exact provenance linking each hit back to the specific evidence file and row/page number.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Set, Optional

from .models import ResolvedIdentity, IdentifierType
from src.ingestion import EvidenceManager, ExtractedRecord


@dataclass
class IdentityOccurrence:
    """
    Represents an evidence record where a customer's identifier was detected.
    """
    target_user_id: str
    file_name: str
    source_reference: str            # e.g., "customer_accounts_failover.sql (Line 42)"
    matched_identifier_type: str     # USER_ID, EMAIL, PHONE, EMAIL_HASH, NAME
    matched_value: str               # The exact identifier matched
    is_historical: bool              # True if matched against a former/historical identifier
    record_type: str                 # tabular_row, log_line, document_page, sql_statement
    snippet: str                     # Contextual text snippet where identifier appeared
    raw_record: ExtractedRecord      # Underlying extracted evidence record


class CrossSystemIdentitySearcher:
    """
    Scans ingested evidence files for any trace of a resolved customer's identity.
    """
    def __init__(self, evidence_manager: EvidenceManager):
        self.evidence_manager = evidence_manager

    def search_customer_records(
        self,
        identity: ResolvedIdentity,
        include_name: bool = False
    ) -> List[IdentityOccurrence]:
        """
        Searches across all evidence in the EvidenceManager for occurrences of the customer's identifiers.

        Args:
            identity: The ResolvedIdentity dossier for the customer.
            include_name: If True, also searches for the full name. Default is False to avoid
                          spurious matches for common names unless explicitly requested.

        Returns:
            A list of IdentityOccurrence objects detailing where data lingers.
        """
        occurrences: List[IdentityOccurrence] = []
        user_id = identity.user_id or identity.seed_identifier

        # Build search catalog mapping search term -> (type, is_historical)
        search_catalog: Dict[str, Dict[str, Any]] = {}

        # 1. User ID (Exact word boundary match)
        if identity.user_id:
            search_catalog[identity.user_id] = {
                "type": IdentifierType.USER_ID.value,
                "is_historical": False,
                "pattern": re.compile(rf"\b{re.escape(identity.user_id)}\b", re.IGNORECASE)
            }

        # 2. Current Emails
        for email in identity.current_identifiers.get(IdentifierType.EMAIL.value, set()):
            if email:
                search_catalog[email] = {
                    "type": IdentifierType.EMAIL.value,
                    "is_historical": False,
                    "pattern": re.compile(rf"\b{re.escape(email)}\b", re.IGNORECASE)
                }

        # 3. Historical Emails
        for email in identity.historical_identifiers.get(IdentifierType.EMAIL.value, set()):
            if email:
                search_catalog[email] = {
                    "type": IdentifierType.EMAIL.value,
                    "is_historical": True,
                    "pattern": re.compile(rf"\b{re.escape(email)}\b", re.IGNORECASE)
                }

        # 4. Email Hashes
        all_hashes = set()
        all_hashes.update(identity.current_identifiers.get(IdentifierType.EMAIL_HASH.value, set()))
        all_hashes.update(identity.historical_identifiers.get(IdentifierType.EMAIL_HASH.value, set()))
        for h in all_hashes:
            if h and len(h) == 64:
                search_catalog[h] = {
                    "type": IdentifierType.EMAIL_HASH.value,
                    "is_historical": h in identity.historical_identifiers.get(IdentifierType.EMAIL_HASH.value, set()),
                    "pattern": re.compile(rf"\b{re.escape(h)}\b", re.IGNORECASE)
                }

        # 5. Phone numbers
        for ph in identity.get_phones():
            if ph and len(ph) >= 7:
                search_catalog[ph] = {
                    "type": IdentifierType.PHONE.value,
                    "is_historical": ph in identity.historical_identifiers.get(IdentifierType.PHONE.value, set()),
                    "pattern": re.compile(rf"{re.escape(ph)}", re.IGNORECASE)
                }

        # 6. Optional: Full Name
        if include_name:
            for name in identity.current_identifiers.get(IdentifierType.NAME.value, set()):
                if name and len(name) >= 4:
                    search_catalog[name] = {
                        "type": IdentifierType.NAME.value,
                        "is_historical": False,
                        "pattern": re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
                    }

        # Scan all files and records in evidence manager
        for file_obj in self.evidence_manager.get_all_files():
            for rec in file_obj.records:
                text = rec.raw_text

                for term, info in search_catalog.items():
                    pattern = info["pattern"]
                    if pattern.search(text):
                        # Matched this record!
                        source_ref_str = rec.source_ref.to_display_string()
                        snippet = text[:180] + ("..." if len(text) > 180 else "")

                        occurrences.append(IdentityOccurrence(
                            target_user_id=user_id,
                            file_name=file_obj.file_name,
                            source_reference=source_ref_str,
                            matched_identifier_type=info["type"],
                            matched_value=term,
                            is_historical=info["is_historical"],
                            record_type=rec.record_type,
                            snippet=snippet,
                            raw_record=rec
                        ))
                        # Break inner loop to avoid duplicate hits on the same record if multiple terms match
                        break

        return occurrences

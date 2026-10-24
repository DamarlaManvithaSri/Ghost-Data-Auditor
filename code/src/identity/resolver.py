"""
Identity Resolver Engine for Ghost Data Auditor.
Deterministically resolves current and historical identifiers across identity snapshots and audit logs.
Preserves strict evidence provenance and respects temporal cutoffs (audit_at).
"""

import os
from typing import Dict, List, Set, Any, Optional
import pandas as pd

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


class IdentityResolver:
    """
    Reconstructs an individual's complete identity lineage from current snapshots and historical audit logs.
    """
    def __init__(
        self,
        identities_df: Optional[pd.DataFrame] = None,
        audit_log_df: Optional[pd.DataFrame] = None
    ):
        """
        Initializes the resolver with provided DataFrames or loads from default dataset files.
        """
        self.identities_df = identities_df
        self.audit_log_df = audit_log_df

        # If dataframes not provided, lazily attempt to load from local dataset/
        if self.identities_df is None:
            self._load_default_identities()
        if self.audit_log_df is None:
            self._load_default_audit_log()

    def _load_default_identities(self):
        path = os.path.join(os.getcwd(), "dataset", "user_identities.csv")
        if os.path.exists(path):
            try:
                self.identities_df = pd.read_csv(path)
            except Exception:
                self.identities_df = pd.DataFrame()
        else:
            self.identities_df = pd.DataFrame()

    def _load_default_audit_log(self):
        path = os.path.join(os.getcwd(), "dataset", "user_audit_log.csv")
        if os.path.exists(path):
            try:
                self.audit_log_df = pd.read_csv(path)
            except Exception:
                self.audit_log_df = pd.DataFrame()
        else:
            self.audit_log_df = pd.DataFrame()

    def resolve(
        self,
        seed_identifier: str,
        audit_cutoff_time: Optional[str] = None
    ) -> ResolvedIdentity:
        """
        Resolves a person's current and historical identity given a seed email or user ID.

        Args:
            seed_identifier: The email or user_id supplied with the deletion request.
            audit_cutoff_time: Optional ISO-8601 timestamp (audit_at). Evidence captured
                               after this cutoff is strictly ignored.

        Returns:
            A ResolvedIdentity object with all discovered links, provenance, and conflict flags.
        """
        clean_seed = seed_identifier.strip()
        clean_seed_email = normalize_email(clean_seed)

        resolved = ResolvedIdentity(seed_identifier=clean_seed)
        candidate_user_ids: Set[str] = set()

        # -------------------------------------------------------------
        # STEP 1: Discover candidate user_id from Current Snapshot
        # -------------------------------------------------------------
        if self.identities_df is not None and not self.identities_df.empty:
            for _, row in self.identities_df.iterrows():
                row_user_id = str(row.get("user_id", "")).strip()
                row_email = str(row.get("email", "")).strip()
                row_email_norm = normalize_email(row_email)

                # Match if seed equals user_id or email
                if (clean_seed and row_user_id == clean_seed) or (clean_seed_email and row_email_norm == clean_seed_email):
                    candidate_user_ids.add(row_user_id)

        # -------------------------------------------------------------
        # STEP 2: Discover candidate user_id from Audit Log (Historical)
        # -------------------------------------------------------------
        if self.audit_log_df is not None and not self.audit_log_df.empty:
            for _, log_row in self.audit_log_df.iterrows():
                event_time = str(log_row.get("event_time", ""))
                if audit_cutoff_time and event_time and event_time > audit_cutoff_time:
                    continue # Ignore events after audit cutoff

                u_id = str(log_row.get("user_id", "")).strip()
                field_name = str(log_row.get("field_name", "")).strip().lower()
                old_val = str(log_row.get("old_value", "")).strip()
                new_val = str(log_row.get("new_value", "")).strip()

                if clean_seed and u_id == clean_seed:
                    candidate_user_ids.add(u_id)
                elif field_name == "email":
                    if normalize_email(old_val) == clean_seed_email or normalize_email(new_val) == clean_seed_email:
                        if u_id:
                            candidate_user_ids.add(u_id)

        # -------------------------------------------------------------
        # STEP 3: Populate Dossier for Candidate User(s)
        # -------------------------------------------------------------
        for uid in list(candidate_user_ids):
            # A) Populate Current Snapshot Data for this uid
            if self.identities_df is not None and not self.identities_df.empty:
                user_rows = self.identities_df[self.identities_df["user_id"] == uid]
                for row_idx, row in user_rows.iterrows():
                    updated_at = row.get("updated_at")
                    if audit_cutoff_time and updated_at and str(updated_at) > audit_cutoff_time:
                        resolved.conflicts.append(
                            f"Identity snapshot for {uid} is timestamped {updated_at}, which is after audit cutoff {audit_cutoff_time}."
                        )

                    row_email = str(row.get("email", "")).strip()
                    row_email_norm = normalize_email(row_email)
                    name = str(row.get("name", "")).strip()
                    phone = str(row.get("phone", "")).strip()
                    phone_norm = normalize_phone(phone)
                    email_hash = str(row.get("email_hash", "")).strip().lower()
                    if not email_hash and row_email_norm:
                        email_hash = compute_email_hash(row_email_norm)

                    # Register current identifiers
                    self._add_identifier(resolved.current_identifiers, IdentifierType.USER_ID.value, uid)
                    if row_email_norm:
                        self._add_identifier(resolved.current_identifiers, IdentifierType.EMAIL.value, row_email_norm)
                    if phone_norm:
                        self._add_identifier(resolved.current_identifiers, IdentifierType.PHONE.value, phone_norm)
                    if email_hash:
                        self._add_identifier(resolved.current_identifiers, IdentifierType.EMAIL_HASH.value, email_hash)
                    if name:
                        self._add_identifier(resolved.current_identifiers, IdentifierType.NAME.value, name)

                    # Register confirmed links
                    source_loc = f"Row {row_idx + 1}"
                    resolved.links.append(IdentityLink(
                        target_user_id=uid,
                        identifier_type=IdentifierType.USER_ID,
                        identifier_value=uid,
                        raw_value=uid,
                        confidence=LinkConfidence.CONFIRMED,
                        source_file="user_identities.csv",
                        source_location=source_loc,
                        evidence_text=f"user_id: {uid}, email: {row_email}",
                        timestamp=str(updated_at) if updated_at else None,
                        justification="Primary stable user reference in current identity snapshot."
                    ))

                    if row_email:
                        resolved.links.append(IdentityLink(
                            target_user_id=uid,
                            identifier_type=IdentifierType.EMAIL,
                            identifier_value=row_email_norm,
                            raw_value=row_email,
                            confidence=LinkConfidence.CONFIRMED,
                            source_file="user_identities.csv",
                            source_location=source_loc,
                            evidence_text=f"Current email: {row_email}",
                            timestamp=str(updated_at) if updated_at else None,
                            justification="Current registered email address in identity snapshot."
                        ))

                    if phone:
                        resolved.links.append(IdentityLink(
                            target_user_id=uid,
                            identifier_type=IdentifierType.PHONE,
                            identifier_value=phone_norm,
                            raw_value=phone,
                            confidence=LinkConfidence.CONFIRMED,
                            source_file="user_identities.csv",
                            source_location=source_loc,
                            evidence_text=f"Current phone: {phone}",
                            timestamp=str(updated_at) if updated_at else None,
                            justification="Current registered phone number in identity snapshot."
                        ))

                    if email_hash:
                        resolved.links.append(IdentityLink(
                            target_user_id=uid,
                            identifier_type=IdentifierType.EMAIL_HASH,
                            identifier_value=email_hash,
                            raw_value=email_hash,
                            confidence=LinkConfidence.CONFIRMED,
                            source_file="user_identities.csv",
                            source_location=source_loc,
                            evidence_text=f"email_hash: {email_hash}",
                            timestamp=str(updated_at) if updated_at else None,
                            justification="Computed SHA-256 hash of active customer email."
                        ))

                    if name:
                        resolved.links.append(IdentityLink(
                            target_user_id=uid,
                            identifier_type=IdentifierType.NAME,
                            identifier_value=name,
                            raw_value=name,
                            confidence=LinkConfidence.PROBABLE,
                            source_file="user_identities.csv",
                            source_location=source_loc,
                            evidence_text=f"Full name: {name}",
                            timestamp=str(updated_at) if updated_at else None,
                            justification="Customer name linked to confirmed user_id (not used as a standalone unique key)."
                        ))

            # B) Populate Historical Changes for this uid from Audit Log
            if self.audit_log_df is not None and not self.audit_log_df.empty:
                user_logs = self.audit_log_df[self.audit_log_df["user_id"] == uid]

                for row_idx, log_row in user_logs.iterrows():
                    audit_id = str(log_row.get("audit_id", f"log_{row_idx}"))
                    event_time = str(log_row.get("event_time", ""))
                    field_name = str(log_row.get("field_name", "")).strip().lower()
                    old_val = str(log_row.get("old_value", "")).strip()
                    new_val = str(log_row.get("new_value", "")).strip()

                    # Temporal integrity: ignore events that occurred AFTER audit_at
                    if audit_cutoff_time and event_time and event_time > audit_cutoff_time:
                        continue

                    # Record timeline event
                    resolved.timeline.append({
                        "audit_id": audit_id,
                        "event_time": event_time,
                        "field_name": field_name,
                        "old_value": old_val,
                        "new_value": new_val
                    })

                    id_type = None
                    if field_name == "email":
                        id_type = IdentifierType.EMAIL
                        old_norm = normalize_email(old_val)
                        new_norm = normalize_email(new_val)
                    elif field_name == "phone":
                        id_type = IdentifierType.PHONE
                        old_norm = normalize_phone(old_val)
                        new_norm = normalize_phone(new_val)
                    elif field_name == "name":
                        id_type = IdentifierType.NAME
                        old_norm = old_val
                        new_norm = new_val

                    if id_type and old_val and old_val.lower() != "none" and old_val.lower() != "nan":
                        self._add_identifier(resolved.historical_identifiers, id_type.value, old_norm)

                        resolved.links.append(IdentityLink(
                            target_user_id=uid,
                            identifier_type=id_type,
                            identifier_value=old_norm,
                            raw_value=old_val,
                            confidence=LinkConfidence.CONFIRMED,
                            source_file="user_audit_log.csv",
                            source_location=f"Audit ID: {audit_id}",
                            evidence_text=f"{field_name} changed from '{old_val}' to '{new_val}'",
                            is_historical=True,
                            timestamp=event_time,
                            justification=f"Historical {field_name} changed on {event_time}. Replaced by '{new_val}'."
                        ))

                        if id_type == IdentifierType.EMAIL:
                            hist_hash = compute_email_hash(old_norm)
                            self._add_identifier(resolved.historical_identifiers, IdentifierType.EMAIL_HASH.value, hist_hash)
                            resolved.links.append(IdentityLink(
                                target_user_id=uid,
                                identifier_type=IdentifierType.EMAIL_HASH,
                                identifier_value=hist_hash,
                                raw_value=hist_hash,
                                confidence=LinkConfidence.CONFIRMED,
                                source_file="user_audit_log.csv",
                                source_location=f"Audit ID: {audit_id}",
                                evidence_text=f"Derived from historical email {old_val}",
                                is_historical=True,
                                timestamp=event_time,
                                justification=f"SHA-256 hash of former email '{old_val}'."
                            ))

        # -------------------------------------------------------------
        # STEP 4: Validate Conflicts and Ambiguities
        # -------------------------------------------------------------
        if len(candidate_user_ids) == 1:
            resolved.user_id = list(candidate_user_ids)[0]
            resolved.status = "RESOLVED"
        elif len(candidate_user_ids) > 1:
            resolved.status = "CONFLICT"
            conflict_msg = f"Ambiguous identity: Seed '{clean_seed}' matches multiple user accounts: {sorted(list(candidate_user_ids))}."
            resolved.conflicts.append(conflict_msg)
        else:
            resolved.status = "UNRESOLVED"
            resolved.conflicts.append(f"No customer identity found matching seed '{clean_seed}' up to cutoff time.")

        return resolved

    def _add_identifier(self, store: Dict[str, Set[str]], key: str, value: str):
        """Helper to add unique normalized values to an identifier store."""
        if not value:
            return
        if key not in store:
            store[key] = set()
        store[key].add(value)

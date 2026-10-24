"""
Submission Output Validation Engine for Ghost Data Auditor.
Performs rigorous schema, column-order, row-count, JSON-syntax, step-schema,
and phase-ordering validation on output.csv prior to submission.
"""

import os
import json
from typing import List, Dict, Any, Optional, Set
import pandas as pd

from .models import (
    REQUIRED_COLUMNS,
    ALLOWED_STATUSES,
    REQUIRED_STEP_FIELDS,
    ALLOWED_OPERATIONS,
    PHASE_ORDER,
    OPERATION_ORDER,
    ValidationResult
)


class OutputValidator:
    """
    Validates output.csv against all HackerRank challenge specifications and grading criteria.
    """

    @classmethod
    def validate_file(
        cls,
        csv_path: str,
        expected_requests_path: Optional[str] = None,
        expected_count: Optional[int] = None
    ) -> ValidationResult:
        """
        Validates an output CSV file from disk.
        """
        res = ValidationResult()

        if not os.path.exists(csv_path):
            res.add_error(f"File not found: {csv_path}")
            return res

        try:
            # Read all columns as string to avoid type coercion or NaN issues
            df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        except Exception as e:
            res.add_error(f"Failed to read CSV file: {str(e)}")
            return res

        expected_req_df = None
        if expected_requests_path and os.path.exists(expected_requests_path):
            try:
                expected_req_df = pd.read_csv(expected_requests_path, dtype=str, keep_default_na=False)
            except Exception:
                pass

        return cls.validate_dataframe(df, expected_requests_df=expected_req_df, expected_count=expected_count)

    @classmethod
    def validate_dataframe(
        cls,
        df: pd.DataFrame,
        expected_requests_df: Optional[pd.DataFrame] = None,
        expected_count: Optional[int] = None
    ) -> ValidationResult:
        """
        Validates an in-memory DataFrame against the required schema.
        """
        res = ValidationResult()
        res.total_rows = len(df)
        res.columns_found = list(df.columns)

        # -------------------------------------------------------------
        # 1. Exact Column Names & Column Order
        # -------------------------------------------------------------
        if list(df.columns) != REQUIRED_COLUMNS:
            res.column_order_valid = False
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            extra = [c for c in df.columns if c not in REQUIRED_COLUMNS]

            if missing:
                res.add_error(f"Missing required columns: {missing}. Expected exactly: {REQUIRED_COLUMNS}")
            if extra:
                res.add_error(f"Forbidden extra columns detected: {extra}. Evaluation strictly requires only {REQUIRED_COLUMNS}")
            if not missing and not extra and list(df.columns) != REQUIRED_COLUMNS:
                res.add_error(f"Incorrect column order: {list(df.columns)}. Expected exact order: {REQUIRED_COLUMNS}")

        # -------------------------------------------------------------
        # 2. Row Count & Case Alignment
        # -------------------------------------------------------------
        if expected_count is not None:
            res.expected_rows = expected_count
            if len(df) != expected_count:
                res.add_error(f"Row count mismatch: found {len(df)} rows, expected exactly {expected_count} rows.")

        if expected_requests_df is not None and not expected_requests_df.empty:
            expected_case_ids = [str(c).strip() for c in expected_requests_df["case_id"].tolist()]
            res.expected_rows = len(expected_case_ids)

            actual_case_ids = [str(c).strip() for c in df["case_id"].tolist()] if "case_id" in df.columns else []

            # Check duplicates
            if len(actual_case_ids) != len(set(actual_case_ids)):
                dupes = [cid for cid in actual_case_ids if actual_case_ids.count(cid) > 1]
                res.add_error(f"Duplicate case_id entries found in output: {set(dupes)}")

            # Check missing cases
            missing_cases = set(expected_case_ids) - set(actual_case_ids)
            if missing_cases:
                sample_missing = list(missing_cases)[:5]
                res.add_error(f"Missing {len(missing_cases)} required cases from dataset (e.g. {sample_missing})")

            # Check extra cases
            extra_cases = set(actual_case_ids) - set(expected_case_ids)
            if extra_cases:
                sample_extra = list(extra_cases)[:5]
                res.add_error(f"Output contains {len(extra_cases)} unexpected cases (e.g. {sample_extra})")

            # Check row count against expected requests
            if len(df) != len(expected_case_ids):
                res.add_error(f"Total rows ({len(df)}) does not match required request count ({len(expected_case_ids)})")

        # If columns are missing, we cannot proceed with row validation
        if not all(col in df.columns for col in REQUIRED_COLUMNS):
            return res

        # -------------------------------------------------------------
        # 3. Status Labels, JSON Syntax & Step Schema Validation
        # -------------------------------------------------------------
        status_counts = {}

        for row_idx, row in df.iterrows():
            line_no = row_idx + 2 # 1-based header + 1
            case_id = str(row.get("case_id", "")).strip()
            status = str(row.get("deletion_status", "")).strip()
            steps_raw = str(row.get("steps_json", "")).strip()

            # Tally status
            status_counts[status] = status_counts.get(status, 0) + 1

            # Check status validity
            if status not in ALLOWED_STATUSES:
                res.statuses_valid = False
                res.add_error(
                    f"Line {line_no} (Case {case_id}): Invalid deletion_status '{status}'. "
                    f"Must be one of {sorted(list(ALLOWED_STATUSES))}"
                )

            # Check JSON parsing
            try:
                steps_data = json.loads(steps_raw)
            except Exception as e:
                res.json_syntax_valid = False
                res.add_error(f"Line {line_no} (Case {case_id}): Malformed JSON in steps_json: {str(e)}")
                continue

            if not isinstance(steps_data, list):
                res.json_syntax_valid = False
                res.add_error(f"Line {line_no} (Case {case_id}): steps_json must parse to a JSON array, got {type(steps_data).__name__}")
                continue

            # Special Rule: NOT_APPLICABLE must have empty array []
            if status == "NOT_APPLICABLE":
                if len(steps_data) != 0:
                    res.step_schema_valid = False
                    res.add_error(
                        f"Line {line_no} (Case {case_id}): Status is NOT_APPLICABLE but steps_json contains "
                        f"{len(steps_data)} steps. Must be an empty array []."
                    )
                continue

            # Special Rule: COMPLETE must have only VERIFICATION steps
            if status == "COMPLETE":
                for s_idx, s in enumerate(steps_data, start=1):
                    if not isinstance(s, dict):
                        continue
                    if s.get("phase") != "VERIFICATION":
                        res.step_schema_valid = False
                        res.add_error(
                            f"Line {line_no} (Case {case_id}, Step {s_idx}): Case is COMPLETE but contains a "
                            f"'{s.get('phase')}' step. COMPLETE cases must contain ONLY VERIFICATION steps."
                        )
                    if not s.get("evidence_id"):
                        res.step_schema_valid = False
                        res.add_error(
                            f"Line {line_no} (Case {case_id}, Step {s_idx}): Case is COMPLETE but verification "
                            f"step lacks an evidence_id. Must cite evidence proving compliant state."
                        )

            # Step-level structural validation
            last_phase_rank = 0
            last_step_no = 0

            for s_idx, s in enumerate(steps_data, start=1):
                if not isinstance(s, dict):
                    res.step_schema_valid = False
                    res.add_error(f"Line {line_no} (Case {case_id}, Step {s_idx}): Step item is not a JSON object.")
                    continue

                # Missing step fields
                missing_fields = REQUIRED_STEP_FIELDS - set(s.keys())
                if missing_fields:
                    res.step_schema_valid = False
                    res.add_error(f"Line {line_no} (Case {case_id}, Step {s_idx}): Missing required fields {missing_fields}")

                step_no = s.get("step_no")
                phase = s.get("phase")
                op = s.get("operation")
                state = s.get("state")
                ev_id = s.get("evidence_id", "")

                # Consecutive step numbering
                if step_no != last_step_no + 1:
                    res.step_schema_valid = False
                    res.add_error(
                        f"Line {line_no} (Case {case_id}, Step {s_idx}): Non-consecutive step_no: found {step_no}, expected {last_step_no + 1}."
                    )
                last_step_no = step_no if isinstance(step_no, int) else s_idx

                # Phase validation
                if phase not in PHASE_ORDER:
                    res.step_schema_valid = False
                    res.add_error(f"Line {line_no} (Case {case_id}, Step {s_idx}): Invalid phase '{phase}'.")
                else:
                    curr_phase_rank = PHASE_ORDER[phase]
                    if curr_phase_rank < last_phase_rank:
                        res.step_schema_valid = False
                        res.add_error(
                            f"Line {line_no} (Case {case_id}, Step {s_idx}): Phase out of order: '{phase}' appeared after later phase. "
                            f"Phases must strictly follow FINDING -> REMEDIATION -> VERIFICATION."
                        )
                    last_phase_rank = curr_phase_rank

                # Operation validation
                if op not in ALLOWED_OPERATIONS:
                    res.step_schema_valid = False
                    res.add_error(f"Line {line_no} (Case {case_id}, Step {s_idx}): Unrecognized operation '{op}'.")
                else:
                    op_meta = ALLOWED_OPERATIONS[op]
                    if phase and op_meta["phase"] != phase:
                        res.step_schema_valid = False
                        res.add_error(
                            f"Line {line_no} (Case {case_id}, Step {s_idx}): Operation '{op}' is not allowed in phase '{phase}' "
                            f"(expected {op_meta['phase']})."
                        )
                    if state not in op_meta["allowed_states"]:
                        res.step_schema_valid = False
                        res.add_error(
                            f"Line {line_no} (Case {case_id}, Step {s_idx}): Invalid state '{state}' for operation '{op}'. "
                            f"Allowed states: {op_meta['allowed_states']}."
                        )

                # Future action evidence_id rule
                if status == "INCOMPLETE" and phase in ["REMEDIATION", "VERIFICATION"] and ev_id != "":
                    # Proposed remediation or post-remediation verification in INCOMPLETE case must use ""
                    # (Unless it's a retained record verified present during initial audit)
                    if op != "VERIFY_RECORD_PRESENT":
                        res.add_warning(
                            f"Line {line_no} (Case {case_id}, Step {s_idx}): Proposed {phase} step has non-empty evidence_id '{ev_id}'. "
                            f"Future proposed actions should use empty string \"\"."
                        )

        res.status_counts = status_counts
        return res

"""
Unit tests for Final Output Generation and Submission Validation Layer.
Tests:
1. Exact column order (case_id, deletion_status, steps_json) and rejection of extra/missing columns.
2. Row count validation against expected dataset count.
3. Missing or malformed fields in step schema.
4. CSV escaping, quotes, commas, newlines, and multilingual Unicode characters.
5. All three statuses (COMPLETE, INCOMPLETE, NOT_APPLICABLE) and their serialization rules.
6. Step phase and operation sorting conforming strictly to problem_statement.md.
"""

import unittest
import os
import io
import json
import csv
import pandas as pd

from src.audit_engine.models import (
    AuditStep,
    AuditPhase,
    DeletionVerdict,
    CaseAuditResult
)
from src.export import (
    REQUIRED_COLUMNS,
    ALLOWED_STATUSES,
    ValidationResult,
    canonical_sort_steps,
    convert_audit_results_to_output,
    write_output_csv,
    OutputValidator
)


class TestExportAndValidation(unittest.TestCase):
    def setUp(self):
        # Create a representative set of audit results across all 3 statuses
        self.mock_results = [
            # COMPLETE Case
            CaseAuditResult(
                case_id="case_01",
                deletion_status=DeletionVerdict.COMPLETE,
                email="alice@mock.com",
                steps=[
                    AuditStep(
                        step_no=1,
                        phase=AuditPhase.VERIFICATION.value,
                        system_id="account_service",
                        resource_id="account_001",
                        operation="VERIFY_RECORD_ABSENT",
                        state="ABSENT",
                        evidence_id="evidence_54"
                    ),
                    AuditStep(
                        step_no=2,
                        phase=AuditPhase.VERIFICATION.value,
                        system_id="security_service",
                        resource_id="audit_record_101",
                        operation="VERIFY_RECORD_PRESENT",
                        state="PRESENT",
                        evidence_id="evidence_54"
                    )
                ]
            ),
            # INCOMPLETE Case
            CaseAuditResult(
                case_id="case_02",
                deletion_status=DeletionVerdict.INCOMPLETE,
                email="bob@mock.com",
                steps=[
                    AuditStep(
                        step_no=1,
                        phase=AuditPhase.FINDING.value,
                        system_id="search_service",
                        resource_id="search_002",
                        operation="REPORT_REMAINING_RECORD",
                        state="PRESENT",
                        evidence_id="evidence_57"
                    ),
                    AuditStep(
                        step_no=2,
                        phase=AuditPhase.REMEDIATION.value,
                        system_id="search_service",
                        resource_id="search_002",
                        operation="DELETE_RECORD",
                        state="ABSENT",
                        evidence_id=""
                    ),
                    AuditStep(
                        step_no=3,
                        phase=AuditPhase.VERIFICATION.value,
                        system_id="search_service",
                        resource_id="search_002",
                        operation="VERIFY_RECORD_ABSENT",
                        state="ABSENT",
                        evidence_id=""
                    )
                ]
            ),
            # NOT_APPLICABLE Case
            CaseAuditResult(
                case_id="case_03",
                deletion_status=DeletionVerdict.NOT_APPLICABLE,
                email="charlie@mock.com",
                steps=[]
            )
        ]

    def test_exact_column_order_and_no_extra_columns(self):
        """
        Test 1: Exact Column Order & Rejection of Extra / Missing Columns
        Verifies that output generator produces exactly ['case_id', 'deletion_status', 'steps_json'],
        and validator strictly flags missing, extra, or reordered columns.
        """
        df = convert_audit_results_to_output(self.mock_results)
        self.assertEqual(list(df.columns), REQUIRED_COLUMNS)

        # 1. Valid dataframe passes validation
        val_res = OutputValidator.validate_dataframe(df, expected_count=3)
        self.assertTrue(val_res.is_valid, f"Validation failed: {val_res.errors}")
        self.assertTrue(val_res.column_order_valid)

        # 2. Reordered columns fails validation
        reordered_df = df[["deletion_status", "case_id", "steps_json"]].copy()
        bad_val = OutputValidator.validate_dataframe(reordered_df)
        self.assertFalse(bad_val.is_valid)
        self.assertFalse(bad_val.column_order_valid)
        self.assertTrue(any("Incorrect column order" in e for e in bad_val.errors))

        # 3. Missing column fails validation
        missing_df = df[["case_id", "deletion_status"]].copy()
        missing_val = OutputValidator.validate_dataframe(missing_df)
        self.assertFalse(missing_val.is_valid)
        self.assertTrue(any("Missing required columns" in e for e in missing_val.errors))

        # 4. Extra debug column fails validation
        extra_df = df.copy()
        extra_df["debug_score"] = "1.0"
        extra_val = OutputValidator.validate_dataframe(extra_df)
        self.assertFalse(extra_val.is_valid)
        self.assertTrue(any("Forbidden extra columns" in e for e in extra_val.errors))

    def test_row_count_and_request_preservation(self):
        """
        Test 2: Row Count and Request Preservation
        Verifies that row count matches expected requests exactly,
        and missing or extra requests are detected.
        """
        req_df = pd.DataFrame([
            {"case_id": "case_01"},
            {"case_id": "case_02"},
            {"case_id": "case_03"}
        ])

        # Exact match
        df = convert_audit_results_to_output(self.mock_results, requests_df=req_df)
        val = OutputValidator.validate_dataframe(df, expected_requests_df=req_df, expected_count=3)
        self.assertTrue(val.is_valid)
        self.assertEqual(val.total_rows, 3)

        # Row count mismatch
        val_wrong_count = OutputValidator.validate_dataframe(df, expected_count=518)
        self.assertFalse(val_wrong_count.is_valid)
        self.assertTrue(any("Row count mismatch" in e for e in val_wrong_count.errors))

        # Missing case
        incomplete_df = df[df["case_id"] != "case_02"].copy()
        val_missing_case = OutputValidator.validate_dataframe(incomplete_df, expected_requests_df=req_df)
        self.assertFalse(val_missing_case.is_valid)
        self.assertTrue(any("Missing 1 required cases" in e for e in val_missing_case.errors))

    def test_missing_fields_in_steps(self):
        """
        Test 3: Missing Fields & Step Schema Validation
        Verifies that any step missing required schema keys (e.g. evidence_id or operation)
        is flagged as invalid.
        """
        # Step missing 'evidence_id'
        bad_step = {
            "step_no": 1,
            "phase": "FINDING",
            "system_id": "account_service",
            "resource_id": "acc_01",
            "operation": "REPORT_REMAINING_RECORD",
            "state": "PRESENT"
            # missing evidence_id
        }
        bad_df = pd.DataFrame([
            {
                "case_id": "case_01",
                "deletion_status": "INCOMPLETE",
                "steps_json": json.dumps([bad_step])
            }
        ])

        val = OutputValidator.validate_dataframe(bad_df, expected_count=1)
        self.assertFalse(val.is_valid)
        self.assertFalse(val.step_schema_valid)
        self.assertTrue(any("Missing required fields" in e for e in val.errors))

    def test_csv_escaping_and_special_characters(self):
        """
        Test 4: CSV Escaping, Quotes, Commas, Newlines & Unicode
        Verifies that steps_json containing commas, quotes, brackets, and multilingual
        characters (Japanese, Portuguese, accented chars) is written and read back without corruption.
        """
        temp_path = "temp_test_output.csv"
        try:
            df = convert_audit_results_to_output(self.mock_results)
            # Write to CSV
            write_output_csv(df, output_path=temp_path)

            # Re-read with standard csv reader
            with open(temp_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, REQUIRED_COLUMNS)
                rows = list(reader)
                self.assertEqual(len(rows), 3)

            # Validate file from disk
            val_file = OutputValidator.validate_file(temp_path, expected_count=3)
            self.assertTrue(val_file.is_valid, f"Disk CSV validation failed: {val_file.errors}")

            # Test Unicode characters in steps (e.g. Japanese or Portuguese system/resource names)
            unicode_step = AuditStep(
                step_no=1,
                phase=AuditPhase.VERIFICATION.value,
                system_id="account_service_東京",
                resource_id="acc_café_123",
                operation="VERIFY_RECORD_ABSENT",
                state="ABSENT",
                evidence_id="evidence_tokyo_01"
            )
            unicode_res = [CaseAuditResult(
                case_id="case_unicode_01",
                deletion_status=DeletionVerdict.COMPLETE,
                steps=[unicode_step]
            )]
            u_df = convert_audit_results_to_output(unicode_res)
            write_output_csv(u_df, output_path=temp_path)

            u_val = OutputValidator.validate_file(temp_path, expected_count=1)
            self.assertTrue(u_val.is_valid)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_all_three_statuses(self):
        """
        Test 5: All Three Statuses (COMPLETE, INCOMPLETE, NOT_APPLICABLE)
        Verifies that:
        - NOT_APPLICABLE always serializes to '[]'.
        - COMPLETE has only VERIFICATION steps with valid evidence citations.
        - INCOMPLETE has FINDING, REMEDIATION, and VERIFICATION steps.
        """
        df = convert_audit_results_to_output(self.mock_results)
        val = OutputValidator.validate_dataframe(df, expected_count=3)
        self.assertTrue(val.is_valid)

        row_map = {row["case_id"]: row for _, row in df.iterrows()}

        # 1. NOT_APPLICABLE
        na_row = row_map["case_03"]
        self.assertEqual(na_row["deletion_status"], "NOT_APPLICABLE")
        self.assertEqual(na_row["steps_json"], "[]")

        # 2. COMPLETE
        comp_row = row_map["case_01"]
        self.assertEqual(comp_row["deletion_status"], "COMPLETE")
        comp_steps = json.loads(comp_row["steps_json"])
        self.assertTrue(all(s["phase"] == "VERIFICATION" for s in comp_steps))
        self.assertTrue(all(s["evidence_id"] != "" for s in comp_steps))

        # 3. INCOMPLETE
        inc_row = row_map["case_02"]
        self.assertEqual(inc_row["deletion_status"], "INCOMPLETE")
        inc_steps = json.loads(inc_row["steps_json"])
        phases = [s["phase"] for s in inc_steps]
        self.assertIn("FINDING", phases)
        self.assertIn("REMEDIATION", phases)
        self.assertIn("VERIFICATION", phases)

    def test_step_phase_and_operation_ordering(self):
        """
        Test 6: Canonical Step Phase & Operation Ordering
        Verifies that steps are sorted by:
        1. Phase: FINDING -> REMEDIATION -> VERIFICATION
        2. Operation order within phase (table order)
        3. system_id ascending
        4. resource_id ascending
        Renumbers step_no consecutively starting at 1.
        """
        # Unsorted mixed steps
        raw_steps = [
            AuditStep(0, "VERIFICATION", "integration_service", "data_flow_01", "VERIFY_DATA_FLOW_DISABLED", "DISABLED", ""),
            AuditStep(0, "REMEDIATION", "search_service", "search_002", "DELETE_RECORD", "ABSENT", ""),
            AuditStep(0, "FINDING", "search_service", "search_002", "REPORT_REMAINING_RECORD", "PRESENT", "ev_01"),
            AuditStep(0, "REMEDIATION", "integration_service", "data_flow_01", "DISABLE_DATA_FLOW", "DISABLED", ""),
            AuditStep(0, "FINDING", "integration_service", "data_flow_01", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE", "ev_01"),
            AuditStep(0, "VERIFICATION", "search_service", "search_002", "VERIFY_RECORD_ABSENT", "ABSENT", "")
        ]

        sorted_steps = canonical_sort_steps(raw_steps)

        # 1. Step numbers must be consecutive 1..6
        self.assertEqual([s.step_no for s in sorted_steps], [1, 2, 3, 4, 5, 6])

        # 2. Phases must be FINDING, FINDING, REMEDIATION, REMEDIATION, VERIFICATION, VERIFICATION
        phases = [s.phase for s in sorted_steps]
        self.assertEqual(phases, ["FINDING", "FINDING", "REMEDIATION", "REMEDIATION", "VERIFICATION", "VERIFICATION"])

        # 3. Within FINDING: REPORT_REMAINING_RECORD (rank 1) before REPORT_ACTIVE_DATA_FLOW (rank 3)
        self.assertEqual(sorted_steps[0].operation, "REPORT_REMAINING_RECORD")
        self.assertEqual(sorted_steps[1].operation, "REPORT_ACTIVE_DATA_FLOW")

        # 4. Within REMEDIATION: DISABLE_DATA_FLOW (rank 10) before DELETE_RECORD (rank 12)
        self.assertEqual(sorted_steps[2].operation, "DISABLE_DATA_FLOW")
        self.assertEqual(sorted_steps[3].operation, "DELETE_RECORD")

        # 5. Within VERIFICATION: VERIFY_RECORD_ABSENT (rank 20) before VERIFY_DATA_FLOW_DISABLED (rank 24)
        self.assertEqual(sorted_steps[4].operation, "VERIFY_RECORD_ABSENT")
        self.assertEqual(sorted_steps[5].operation, "VERIFY_DATA_FLOW_DISABLED")


if __name__ == "__main__":
    unittest.main()

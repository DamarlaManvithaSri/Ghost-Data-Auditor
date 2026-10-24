"""
Unit tests for the Evaluation and Benchmark System.
Tests:
1. Dynamic schema discovery in EvaluationComparator.
2. Status, step, and sequence accuracy calculation.
3. Confusion matrix construction and failure category taxonomy.
4. Handling missing predictions without skipping or crashing.
5. Reference answer isolation (no mutation or leakage).
6. Synthetic edge cases (active sync, retained ledger, historical email).
"""

import unittest
import os
import json
import pandas as pd

from src.evaluation import (
    EvaluationComparator,
    EvaluationReportWriter,
    BenchmarkSummary,
    CaseEvaluationDiff
)


class TestEvaluationWorkflow(unittest.TestCase):
    def setUp(self):
        # 1. Fictional ground truth reference dataframe (schema with non-standard column names)
        self.mock_ref_df = pd.DataFrame([
            {
                "case": "case_test_01",
                "verdict": "COMPLETE",
                "actions": json.dumps([
                    {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "acc_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "ev_01"}
                ])
            },
            {
                "case": "case_test_02",
                "verdict": "INCOMPLETE",
                "actions": json.dumps([
                    {"step_no": 1, "phase": "FINDING", "system_id": "search_service", "resource_id": "search_02", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "ev_02"},
                    {"step_no": 2, "phase": "REMEDIATION", "system_id": "search_service", "resource_id": "search_02", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
                    {"step_no": 3, "phase": "VERIFICATION", "system_id": "search_service", "resource_id": "search_02", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""}
                ])
            },
            {
                "case": "case_test_03",
                "verdict": "NOT_APPLICABLE",
                "actions": "[]"
            }
        ])

        # 2. Fictional prediction dataframe (perfect match)
        self.mock_pred_perfect = pd.DataFrame([
            {
                "case_id": "case_test_01",
                "deletion_status": "COMPLETE",
                "steps_json": self.mock_ref_df.iloc[0]["actions"]
            },
            {
                "case_id": "case_test_02",
                "deletion_status": "INCOMPLETE",
                "steps_json": self.mock_ref_df.iloc[1]["actions"]
            },
            {
                "case_id": "case_test_03",
                "deletion_status": "NOT_APPLICABLE",
                "steps_json": "[]"
            }
        ])

        # 3. Fictional prediction dataframe with deliberate mismatches
        self.mock_pred_mismatched = pd.DataFrame([
            {
                "case_id": "case_test_01",
                "deletion_status": "INCOMPLETE", # Status mismatch
                "steps_json": "[]"
            },
            {
                "case_id": "case_test_02",
                "deletion_status": "INCOMPLETE", # Status match, but step count mismatch
                "steps_json": json.dumps([
                    {"step_no": 1, "phase": "FINDING", "system_id": "search_service", "resource_id": "search_02", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "ev_02"}
                ])
            }
            # Note: case_test_03 is missing entirely
        ])

    def test_dynamic_schema_discovery(self):
        """
        Test 1: Dynamic Schema Discovery
        Verifies that comparator discovers case_id, status, and steps columns regardless of naming.
        """
        id_col, stat_col, steps_col = EvaluationComparator.discover_column_names(self.mock_ref_df)
        self.assertEqual(id_col, "case")
        self.assertEqual(stat_col, "verdict")
        self.assertEqual(steps_col, "actions")

        id_p, stat_p, steps_p = EvaluationComparator.discover_column_names(self.mock_pred_perfect)
        self.assertEqual(id_p, "case_id")
        self.assertEqual(stat_p, "deletion_status")
        self.assertEqual(steps_p, "steps_json")

    def test_perfect_benchmark_evaluation(self):
        """
        Test 2: Perfect Benchmark Evaluation
        Verifies 100% accuracy metrics and clean confusion matrix on matching predictions.
        """
        summary = EvaluationComparator.evaluate_dataframes(
            predictions_df=self.mock_pred_perfect,
            reference_df=self.mock_ref_df,
            execution_time=1.23
        )
        self.assertEqual(summary.total_cases, 3)
        self.assertEqual(summary.status_matches, 3)
        self.assertEqual(summary.status_accuracy, 100.0)
        self.assertEqual(summary.exact_step_matches, 3)
        self.assertEqual(summary.step_accuracy, 100.0)
        self.assertEqual(summary.failure_categories, {})

        # Confusion matrix checks
        self.assertEqual(summary.confusion_matrix["COMPLETE"]["COMPLETE"], 1)
        self.assertEqual(summary.confusion_matrix["INCOMPLETE"]["INCOMPLETE"], 1)
        self.assertEqual(summary.confusion_matrix["NOT_APPLICABLE"]["NOT_APPLICABLE"], 1)

    def test_mismatch_categorization_and_missing_case(self):
        """
        Test 3: Mismatch Taxonomy and Missing Case Tracking
        Verifies that status mismatches, step count mismatches, and missing cases are
        properly flagged without crashing or skipping cases.
        """
        summary = EvaluationComparator.evaluate_dataframes(
            predictions_df=self.mock_pred_mismatched,
            reference_df=self.mock_ref_df,
            execution_time=0.5
        )
        self.assertEqual(summary.total_cases, 3)
        self.assertEqual(summary.status_matches, 1) # Only case_02 matched status
        self.assertAlmostEqual(summary.status_accuracy, 33.33, places=1)

        # Check failure categories
        self.assertIn("STATUS_MISMATCH", summary.failure_categories)
        self.assertIn("STEP_COUNT_MISMATCH", summary.failure_categories)
        self.assertIn("MISSING_PREDICTION", summary.failure_categories)

        # Ensure missing case was captured
        missing_diff = next(d for d in summary.case_diffs if d.case_id == "case_test_03")
        self.assertEqual(missing_diff.predicted_status, "MISSING")
        self.assertFalse(missing_diff.status_match)

    def test_reference_isolation(self):
        """
        Test 4: Reference Answer Isolation
        Verifies that evaluating predictions does not mutate the reference answers.
        """
        original_ref = self.mock_ref_df.copy(deep=True)
        _ = EvaluationComparator.evaluate_dataframes(self.mock_pred_mismatched, self.mock_ref_df)
        pd.testing.assert_frame_equal(self.mock_ref_df, original_ref)

    def test_report_generation(self):
        """
        Test 5: Report Generation
        Verifies that EvaluationReportWriter creates valid markdown strings containing
        accuracy metrics, confusion matrices, and custom evaluation scenarios.
        """
        summary = EvaluationComparator.evaluate_dataframes(self.mock_pred_perfect, self.mock_ref_df)
        md = EvaluationReportWriter.generate_evaluation_markdown(summary, "test_dataset.csv")

        self.assertIn("Formal Evaluation Report", md)
        self.assertIn("100.00%", md)
        self.assertIn("Confusion Matrix", md)
        self.assertIn("Active Data Sync Recreation Loop", md)
        self.assertIn("Policy-Mandated Retained Financial Record", md)

        usage_md = EvaluationReportWriter.generate_usage_markdown(total_requests=3)
        self.assertIn("Token Usage and Cost Report", usage_md)
        self.assertIn("$0.00", usage_md)


if __name__ == "__main__":
    unittest.main()

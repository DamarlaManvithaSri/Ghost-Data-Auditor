"""
Evaluation Comparator Engine for Ghost Data Auditor.
Performs schema-agnostic comparison between predictions and reference answers.
Discovers column mappings dynamically and reports case-level, step-level, and sequence metrics.
"""

import json
from typing import List, Dict, Any, Optional, Tuple, Set
import pandas as pd

from .models import CaseEvaluationDiff, BenchmarkSummary


class EvaluationComparator:
    """
    Compares audit predictions against ground-truth answers without hardcoding schemas.
    """

    @staticmethod
    def discover_column_names(df: pd.DataFrame) -> Tuple[str, str, str]:
        """
        Dynamically discovers case_id, deletion_status, and steps_json column names.
        """
        cols = [c.lower() for c in df.columns]

        # Case ID column discovery
        id_col = next((orig for orig, c in zip(df.columns, cols) if c in ["case_id", "id", "case", "request_id"]), df.columns[0])

        # Status column discovery
        status_col = next((orig for orig, c in zip(df.columns, cols) if any(k in c for k in ["status", "verdict", "decision", "state"])), df.columns[1] if len(df.columns) > 1 else "")

        # Steps column discovery
        steps_col = next((orig for orig, c in zip(df.columns, cols) if any(k in c for k in ["steps", "steps_json", "plan", "actions"])), df.columns[2] if len(df.columns) > 2 else "")

        return id_col, status_col, steps_col

    @classmethod
    def parse_steps_safely(cls, raw_val: Any) -> List[Dict[str, Any]]:
        """
        Safely parses steps field from string, list, or JSON object.
        """
        if isinstance(raw_val, list):
            return raw_val
        if not raw_val or str(raw_val).strip() in ["", "[]", "nan", "None"]:
            return []
        try:
            parsed = json.loads(str(raw_val))
            if isinstance(parsed, list):
                return parsed
            return []
        except Exception:
            return []

    @classmethod
    def compare_case(
        cls,
        case_id: str,
        pred_status: str,
        ref_status: str,
        pred_steps_raw: Any,
        ref_steps_raw: Any
    ) -> CaseEvaluationDiff:
        """
        Evaluates a single prediction against reference ground truth.
        """
        norm_pred_status = str(pred_status).strip().upper()
        norm_ref_status = str(ref_status).strip().upper()
        status_match = (norm_pred_status == norm_ref_status)

        pred_steps = cls.parse_steps_safely(pred_steps_raw)
        ref_steps = cls.parse_steps_safely(ref_steps_raw)

        diff = CaseEvaluationDiff(
            case_id=case_id,
            predicted_status=norm_pred_status,
            reference_status=norm_ref_status,
            status_match=status_match,
            predicted_steps=pred_steps,
            reference_steps=ref_steps,
            step_count_match=(len(pred_steps) == len(ref_steps))
        )

        # 1. Status Comparison
        if not status_match:
            diff.mismatch_categories.append("STATUS_MISMATCH")
            diff.diagnostic_notes.append(
                f"Status mismatch: predicted '{norm_pred_status}', expected '{norm_ref_status}'."
            )

        # 2. Step Comparison
        if not diff.step_count_match:
            diff.mismatch_categories.append("STEP_COUNT_MISMATCH")
            diff.diagnostic_notes.append(
                f"Step count mismatch: predicted {len(pred_steps)} steps, reference has {len(ref_steps)} steps."
            )

        pred_ops = [s.get("operation") for s in pred_steps if isinstance(s, dict)]
        ref_ops = [s.get("operation") for s in ref_steps if isinstance(s, dict)]
        diff.operations_match = (pred_ops == ref_ops)

        if not diff.operations_match and diff.step_count_match:
            diff.mismatch_categories.append("OPERATION_MISMATCH")
            diff.diagnostic_notes.append("Operation sequence mismatch within steps.")

        # Check exact field matches
        exact_match = True
        if len(pred_steps) != len(ref_steps):
            exact_match = False
        else:
            for idx, (p, r) in enumerate(zip(pred_steps, ref_steps), start=1):
                if not isinstance(p, dict) or not isinstance(r, dict):
                    exact_match = False
                    break
                p_op = p.get("operation")
                r_op = r.get("operation")
                p_st = p.get("state")
                r_st = r.get("state")
                p_res = p.get("resource_id")
                r_res = r.get("resource_id")

                if p_op != r_op or p_st != r_st or p_res != r_res:
                    exact_match = False
                    diff.mismatch_categories.append("FIELD_MISMATCH")
                    diff.diagnostic_notes.append(
                        f"Step {idx} mismatch: pred ({p_op}, {p_res}, {p_st}) != ref ({r_op}, r_res={r_res}, {r_st})"
                    )
                    break

        diff.exact_steps_match = exact_match
        return diff

    @classmethod
    def evaluate_dataframes(
        cls,
        predictions_df: pd.DataFrame,
        reference_df: pd.DataFrame,
        execution_time: float = 0.0
    ) -> BenchmarkSummary:
        """
        Executes a schema-agnostic evaluation across predictions and ground-truth answers.
        Never skips cases or alters expected answers.
        """
        pred_id_col, pred_stat_col, pred_steps_col = cls.discover_column_names(predictions_df)
        ref_id_col, ref_stat_col, ref_steps_col = cls.discover_column_names(reference_df)

        pred_map = {str(row[pred_id_col]).strip(): row for _, row in predictions_df.iterrows()}
        ref_case_ids = [str(row[ref_id_col]).strip() for _, row in reference_df.iterrows()]

        summary = BenchmarkSummary(
            total_cases=len(ref_case_ids),
            execution_time_seconds=execution_time
        )

        confusion = {
            "COMPLETE": {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0},
            "INCOMPLETE": {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0},
            "NOT_APPLICABLE": {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}
        }
        failure_cats: Dict[str, int] = {}

        for _, ref_row in reference_df.iterrows():
            cid = str(ref_row[ref_id_col]).strip()
            ref_status = str(ref_row[ref_stat_col]).strip().upper()
            ref_steps_raw = ref_row.get(ref_steps_col, "[]")

            pred_row = pred_map.get(cid)
            if pred_row is None:
                # Missing prediction entirely
                diff = CaseEvaluationDiff(
                    case_id=cid,
                    predicted_status="MISSING",
                    reference_status=ref_status,
                    status_match=False,
                    mismatch_categories=["MISSING_PREDICTION"],
                    diagnostic_notes=[f"Case '{cid}' was not present in prediction output."]
                )
                summary.case_diffs.append(diff)
                failure_cats["MISSING_PREDICTION"] = failure_cats.get("MISSING_PREDICTION", 0) + 1
                continue

            pred_status = str(pred_row[pred_stat_col]).strip().upper()
            pred_steps_raw = pred_row.get(pred_steps_col, "[]")

            diff = cls.compare_case(
                case_id=cid,
                pred_status=pred_status,
                ref_status=ref_status,
                pred_steps_raw=pred_steps_raw,
                ref_steps_raw=ref_steps_raw
            )
            summary.case_diffs.append(diff)

            # Record confusion matrix
            if ref_status in confusion and pred_status in confusion[ref_status]:
                confusion[ref_status][pred_status] += 1

            if diff.status_match:
                summary.status_matches += 1

            if diff.exact_steps_match:
                summary.exact_step_matches += 1

            if diff.operations_match:
                summary.sequence_matches += 1

            for cat in diff.mismatch_categories:
                failure_cats[cat] = failure_cats.get(cat, 0) + 1

        summary.confusion_matrix = confusion
        summary.failure_categories = failure_cats

        if summary.total_cases > 0:
            summary.status_accuracy = (summary.status_matches / summary.total_cases) * 100.0
            summary.step_accuracy = (summary.exact_step_matches / summary.total_cases) * 100.0
            summary.sequence_accuracy = (summary.sequence_matches / summary.total_cases) * 100.0

        return summary

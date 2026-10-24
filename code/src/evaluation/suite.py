"""
Evaluation Benchmark Suite for Ghost Data Auditor.
Runs blind predictions over benchmark datasets, executes multi-tier comparisons against reference answers,
and evaluates synthetic edge-case scenarios.
"""

import os
import time
from typing import Optional, Tuple, Dict, Any
import pandas as pd

from src.audit_engine import run_batch_audit
from .models import BenchmarkSummary
from .comparator import EvaluationComparator
from .report_writer import EvaluationReportWriter


class EvaluationSuite:
    """
    Executes automated evaluations, compares predictions against ground truth,
    and updates submission evaluation reports.
    """

    def __init__(
        self,
        sample_requests_path: Optional[str] = None,
        sample_output_path: Optional[str] = None
    ):
        root = os.getcwd()
        self.sample_req_path = sample_requests_path or os.path.join(root, "dataset", "sample_deletion_requests.csv")
        self.sample_out_path = sample_output_path or os.path.join(root, "dataset", "sample_output.csv")

    def run_benchmark(self, update_reports: bool = True) -> BenchmarkSummary:
        """
        Executes a blind benchmark of the audit engine against sample_output.csv.
        Never exposes reference answers to the engine during generation.
        """
        if not os.path.exists(self.sample_req_path):
            raise FileNotFoundError(f"Sample requests file missing: {self.sample_req_path}")
        if not os.path.exists(self.sample_out_path):
            raise FileNotFoundError(f"Sample reference output file missing: {self.sample_out_path}")

        # 1. Read reference answers (only for evaluation, never given to engine)
        ref_df = pd.read_csv(self.sample_out_path, dtype=str, keep_default_na=False)

        # 2. Run the audit engine blinds over sample requests
        t0 = time.time()
        results, pred_df = run_batch_audit(self.sample_req_path)
        elapsed = time.time() - t0

        # 3. Compare predictions against reference answers
        summary = EvaluationComparator.evaluate_dataframes(
            predictions_df=pred_df,
            reference_df=ref_df,
            execution_time=elapsed
        )

        # 4. Optionally update formal evaluation and usage reports on disk
        if update_reports:
            EvaluationReportWriter.write_reports(summary)

        return summary

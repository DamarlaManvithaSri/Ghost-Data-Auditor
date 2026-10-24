"""
Audit Batch Runner.
Executes the deletion audit engine across batch request files,
generates verified predictions, and outputs compliant output.csv files.
100% independent of Streamlit for use in automated evaluation pipelines and CI/CD.
"""

import os
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd

from .investigator import DeletionInvestigator
from .models import CaseAuditResult, DeletionVerdict


def run_batch_audit(
    requests_path: str,
    output_csv_path: Optional[str] = None,
    investigator: Optional[DeletionInvestigator] = None
) -> Tuple[List[CaseAuditResult], pd.DataFrame]:
    """
    Runs the audit engine over a batch of deletion requests and optionally writes output.csv.

    Args:
        requests_path: Path to deletion_requests.csv or sample_deletion_requests.csv.
        output_csv_path: Optional destination path to write the formatted output.csv.
        investigator: Optional pre-configured DeletionInvestigator instance.

    Returns:
        Tuple of (List of CaseAuditResult objects, output DataFrame).
    """
    from src.export.generator import convert_audit_results_to_output, write_output_csv
    if not os.path.exists(requests_path):
        raise FileNotFoundError(f"Requests file not found at: {requests_path}")

    req_df = pd.read_csv(requests_path)
    engine = investigator or DeletionInvestigator()

    results: List[CaseAuditResult] = []

    for _, row in req_df.iterrows():
        case_dict = row.to_dict()
        res = engine.audit_case(case_dict)
        results.append(res)

    # Convert results into strictly compliant output DataFrame
    out_df = convert_audit_results_to_output(results, requests_df=req_df)

    # Write output CSV if requested
    if output_csv_path:
        write_output_csv(out_df, output_csv_path)

    return results, out_df

"""
Output Generation Layer for Ghost Data Auditor.
Transforms audit results into the exact HackerRank challenge output format:
case_id,deletion_status,steps_json
Preserves request ordering, enforces canonical step sequencing, handles RFC 4180 CSV escaping,
and guarantees zero extra or debug columns.
"""

import os
import csv
import json
import re
from typing import List, Dict, Any, Optional
import pandas as pd

from src.audit_engine.models import (
    AuditStep,
    AuditPhase,
    DeletionVerdict,
    CaseAuditResult
)
from .models import (
    REQUIRED_COLUMNS,
    ALLOWED_STATUSES,
    PHASE_ORDER,
    OPERATION_ORDER
)


def canonical_sort_steps(steps: List[AuditStep]) -> List[AuditStep]:
    """
    Sorts audit steps strictly according to problem_statement.md:
    1. Phase order: FINDING -> REMEDIATION -> VERIFICATION
    2. Operation order within each phase as defined in the challenge table
    3. system_id ascending
    4. resource_id ascending
    Renumbers step_no consecutively starting at 1.
    """
    def _step_key(s: AuditStep):
        phase_rank = PHASE_ORDER.get(s.phase, 99)
        op_rank = OPERATION_ORDER.get(s.operation, 99)
        sys_key = (s.system_id or "").lower()
        res_key = (s.resource_id or "").lower()
        return (phase_rank, op_rank, sys_key, res_key)

    # Sort steps by canonical hierarchy
    sorted_steps = sorted(steps, key=_step_key)

    # Renumber step_no consecutively from 1
    reindexed_steps = []
    for idx, s in enumerate(sorted_steps, start=1):
        reindexed_steps.append(AuditStep(
            step_no=idx,
            phase=s.phase,
            system_id=s.system_id,
            resource_id=s.resource_id,
            operation=s.operation,
            state=s.state,
            evidence_id=s.evidence_id or ""
        ))

    return reindexed_steps


def _case_sort_key(case_id: str) -> tuple:
    """
    Natural sort key for case identifiers e.g. 'case_01' -> ('case', 1).
    """
    match = re.search(r'(\d+)', str(case_id))
    num = int(match.group(1)) if match else 0
    prefix = re.sub(r'\d+', '', str(case_id))
    return (prefix, num)


def convert_audit_results_to_output(
    results: List[CaseAuditResult],
    requests_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Converts CaseAuditResult objects into a strictly compliant DataFrame.

    Schema:
        case_id (str)
        deletion_status (str: COMPLETE | INCOMPLETE | NOT_APPLICABLE)
        steps_json (str: JSON array or "[]")

    Guarantees:
        - Exactly one row per request.
        - Preserves ordering matching requests_df or natural case_id sort.
        - Strict column ordering: ['case_id', 'deletion_status', 'steps_json'].
        - Zero extra columns or debug fields.
    """
    result_map: Dict[str, CaseAuditResult] = {r.case_id: r for r in results}
    rows: List[Dict[str, str]] = []

    # Determine case order
    if requests_df is not None and not requests_df.empty:
        case_ids = [str(cid).strip() for cid in requests_df["case_id"].tolist()]
    else:
        case_ids = sorted(list(result_map.keys()), key=_case_sort_key)

    for case_id in case_ids:
        res = result_map.get(case_id)
        if res is None:
            # Conservative fallback if a case was not processed: mark INCOMPLETE
            status_val = DeletionVerdict.INCOMPLETE.value
            steps_json = "[]"
        else:
            status_val = res.deletion_status.value
            if status_val == DeletionVerdict.NOT_APPLICABLE.value:
                steps_json = "[]"
            else:
                # Canonical sort of steps
                sorted_steps = canonical_sort_steps(res.steps)
                step_dicts = [s.to_dict() for s in sorted_steps]
                # Compact JSON serialization without excess whitespace
                steps_json = json.dumps(step_dicts, separators=(',', ':'), ensure_ascii=False)

        rows.append({
            "case_id": case_id,
            "deletion_status": status_val,
            "steps_json": steps_json
        })

    # Create dataframe with strictly required columns in exact order
    df = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
    return df


def write_output_csv(
    df: pd.DataFrame,
    output_path: str = "output.csv"
) -> str:
    """
    Writes the output DataFrame to a CSV file strictly matching RFC 4180.
    Handles quotes, commas, newlines, and UTF-8 characters safely.
    """
    # Enforce strictly required columns
    out_df = df[REQUIRED_COLUMNS].copy()

    # Write using standard comma separator and UTF-8 encoding
    out_df.to_csv(
        output_path,
        index=False,
        columns=REQUIRED_COLUMNS,
        quoting=csv.QUOTE_MINIMAL,
        encoding="utf-8",
        lineterminator="\n"
    )

    return os.path.abspath(output_path)

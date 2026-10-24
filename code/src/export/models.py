"""
Data Models for Final Output Generation and Submission Validation.
Defines validation schemas, result containers, and allowed values.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set


# Exact required columns in required order
REQUIRED_COLUMNS = ["case_id", "deletion_status", "steps_json"]

# Allowed status labels
ALLOWED_STATUSES: Set[str] = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}

# Allowed step schema fields
REQUIRED_STEP_FIELDS: Set[str] = {
    "step_no",
    "phase",
    "system_id",
    "resource_id",
    "operation",
    "state",
    "evidence_id"
}

# Allowed operations mapped to allowed states and phase
ALLOWED_OPERATIONS: Dict[str, Dict[str, Any]] = {
    # Findings
    "REPORT_REMAINING_RECORD": {"phase": "FINDING", "allowed_states": {"PRESENT"}},
    "REPORT_EXPOSED_PII": {"phase": "FINDING", "allowed_states": {"PRESENT"}},
    "REPORT_ACTIVE_DATA_FLOW": {"phase": "FINDING", "allowed_states": {"ACTIVE"}},
    "REPORT_RESTORE_RISK": {"phase": "FINDING", "allowed_states": {"ACTIVE"}},
    # Remediation
    "DISABLE_DATA_FLOW": {"phase": "REMEDIATION", "allowed_states": {"DISABLED"}},
    "BLOCK_RESTORE": {"phase": "REMEDIATION", "allowed_states": {"BLOCKED"}},
    "DELETE_RECORD": {"phase": "REMEDIATION", "allowed_states": {"ABSENT"}},
    "REDACT_RECORD": {"phase": "REMEDIATION", "allowed_states": {"REDACTED"}},
    "ANONYMIZE_RECORD": {"phase": "REMEDIATION", "allowed_states": {"ANONYMIZED"}},
    # Verification
    "VERIFY_RECORD_ABSENT": {"phase": "VERIFICATION", "allowed_states": {"ABSENT"}},
    "VERIFY_RECORD_PRESENT": {"phase": "VERIFICATION", "allowed_states": {"PRESENT"}},
    "VERIFY_RECORD_REDACTED": {"phase": "VERIFICATION", "allowed_states": {"REDACTED"}},
    "VERIFY_RECORD_ANONYMIZED": {"phase": "VERIFICATION", "allowed_states": {"ANONYMIZED"}},
    "VERIFY_DATA_FLOW_DISABLED": {"phase": "VERIFICATION", "allowed_states": {"DISABLED"}},
    "VERIFY_RESTORE_BLOCKED": {"phase": "VERIFICATION", "allowed_states": {"BLOCKED"}},
}

# Strict phase order
PHASE_ORDER: Dict[str, int] = {
    "FINDING": 1,
    "REMEDIATION": 2,
    "VERIFICATION": 3
}

# Strict operation order within phase (from problem_statement.md)
OPERATION_ORDER: Dict[str, int] = {
    # Findings
    "REPORT_REMAINING_RECORD": 1,
    "REPORT_EXPOSED_PII": 2,
    "REPORT_ACTIVE_DATA_FLOW": 3,
    "REPORT_RESTORE_RISK": 4,
    # Remediation
    "DISABLE_DATA_FLOW": 10,
    "BLOCK_RESTORE": 11,
    "DELETE_RECORD": 12,
    "REDACT_RECORD": 13,
    "ANONYMIZE_RECORD": 14,
    # Verification
    "VERIFY_RECORD_ABSENT": 20,
    "VERIFY_RECORD_PRESENT": 21,
    "VERIFY_RECORD_REDACTED": 22,
    "VERIFY_RECORD_ANONYMIZED": 23,
    "VERIFY_DATA_FLOW_DISABLED": 24,
    "VERIFY_RESTORE_BLOCKED": 25,
}


@dataclass
class ValidationResult:
    """
    Detailed validation diagnostics for output.csv.
    """
    is_valid: bool = True
    total_rows: int = 0
    expected_rows: Optional[int] = None
    columns_found: List[str] = field(default_factory=list)
    column_order_valid: bool = True
    statuses_valid: bool = True
    json_syntax_valid: bool = True
    step_schema_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    status_counts: Dict[str, int] = field(default_factory=dict)

    def add_error(self, message: str):
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def summary_message(self) -> str:
        if self.is_valid:
            return f"[PASSED] {self.total_rows} rows valid against HackerRank submission schema."
        return f"[FAILED] Found {len(self.errors)} validation errors in {self.total_rows} rows."

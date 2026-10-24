"""
Data Models for Remediation Planning and Verification Reporting.
Provides structured definitions for proposed remediation actions, dependency graphs,
audit trail links, and verification reports.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from src.audit_engine.models import AuditStep, DeletionVerdict


@dataclass
class RemediationAction:
    """
    Represents an atomic proposed remediation action.
    Maintains dependency order, policy grounding, and paired verification check.
    Never marks itself as executed; all remediation actions are proposed plans.
    """
    action_id: str
    system_id: str
    resource_id: str
    operation: str                   # DISABLE_DATA_FLOW, BLOCK_RESTORE, DELETE_RECORD, REDACT_RECORD, ANONYMIZE_RECORD
    target_state: str                # DISABLED, BLOCKED, ABSENT, REDACTED, ANONYMIZED
    policy_rule_id: str              # e.g., rule_01, rule_05, rule_15, or OP_RECREATION
    policy_category: str             # e.g., USER_PROFILE, ACCOUNT_TOMBSTONE, ACTIVE_DATA_FLOW
    reason: str                      # Plain English explanation grounded in findings
    source_evidence_id: str          # Evidence ID from finding proving the failure
    dependency_order: int            # 1: data flows / restores, 2: downstream copies & caches, 3: primary stores
    dependencies: List[str] = field(default_factory=list) # List of action_ids that must complete first
    verification_operation: str = "" # Paired verification check
    verification_state: str = ""
    is_executed: bool = False        # Always False: system never executes destructive changes automatically


@dataclass
class RemediationPlan:
    """
    Complete remediation blueprint and verification report for a case.
    Strictly preserves the Hackerrank challenge format while providing rich auditing context.
    """
    case_id: str
    deletion_status: DeletionVerdict
    customer_email: str = ""
    user_id: Optional[str] = None
    actions: List[RemediationAction] = field(default_factory=list)
    ordered_steps: List[AuditStep] = field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    additional_investigations: List[str] = field(default_factory=list)
    safety_guarantee: str = "READ_ONLY: All remediation steps are recommended actions. Zero destructive modifications executed."

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def requires_remediation(self) -> bool:
        return self.deletion_status == DeletionVerdict.INCOMPLETE and len(self.actions) > 0

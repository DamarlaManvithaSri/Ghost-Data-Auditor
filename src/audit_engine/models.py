"""
Audit Engine Data Models.
Defines standardized phases, operations, states, and the exact challenge output schema.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import json


class AuditPhase(str, Enum):
    """The three mandatory sequential audit phases."""
    FINDING = "FINDING"
    REMEDIATION = "REMEDIATION"
    VERIFICATION = "VERIFICATION"


class DeletionVerdict(str, Enum):
    """The three valid case statuses."""
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class AuditStep:
    """
    Represents a single atomic step in an audit result.
    Conforms strictly to the challenge schema:
    step_no, phase, system_id, resource_id, operation, state, evidence_id
    """
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializes to the exact dictionary structure expected by evaluation."""
        return {
            "step_no": self.step_no,
            "phase": self.phase,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "state": self.state,
            "evidence_id": self.evidence_id
        }


@dataclass
class CaseAuditResult:
    """
    Complete audit evaluation for a single deletion request case.
    """
    case_id: str
    deletion_status: DeletionVerdict
    steps: List[AuditStep] = field(default_factory=list)
    email: str = ""
    user_id: Optional[str] = None
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    evidence_cited: List[str] = field(default_factory=list)
    rationale: str = ""
    remediation_plan: Optional[Any] = None

    def get_steps_json(self) -> str:
        """Returns JSON-serialized array of steps."""
        if self.deletion_status == DeletionVerdict.NOT_APPLICABLE:
            return "[]"
        return json.dumps([step.to_dict() for step in self.steps])

    def to_csv_dict(self) -> Dict[str, str]:
        """Returns row dictionary for output.csv."""
        return {
            "case_id": self.case_id,
            "deletion_status": self.deletion_status.value,
            "steps_json": self.get_steps_json()
        }

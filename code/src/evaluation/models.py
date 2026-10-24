"""
Data Models for Evaluation and Benchmark Assessment.
Defines comparative diff structures, metrics containers, and failure classifications.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class CaseEvaluationDiff:
    """
    Detailed comparison between predicted audit result and ground truth for a single case.
    """
    case_id: str
    predicted_status: str
    reference_status: str
    status_match: bool
    predicted_steps: List[Dict[str, Any]] = field(default_factory=list)
    reference_steps: List[Dict[str, Any]] = field(default_factory=list)
    step_count_match: bool = False
    operations_match: bool = False
    exact_steps_match: bool = False
    sequence_match: bool = False
    mismatch_categories: List[str] = field(default_factory=list)
    diagnostic_notes: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return not self.status_match or not self.exact_steps_match


@dataclass
class BenchmarkSummary:
    """
    Aggregated benchmark metrics across an evaluation dataset.
    """
    total_cases: int = 0
    status_matches: int = 0
    status_accuracy: float = 0.0
    exact_step_matches: int = 0
    step_accuracy: float = 0.0
    sequence_matches: int = 0
    sequence_accuracy: float = 0.0
    failure_categories: Dict[str, int] = field(default_factory=dict)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    case_diffs: List[CaseEvaluationDiff] = field(default_factory=list)
    execution_time_seconds: float = 0.0

    @property
    def passed_cases(self) -> int:
        return self.status_matches

    @property
    def failed_cases(self) -> int:
        return self.total_cases - self.status_matches

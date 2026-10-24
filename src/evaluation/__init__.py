"""
Evaluation Package for Ghost Data Auditor.
Provides benchmark comparison, accuracy metrics, and formal report generation.
"""

from .models import CaseEvaluationDiff, BenchmarkSummary
from .comparator import EvaluationComparator
from .report_writer import EvaluationReportWriter
from .suite import EvaluationSuite

__all__ = [
    "CaseEvaluationDiff",
    "BenchmarkSummary",
    "EvaluationComparator",
    "EvaluationReportWriter",
    "EvaluationSuite"
]

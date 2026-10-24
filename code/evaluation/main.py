"""
Evaluation Command Line Runner for Ghost Data Auditor.
Reproducible single-command benchmark runner that evaluates predictions against ground truth,
prints detailed diagnostic accuracy metrics, and writes official markdown reports.

Usage:
    python code/evaluation/main.py
"""

import sys
import os

# Ensure repository root is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure console handles UTF-8 safely
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.evaluation import EvaluationSuite, BenchmarkSummary


def run_evaluation() -> int:
    print("==================================================================")
    print("Ghost Data Auditor - Automated Evaluation & Benchmark Suite")
    print("==================================================================")

    sample_requests = os.path.join(root_dir, "dataset", "sample_deletion_requests.csv")
    sample_output = os.path.join(root_dir, "dataset", "sample_output.csv")

    if not os.path.exists(sample_requests) or not os.path.exists(sample_output):
        print("Error: Could not locate sample ground truth files under dataset/.")
        return 1

    print(f"Loading benchmark reference: {sample_output}")
    print("Executing blind audit engine predictions over sample cases...")

    suite = EvaluationSuite(
        sample_requests_path=sample_requests,
        sample_output_path=sample_output
    )

    summary: BenchmarkSummary = suite.run_benchmark(update_reports=True)

    print("\n------------------------------------------------------------------")
    print("BENCHMARK ACCURACY RESULTS")
    print("------------------------------------------------------------------")
    print(f"Total Reference Cases:      {summary.total_cases}")
    print(f"Status Accuracy:            {summary.status_accuracy:.2f}% ({summary.status_matches}/{summary.total_cases})")
    print(f"Sequence Accuracy:          {summary.sequence_accuracy:.2f}% ({summary.sequence_matches}/{summary.total_cases})")
    print(f"Exact Step & Field Match:   {summary.step_accuracy:.2f}% ({summary.exact_step_matches}/{summary.total_cases})")
    print(f"Execution Runtime:          {summary.execution_time_seconds:.2f}s")
    print("------------------------------------------------------------------")

    print("\nConfusion Matrix:")
    for status, preds in summary.confusion_matrix.items():
        print(f"  Expected {status:<15}: Pred COMPLETE={preds['COMPLETE']}, INCOMPLETE={preds['INCOMPLETE']}, NOT_APPLICABLE={preds['NOT_APPLICABLE']}")

    if summary.failure_categories:
        print("\nDiscovered Failure Categories:")
        for cat, cnt in summary.failure_categories.items():
            print(f"  - {cat}: {cnt}")
    else:
        print("\nDiscovered Failure Categories: None (0 failures)")

    eval_report_path = os.path.join(root_dir, "code", "evaluation", "evaluation_report.md")
    usage_report_path = os.path.join(root_dir, "code", "evaluation", "usage_report.md")

    print("\n------------------------------------------------------------------")
    print(f"[OK] Generated: {eval_report_path}")
    print(f"[OK] Generated: {usage_report_path}")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(run_evaluation())

"""
Ghost Data Auditor - Command Line Entry Point & Automated Evaluation Runner.
Runs the independent audit engine over dataset/deletion_requests.csv and writes root output.csv.
"""

import sys
import os
import time

# Ensure both local directory and parent root are on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audit_engine import run_batch_audit, DeletionVerdict

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("==================================================")
    print("Ghost Data Auditor - Automated Evaluation Runner")
    print("==================================================")
    
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    requests_path = os.path.join(workspace_root, "dataset", "deletion_requests.csv")
    output_path = os.path.join(workspace_root, "output.csv")

    if not os.path.exists(requests_path):
        local_requests = os.path.join(os.path.dirname(__file__), "dataset", "deletion_requests.csv")
        if os.path.exists(local_requests):
            requests_path = local_requests
            output_path = os.path.join(os.path.dirname(__file__), "output.csv")
        else:
            print(f"Error: Could not locate requests file at {requests_path}")
            sys.exit(1)

    print(f"Loading deletion requests from: {requests_path}")
    start_time = time.time()

    results, out_df = run_batch_audit(requests_path, output_csv_path=output_path)
    elapsed = time.time() - start_time

    status_counts = {}
    for r in results:
        v = r.deletion_status.value
        status_counts[v] = status_counts.get(v, 0) + 1

    print("\n--------------------------------------------------")
    print(f"[OK] Successfully processed {len(results)} cases in {elapsed:.2f}s")
    print(f"[OK] Output written to: {output_path}")
    print("--------------------------------------------------")
    print("Status Breakdown:")
    for status, count in status_counts.items():
        print(f"  - {status}: {count} cases ({count / len(results) * 100:.1f}%)")
    print("==================================================")

if __name__ == "__main__":
    main()

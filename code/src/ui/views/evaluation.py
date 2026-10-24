"""
Evaluation View for Ghost Data Auditor.
Provides interactive model assessment benchmarks, comparative diagnostics,
confusion matrix visualizations, and formal submission evaluation report inspection.
"""

import os
import streamlit as st
import pandas as pd
import json

from src.evaluation import EvaluationSuite, BenchmarkSummary, CaseEvaluationDiff

SUBMISSION_URL = "https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists"


def render_evaluation_view():
    """
    Renders the Evaluation and Validation view.
    """
    st.markdown('<div class="dashboard-title">📈 Model Evaluation & Benchmarks</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Benchmark deletion audit predictions against ground truth, inspect comparative diffs, and review submission metrics.</div>',
        unsafe_allow_html=True
    )

    tab_benchmark, tab_diffs, tab_reports, tab_guide = st.tabs([
        "🧪 Ground-Truth Benchmark",
        "🔍 Case-Level Comparative Diffs",
        "📝 Submission Evaluation Reports",
        "🛡️ Deletion Rule Integrity Guide"
    ])

    sample_requests_path = os.path.join(os.getcwd(), "dataset", "sample_deletion_requests.csv")
    sample_output_path = os.path.join(os.getcwd(), "dataset", "sample_output.csv")
    sample_available = os.path.exists(sample_requests_path) and os.path.exists(sample_output_path)

    # -------------------------------------------------------------
    # TAB 1: Ground-Truth Benchmark
    # -------------------------------------------------------------
    with tab_benchmark:
        st.markdown("#### Sample Ground-Truth Benchmark")
        st.write(
            "Executes blind predictions across `dataset/sample_deletion_requests.csv` and evaluates them "
            "against `dataset/sample_output.csv` without exposing answers to the audit engine."
        )

        col_b1, col_b2 = st.columns([1.5, 2])
        with col_b1:
            run_btn = st.button("🚀 Run Automated Benchmark", type="primary", use_container_width=True, disabled=not sample_available)
        with col_b2:
            st.caption(f"Reference Source: `{sample_output_path}` (32 Reference Cases)")

        if run_btn:
            with st.spinner("Executing blind audit engine across sample cases and computing multi-tier metrics..."):
                suite = EvaluationSuite(
                    sample_requests_path=sample_requests_path,
                    sample_output_path=sample_output_path
                )
                summary = suite.run_benchmark(update_reports=True)
                st.session_state["benchmark_summary"] = summary
                st.success("✓ Benchmark complete. Comparative metrics and reports updated.")

        summary: BenchmarkSummary = st.session_state.get("benchmark_summary")

        if summary:
            st.markdown("##### 📊 Benchmark Accuracy Performance")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Status Accuracy", f"{summary.status_accuracy:.1f}%", f"{summary.status_matches}/{summary.total_cases} cases")
            m2.metric("Sequence Accuracy", f"{summary.sequence_accuracy:.1f}%", f"{summary.sequence_matches}/{summary.total_cases} cases")
            m3.metric("Step & Field Match", f"{summary.step_accuracy:.1f}%", f"{summary.exact_step_matches}/{summary.total_cases} cases")
            m4.metric("Benchmark Runtime", f"{summary.execution_time_seconds:.2f}s", "32 requests")

            st.markdown("##### 🔲 Status Confusion Matrix")
            conf_df = pd.DataFrame.from_dict(summary.confusion_matrix, orient="index")
            conf_df.index.name = "Expected Status"
            st.dataframe(conf_df, use_container_width=True)

            if summary.failure_categories:
                st.markdown("##### ⚠️ Discovered Failure Categories")
                f_cols = st.columns(min(4, len(summary.failure_categories)))
                for idx, (cat, count) in enumerate(summary.failure_categories.items()):
                    f_cols[idx % len(f_cols)].metric(cat.replace("_", " ").title(), count)

        else:
            st.markdown(
                """
                <div class="empty-state-box">
                    <div class="empty-state-icon">📊</div>
                    <div class="empty-state-title">No Benchmark Run Yet</div>
                    <div class="empty-state-desc">
                        Click <strong>🚀 Run Automated Benchmark</strong> above to evaluate the audit engine 
                        against reference ground truth answers.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # -------------------------------------------------------------
    # TAB 2: Case-Level Comparative Diffs
    # -------------------------------------------------------------
    with tab_diffs:
        st.markdown("#### Case-by-Case Comparative Diffs")
        st.write("Inspect predictions side-by-side with reference answers to isolate step mismatches and field differences.")

        if not summary:
            st.info("Run the benchmark in the first tab to view comparative diffs.")
        else:
            filter_mode = st.radio(
                "Filter Case Diffs:",
                ["All Cases (32)", "Status Matches", "Mismatches Only"],
                horizontal=True
            )

            diffs = summary.case_diffs
            if filter_mode == "Status Matches":
                diffs = [d for d in diffs if d.status_match]
            elif filter_mode == "Mismatches Only":
                diffs = [d for d in diffs if not d.status_match or not d.exact_steps_match]

            if not diffs:
                st.success(f"No cases found matching filter '{filter_mode}'.")
            else:
                sel_case_id = st.selectbox(
                    "Select Case to Inspect Comparative Diff:",
                    options=[f"{d.case_id} (Pred: {d.predicted_status} | Ref: {d.reference_status})" for d in diffs]
                )
                selected_cid = sel_case_id.split()[0]
                diff_obj = next((d for d in diffs if d.case_id == selected_cid), None)

                if diff_obj:
                    c_col1, c_col2 = st.columns(2)
                    with c_col1:
                        st.markdown(f"**Predicted Status:** `{diff_obj.predicted_status}`")
                    with c_col2:
                        st.markdown(f"**Reference Status:** `{diff_obj.reference_status}`")

                    if diff_obj.status_match:
                        st.success("✓ Deletion status matches reference answer.")
                    else:
                        st.error(f"✗ Status Mismatch: predicted '{diff_obj.predicted_status}', expected '{diff_obj.reference_status}'")

                    if diff_obj.diagnostic_notes:
                        st.markdown("##### Diagnostic Findings:")
                        for note in diff_obj.diagnostic_notes:
                            st.warning(f"• {note}")

                    col_steps1, col_steps2 = st.columns(2)
                    with col_steps1:
                        st.markdown(f"##### Predicted Steps ({len(diff_obj.predicted_steps)})")
                        if diff_obj.predicted_steps:
                            st.dataframe(pd.DataFrame(diff_obj.predicted_steps), use_container_width=True)
                        else:
                            st.info("Empty steps array `[]`")

                    with col_steps2:
                        st.markdown(f"##### Reference Steps ({len(diff_obj.reference_steps)})")
                        if diff_obj.reference_steps:
                            st.dataframe(pd.DataFrame(diff_obj.reference_steps), use_container_width=True)
                        else:
                            st.info("Empty steps array `[]`")

    # -------------------------------------------------------------
    # TAB 3: Submission Evaluation Reports
    # -------------------------------------------------------------
    with tab_reports:
        st.markdown("#### Submission Markdown Reports")
        st.write(
            "The submission bundle requires `code/evaluation/evaluation_report.md` and `usage_report.md`. "
            "These reports document accuracy metrics, custom synthetic cases, failure analysis, and token consumption."
        )

        eval_rep_path = os.path.join(os.getcwd(), "code", "evaluation", "evaluation_report.md")
        usage_rep_path = os.path.join(os.getcwd(), "code", "evaluation", "usage_report.md")

        sub_tab1, sub_tab2 = st.tabs(["📄 evaluation_report.md", "💰 usage_report.md"])

        with sub_tab1:
            if os.path.exists(eval_rep_path):
                with open(eval_rep_path, "r", encoding="utf-8") as f:
                    eval_md_content = f.read()

                st.download_button(
                    "📥 Download evaluation_report.md",
                    data=eval_md_content,
                    file_name="evaluation_report.md",
                    mime="text/markdown"
                )
                st.markdown(eval_md_content)
            else:
                st.info("Run the benchmark or `python code/evaluation/main.py` to generate `evaluation_report.md`.")

        with sub_tab2:
            if os.path.exists(usage_rep_path):
                with open(usage_rep_path, "r", encoding="utf-8") as f:
                    usage_md_content = f.read()

                st.download_button(
                    "📥 Download usage_report.md",
                    data=usage_md_content,
                    file_name="usage_report.md",
                    mime="text/markdown"
                )
                st.markdown(usage_md_content)
            else:
                st.info("Run the benchmark or `python code/evaluation/main.py` to generate `usage_report.md`.")

    # -------------------------------------------------------------
    # TAB 4: Deletion Rule Integrity Guide
    # -------------------------------------------------------------
    with tab_guide:
        st.markdown("#### How to Fix Failing Tests Without Weakening Deletion Rules")
        st.markdown(
            """
            When a benchmark case fails, it is critical **never** to weaken privacy rules or hardcode case IDs simply to inflate the evaluation score. Follow this systematic debugging protocol:

            ##### 1. Trace the Root Cause of the Discrepancy
            - **Identity Linkage Gap:** Did the resolver fail to discover a historical email from `user_audit_log.csv` before `audit_at`?
              *Fix:* Improve alias and email hash normalization in `src/identity/` so all historical links are discovered.
            - **Evidence Discovery Gap:** Was an active sync job (`CHECK_DATA_FLOW`) missed in `system_activity.csv` because of a case-sensitivity issue in resource naming?
              *Fix:* Standardize case-insensitive matching across resource identifiers in `RecreationRiskDetector`.
            - **Downstream Precedence:** Did the remediation plan try to delete the account record before disabling the sync process?
              *Fix:* Verify that Level 1 processes (`DISABLE_DATA_FLOW`, `BLOCK_RESTORE`) precede Level 2/3 store modifications.

            ##### 2. Maintain Policy Integrity Guardrails
            - **Mandatory Retention is Non-Negotiable:** If `deletion_rules.csv` marks `FINANCIAL_LEDGER` or `SECURITY_AUDIT_LOG` as `RETAIN`, never switch the rule to `DELETE` to match a flawed expectation.
            - **Account Tombstones:** Always preserve the internal `user_id` while stripping direct identifiers (`name`, `email`, `phone`, `email_hash`).
            - **Conservative Bias:** When evidence is ambiguous or missing, always choose `INCOMPLETE` with logged `additional_investigations`. Never guess `COMPLETE`.

            ##### 3. Challenge Submission Link
            Upload the validated `output.csv`, `code.zip`, and `log.txt` directly to HackerRank:  
            🔗 **[HackerRank Submission Portal]({SUBMISSION_URL})**
            """
        )

"""
Export and Validation View for Ghost Data Auditor.
Provides output.csv generation, live schema validation against HackerRank standards,
row-count and column-order verification, and packaging guidance.
"""

import os
import streamlit as st
import pandas as pd
import json

from src.export import (
    REQUIRED_COLUMNS,
    ALLOWED_STATUSES,
    OutputValidator,
    ValidationResult,
    convert_audit_results_to_output,
    write_output_csv
)
from src.audit_engine import run_batch_audit

SUBMISSION_URL = "https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists"


def render_export_view():
    """
    Renders the Submission Export & Validation view.
    """
    st.markdown('<div class="dashboard-title">📦 Submission Export & Validation</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Generate, inspect, and rigorously validate <code>output.csv</code> against HackerRank evaluation criteria.</div>',
        unsafe_allow_html=True
    )

    tab_output, tab_validate, tab_package = st.tabs([
        "📄 output.csv Generator & Preview",
        "🔬 Schema & Contract Validator",
        "🗜️ Packaging & Submission Guide"
    ])

    root_output_path = os.path.join(os.getcwd(), "output.csv")
    full_eval_requests = os.path.join(os.getcwd(), "dataset", "deletion_requests.csv")
    sample_requests = os.path.join(os.getcwd(), "dataset", "sample_deletion_requests.csv")

    # -------------------------------------------------------------
    # TAB 1: Generator & Preview
    # -------------------------------------------------------------
    with tab_output:
        st.markdown("#### Primary Submission Artifact (`output.csv`)")
        st.write(
            "The final evaluation submission requires a single `output.csv` at the workspace root, "
            "containing exactly 518 data rows corresponding to `dataset/deletion_requests.csv`."
        )

        col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1])
        with col_g1:
            dataset_choice = st.selectbox(
                "Select Dataset to Generate `output.csv` From:",
                [
                    "Full Challenge Dataset (518 cases - dataset/deletion_requests.csv)",
                    "Sample Benchmark (32 cases - dataset/sample_deletion_requests.csv)"
                ],
                index=0
            )
        with col_g2:
            st.markdown("<br>", unsafe_allow_html=True)
            gen_btn = st.button("⚡ Run & Write output.csv", type="primary", use_container_width=True)
        with col_g3:
            st.markdown("<br>", unsafe_allow_html=True)
            validate_btn = st.button("🔍 Validate output.csv", use_container_width=True)

        if gen_btn:
            is_sample = "sample" in dataset_choice.lower()
            req_path = sample_requests if is_sample else full_eval_requests
            label = "sample" if is_sample else "evaluation"

            with st.spinner(f"Executing audit engine and generating canonical output.csv for {label} dataset..."):
                results, out_df = run_batch_audit(req_path, output_csv_path=root_output_path)
                st.session_state["active_audit_results"] = results
                st.session_state["active_output_df"] = out_df
                st.session_state["active_audit_dataset"] = os.path.basename(req_path)
                st.success(f"✓ Successfully audited {len(results)} cases and saved root `{root_output_path}`.")
                st.rerun()

        # Check file state on disk
        output_exists = os.path.exists(root_output_path)
        if output_exists:
            try:
                disk_df = pd.read_csv(root_output_path, dtype=str, keep_default_na=False)

                st.markdown("##### 📊 Current `output.csv` Summary")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Data Rows", len(disk_df))
                
                status_counts = disk_df["deletion_status"].value_counts().to_dict() if "deletion_status" in disk_df.columns else {}
                m2.metric("COMPLETE Cases", status_counts.get("COMPLETE", 0))
                m3.metric("INCOMPLETE Cases", status_counts.get("INCOMPLETE", 0))
                m4.metric("NOT_APPLICABLE Cases", status_counts.get("NOT_APPLICABLE", 0))

                # Download button
                with open(root_output_path, "r", encoding="utf-8") as f:
                    csv_bytes = f.read()

                st.download_button(
                    label="📥 Download output.csv",
                    data=csv_bytes,
                    file_name="output.csv",
                    mime="text/csv"
                )

                st.markdown("##### 🔍 Data Preview (First 15 Rows):")
                st.dataframe(disk_df.head(15), use_container_width=True)

            except Exception as e:
                st.error(f"Error reading root output.csv: {str(e)}")
        else:
            st.markdown(
                """
                <div class="empty-state-box">
                    <div class="empty-state-icon">📄</div>
                    <div class="empty-state-title">output.csv Not Generated Yet</div>
                    <div class="empty-state-desc">
                        Click <strong>⚡ Run & Write output.csv</strong> above to execute the audit engine 
                        over all 518 requests and build the submission file.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # -------------------------------------------------------------
    # TAB 2: Schema & Contract Validator
    # -------------------------------------------------------------
    with tab_validate:
        st.markdown("#### Comprehensive Submission Schema Validator")
        st.write(
            "Validates that `output.csv` conforms to all specifications in `problem_statement.md`: "
            "column names, exact column order, row counts, valid status labels, JSON array formatting, "
            "consecutive step numbers, and strict phase ordering."
        )

        if not os.path.exists(root_output_path):
            st.warning("⚠️ `output.csv` does not exist on disk yet. Generate it in the first tab to validate.")
        else:
            # Run validator against full evaluation requests
            # Determine which dataset to validate against based on row count
            try:
                temp_df = pd.read_csv(root_output_path, dtype=str, keep_default_na=False)
                expected_target = full_eval_requests if len(temp_df) > 50 else sample_requests
                val_result = OutputValidator.validate_file(root_output_path, expected_requests_path=expected_target)

                if val_result.is_valid:
                    st.markdown(
                        f"""
                        <div class="safety-card">
                            <strong>✅ 100% VALIDATION PASSED:</strong><br>
                            - Exactly <code>{val_result.total_rows}</code> rows matching required cases.<br>
                            - Columns are strictly <code>{val_result.columns_found}</code>.<br>
                            - Statuses strictly conform to <code>COMPLETE</code>, <code>INCOMPLETE</code>, and <code>NOT_APPLICABLE</code>.<br>
                            - All <code>steps_json</code> values parse as valid JSON arrays with consecutive step numbers.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"""
                        <div class="warning-card">
                            <strong>❌ VALIDATION FAILED:</strong> Found {len(val_result.errors)} errors in <code>output.csv</code>.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown("##### Detailed Errors:")
                    for err in val_result.errors[:15]:
                        st.error(f"• {err}")
                    if len(val_result.errors) > 15:
                        st.caption(f"... and {len(val_result.errors) - 15} additional errors.")

                if val_result.warnings:
                    st.markdown("##### Warnings:")
                    for w in val_result.warnings[:10]:
                        st.warning(f"• {w}")

                st.markdown("##### Validation Metrics:")
                c_v1, c_v2, c_v3 = st.columns(3)
                c_v1.metric("Column Order Valid", "Yes" if val_result.column_order_valid else "No")
                c_v2.metric("Statuses Valid", "Yes" if val_result.statuses_valid else "No")
                c_v3.metric("JSON Syntax Valid", "Yes" if val_result.json_syntax_valid else "No")

            except Exception as e:
                st.error(f"Validation execution failed: {str(e)}")

        with st.expander("🔬 Terminal Command to Independently Validate output.csv"):
            st.markdown(
                """
                You can independently validate your `output.csv` file at any time using PowerShell or terminal:
                """
            )
            st.code(
                'python -c "from src.export import OutputValidator; res = OutputValidator.validate_file(\'output.csv\', \'dataset/deletion_requests.csv\'); print(res.summary_message()); exit(0 if res.is_valid else 1)"',
                language="powershell"
            )

    # -------------------------------------------------------------
    # TAB 3: Packaging & Submission Guide
    # -------------------------------------------------------------
    with tab_package:
        st.markdown("#### Submission Artifacts Packaging")
        st.write("According to the challenge contract, the final submission requires four components:")

        st.markdown(
            """
            | Artifact | Description |
            | :--- | :--- |
            | **`code.zip`** | Runnable solution, prompts, configuration, `README.md`, and `evaluation/` folder. Excludes `dataset/` and cache files. |
            | **`output.csv`** | Single CSV file at repo root containing exactly 518 data rows. |
            | **`chat_transcript`** | The root `log.txt` generated during agent pair-programming. |
            | **AI Interview** | Brief walkthrough of the architecture, investigation strategy, and evaluation. |
            """
        )

        st.markdown("##### Packaging `code.zip` from PowerShell on Windows:")
        st.code(
            "Compress-Archive -Path README.md, requirements.txt, app.py, src, evaluation -DestinationPath code.zip -Force",
            language="powershell"
        )

        st.markdown("##### Official Submission Portal:")
        st.markdown(
            f"""
            Upload your `code.zip`, `output.csv`, and `log.txt` directly to the HackerRank challenge portal:  
            🔗 **[HackerRank Contest Submission URL]({SUBMISSION_URL})**  
            `{SUBMISSION_URL}`
            """
        )

"""
Run Audit View for Ghost Data Auditor.
Provides execution controls, audit parameters, real-time progress, and granular case inspection.
Powered by the independent core audit engine.
"""

import os
import streamlit as st
import pandas as pd
import json

from src.audit_engine import (
    run_batch_audit,
    DeletionVerdict,
    CaseAuditResult,
    AuditPhase
)
from src.ui.views.evidence import get_evidence_manager


def get_verdict_badge_html(verdict: DeletionVerdict) -> str:
    """Returns styled HTML badge for DeletionVerdict."""
    if verdict == DeletionVerdict.COMPLETE:
        return '<span class="status-badge status-complete">COMPLETE</span>'
    elif verdict == DeletionVerdict.INCOMPLETE:
        return '<span class="status-badge status-incomplete">INCOMPLETE</span>'
    else:
        return '<span class="status-badge status-na">NOT_APPLICABLE</span>'


def render_audit_view():
    """
    Renders the Run Audit control panel, execution monitor, and case inspector.
    """
    st.markdown('<div class="dashboard-title">⚡ Deletion Audit Engine</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Execute policy-grounded deletion audits, detect recreation risks, and compile compliant remediation plans.</div>',
        unsafe_allow_html=True
    )

    # Informational banner
    st.markdown(
        """
        <div class="info-card">
            🛡️ <strong>Evidence-Driven Verification:</strong> Decisions are derived strictly from policy rules and available evidence up to <code>audit_at</code>. Missing evidence is never assumed to be proof of deletion.
        </div>
        """,
        unsafe_allow_html=True
    )

    # Configuration Controls
    col_conf1, col_conf2 = st.columns([1.5, 1])
    with col_conf1:
        target_dataset_option = st.selectbox(
            "Select Request Dataset to Audit:",
            [
                "Sample Requests (32 cases - dataset/sample_deletion_requests.csv)",
                "Full Challenge Evaluation (518 cases - dataset/deletion_requests.csv)"
            ],
            help="Choose between the sample benchmark dataset or the full evaluation dataset."
        )

    with col_conf2:
        st.markdown(
            """
            <div style="background: rgba(30, 41, 59, 0.4); padding: 12px; border-radius: 8px; font-size: 0.85rem; color: #94a3b8;">
                <strong>Temporal Cutoff Rule:</strong><br>
                For every case, evidence captured after <code>audit_at</code> is strictly ignored to preserve temporal integrity.
            </div>
            """,
            unsafe_allow_html=True
        )

    # Determine file path based on selection
    is_sample = "sample" in target_dataset_option.lower()
    requests_filename = "sample_deletion_requests.csv" if is_sample else "deletion_requests.csv"
    requests_path = os.path.join(os.getcwd(), "dataset", requests_filename)
    output_path = os.path.join(os.getcwd(), "output.csv")

    # Run Button
    c_btn, _ = st.columns([1, 2])
    with c_btn:
        run_audit_clicked = st.button("🚀 Execute Audit Engine", type="primary", use_container_width=True)

    if run_audit_clicked:
        with st.spinner(f"Running deletion audit engine across {requests_filename}..."):
            progress_bar = st.progress(0, text="Initializing policy rules & identity resolver...")
            progress_bar.progress(30, text="Auditing cases against evidence & temporal cutoffs...")

            results, out_df = run_batch_audit(requests_path, output_csv_path=output_path)
            st.session_state["active_audit_results"] = results
            st.session_state["active_output_df"] = out_df
            st.session_state["active_audit_dataset"] = requests_filename

            progress_bar.progress(100, text="Audit complete. Output written to output.csv.")
            st.success(f"✓ Audited {len(results)} cases. Results written to `{output_path}`.")
            st.rerun()

    st.divider()

    # Results Display
    results: list[CaseAuditResult] = st.session_state.get("active_audit_results", [])

    if not results:
        # Check if output.csv exists on disk
        if os.path.exists(output_path):
            st.info(f"ℹ️ An `output.csv` file exists on disk. Click **Execute Audit Engine** above to inspect live results.")

        st.markdown(
            """
            <div class="empty-state-box">
                <div class="empty-state-icon">⏱️</div>
                <div class="empty-state-title">No Active Audit Results</div>
                <div class="empty-state-desc">
                    Click <strong>"Execute Audit Engine"</strong> above to run the independent audit engine 
                    over the selected requests dataset and inspect verified deletion verdicts.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    # Summary Metrics Row
    st.markdown(f"### 📊 Audit Summary ({st.session_state.get('active_audit_dataset', 'Dataset')})")
    
    total_cases = len(results)
    complete_count = sum(1 for r in results if r.deletion_status == DeletionVerdict.COMPLETE)
    incomplete_count = sum(1 for r in results if r.deletion_status == DeletionVerdict.INCOMPLETE)
    na_count = sum(1 for r in results if r.deletion_status == DeletionVerdict.NOT_APPLICABLE)
    recreation_count = sum(1 for r in results if any(s.operation in ["REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK"] for s in r.steps))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Cases", total_cases)
    m2.metric("Verified Complete", complete_count)
    m3.metric("Incomplete (Ghost Data)", incomplete_count)
    m4.metric("Not Applicable", na_count)
    m5.metric("Recreation Risks", recreation_count)

    st.divider()

    # Interactive Cases Table & Filter
    st.markdown("### 📋 Case Verdicts Table")
    status_filter = st.selectbox(
        "Filter Cases by Verdict Status:",
        ["All Cases", "COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"],
        index=0
    )

    filtered_results = results
    if status_filter != "All Cases":
        filtered_results = [r for r in results if r.deletion_status.value == status_filter]

    table_data = []
    for r in filtered_results:
        table_data.append({
            "Case ID": r.case_id,
            "Customer Email": r.email,
            "Resolved User ID": r.user_id or "N/A",
            "Verdict": r.deletion_status.value,
            "Total Steps": len(r.steps),
            "Findings": sum(1 for s in r.steps if s.phase == AuditPhase.FINDING.value),
            "Remediation Actions": sum(1 for s in r.steps if s.phase == AuditPhase.REMEDIATION.value),
            "Verifications": sum(1 for s in r.steps if s.phase == AuditPhase.VERIFICATION.value)
        })

    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    st.divider()

    # Detailed Individual Case Inspector
    st.markdown("### 🔬 Inspect Individual Case Audit Details")
    selected_case_id = st.selectbox(
        "Select a Case to Inspect:",
        options=[r.case_id for r in results]
    )

    selected_case = next((r for r in results if r.case_id == selected_case_id), None)
    if selected_case:
        render_case_inspector(selected_case)


def render_case_inspector(case: CaseAuditResult):
    """
    Renders in-depth audit findings, steps, checks, and evidence citations for a single case.
    """
    hdr_col1, hdr_col2 = st.columns([3, 1])
    with hdr_col1:
        st.markdown(f"#### 📄 Case `{case.case_id}` ({case.email})")
        st.caption(f"Resolved Account: **{case.user_id or 'Unresolved'}** • {len(case.steps)} audit step(s) compiled")
    with hdr_col2:
        st.markdown(
            f"<div style='text-align: right; margin-top: 10px;'>{get_verdict_badge_html(case.deletion_status)}</div>",
            unsafe_allow_html=True
        )

    # Rationale or classification note
    if case.rationale:
        st.info(f"**Audit Rationale:** {case.rationale}")

    # Checks summary
    col_pass, col_fail = st.columns(2)
    with col_pass:
        st.markdown("##### ✅ Checks Passed")
        if case.checks_passed:
            for cp in case.checks_passed:
                st.markdown(f"- {cp}")
        else:
            st.caption("No positive compliance checks verified.")

    with col_fail:
        st.markdown("##### ⚠️ Checks Failed / Recreation Risks")
        if case.checks_failed:
            for cf in case.checks_failed:
                st.markdown(f"- <span style='color: #ef4444;'>{cf}</span>", unsafe_allow_html=True)
        else:
            st.caption("No policy failures or recreation risks detected.")

    # Steps Table
    st.markdown("##### 🪜 Compiled Audit Steps (Exact Submission Output)")
    if case.steps:
        steps_data = []
        for s in case.steps:
            steps_data.append({
                "Step #": s.step_no,
                "Phase": s.phase,
                "System": s.system_id,
                "Resource": s.resource_id,
                "Operation": s.operation,
                "State": s.state,
                "Evidence ID": s.evidence_id if s.evidence_id else "(Future Action)"
            })
        st.dataframe(pd.DataFrame(steps_data), use_container_width=True, hide_index=True)
    else:
        st.info("No steps required (NOT_APPLICABLE request). Output steps array is `[]`.")

    # JSON output preview
    with st.expander(f"Inspect JSON Steps Payload ({case.case_id})"):
        st.code(case.get_steps_json(), language="json")

"""
Remediation View for Ghost Data Auditor.
Displays ordered remediation steps, verification checks, dependency hierarchies,
and traceable audit reports compiled by the remediation planning engine.
"""

import streamlit as st
import pandas as pd
import json

from src.audit_engine import DeletionVerdict, AuditPhase, CaseAuditResult
from src.remediation import RemediationPlan, RemediationPlanner, DeletionVerificationReport


def render_remediation_view():
    """
    Renders the Remediation Planning, Verification Reporting, and Audit Trail view.
    """
    st.markdown('<div class="dashboard-title">🛠️ Remediation & Verification</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Inspect dependency-ordered remediation plans, policy guardrails, and verification reports.</div>',
        unsafe_allow_html=True
    )

    # -------------------------------------------------------------
    # Safety Guarantee Callout
    # -------------------------------------------------------------
    st.markdown(
        """
        <div class="safety-card">
            <strong>🛡️ READ-ONLY SAFETY GUARANTEE:</strong> All remediation actions displayed below are proposed engineering recommendations.
            The Ghost Data Auditor operates in <strong>Read-Only Inspection Mode</strong> and <strong>never</strong> performs automatic external deletions, database updates, or process terminations.
        </div>
        """,
        unsafe_allow_html=True
    )

    results: list[CaseAuditResult] = st.session_state.get("active_audit_results", [])

    if not results:
        st.markdown(
            """
            <div class="empty-state-box">
                <div class="empty-state-icon">🛡️</div>
                <div class="empty-state-title">No Audit Executed Yet</div>
                <div class="empty-state-desc">
                    Remediation plans and verification checks are compiled during audit execution when ghost records 
                    or active recreation risks are identified. Run an audit in the <strong>Run Audit</strong> section.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    # Tabs for Plan, Full Audit Trail, Export Reports, and Operations Reference
    tab_plan, tab_trail, tab_report, tab_rules = st.tabs([
        "📋 Action & Verification Blueprint",
        "🔍 Traceable Audit Trail",
        "📄 Export Verification Report",
        "📚 Operations & Policy Reference"
    ])

    # Case Selection Controls
    status_filter = st.sidebar.selectbox(
        "Filter Cases by Verdict:",
        options=["ALL", "INCOMPLETE", "COMPLETE", "NOT_APPLICABLE"],
        index=0
    )

    filtered_cases = results
    if status_filter != "ALL":
        filtered_cases = [r for r in results if r.deletion_status.value == status_filter]

    if not filtered_cases:
        st.info(f"No cases found matching filter '{status_filter}'.")
        return

    selected_case_id = st.selectbox(
        "Select a Case to Inspect Remediation & Verification Blueprint:",
        options=[c.case_id for c in filtered_cases]
    )

    case = next((c for c in filtered_cases if c.case_id == selected_case_id), None)
    if not case:
        return

    # Ensure plan exists on the case object
    planner = RemediationPlanner()
    plan: RemediationPlan = getattr(case, "remediation_plan", None) or planner.build_plan(case.case_id, case)

    # -------------------------------------------------------------
    # TAB 1: Action & Verification Blueprint
    # -------------------------------------------------------------
    with tab_plan:
        st.markdown(f"#### Case Dossier: `{case.case_id}`")
        badge_cls = {
            DeletionVerdict.COMPLETE: "status-complete",
            DeletionVerdict.INCOMPLETE: "status-incomplete",
            DeletionVerdict.NOT_APPLICABLE: "status-na"
        }.get(case.deletion_status, "status-na")

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Customer Email:** `{case.email or 'N/A'}`")
        c2.markdown(f"**Resolved User ID:** `{case.user_id or 'Unlinked / Unknown'}`")
        c3.markdown(
            f"**Audit Status:** <span class='status-badge {badge_cls}'>{case.deletion_status.value}</span>",
            unsafe_allow_html=True
        )

        st.markdown("---")

        # CASE TYPE 1: NOT_APPLICABLE
        if case.deletion_status == DeletionVerdict.NOT_APPLICABLE:
            st.info(
                "ℹ️ **Status: NOT_APPLICABLE** — The customer's request did not authorize deletion "
                "(e.g., requested an invoice copy, data export, or address update). "
                "Per policy guardrails, zero remediation actions are generated to avoid destroying data without customer consent."
            )
            if case.rationale:
                st.caption(f"**Intent Rationale:** {case.rationale}")

        # CASE TYPE 2: COMPLETE
        elif case.deletion_status == DeletionVerdict.COMPLETE:
            st.success(
                "✅ **Status: COMPLETE** — Deletion is fully verified compliant up to the `audit_at` cutoff. "
                "No lingering records or recreation risks exist. The following evidence proves compliance:"
            )
            ver_steps = [s for s in case.steps if s.phase == AuditPhase.VERIFICATION.value]
            if ver_steps:
                ver_df = pd.DataFrame([
                    {
                        "Step #": s.step_no,
                        "System": s.system_id,
                        "Resource": s.resource_id,
                        "Verification Check": s.operation,
                        "Verified State": s.state,
                        "Supporting Evidence": s.evidence_id
                    }
                    for s in ver_steps
                ])
                st.dataframe(ver_df, use_container_width=True, hide_index=True)
            else:
                st.info("No explicit verification steps recorded.")

        # CASE TYPE 3: INCOMPLETE
        else:
            findings = [s for s in plan.ordered_steps if s.phase == AuditPhase.FINDING.value]
            rem_steps = [s for s in plan.ordered_steps if s.phase == AuditPhase.REMEDIATION.value]
            ver_steps = [s for s in plan.ordered_steps if s.phase == AuditPhase.VERIFICATION.value]

            m1, m2, m3 = st.columns(3)
            m1.metric("Confirmed Findings", len(findings))
            m2.metric("Proposed Remediation Actions", len(rem_steps))
            m3.metric("Required Post-Verifications", len(ver_steps))

            # Sub-Section A: Evidence-Backed Findings
            st.markdown("##### 1. Evidence-Backed Findings (Confirmed Failures)")
            if findings:
                f_df = pd.DataFrame([
                    {
                        "Step #": f.step_no,
                        "System": f.system_id,
                        "Resource": f.resource_id,
                        "Finding Type": f.operation,
                        "Detected State": f.state,
                        "Evidence ID": f.evidence_id
                    }
                    for f in findings
                ])
                st.dataframe(f_df, use_container_width=True, hide_index=True)
            else:
                st.warning("No individual record findings logged, but compliance checks failed.")

            # Sub-Section B: Dependency-Ordered Remediation
            st.markdown("##### 2. Proposed Remediation Sequence (Dependency-Ordered)")
            st.caption(
                "🛡️ **Precedence Hierarchy:** "
                "Order 1 (Process Neutralization) must execute before Order 2 (Downstream Stores), "
                "which must execute before Order 3 (Primary Stores & Tombstones)."
            )

            if plan.actions:
                action_rows = []
                for s in rem_steps:
                    action = next((a for a in plan.actions if a.resource_id == s.resource_id), None)
                    order_badge = f"Level {action.dependency_order}" if action else "Level 3"
                    rule_id = action.policy_rule_id if action else "POLICY_DEFAULT"
                    deps = ", ".join(action.dependencies) if action and action.dependencies else "None (Prerequisite)"
                    reason = action.reason if action else "Remediation required by policy."

                    action_rows.append({
                        "Step #": s.step_no,
                        "Dependency Order": order_badge,
                        "System": s.system_id,
                        "Resource": s.resource_id,
                        "Remediation Op": s.operation,
                        "Target State": s.state,
                        "Policy Rule": rule_id,
                        "Dependencies": deps,
                        "Reason": reason,
                        "Execution Status": "RECOMMENDED (Pending)"
                    })
                st.dataframe(pd.DataFrame(action_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No remediation actions compiled.")

            # Sub-Section C: Post-Remediation Verification
            st.markdown("##### 3. Post-Remediation Verification Matrix (Future Work)")
            st.caption("Checks that must be performed by engineering after completing the remediation sequence.")
            if ver_steps:
                ver_rows = []
                for v in ver_steps:
                    action = next((a for a in plan.actions if a.resource_id == v.resource_id), None)
                    if v.operation == "VERIFY_DATA_FLOW_DISABLED":
                        crit = "Query pipeline orchestrator to confirm sync job is inactive/disabled."
                    elif v.operation == "VERIFY_RESTORE_BLOCKED":
                        crit = "Inspect backup restore access policy to confirm snapshot restore is prohibited."
                    elif v.operation == "VERIFY_RECORD_ABSENT":
                        crit = "Execute readback lookup returning 404 / 0 rows."
                    elif v.operation == "VERIFY_RECORD_REDACTED":
                        crit = "Verify direct identifiers (email, name, phone, hash) are NULL while preserving user_id."
                    elif v.operation == "VERIFY_RECORD_ANONYMIZED":
                        crit = "Confirm record is irreversibly unlinked from personal identifiers."
                    elif v.operation == "VERIFY_RECORD_PRESENT":
                        crit = "Verify policy-required retained record remains intact."
                    else:
                        crit = f"Confirm resource {v.resource_id} is in {v.state} state."

                    ver_rows.append({
                        "Step #": v.step_no,
                        "System": v.system_id,
                        "Resource": v.resource_id,
                        "Verification Check": v.operation,
                        "Required State": v.state,
                        "Verification Criteria": crit,
                        "Evidence ID": v.evidence_id or "(Future Verification)"
                    })
                st.dataframe(pd.DataFrame(ver_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No verification checks registered.")

    # -------------------------------------------------------------
    # TAB 2: Complete Traceable Audit Trail
    # -------------------------------------------------------------
    with tab_trail:
        st.markdown(f"#### Complete Traceable Audit Trail for `{case.case_id}`")
        st.write(
            "Every step is rigorously grounded with evidence IDs, applicable policy rules, "
            "and an explicit distinction between evidencing existing state versus recommending future remediation."
        )

        if plan.audit_trail:
            trail_df = pd.DataFrame([
                {
                    "Step #": item.get("step_no", "-"),
                    "Phase": item.get("phase", "-"),
                    "System": item.get("system_id", "-"),
                    "Resource": item.get("resource_id", "-"),
                    "Operation": item.get("operation", "-"),
                    "Target State": item.get("target_state", item.get("state", "-")),
                    "Evidence ID": item.get("evidence_id", "-"),
                    "Policy Rule": item.get("policy_rule", "-"),
                    "Status": item.get("status", "PENDING"),
                    "Justification": item.get("justification", "-")
                }
                for item in plan.audit_trail
            ])
            st.dataframe(trail_df, use_container_width=True, hide_index=True)
        else:
            st.info("No audit trail entries logged.")

        if plan.additional_investigations:
            st.markdown("##### ⚠️ Additional Investigations Required")
            for inv in plan.additional_investigations:
                st.warning(inv)

    # -------------------------------------------------------------
    # TAB 3: Export Verification Report
    # -------------------------------------------------------------
    with tab_report:
        st.markdown(f"#### Deletion Verification Report: `{case.case_id}`")
        st.write("Generate and download formal verification reports for compliance review or audit sign-off.")

        md_report = DeletionVerificationReport.generate_markdown_report(plan)
        summary_dict = DeletionVerificationReport.generate_summary_dict(plan)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📥 Download Markdown Report (.md)",
                data=md_report,
                file_name=f"deletion_verification_report_{case.case_id}.md",
                mime="text/markdown"
            )
        with col_d2:
            st.download_button(
                label="📥 Download Structured Plan (.json)",
                data=json.dumps(summary_dict, indent=2),
                file_name=f"remediation_plan_{case.case_id}.json",
                mime="application/json"
            )

        st.markdown("##### Report Preview:")
        st.markdown(md_report)

    # -------------------------------------------------------------
    # TAB 4: Operations & Policy Reference Guide
    # -------------------------------------------------------------
    with tab_rules:
        st.markdown("#### Phase Sequencing & Allowed Operations")
        st.markdown(
            """
            Every generated plan must follow strict chronological phase ordering:
            1. **FINDING Phase:** Document all remaining records, exposed PII, active pipelines, and restore risks citing participant evidence.
            2. **REMEDIATION Phase:** Propose corrective measures (disable syncs, block restores, delete or redact data) with empty evidence ID.
            3. **VERIFICATION Phase:** Formally verify that data is absent/redacted and data flows are disabled.
            """
        )

        st.markdown("##### 🛠️ Allowed Remediation Operations")
        remediation_ops = [
            {"Operation": "DISABLE_DATA_FLOW", "State": "DISABLED", "Dependency": "Level 1", "Meaning": "Stop the sync, ETL, or export process that can recreate data."},
            {"Operation": "BLOCK_RESTORE", "State": "BLOCKED", "Dependency": "Level 1", "Meaning": "Prevent the affected backup snapshot from restoring deleted records."},
            {"Operation": "DELETE_RECORD", "State": "ABSENT", "Dependency": "Level 2/3", "Meaning": "Permanently remove the entire record from the data store."},
            {"Operation": "REDACT_RECORD", "State": "REDACTED", "Dependency": "Level 3", "Meaning": "Keep the record structure but blank out prohibited personal identifiers."},
            {"Operation": "ANONYMIZE_RECORD", "State": "ANONYMIZED", "Dependency": "Level 2/3", "Meaning": "Irreversibly unlink the record from the individual user identity."}
        ]
        st.dataframe(pd.DataFrame(remediation_ops), use_container_width=True, hide_index=True)

        st.markdown("##### 🔬 Allowed Verification Operations")
        verification_ops = [
            {"Operation": "VERIFY_RECORD_ABSENT", "State": "ABSENT", "Meaning": "Confirm that an unauthorized record no longer exists."},
            {"Operation": "VERIFY_RECORD_PRESENT", "State": "PRESENT", "Meaning": "Confirm that a policy-required retained record remains available."},
            {"Operation": "VERIFY_RECORD_REDACTED", "State": "REDACTED", "Meaning": "Confirm that required personal fields have been stripped."},
            {"Operation": "VERIFY_RECORD_ANONYMIZED", "State": "ANONYMIZED", "Meaning": "Confirm that the record cannot be linked to the user."},
            {"Operation": "VERIFY_DATA_FLOW_DISABLED", "State": "DISABLED", "Meaning": "Confirm that the relevant data sync flow is inactive."},
            {"Operation": "VERIFY_RESTORE_BLOCKED", "State": "BLOCKED", "Meaning": "Confirm that the affected backup cannot restore deleted data."}
        ]
        st.dataframe(pd.DataFrame(verification_ops), use_container_width=True, hide_index=True)

        st.markdown("##### 🛡️ Core Policy Guardrails")
        st.markdown(
            """
            - **Mandatory Retention:** Never delete records governed by retention requirements (`SECURITY_AUDIT_LOG`, `FINANCIAL_LEDGER`, `LEGAL_HOLD`).
            - **Account Tombstones:** Preserve internal `user_id` while redacting all direct identifiers (email, name, phone, hash).
            - **Process Precedence:** Always neutralize sync pipelines and restore paths before altering data records.
            - **Non-Destructive Execution:** Recommendations are never automatically applied to external systems.
            """
        )

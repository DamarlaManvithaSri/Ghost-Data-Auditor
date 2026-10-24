"""
Dashboard View for Ghost Data Auditor.
Provides a cybersecurity overview, system metrics, architecture explanation, and beginner guide.
"""

import streamlit as st

def render_dashboard_view():
    """
    Renders the primary dashboard view.
    """
    # Header Banner
    st.markdown('<div class="dashboard-title">🛡️ Ghost Data Auditor</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Enterprise Data Deletion Verification & Ghost Data Remediation System</div>',
        unsafe_allow_html=True
    )

    # Top Metrics Bar
    col1, col2, col3, col4 = st.columns(4)
    results = st.session_state.get("active_audit_results", [])
    with col1:
        engine_status = f"AUDITED ({len(results)} Cases)" if results else "READY (Planner Active)"
        engine_color = "#10b981" if results else "#38bdf8"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Audit Engine Status</div>
                <div class="metric-card-value" style="color: {engine_color}; font-size: 1.25rem;">{engine_status}</div>
                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">Local & Non-Destructive</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        manager = st.session_state.get("evidence_manager")
        evidence_count = len(manager.get_all_files()) if manager else len(st.session_state.get("uploaded_files", []))
        total_records = manager.get_summary()["total_records"] if manager else 0
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Evidence Files Ingested</div>
                <div class="metric-card-value">{evidence_count}</div>
                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">{total_records} records indexed</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col3:
        resolved_identity = st.session_state.get("active_resolved_identity")
        id_display = "1 Active" if resolved_identity and resolved_identity.status == "RESOLVED" else f"{len(results)} Tracked" if results else "0"
        sub_text = f"User: {resolved_identity.user_id}" if resolved_identity and resolved_identity.user_id else f"{len(results)} cases mapped" if results else "No active query"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Identities Resolved</div>
                <div class="metric-card-value">{id_display}</div>
                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">{sub_text}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col4:
        total_rem_steps = 0
        for r in results:
            if hasattr(r, "steps"):
                total_rem_steps += len([s for s in r.steps if s.phase == "REMEDIATION"])
        rem_sub = f"Across {len(results)} cases" if results else "Awaiting audit run"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Remediation Steps</div>
                <div class="metric-card-value">{total_rem_steps}</div>
                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">{rem_sub}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Status Overview Section
    st.markdown("### 📊 Deletion Verdict Statuses")
    st.write(
        "When investigating data deletion requests, the system classifies every case into one of three standardized states:"
    )

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.markdown(
            """
            <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 16px;">
                <span class="status-badge status-complete">COMPLETE</span>
                <h4 style="margin-top: 10px; color: #10b981;">Deletion Verified</h4>
                <p style="font-size: 0.88rem; color: #94a3b8; line-height: 1.5;">
                    The customer's personal data has been fully removed, redacted, or anonymized across all primary & replica stores, logs, and exports. Required policy records are retained safely, and no active processes recreate the data.
                </p>
                <div style="font-size: 0.8rem; color: #6ee7b7;">✓ Produces evidence-backed verification proofs.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with stat_col2:
        st.markdown(
            """
            <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 16px;">
                <span class="status-badge status-incomplete">INCOMPLETE</span>
                <h4 style="margin-top: 10px; color: #ef4444;">Ghost Data Persists</h4>
                <p style="font-size: 0.88rem; color: #94a3b8; line-height: 1.5;">
                    Personal data or unauthorized identifiers were detected in databases, backups, search indexes, or logs. Active replication, sync jobs, or restore workflows can also revive deleted records.
                </p>
                <div style="font-size: 0.8rem; color: #fca5a5;">⚠ Generates findings and ordered remediation plan.</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with stat_col3:
        st.markdown(
            """
            <div style="background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 8px; padding: 16px;">
                <span class="status-badge status-na">NOT_APPLICABLE</span>
                <h4 style="margin-top: 10px; color: #94a3b8;">No Deletion Authorized</h4>
                <p style="font-size: 0.88rem; color: #94a3b8; line-height: 1.5;">
                    The customer inquiry or message did not authorize data erasure (for example: shipping inquiry, change of address request, or account question). No deletion or remediation is allowed.
                </p>
                <div style="font-size: 0.8rem; color: #cbd5e1;">ℹ Result contains an empty steps array [].</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Detailed Architecture & Beginner Guide in Tabs
    tab_guide, tab_lifecycle, tab_arch = st.tabs([
        "🚀 Beginner's Quick Start",
        "🔄 The 5-Phase Audit Lifecycle",
        "🏗️ How Ghost Data Appears"
    ])

    with tab_guide:
        st.markdown("#### How to Use Ghost Data Auditor")
        st.markdown(
            """
            Welcome! This dashboard is designed to make complex privacy audits clear and intuitive, even if you are new to programming:

            1. **Step 1: Check Evidence Files**  
               Go to the **Evidence Files** tab in the sidebar. You can upload custom audit dumps (databases, logs, tickets, JSON, exports) or load the provided challenge files from the `dataset/` directory.

            2. **Step 2: Configure and Run the Audit**  
               In the **Run Audit** section, select which cases to audit (sample cases or full dataset). Review the cutoff timestamp (`audit_at`).

            3. **Step 3: Inspect Findings & Discovered Identifiers**  
               View all identified personal records, exposed PII, active sync loops, and backup restore risks in **Findings**.

            4. **Step 4: Review Remediation & Verification Plan**  
               Inspect the ordered action plan (`DISABLE_DATA_FLOW`, `BLOCK_RESTORE`, `DELETE_RECORD`, `REDACT_RECORD`, `ANONYMIZE_RECORD`) in **Remediation**.

            5. **Step 5: Export Submission File**  
               Generate and validate your final `output.csv` matching the strict challenge schema in the **Export** tab.
            """
        )
        st.info("💡 **Local Safety Guarantee:** All processing stays on your machine. No real customer data is ever deleted, altered, or sent to external servers.")

    with tab_lifecycle:
        st.markdown("#### The 5-Phase Investigation Lifecycle")
        st.markdown(
            """
            ```
            ┌────────────────────────┐
            │ 1. Request Intent      │  Determine if user requested deletion:
            │    Verification        │  COMPLETE / INCOMPLETE vs NOT_APPLICABLE
            └───────────┬────────────┘
                        │
            ┌───────────▼────────────┐
            │ 2. Identity Resolution │  Reconstruct current & historical IDs:
            │    & Lineage Graph     │  user_id, names, emails, phones, hashes
            └───────────┬────────────┘
                        │
            ┌───────────▼────────────┐
            │ 3. Multi-Store Evidence│  Scan DBs, replicas, logs, exports,
            │    Investigation       │  indexes, and support attachments
            └───────────┬────────────┘
                        │
            ┌───────────▼────────────┐
            │ 4. Policy & Retention  │  Apply deletion_rules.csv:
            │    Rule Matching       │  Keep tombstones, preserve required logs
            └───────────┬────────────┘
                        │
            ┌───────────▼────────────┐
            │ 5. Remediation &       │  Generate ordered JSON action plan:
            │    Verification Plan   │  Findings -> Remediation -> Verification
            └────────────────────────┘
            ```
            """
        )

    with tab_arch:
        st.markdown("#### Why Does 'Ghost Data' Happen?")
        st.markdown(
            """
            When a modern application executes a deletion request, data often lingers in hidden places:
            
            * **Replication Drift:** Primary database deletes the row, but read-replicas, failover clusters, or regional caches lag behind.
            * **Log & Metric Aggregators:** Audit trails, error logs, and HTTP access logs often capture request payloads containing raw emails or phone numbers.
            * **Support Attachments:** Customer service screenshots, CSV attachments, and PDF invoices stored in file buckets.
            * **Automated Sync Jobs:** Nightly data warehouse syncs or CRM syncs can push stale data back into production databases.
            * **Backup Restores:** Restoring a disaster recovery snapshot can bring permanently deleted users back to life.
            * **Account Tombstones:** Some systems must keep the user record for accounting, but fail to redact prohibited personal fields.
            """
        )

    # Empty State Notice
    if evidence_count == 0:
        st.markdown(
            """
            <div class="empty-state-box">
                <div class="empty-state-icon">📂</div>
                <div class="empty-state-title">No Evidence Loaded Yet</div>
                <div class="empty-state-desc">
                    To start an audit investigation, upload your evidence files or load the challenge dataset from the <strong>Evidence Files</strong> section in the sidebar.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

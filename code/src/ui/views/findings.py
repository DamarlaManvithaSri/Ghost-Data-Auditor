"""
Findings & Identity Resolution View for Ghost Data Auditor.
Displays evidence-backed customer identity lineage, justification for each link,
and cross-system ghost data occurrences.
"""

import os
import streamlit as st
import pandas as pd

from src.identity import (
    IdentityResolver,
    ResolvedIdentity,
    LinkConfidence,
    IdentifierType,
    CrossSystemIdentitySearcher
)
from src.ui.views.evidence import get_evidence_manager


def get_confidence_badge_html(confidence: LinkConfidence) -> str:
    """Returns styled HTML badge for LinkConfidence."""
    badge_map = {
        LinkConfidence.CONFIRMED: ("badge-confirmed", "CONFIRMED"),
        LinkConfidence.PROBABLE: ("badge-probable", "PROBABLE"),
        LinkConfidence.CONFLICT: ("badge-conflict", "CONFLICT"),
        LinkConfidence.UNRESOLVED: ("badge-unresolved", "UNRESOLVED")
    }
    css_class, label = badge_map.get(confidence, ("badge-unresolved", confidence.value))
    return f'<span class="status-badge {css_class}">{label}</span>'


def render_findings_view():
    """
    Renders the Findings view including interactive identity resolution and cross-system discoveries.
    """
    st.markdown('<div class="dashboard-title">🔎 Audit Findings & Identity Resolution</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Trace current and historical customer identities, inspect evidence links, and detect ghost data across stores.</div>',
        unsafe_allow_html=True
    )

    tab_identity, tab_findings, tab_operations = st.tabs([
        "👤 Identity Resolution & Lineage",
        "⚠️ Ghost Data & Recreation Findings",
        "📖 Allowed Finding Operations"
    ])

    with tab_identity:
        render_identity_resolution_tab()

    with tab_findings:
        render_evidence_findings_tab()

    with tab_operations:
        render_operations_reference_tab()


def render_identity_resolution_tab():
    """
    Interactive customer identity lineage resolver.
    """
    st.markdown("#### 👤 Customer Identity Resolution")
    st.write(
        "Enter a customer email or stable `user_id` to reconstruct their complete identity graph, "
        "including former emails, phone numbers, and SHA-256 hashes from identity snapshots and audit logs."
    )

    # Load potential cases from dataset if available
    sample_requests_path = os.path.join(os.getcwd(), "dataset", "sample_deletion_requests.csv")
    full_requests_path = os.path.join(os.getcwd(), "dataset", "deletion_requests.csv")
    
    prefill_options = []
    if os.path.exists(sample_requests_path):
        try:
            req_df = pd.read_csv(sample_requests_path)
            for _, r in req_df.head(10).iterrows():
                prefill_options.append(f"{r.get('case_id')}: {r.get('email')} (Audit at: {r.get('audit_at')})")
        except Exception:
            pass

    col_input, col_cutoff = st.columns([2, 1])
    with col_input:
        if prefill_options:
            selected_case = st.selectbox(
                "Quick-Select Case from Sample Requests (or type custom below):",
                ["-- Manual Input --"] + prefill_options
            )
            if selected_case != "-- Manual Input --":
                # Parse email and audit_at
                parts = selected_case.split(": ")
                email_part = parts[1].split(" (Audit at: ")[0]
                audit_part = parts[1].split(" (Audit at: ")[1].rstrip(")")
                default_seed = email_part
                default_cutoff = audit_part
            else:
                default_seed = "ingrid.dahl@outlook.com"
                default_cutoff = ""
        else:
            default_seed = "ingrid.dahl@outlook.com"
            default_cutoff = ""

        seed_input = st.text_input(
            "Customer Seed Identifier (Email or user_id):",
            value=default_seed,
            help="The identifier provided in the deletion request."
        )

    with col_cutoff:
        cutoff_input = st.text_input(
            "Audit Cutoff Time (`audit_at`):",
            value=default_cutoff,
            placeholder="e.g. 2026-07-19T13:00:00Z",
            help="Optional ISO-8601 cutoff timestamp. Changes after this timestamp are ignored."
        )

    # Resolution Action
    if st.button("🔍 Resolve & Trace Customer Identity", type="primary"):
        resolver = IdentityResolver()
        cutoff = cutoff_input.strip() if cutoff_input.strip() else None
        resolved = resolver.resolve(seed_input, audit_cutoff_time=cutoff)
        st.session_state["active_resolved_identity"] = resolved

    st.divider()

    # Display Resolved Identity Dossier
    resolved_id: ResolvedIdentity = st.session_state.get("active_resolved_identity")
    if not resolved_id:
        st.markdown(
            """
            <div class="empty-state-box">
                <div class="empty-state-icon">👤</div>
                <div class="empty-state-title">No Customer Identity Resolved Yet</div>
                <div class="empty-state-desc">
                    Enter a customer email or account ID above and click <strong>"Resolve & Trace Customer Identity"</strong> 
                    to construct an evidence-backed identity lineage.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    # Status Banner
    status_color = "#10b981" if resolved_id.status == "RESOLVED" else "#ef4444" if resolved_id.status == "CONFLICT" else "#94a3b8"
    st.markdown(
        f"""
        <div style="background: rgba(17, 24, 39, 0.6); border-left: 4px solid {status_color}; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin: 0; color: #f8fafc;">Customer Dossier: <code>{resolved_id.user_id or 'Unresolved Account'}</code></h3>
                    <div style="color: #94a3b8; font-size: 0.9rem; margin-top: 4px;">Seed Query: <code>{resolved_id.seed_identifier}</code></div>
                </div>
                <div>
                    <span class="status-badge" style="background: rgba(255,255,255,0.1); color: {status_color}; border: 1px solid {status_color};">
                        {resolved_id.status}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if resolved_id.conflicts:
        for c in resolved_id.conflicts:
            st.warning(f"⚠️ {c}")

    # Summary Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Stable User ID", resolved_id.user_id or "N/A")
    with c2:
        st.metric("Associated Emails", len(resolved_id.get_emails()))
    with c3:
        st.metric("Phone Numbers", len(resolved_id.get_phones()))
    with c4:
        st.metric("Historical Changes", len(resolved_id.timeline))

    # Identifiers Breakdown (Current vs Historical)
    col_curr, col_hist = st.columns(2)
    with col_curr:
        st.markdown("##### 🟢 Current Active Identifiers")
        if resolved_id.current_identifiers:
            for id_type, vals in resolved_id.current_identifiers.items():
                st.markdown(f"**{id_type}:** `{'`, `'.join(sorted(vals))}`")
        else:
            st.caption("No active identifiers registered.")

    with col_hist:
        st.markdown("##### 📜 Historical / Former Identifiers")
        if resolved_id.historical_identifiers:
            for id_type, vals in resolved_id.historical_identifiers.items():
                st.markdown(f"**{id_type} (Former):** `{'`, `'.join(sorted(vals))}`")
        else:
            st.caption("No historical changes recorded before cutoff.")

    # Traceable Identity Links Table (Requirement 4 & 11)
    st.markdown("#### 🔗 Evidence-Backed Identity Links")
    st.write("Inspect the exact source file, record, and justification supporting each linked identifier:")

    links_data = []
    for link in resolved_id.links:
        links_data.append({
            "Identifier Type": link.identifier_type.value,
            "Value": link.identifier_value,
            "Timeline": "Historical Former" if link.is_historical else "Current Active",
            "Confidence": link.confidence.value,
            "Source File": link.source_file,
            "Location": link.source_location,
            "Evidence Snippet": link.evidence_text[:80],
            "Justification": link.justification
        })

    st.dataframe(pd.DataFrame(links_data), use_container_width=True, hide_index=True)

    # Timeline of Changes (Requirement 10)
    if resolved_id.timeline:
        with st.expander(f"🕒 Historical Identity Change Audit Trail ({len(resolved_id.timeline)} Events)"):
            timeline_df = pd.DataFrame(resolved_id.timeline)
            st.dataframe(timeline_df, use_container_width=True, hide_index=True)

    # Cross-System Secondary Search (Requirement 8)
    st.divider()
    st.markdown("#### 📡 Cross-System Evidence Discovery")
    st.write(
        "Search across all loaded databases, replicas, server logs, PDF statements, and exports "
        "to discover everywhere this customer's current and historical identifiers linger."
    )

    evidence_mgr = get_evidence_manager()
    files_available = len(evidence_mgr.get_all_files())

    if files_available == 0:
        st.info("💡 To search across evidence files, please first ingest evidence in the **Evidence Files** tab.")
    else:
        st.caption(f"Ready to scan across **{files_available}** ingested evidence files.")
        if st.button("🚀 Scan All Evidence Files for Customer Traces", type="primary"):
            with st.spinner("Scanning cross-system evidence..."):
                searcher = CrossSystemIdentitySearcher(evidence_mgr)
                occurrences = searcher.search_customer_records(resolved_id, include_name=False)
                st.session_state["active_customer_occurrences"] = occurrences

        # Show scan results if available
        occurrences = st.session_state.get("active_customer_occurrences", [])
        if occurrences:
            st.success(f"✓ Detected customer identifiers in **{len(occurrences)}** evidence records:")
            occ_data = []
            for occ in occurrences:
                occ_data.append({
                    "Target User ID": occ.target_user_id,
                    "Source Evidence Reference": occ.source_reference,
                    "Matched Identifier": f"{occ.matched_identifier_type}: {occ.matched_value}",
                    "Is Historical?": "Yes (Former)" if occ.is_historical else "No (Current)",
                    "Record Type": occ.record_type,
                    "Snippet": occ.snippet
                })
            st.dataframe(pd.DataFrame(occ_data), use_container_width=True, hide_index=True)


def render_evidence_findings_tab():
    """
    Renders the Evidence-Backed Findings tab.
    """
    st.markdown("#### Evidence-Backed Findings")
    st.write(
        "Every lingering piece of personal data and every process capable of recreating it is cataloged with concrete evidence IDs."
    )

    st.markdown(
        """
        <div class="empty-state-box">
            <div class="empty-state-icon">🛡️</div>
            <div class="empty-state-title">No Findings Recorded Yet</div>
            <div class="empty-state-desc">
                Audit findings will populate here once the auditor processes the loaded evidence files.
                Findings identify lingering database records, exposed PII in tombstones, and active sync pipelines.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_operations_reference_tab():
    """
    Allowed Finding Operations Reference.
    """
    st.markdown("#### Allowed Finding Operations Reference")
    st.write("The auditor strictly adheres to the challenge specification for finding classification:")

    ops_data = [
        {
            "Operation": "REPORT_REMAINING_RECORD",
            "State": "PRESENT",
            "Description": "A record that should have been deleted still exists in a database, replica, export, or attachment."
        },
        {
            "Operation": "REPORT_EXPOSED_PII",
            "State": "PRESENT",
            "Description": "A record is allowed to remain (e.g., account tombstone), but still contains unredacted direct identifiers (name, email, phone)."
        },
        {
            "Operation": "REPORT_ACTIVE_DATA_FLOW",
            "State": "ACTIVE",
            "Description": "An active process (e.g. ETL sync, indexing pipeline) can copy or recreate the customer's data."
        },
        {
            "Operation": "REPORT_RESTORE_RISK",
            "State": "ACTIVE",
            "Description": "An automated backup or disaster-recovery restore mechanism can bring deleted data back."
        }
    ]
    st.dataframe(pd.DataFrame(ops_data), use_container_width=True, hide_index=True)

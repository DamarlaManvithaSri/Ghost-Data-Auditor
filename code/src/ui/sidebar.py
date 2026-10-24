"""
Sidebar component for Ghost Data Auditor.
Handles navigation and explains the audit statuses.
"""

import streamlit as st

def render_sidebar():
    """
    Renders the sidebar navigation and status explanation.
    Returns the selected section name.
    """
    with st.sidebar:
        # App branding header
        st.markdown("### 🛡️ Ghost Data Auditor")
        st.caption("Privacy & Deletion Verification System • v0.1.0 Foundation")
        st.divider()

        # Navigation menu
        st.markdown("#### 🧭 Navigation")
        nav_options = [
            "Dashboard",
            "Evidence Files",
            "Run Audit",
            "Findings",
            "Remediation",
            "Evaluation",
            "Export"
        ]
        
        selected_section = st.radio(
            "Go to section:",
            nav_options,
            index=0,
            label_visibility="collapsed"
        )

        st.divider()

        # Audit Status Explanation (Required by specification)
        st.markdown("#### 📋 Audit Statuses")
        st.markdown(
            """
            Understanding the 3 verdict statuses:

            * <span class="status-badge status-complete">COMPLETE</span>  
              **All verified.** All personal data is proven deleted, redacted, or anonymized in accordance with retention rules, and no active sync/restore processes can recreate it.

            * <span class="status-badge status-incomplete">INCOMPLETE</span>  
              **Ghost data persists.** Personal identifiers remain in secondary stores, backups, logs, or active processes can revive deleted data. Remediation is required.

            * <span class="status-badge status-na">NOT_APPLICABLE</span>  
              **Not a deletion request.** The customer's message did not authorize data erasure (e.g., general inquiry, order tracking, address update). No deletion is performed.
            """,
            unsafe_allow_html=True
        )

        st.divider()

        # Privacy and Execution Guarantee badge
        st.markdown("#### 🔒 Security & Privacy")
        st.markdown(
            """
            - **100% Local Execution:** No customer data is sent to external servers or cloud APIs.
            - **Read-Only Mode:** Source databases and evidence files are never modified or deleted.
            """
        )

    return selected_section

"""
Ghost Data Auditor - Main Application Entrypoint
A Streamlit-based cybersecurity dashboard for investigating and remediating ghost data deletion failures.
"""

import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="Ghost Data Auditor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import UI components
from src.ui.styles import apply_custom_styles
from src.ui.sidebar import render_sidebar
from src.ui.views.dashboard import render_dashboard_view
from src.ui.views.evidence import render_evidence_view
from src.ui.views.audit import render_audit_view
from src.ui.views.findings import render_findings_view
from src.ui.views.remediation import render_remediation_view
from src.ui.views.evaluation import render_evaluation_view
from src.ui.views.export import render_export_view

def main():
    """
    Main application router.
    Applies global styles, renders the sidebar navigation, and routes to selected view.
    """
    try:
        # 1. Apply cybersecurity custom styling
        apply_custom_styles()

        # 2. Render navigation sidebar and retrieve current selection
        selected_section = render_sidebar()

        # 3. Route to the appropriate view
        if selected_section == "Dashboard":
            render_dashboard_view()
        elif selected_section == "Evidence Files":
            render_evidence_view()
        elif selected_section == "Run Audit":
            render_audit_view()
        elif selected_section == "Findings":
            render_findings_view()
        elif selected_section == "Remediation":
            render_remediation_view()
        elif selected_section == "Evaluation":
            render_evaluation_view()
        elif selected_section == "Export":
            render_export_view()
        else:
            render_dashboard_view()

    except Exception as e:
        st.error(f"An unexpected error occurred in the dashboard: {str(e)}")
        st.info("Tip for beginners: If you modified any source files or packages, verify the syntax and restart the app.")

if __name__ == "__main__":
    main()

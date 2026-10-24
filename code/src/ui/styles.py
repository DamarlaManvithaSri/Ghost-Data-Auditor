"""
Cybersecurity Dashboard Design Styles.
Provides custom CSS to give Ghost Data Auditor a sleek, professional, modern theme.
"""

import streamlit as st

def apply_custom_styles():
    """
    Applies custom CSS styling for a cybersecurity auditor look and feel.
    Uses high-contrast dark tones, subtle neon accents, and clean status badges.
    """
    st.markdown(
        """
        <style>
        /* Import Google Font */
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

        /* Global typography & background adjustments */
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        
        code, pre {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* Top header accent bar */
        header[data-testid="stHeader"] {
            background: linear-gradient(90deg, rgba(16, 185, 129, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        /* Main title styling */
        .dashboard-title {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8 0%, #34d399 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
            letter-spacing: -0.5px;
        }

        .dashboard-subtitle {
            color: #94a3b8;
            font-size: 1.0rem;
            margin-bottom: 1.5rem;
        }

        /* Status Badge Classes */
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        .status-complete {
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }

        .status-incomplete {
            background-color: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .status-na {
            background-color: rgba(148, 163, 184, 0.15);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.4);
        }

        /* Ingestion Specific Badges */
        .badge-success {
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }

        .badge-partial {
            background-color: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.4);
        }

        .badge-malformed {
            background-color: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .badge-empty {
            background-color: rgba(148, 163, 184, 0.15);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.4);
        }

        .badge-error {
            background-color: rgba(220, 38, 38, 0.2);
            color: #f87171;
            border: 1px solid rgba(220, 38, 38, 0.5);
        }

        .badge-unsupported {
            background-color: rgba(99, 102, 241, 0.15);
            color: #818cf8;
            border: 1px solid rgba(99, 102, 241, 0.4);
        }

        /* Identity Confidence Badges */
        .badge-confirmed {
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }

        .badge-probable {
            background-color: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.4);
        }

        .badge-conflict {
            background-color: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .badge-unresolved {
            background-color: rgba(148, 163, 184, 0.15);
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.4);
        }

        /* Metric card container */
        .metric-card {
            background: rgba(17, 24, 39, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        .metric-card-title {
            color: #94a3b8;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .metric-card-value {
            color: #f8fafc;
            font-size: 1.8rem;
            font-weight: 700;
            margin-top: 4px;
        }

        /* Empty state container */
        .empty-state-box {
            text-align: center;
            padding: 40px 20px;
            background: rgba(15, 23, 42, 0.5);
            border: 2px dashed rgba(148, 163, 184, 0.25);
            border-radius: 12px;
            margin: 20px 0;
        }

        .empty-state-icon {
            font-size: 2.8rem;
            margin-bottom: 12px;
            opacity: 0.8;
        }

        .empty-state-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #e2e8f0;
            margin-bottom: 8px;
        }

        .empty-state-desc {
            color: #94a3b8;
            font-size: 0.95rem;
            max-width: 520px;
            margin: 0 auto 18px auto;
            line-height: 1.5;
        }

        /* Informational Card */
        .info-card {
            background: rgba(30, 41, 59, 0.4);
            border-left: 4px solid #38bdf8;
            padding: 14px 18px;
            border-radius: 6px;
            margin: 12px 0;
            color: #cbd5e1;
            font-size: 0.92rem;
        }

        .warning-card {
            background: rgba(45, 30, 15, 0.4);
            border-left: 4px solid #f59e0b;
            padding: 14px 18px;
            border-radius: 6px;
            margin: 12px 0;
            color: #fde68a;
            font-size: 0.92rem;
        }

        .safety-card {
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-left: 4px solid #10b981;
            padding: 14px 18px;
            border-radius: 6px;
            margin: 12px 0;
            color: #a7f3d0;
            font-size: 0.92rem;
        }

        .badge-dep-1 {
            background-color: rgba(6, 182, 212, 0.15);
            color: #06b6d4;
            border: 1px solid rgba(6, 182, 212, 0.4);
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.75rem;
        }

        .badge-dep-2 {
            background-color: rgba(168, 85, 247, 0.15);
            color: #c084fc;
            border: 1px solid rgba(168, 85, 247, 0.4);
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.75rem;
        }

        .badge-dep-3 {
            background-color: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.4);
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.75rem;
        }

        /* Sidebar enhancement */
        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

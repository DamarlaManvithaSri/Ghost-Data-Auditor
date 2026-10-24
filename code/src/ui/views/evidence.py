"""
Evidence Files View for Ghost Data Auditor.
Provides resilient multi-format file ingestion, status inspection, extracted records preview,
source provenance tracing, and testing tools for malformed/corrupted files.
"""

import os
import streamlit as st
import pandas as pd

from src.ingestion import EvidenceManager, IngestionStatus, IngestedFile

# Formats supported by the ingestion pipeline
SUPPORTED_EXTENSIONS = [
    "csv", "txt", "json", "jsonl", "log", "md", "pdf", "png", "jpg", "jpeg", "webp", "sql"
]


def get_evidence_manager() -> EvidenceManager:
    """
    Retrieves or initializes the session-scoped EvidenceManager singleton.
    """
    if "evidence_manager" not in st.session_state:
        st.session_state["evidence_manager"] = EvidenceManager()
    return st.session_state["evidence_manager"]


def get_status_badge_html(status: IngestionStatus) -> str:
    """
    Returns styled HTML badge for an IngestionStatus.
    """
    badge_map = {
        IngestionStatus.SUCCESS: ("badge-success", "SUCCESS"),
        IngestionStatus.PARTIAL_SUCCESS: ("badge-partial", "PARTIAL SUCCESS"),
        IngestionStatus.MALFORMED: ("badge-malformed", "MALFORMED"),
        IngestionStatus.EMPTY: ("badge-empty", "EMPTY"),
        IngestionStatus.UNSUPPORTED: ("badge-unsupported", "UNSUPPORTED"),
        IngestionStatus.ERROR: ("badge-error", "ERROR")
    }
    css_class, label = badge_map.get(status, ("badge-unsupported", status.value))
    return f'<span class="status-badge {css_class}">{label}</span>'


def render_evidence_view():
    """
    Renders the Evidence Files ingestion view.
    """
    manager = get_evidence_manager()

    st.markdown('<div class="dashboard-title">📁 Evidence Ingestion & Normalization</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Multi-format evidence parser with strict provenance tracking, schema diagnostics, and error tolerance.</div>',
        unsafe_allow_html=True
    )

    # Informational notice on local privacy guarantee
    st.markdown(
        """
        <div class="info-card">
            🔒 <strong>100% Local Ingestion:</strong> All parsing (Pandas, PDF extraction, JSON parsing, Image decoding) runs strictly on your local machine. No evidence or customer data is transmitted to external AI APIs.
        </div>
        """,
        unsafe_allow_html=True
    )

    # Ingestion Actions: Upload vs Load Dataset
    col_upload, col_dataset = st.columns([1.2, 1])

    with col_upload:
        st.markdown("#### 📤 Upload Evidence Files")
        uploaded_files = st.file_uploader(
            "Choose files to ingest (Multiple files supported):",
            type=SUPPORTED_EXTENSIONS,
            accept_multiple_files=True,
            help="Select one or more evidence files from your machine."
        )

        if uploaded_files:
            newly_added = 0
            for uploaded in uploaded_files:
                # Check if file is already ingested to prevent duplicate re-ingestion
                existing = manager.get_file(uploaded.name)
                if not existing:
                    bytes_data = uploaded.read()
                    manager.ingest_bytes(uploaded.name, bytes_data)
                    newly_added += 1

            if newly_added > 0:
                st.success(f"✓ Ingested {newly_added} new file(s) into active catalog.")

    with col_dataset:
        st.markdown("#### 📦 Load Local Challenge Dataset")
        st.write("Scan and ingest evidence files from the repository's `dataset/` directory.")

        dataset_path = os.path.join(os.getcwd(), "dataset")
        dataset_exists = os.path.exists(dataset_path)

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if dataset_exists:
                if st.button("📂 Ingest Local Dataset", type="primary"):
                    with st.spinner("Ingesting challenge dataset..."):
                        ingested_count = 0
                        # Traverse dataset folder and ingest all supported files
                        for root, _, files in os.walk(dataset_path):
                            for file in files:
                                ext = file.split(".")[-1].lower() if "." in file else ""
                                if ext in SUPPORTED_EXTENSIONS:
                                    full_path = os.path.join(root, file)
                                    manager.ingest_path(full_path)
                                    ingested_count += 1
                        st.success(f"✓ Ingested {ingested_count} evidence files from `{dataset_path}`.")
                        st.rerun()
            else:
                st.warning("`dataset/` folder was not found.")

        with c_btn2:
            if st.button("🗑️ Clear All Evidence"):
                manager.clear()
                st.rerun()

    # Interactive Test Lab & Malformed File Generator
    with st.expander("🧪 Test Lab: Try Malformed, Empty, and Corrupted Files"):
        st.markdown(
            """
            As required by the specification, the ingestion layer gracefully handles malformed files,
            empty files, corrupted data, and missing fields without crashing. You can inject test files below to observe how each parser responds:
            """
        )
        t_col1, t_col2, t_col3, t_col4 = st.columns(4)

        with t_col1:
            if st.button("Inject Corrupted CSV"):
                corrupted_csv = b"col1,col2\nval1,val2,extra_column_error\nval3"
                manager.ingest_bytes("test_corrupted_columns.csv", corrupted_csv)
                st.rerun()

        with t_col2:
            if st.button("Inject Invalid JSON"):
                broken_json = b"{'key': unquoted_value_bad_syntax, }"
                manager.ingest_bytes("test_broken_syntax.json", broken_json)
                st.rerun()

        with t_col3:
            if st.button("Inject Empty File (0 bytes)"):
                manager.ingest_bytes("test_empty_zero_bytes.log", b"")
                st.rerun()

        with t_col4:
            if st.button("Inject Duplicate File"):
                sample_bytes = b"user_id,email\nuser_99,alice@example.com\n"
                manager.ingest_bytes("original_identity.csv", sample_bytes)
                manager.ingest_bytes("duplicate_copy.csv", sample_bytes)
                st.rerun()

    st.divider()

    # Summary Metrics
    all_files = manager.get_all_files()
    summary = manager.get_summary()

    if not all_files:
        st.markdown(
            """
            <div class="empty-state-box">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-title">No Evidence Files Ingested Yet</div>
                <div class="empty-state-desc">
                    Upload your evidence files above or click <strong>"Ingest Local Dataset"</strong> 
                    to load databases, logs, PDFs, and records from the challenge directory.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    # Metrics Row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Total Ingested Files", summary["total_files"])
    with m_col2:
        st.metric("Extracted Records", summary["total_records"])
    with m_col3:
        st.metric("Total Size", f"{summary['total_size_mb']:.2f} MB")
    with m_col4:
        attention = (
            summary["status_counts"]["MALFORMED"] +
            summary["status_counts"]["PARTIAL_SUCCESS"] +
            summary["status_counts"]["ERROR"]
        )
        st.metric("Needs Review (Partial/Malformed)", attention)

    # Ingestion Status Distribution
    st.markdown("##### Ingestion Status Breakdown")
    stat_cols = st.columns(6)
    stat_items = [
        (IngestionStatus.SUCCESS, "SUCCESS"),
        (IngestionStatus.PARTIAL_SUCCESS, "PARTIAL SUCCESS"),
        (IngestionStatus.MALFORMED, "MALFORMED"),
        (IngestionStatus.EMPTY, "EMPTY"),
        (IngestionStatus.UNSUPPORTED, "UNSUPPORTED"),
        (IngestionStatus.ERROR, "ERROR")
    ]
    for idx, (st_enum, label) in enumerate(stat_items):
        cnt = summary["status_counts"].get(st_enum.value, 0)
        with stat_cols[idx]:
            st.markdown(
                f"""
                <div style="background: rgba(17, 24, 39, 0.5); padding: 8px 12px; border-radius: 6px; text-align: center; border: 1px solid rgba(255,255,255,0.06);">
                    <div style="font-size: 0.75rem; color: #94a3b8;">{label}</div>
                    <div style="font-size: 1.2rem; font-weight: 700; color: #f8fafc;">{cnt}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Search Bar for Records
    st.markdown("#### 🔍 Search Extracted Records Across All Files")
    search_query = st.text_input(
        "Search by customer email, user ID, keyword, or phrase:",
        placeholder="e.g. user_18 or ingrid.dahl@outlook.com or ORD-20261260",
        help="Searches through normalized records in all ingested databases, PDFs, logs, and CSVs."
    )

    if search_query:
        matches = manager.search_records(search_query)
        st.caption(f"Found {len(matches)} matching record(s) across all evidence files:")
        if matches:
            results_data = [
                {
                    "Source Origin": m.source_ref.to_display_string(),
                    "Record Type": m.record_type,
                    "Matched Text Snippet": m.raw_text[:120] + ("..." if len(m.raw_text) > 120 else "")
                }
                for m in matches[:50]
            ]
            st.dataframe(pd.DataFrame(results_data), use_container_width=True, hide_index=True)
            if len(matches) > 50:
                st.info(f"Showing first 50 of {len(matches)} matches.")
        else:
            st.warning(f"No records matching '{search_query}' were found in the ingested evidence.")

    st.divider()

    # Evidence Manifest Table
    st.markdown("### 📑 Evidence Manifest & File Diagnostics")
    
    # Filter by status
    status_filter = st.selectbox(
        "Filter by Ingestion Status:",
        options=["All Statuses"] + [s.value for s in IngestionStatus],
        index=0
    )

    filtered_files = all_files
    if status_filter != "All Statuses":
        filtered_files = [f for f in all_files if f.status.value == status_filter]

    manifest_rows = []
    for f in filtered_files:
        manifest_rows.append({
            "File Name": f.file_name,
            "Format": f.detected_format,
            "Status": f.status.value,
            "Records": f.record_count,
            "Size (KB)": round(f.raw_evidence.file_size_bytes / 1024, 1),
            "Status Summary": f.status_message
        })

    st.dataframe(pd.DataFrame(manifest_rows), use_container_width=True, hide_index=True)

    st.divider()

    # Deep File Inspector
    st.markdown("### 🔬 File Inspector: Content, Schema & Provenance")
    
    selected_name = st.selectbox(
        "Select a file to inspect in depth:",
        options=[f.file_name for f in all_files]
    )

    selected_file = manager.get_file(selected_name)
    if selected_file:
        render_file_inspector(selected_file)


def render_file_inspector(file_obj: IngestedFile):
    """
    Renders detailed inspection tabs for a single ingested file.
    Separates raw evidence, extracted text, and normalized records.
    """
    # Top File Status Header
    c_hdr1, c_hdr2 = st.columns([3, 1])
    with c_hdr1:
        st.markdown(f"#### 📄 `{file_obj.file_name}`")
        st.caption(f"Detected Format: **{file_obj.detected_format}** • {file_obj.status_message}")
    with c_hdr2:
        st.markdown(
            f"<div style='text-align: right; margin-top: 10px;'>{get_status_badge_html(file_obj.status)}</div>",
            unsafe_allow_html=True
        )

    # Any Warnings or Errors
    if file_obj.warnings:
        for w in file_obj.warnings:
            st.warning(w)

    if file_obj.errors:
        for e in file_obj.errors:
            st.error(f"Error during parsing: {e}")

    # Tabs for separation of concerns
    tab_preview, tab_records, tab_schema, tab_provenance = st.tabs([
        "👁️ Extracted Text Preview",
        f"📊 Normalized Records ({file_obj.record_count})",
        "⚙️ Schema & Diagnostics",
        "🛡️ Raw Evidence & Hash"
    ])

    with tab_preview:
        st.markdown("##### Extracted Content (Bounded Size Preview)")
        if file_obj.extracted_text:
            st.caption(f"Showing text preview (Characters: {len(file_obj.extracted_text)}):")
            st.code(
                file_obj.extracted_text,
                language="sql" if file_obj.detected_format == "SQL" else "json" if file_obj.detected_format in ["JSON", "JSONL"] else "text"
            )
        else:
            st.info("No text content could be extracted from this file.")

    with tab_records:
        st.markdown("##### Granular Extracted Records with Source References")
        if file_obj.records:
            st.write(
                "Each record maintains a strict provenance reference back to its originating row, line, or page number:"
            )

            records_table = []
            for r in file_obj.records[:100]: # Limit display table to first 100 for responsive UI
                records_table.append({
                    "Record ID": r.record_id,
                    "Source Reference": r.source_ref.to_display_string(),
                    "Type": r.record_type,
                    "Content Snippet": r.raw_text[:100] + ("..." if len(r.raw_text) > 100 else "")
                })

            st.dataframe(pd.DataFrame(records_table), use_container_width=True, hide_index=True)
            if file_obj.record_count > 100:
                st.info(f"Displaying first 100 of {file_obj.record_count} total records.")
        else:
            st.info("No individual records extracted for this file.")

    with tab_schema:
        st.markdown("##### Schema & Parser Diagnostics")
        
        # Display specific diagnostics based on format
        if file_obj.detected_format == "CSV":
            meta = file_obj.metadata
            c1, c2 = st.columns(2)
            c1.metric("Row Count", meta.get("row_count", 0))
            c2.metric("Column Count", meta.get("column_count", 0))

            if "data_types" in meta and meta["data_types"]:
                st.markdown("**Pandas Data Types:**")
                types_df = pd.DataFrame([
                    {"Column Name": col, "Data Type": dt}
                    for col, dt in meta["data_types"].items()
                ])
                st.dataframe(types_df, use_container_width=True, hide_index=True)

        elif file_obj.detected_format == "PDF":
            meta = file_obj.metadata
            p_col1, p_col2 = st.columns(2)
            p_col1.metric("Total Pages", meta.get("page_count", 0))
            p_col2.metric("Pages with Text", meta.get("pages_with_text", 0))

        elif file_obj.detected_format == "IMAGE":
            meta = file_obj.metadata
            i_col1, i_col2, i_col3 = st.columns(3)
            i_col1.metric("Resolution", meta.get("dimensions", "N/A"))
            i_col2.metric("Color Mode", meta.get("color_mode", "N/A"))
            i_col3.metric("OCR Status", "APPLIED" if meta.get("ocr_applied") else "UNAVAILABLE")

        elif file_obj.detected_format in ["LOG", "TEXT", "MD"]:
            meta = file_obj.metadata
            st.metric("Total Lines", meta.get("line_count", 0))
            st.caption(f"Detected Encoding: **{meta.get('encoding', 'utf-8')}**")

        # Full metadata dict viewer
        with st.expander("Detailed Metadata JSON"):
            st.json(file_obj.metadata)

    with tab_provenance:
        st.markdown("##### Provenance & Raw Evidence Integrity")
        raw = file_obj.raw_evidence
        st.markdown(
            f"""
            - **Original File Name:** `{raw.file_name}`
            - **File Size:** `{raw.file_size_bytes}` bytes ({raw.file_size_bytes / 1024:.2f} KB)
            - **Cryptographic Hash (SHA-256):**  
              `{raw.file_hash_sha256}`
            - **File Path on Disk:** `{raw.file_path or 'Uploaded in-memory'}`
            - **MIME / Media Type:** `{raw.mime_type or 'Unknown'}`
            """
        )
        if file_obj.metadata.get("is_duplicate"):
            st.warning(
                f"⚠️ Content Collision: This file has an identical SHA-256 hash to `{file_obj.metadata.get('duplicate_of')}`."
            )

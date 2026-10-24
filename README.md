# Ghost-Data-Auditor
An AI-powered cybersecurity & privacy compliance dashboard built for the **HackerRank Orchestrate** challenge (*Ghost Data Still Exists*).

Ghost Data Auditor investigates whether a customer's personal data was truly deleted across databases, replicas, logs, support attachments, search indexes, analytics exports, archives, and backups. It verifies adherence to mandatory retention rules, identifies account tombstones with leaked PII, and detects automated processes (such as ETL syncs or backup restores) that could recreate deleted data.

---

## 🧭 Navigation & Core Features

The application features a clean sidebar with the following sections:

1. **Dashboard:** High-level cybersecurity overview, key metrics, visual explanation of the 3 statuses, and the 5-phase audit lifecycle.
2. **Evidence Files:** Multi-format file uploader (supporting `.sql`, `.log`, `.txt`, `.json`, `.jsonl`, `.csv`, `.md`, `.pdf`, `.png`, `.jpg`) and one-click loader for the local challenge dataset. Includes safe, read-only content previewers and clear empty states.
3. **Run Audit:** Audit configuration panel (sample vs. full evaluation cases), temporal cutoff rule enforcement (`audit_at`), and execution monitor.
4. **Findings:** Detailed inspection of discovered customer identifiers (historical emails, account IDs, phone numbers, hashes) and evidence-backed findings (remaining records, exposed PII, active sync loops, and restore risks).
5. **Remediation:** Chronologically ordered mitigation steps (`DISABLE_DATA_FLOW`, `BLOCK_RESTORE`, `DELETE_RECORD`, `REDACT_RECORD`, `ANONYMIZE_RECORD`) and subsequent verification checks.
6. **Evaluation:** Benchmark predictions against the 32 sample ground-truth answers in `dataset/sample_output.csv`, review scoring criteria, and inspect required evaluation reports.
7. **Export:** Pre-submission validation checklist for `output.csv` (518 cases) and one-command packaging for `code.zip`.

---

## 📋 The Three Audit Statuses

Every case is evaluated into one of three standardized verdicts:

- 🟢 **`COMPLETE`**: All personal data is verified as completely deleted, redacted, or anonymized in accordance with retention rules. No active sync or backup restore paths can recreate the data. Verification proofs are produced.
- 🔴 **`INCOMPLETE`**: Ghost data persists. Personal records or direct identifiers were found lingering in secondary systems, or active processes pose recreation risks. An ordered remediation plan is produced.
- ⚪ **`NOT_APPLICABLE`**: The customer inquiry or message did not authorize data erasure (e.g., general support question, address change request, or order inquiry). No deletion or remediation is allowed.

---

## 📁 Project Structure

```text
├── app.py                      # Main Streamlit web application entry point
├── requirements.txt            # Python dependencies (Streamlit, Pandas, etc.)
├── README.md                   # Beginner-friendly setup and usage guide
├── log.txt                     # Challenge activity log adhering to AGENTS.md
├── src/                        # Cleanly organized application source code
│   ├── ui/                     # Interface presentation layer
│   │   ├── styles.py           # Custom cybersecurity dark theme CSS
│   │   ├── sidebar.py          # Sidebar navigation & status definitions
│   │   └── views/              # Modular page views
│   │       ├── dashboard.py    # Primary dashboard & getting started guide
│   │       ├── evidence.py     # File uploader & dataset manager
│   │       ├── audit.py        # Audit configuration & monitor
│   │       ├── findings.py     # Discovered identifiers & risk findings
│   │       ├── remediation.py  # Ordered remediation & verification steps
│   │       ├── evaluation.py   # Benchmarks & evaluation reports
│   │       └── export.py       # Submission packaging & validator
│   └── audit_engine/           # Future audit logic (separated from UI)
│       ├── identity.py         # Customer identity & lineage resolution
│       ├── policy.py           # Deletion policy & retention rule matcher
│       └── auditor.py          # Single-case audit investigator
├── dataset/                    # Official challenge dataset & evidence files
│   ├── deletion_requests.csv   # 518 evaluation cases
│   ├── sample_deletion_requests.csv # 32 sample cases
│   ├── sample_output.csv       # Reference ground-truth answers
│   ├── deletion_rules.csv      # Mandatory treatment rules per category
│   └── evidence/               # Databases (.sql), logs, attachments
└── code/                       # Challenge starter entry points & reports
    ├── main.py                 # CLI entry point
    └── evaluation/             # Evaluation & usage markdown reports
```

---

## 🚀 Beginner's Guide: Launching on Windows

Follow these simple steps in order. No advanced programming knowledge is required!

### Step 1: Open Terminal in the Project Folder
1. Open PowerShell or Command Prompt.
2. Ensure you are in the project folder:
   ```powershell
   cd "c:\Users\manvi\OneDrive\Documents\Amrita Vishwa vidya peetam\Hackerrank"
   ```

### Step 2: Install Dependencies
Run this command to make sure Streamlit and Pandas are installed:
```powershell
python -m pip install -r requirements.txt
```
*(If dependencies are already installed, pip will quickly confirm they are satisfied).*

### Step 3: Launch the Streamlit Dashboard
Run:
```powershell
streamlit run app.py
```

### Step 4: What You Should See in Your Browser
- Your default web browser will automatically open a new tab at:
  ```text
  http://localhost:8501
  ```
- You will be greeted by the **Ghost Data Auditor** cybersecurity dashboard with:
  - Top header: **🛡️ Ghost Data Auditor**
  - Metrics cards (Audit Engine Status: READY, Evidence Files Loaded: 0)
  - Color-coded status badges for **COMPLETE**, **INCOMPLETE**, and **NOT_APPLICABLE**
  - Interactive tabs for **Beginner's Quick Start**, **The 5-Phase Audit Lifecycle**, and **How Ghost Data Appears**
  - A friendly empty state box prompting you to load evidence files from the sidebar.

---

## 🔒 Security & Privacy Guarantees

- **100% Local Execution:** All analysis runs on your local machine. No customer data or credentials are ever transmitted over the network.
- **Read-Only Evidence Mode:** The auditor never deletes, alters, or mutates any original database or evidence files.
- **Honest Metrics:** No fake or hardcoded answers are presented in the dashboard.

---

## 📦 Challenge Submission Link

Official HackerRank Contest Submission Portal:  
https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

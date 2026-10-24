"""
Deletion Verification & Remediation Reporting Engine.
Produces comprehensive, policy-grounded verification reports and audit trails.
Strictly distinguishes between proposed remediation recommendations and verified outcomes.
"""

from typing import Dict, List, Any, Optional
import json
from src.audit_engine.models import AuditPhase, DeletionVerdict
from .models import RemediationAction, RemediationPlan


class DeletionVerificationReport:
    """
    Generates human-readable and structured deletion verification reports
    based on audit findings, policy rules, and dependency-ordered remediation plans.
    """

    @staticmethod
    def generate_markdown_report(plan: RemediationPlan) -> str:
        """
        Builds a comprehensive, publication-ready Markdown audit and remediation report.
        """
        lines = []

        # -------------------------------------------------------------
        # Header & Case Metadata
        # -------------------------------------------------------------
        lines.append(f"# 🛡️ Deletion Audit & Remediation Report: Case `{plan.case_id}`")
        lines.append("")
        lines.append(f"- **Customer Email:** `{plan.customer_email or 'N/A'}`")
        lines.append(f"- **Resolved User ID:** `{plan.user_id or 'Unlinked / Unknown'}`")
        lines.append(f"- **Audit Status:** **`{plan.deletion_status.value}`**")
        lines.append(f"- **Generated Actions:** `{len(plan.actions)} proposed remediation steps`")
        lines.append("")

        # -------------------------------------------------------------
        # Safety & Non-Destructive Operation Callout
        # -------------------------------------------------------------
        lines.append("> [!IMPORTANT]")
        lines.append(f"> **Safety Guarantee:** {plan.safety_guarantee}")
        lines.append("> The auditor runs in **Read-Only Inspection Mode**. It proposes safe, dependency-ordered actions for engineering execution but **never** performs automatic external deletions or system alterations.")
        lines.append("")

        # -------------------------------------------------------------
        # Section A: Case Status & Verdict Executive Summary
        # -------------------------------------------------------------
        lines.append("## 1. Executive Summary")
        lines.append("")

        if plan.deletion_status == DeletionVerdict.NOT_APPLICABLE:
            lines.append("### ℹ️ Verdict: NOT_APPLICABLE (No Deletion Authorized)")
            lines.append("The subject's request does not authorize account or personal data deletion (e.g., invoice copy request, data export, or marketing preference update).")
            lines.append("**Policy Guardrail:** The system strictly avoids suggesting unnecessary or unauthorized data destruction.")
            lines.append("")
            return "\n".join(lines)

        elif plan.deletion_status == DeletionVerdict.COMPLETE:
            lines.append("### ✅ Verdict: COMPLETE (Verified Compliant)")
            lines.append("All personal data copies across primary stores, downstream replicas, and exports have been verified absent or compliant with policy. No active synchronization pipelines or restoration risks were detected.")
            lines.append("")
            lines.append("### Evidence-Backed Verification Proving Complete State:")
            lines.append("| Step # | System | Resource | Verification Check | Verified State | Supporting Evidence |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for step in plan.ordered_steps:
                lines.append(
                    f"| {step.step_no} | `{step.system_id}` | `{step.resource_id}` | `{step.operation}` | **`{step.state}`** | `{step.evidence_id}` |"
                )
            lines.append("")
            lines.append("All listed checks are grounded in participant-visible evidence captured at or before the `audit_at` cutoff.")
            return "\n".join(lines)

        else:
            # INCOMPLETE
            lines.append("### ⚠️ Verdict: INCOMPLETE (Action Required)")
            lines.append(
                "Personal data remains in data stores, or active data recreation risks (sync pipelines / backup restore paths) exist. "
                "Remediation is required to achieve compliance."
            )
            lines.append("")

        # -------------------------------------------------------------
        # Section B: Grounded Findings (Evidence-Backed)
        # -------------------------------------------------------------
        findings = [s for s in plan.ordered_steps if s.phase == AuditPhase.FINDING.value]
        lines.append("## 2. Evidence-Backed Findings")
        lines.append("The following compliance failures and ghost data risks were identified in participant-visible evidence:")
        lines.append("")
        if findings:
            lines.append("| Step # | System | Resource | Finding Type | Detected State | Evidence ID | Rationale |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for f in findings:
                # Find matching reason from audit trail
                trail_item = next((t for t in plan.audit_trail if t.get("step_no") == f.step_no), {})
                justification = trail_item.get("justification", f"Proven by evidence {f.evidence_id}")
                lines.append(
                    f"| {f.step_no} | `{f.system_id}` | `{f.resource_id}` | `{f.operation}` | **`{f.state}`** | `{f.evidence_id}` | {justification} |"
                )
            lines.append("")
        else:
            lines.append("*No individual record findings logged, but unresolved compliance factors prevent claiming COMPLETE.*")
            lines.append("")

        # -------------------------------------------------------------
        # Section C: Ordered Remediation Actions (Proposed Future Work)
        # -------------------------------------------------------------
        lines.append("## 3. Ordered Remediation Blueprint (Recommendations)")
        lines.append(
            "Actions must be executed in strict **dependency order** to prevent race conditions or automatic data recreation:"
        )
        lines.append("1. **Order 1 (Process Neutralization):** Disable active ETL sync flows and block backup restore paths.")
        lines.append("2. **Order 2 (Downstream Stores):** Purge or anonymize downstream caches, search indexes, and analytical exports.")
        lines.append("3. **Order 3 (Primary Stores & Tombstones):** Delete primary user records or redact direct PII from account tombstones while preserving internal IDs.")
        lines.append("")

        if plan.actions:
            lines.append("| Step # | Order | Target System | Target Resource | Remediation Operation | Target State | Policy Rule | Dependencies | Justification |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            
            # Find remediation steps
            rem_steps = [s for s in plan.ordered_steps if s.phase == AuditPhase.REMEDIATION.value]
            for s in rem_steps:
                action = next((a for a in plan.actions if a.resource_id == s.resource_id), None)
                order_num = action.dependency_order if action else 3
                rule_id = action.policy_rule_id if action else "POLICY_DEFAULT"
                deps = ", ".join(action.dependencies) if action and action.dependencies else "None (Prerequisite)"
                reason = action.reason if action else "Remediation required by policy."
                lines.append(
                    f"| {s.step_no} | Level {order_num} | `{s.system_id}` | `{s.resource_id}` | `{s.operation}` | **`{s.state}`** | `{rule_id}` | {deps} | {reason} |"
                )
            lines.append("")
        else:
            lines.append("*No remediation actions compiled.*")
            lines.append("")

        # -------------------------------------------------------------
        # Section D: Post-Remediation Verification Matrix
        # -------------------------------------------------------------
        lines.append("## 4. Post-Remediation Verification Checks")
        lines.append(
            "Once engineering completes the recommended remediation steps, the following verification checks must be run to confirm compliance:"
        )
        lines.append("")
        ver_steps = [s for s in plan.ordered_steps if s.phase == AuditPhase.VERIFICATION.value]
        if ver_steps:
            lines.append("| Step # | System | Resource | Verification Check | Required State | Verification Criteria |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for v in ver_steps:
                action = next((a for a in plan.actions if a.resource_id == v.resource_id), None)
                rule_id = action.policy_rule_id if action else "N/A"
                if v.operation == "VERIFY_DATA_FLOW_DISABLED":
                    crit = "Query pipeline orchestrator to confirm sync job is inactive/disabled."
                elif v.operation == "VERIFY_RESTORE_BLOCKED":
                    crit = "Inspect backup restore access policy to confirm snapshot restore is prohibited."
                elif v.operation == "VERIFY_RECORD_ABSENT":
                    crit = "Execute primary key readback lookup returning 404 / 0 rows."
                elif v.operation == "VERIFY_RECORD_REDACTED":
                    crit = "Verify direct identifiers (email, name, phone, hash) are NULL while preserving user_id."
                elif v.operation == "VERIFY_RECORD_ANONYMIZED":
                    crit = "Confirm record is irreversibly unlinked from personal identifiers."
                elif v.operation == "VERIFY_RECORD_PRESENT":
                    crit = "Verify policy-required retained record remains intact."
                else:
                    crit = f"Confirm resource {v.resource_id} is in {v.state} state."

                lines.append(
                    f"| {v.step_no} | `{v.system_id}` | `{v.resource_id}` | `{v.operation}` | **`{v.state}`** | {crit} |"
                )
            lines.append("")
        else:
            lines.append("*No post-remediation verification steps registered.*")
            lines.append("")

        # -------------------------------------------------------------
        # Section E: Policy Guardrails & Retention Rules
        # -------------------------------------------------------------
        lines.append("## 5. Policy Guardrails Enforced")
        lines.append("- **Retention Protection:** Records governed by mandatory retention policies (e.g. `SECURITY_AUDIT_LOG`, `FINANCIAL_LEDGER`, `LEGAL_HOLD`) are **never** scheduled for deletion.")
        lines.append("- **Account Tombstone Treatment:** In accordance with policy, account tombstones preserve the stable internal reference while stripping direct PII (name, email, phone, email hash).")
        lines.append("- **Process Precedence:** Sync processes and restore routes are always scheduled for deactivation before modifying dependent storage tiers.")
        lines.append("")

        # -------------------------------------------------------------
        # Section F: Additional Investigations & Gaps
        # -------------------------------------------------------------
        if plan.additional_investigations:
            lines.append("## 6. Additional Investigation Required")
            lines.append("The following data gaps, ambiguous evidence, or uninspected files require further investigation:")
            for item in plan.additional_investigations:
                lines.append(f"- ⚠️ {item}")
            lines.append("")

        # -------------------------------------------------------------
        # Section G: Traceable Audit Trail
        # -------------------------------------------------------------
        lines.append("## 7. Complete Traceable Audit Trail")
        lines.append("| Step # | Phase | System | Resource | Operation | State | Evidence ID | Policy Rule | Execution Status |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for item in plan.audit_trail:
            lines.append(
                f"| {item.get('step_no', '-')} | `{item.get('phase', '-')}` | `{item.get('system_id', '-')}` | `{item.get('resource_id', '-')}` | "
                f"`{item.get('operation', '-')}` | `{item.get('target_state', item.get('state', '-'))}` | `{item.get('evidence_id', '-')}` | "
                f"`{item.get('policy_rule', '-')}` | **`{item.get('status', 'PENDING')}`** |"
            )
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def generate_summary_dict(plan: RemediationPlan) -> Dict[str, Any]:
        """
        Produces a structured JSON-serializable dictionary representation of the report.
        """
        return {
            "case_id": plan.case_id,
            "deletion_status": plan.deletion_status.value,
            "customer_email": plan.customer_email,
            "user_id": plan.user_id,
            "safety_guarantee": plan.safety_guarantee,
            "total_actions": len(plan.actions),
            "total_steps": len(plan.ordered_steps),
            "findings_count": len([s for s in plan.ordered_steps if s.phase == AuditPhase.FINDING.value]),
            "remediations_count": len([s for s in plan.ordered_steps if s.phase == AuditPhase.REMEDIATION.value]),
            "verifications_count": len([s for s in plan.ordered_steps if s.phase == AuditPhase.VERIFICATION.value]),
            "actions": [
                {
                    "action_id": a.action_id,
                    "system_id": a.system_id,
                    "resource_id": a.resource_id,
                    "operation": a.operation,
                    "target_state": a.target_state,
                    "policy_rule_id": a.policy_rule_id,
                    "policy_category": a.policy_category,
                    "dependency_order": a.dependency_order,
                    "dependencies": a.dependencies,
                    "reason": a.reason,
                    "verification_operation": a.verification_operation,
                    "is_executed": a.is_executed
                }
                for a in plan.actions
            ],
            "ordered_steps": [s.to_dict() for s in plan.ordered_steps],
            "additional_investigations": plan.additional_investigations,
            "audit_trail": plan.audit_trail
        }

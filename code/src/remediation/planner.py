"""
Remediation Planner for Ghost Data Auditor.
Synthesizes dependency-ordered remediation plans, pairs actions with verification checks,
enforces retention guardrails, and builds comprehensive audit trails.
"""

from typing import Dict, List, Set, Any, Optional
from src.audit_engine.models import (
    AuditStep,
    AuditPhase,
    DeletionVerdict,
    CaseAuditResult
)
from src.policy import PolicyRegistry, DeletionRule
from src.identity import ResolvedIdentity
from .models import RemediationAction, RemediationPlan


class RemediationPlanner:
    """
    Constructs ordered, safe remediation plans grounded strictly in evidence and policy rules.
    Respects operational dependency order: process neutralization -> downstream stores -> primary records.
    """
    def __init__(self, policy_registry: Optional[PolicyRegistry] = None):
        self.policy = policy_registry or PolicyRegistry()

    def build_plan(
        self,
        case_id: str,
        audit_result: CaseAuditResult,
        identity: Optional[ResolvedIdentity] = None,
        unresolved_evidence: Optional[List[str]] = None
    ) -> RemediationPlan:
        """
        Builds a comprehensive RemediationPlan from an audit result.
        """
        plan = RemediationPlan(
            case_id=case_id,
            deletion_status=audit_result.deletion_status,
            customer_email=audit_result.email,
            user_id=audit_result.user_id,
            ordered_steps=[]
        )

        # -------------------------------------------------------------
        # Case 1: NOT_APPLICABLE (No Deletion Authorized)
        # -------------------------------------------------------------
        if audit_result.deletion_status == DeletionVerdict.NOT_APPLICABLE:
            plan.ordered_steps = []
            plan.additional_investigations = []
            plan.audit_trail.append({
                "phase": "EVALUATION",
                "summary": "Request does not authorize deletion. No destructive or remediation action recommended.",
                "policy_rule": "POLICY_GUARDRAIL_NO_DELETION",
                "status": "NOT_APPLICABLE",
                "justification": "Customer did not authorize account or data deletion; preserved existing records intact."
            })
            return plan

        # -------------------------------------------------------------
        # Case 2: COMPLETE (Already Verified Compliant)
        # -------------------------------------------------------------
        if audit_result.deletion_status == DeletionVerdict.COMPLETE:
            # For COMPLETE cases, steps must contain ONLY evidence-backed VERIFICATION steps
            plan.ordered_steps = audit_result.steps
            for step in audit_result.steps:
                plan.audit_trail.append({
                    "step_no": step.step_no,
                    "phase": step.phase,
                    "operation": step.operation,
                    "system_id": step.system_id,
                    "resource_id": step.resource_id,
                    "state": step.state,
                    "evidence_id": step.evidence_id,
                    "policy_rule": "VERIFIED_COMPLIANCE",
                    "status": "VERIFIED_COMPLIANT",
                    "justification": f"Verified {step.state} state in {step.system_id} using evidence {step.evidence_id}."
                })
            return plan

        # -------------------------------------------------------------
        # Case 3: INCOMPLETE (Grounded Remediation Planning)
        # -------------------------------------------------------------
        findings = [s for s in audit_result.steps if s.phase == AuditPhase.FINDING.value]
        existing_verifications = [
            s for s in audit_result.steps
            if s.phase == AuditPhase.VERIFICATION.value and s.evidence_id
        ]
        actions: List[RemediationAction] = []

        # Categorize findings into operational dependency buckets:
        # Bucket 1 (Priority 1): Active Data Flows & Restores (Must be disabled FIRST before data deletion)
        # Bucket 2 (Priority 2): Downstream Copies, Exports & Indexes (Remove before primary source)
        # Bucket 3 (Priority 3): Primary Stores & Account Tombstones (Final primary store state)

        bucket_processes = []
        bucket_downstream = []
        bucket_primary = []

        for finding in findings:
            res_id = finding.resource_id.lower()
            if finding.operation == "REPORT_ACTIVE_DATA_FLOW" or res_id.startswith("data_flow_"):
                bucket_processes.append((finding, 1))
            elif finding.operation == "REPORT_RESTORE_RISK" or res_id.startswith("backup_"):
                bucket_processes.append((finding, 1))
            elif any(res_id.startswith(p) for p in ["search_", "cache_", "export_", "marketing_", "analytics_", "telemetry_"]):
                bucket_downstream.append((finding, 2))
            else:
                bucket_primary.append((finding, 3))

        sorted_findings = bucket_processes + bucket_downstream + bucket_primary

        for finding, priority in sorted_findings:
            res_id = finding.resource_id
            sys_id = finding.system_id
            category = self.policy.match_resource_category(res_id, sys_id)
            rule = self.policy.get_rule_for_category(category)
            rule_id = rule.rule_id if rule else "POLICY_DEFAULT"
            required_action = rule.required_action if rule else "DELETE"

            # Determine safe remediation operation and paired verification
            if finding.operation == "REPORT_ACTIVE_DATA_FLOW":
                rem_op = "DISABLE_DATA_FLOW"
                target_st = "DISABLED"
                ver_op = "VERIFY_DATA_FLOW_DISABLED"
                ver_st = "DISABLED"
                reason = f"Active data sync process {res_id} must be disabled to prevent recreating deleted data."
            elif finding.operation == "REPORT_RESTORE_RISK":
                rem_op = "BLOCK_RESTORE"
                target_st = "BLOCKED"
                ver_op = "VERIFY_RESTORE_BLOCKED"
                ver_st = "BLOCKED"
                reason = f"Backup restore path {res_id} must be blocked to prevent bringing back deleted records."
            elif finding.operation == "REPORT_EXPOSED_PII":
                # Check category: if analytics -> ANONYMIZE; if tombstone/support -> REDACT
                if required_action == "ANONYMIZE" or "ANALYTICS" in category or "TELEMETRY" in category:
                    rem_op = "ANONYMIZE_RECORD"
                    target_st = "ANONYMIZED"
                    ver_op = "VERIFY_RECORD_ANONYMIZED"
                    ver_st = "ANONYMIZED"
                    reason = f"Record {res_id} must be anonymized to permanently decouple it from customer identity."
                else:
                    # Account Tombstone or Support Message -> REDACT direct identifiers while preserving structure/user_id
                    rem_op = "REDACT_RECORD"
                    target_st = "REDACTED"
                    ver_op = "VERIFY_RECORD_REDACTED"
                    ver_st = "REDACTED"
                    reason = f"Record {res_id} must be redacted to remove direct identifiers (name, email, phone, hash) under rule {rule_id}."
            else:
                # REPORT_REMAINING_RECORD
                # Guardrail: Check if policy strictly mandates RETAIN
                if required_action == "RETAIN":
                    # Absolute guardrail: never delete a policy-retained record!
                    # Do not generate a DELETE action for a retained record
                    continue

                if category == "ACCOUNT_TOMBSTONE" or required_action == "REDACT":
                    rem_op = "REDACT_RECORD"
                    target_st = "REDACTED"
                    ver_op = "VERIFY_RECORD_REDACTED"
                    ver_st = "REDACTED"
                    reason = f"Tombstone policy requires redacting identifying fields from {res_id} while preserving internal user_id."
                elif required_action == "ANONYMIZE":
                    rem_op = "ANONYMIZE_RECORD"
                    target_st = "ANONYMIZED"
                    ver_op = "VERIFY_RECORD_ANONYMIZED"
                    ver_st = "ANONYMIZED"
                    reason = f"Policy requires irreversibly unlinking {res_id} from personal identity."
                else:
                    rem_op = "DELETE_RECORD"
                    target_st = "ABSENT"
                    ver_op = "VERIFY_RECORD_ABSENT"
                    ver_st = "ABSENT"
                    reason = f"Lingering unauthorized record {res_id} in {sys_id} must be completely deleted."

            act_id = f"action_{len(actions) + 1}_{res_id}"

            # Explicit, safe dependency ordering
            if priority == 1:
                deps = []  # Root prerequisites (process deactivation must happen first)
            elif priority == 2:
                # Downstream stores depend on active process neutralization
                deps = [a.action_id for a in actions if a.dependency_order == 1]
            else:
                # Primary stores depend on process neutralization and downstream purges
                deps = [a.action_id for a in actions if a.dependency_order in (1, 2)]

            action_obj = RemediationAction(
                action_id=act_id,
                system_id=sys_id,
                resource_id=res_id,
                operation=rem_op,
                target_state=target_st,
                policy_rule_id=rule_id,
                policy_category=category,
                reason=reason,
                source_evidence_id=finding.evidence_id,
                dependency_order=priority,
                dependencies=deps,
                verification_operation=ver_op,
                verification_state=ver_st,
                is_executed=False # System never claims it executed external actions
            )
            actions.append(action_obj)

        plan.actions = actions

        # -------------------------------------------------------------
        # Assemble Ordered Steps: FINDING -> REMEDIATION -> VERIFICATION
        # -------------------------------------------------------------
        final_steps: List[AuditStep] = []

        # 1. Findings (citing participant evidence, organized by dependency)
        for finding, _ in sorted_findings:
            final_steps.append(AuditStep(
                step_no=0,
                phase=AuditPhase.FINDING.value,
                system_id=finding.system_id,
                resource_id=finding.resource_id,
                operation=finding.operation,
                state=finding.state,
                evidence_id=finding.evidence_id
            ))

        # 2. Proposed Remediation Steps (evidence_id: "" because these are future recommendations)
        for a in actions:
            final_steps.append(AuditStep(
                step_no=0,
                phase=AuditPhase.REMEDIATION.value,
                system_id=a.system_id,
                resource_id=a.resource_id,
                operation=a.operation,
                state=a.target_state,
                evidence_id=""
            ))

        # 3. Post-Remediation Verification Checks (evidence_id: "")
        for a in actions:
            final_steps.append(AuditStep(
                step_no=0,
                phase=AuditPhase.VERIFICATION.value,
                system_id=a.system_id,
                resource_id=a.resource_id,
                operation=a.verification_operation,
                state=a.verification_state,
                evidence_id=""
            ))

        # 4. Include any already-verified compliant checks (e.g. policy-retained records)
        for ev in existing_verifications:
            if not any(fs.resource_id == ev.resource_id and fs.phase == AuditPhase.VERIFICATION.value for fs in final_steps):
                final_steps.append(AuditStep(
                    step_no=0,
                    phase=AuditPhase.VERIFICATION.value,
                    system_id=ev.system_id,
                    resource_id=ev.resource_id,
                    operation=ev.operation,
                    state=ev.state,
                    evidence_id=ev.evidence_id
                ))

        # Number steps consecutively from 1
        for idx, step in enumerate(final_steps, start=1):
            step.step_no = idx

        plan.ordered_steps = final_steps

        # Build Audit Trail Links
        for s in final_steps:
            matched_act = next((a for a in actions if a.resource_id == s.resource_id), None)
            if s.phase == AuditPhase.FINDING.value:
                status_label = "EVIDENCED_FINDING"
                just = matched_act.reason if matched_act else f"Finding proven by evidence {s.evidence_id}."
            elif s.phase == AuditPhase.REMEDIATION.value:
                status_label = "RECOMMENDED (Pending Execution)"
                just = matched_act.reason if matched_act else "Action required to achieve compliance."
            else:
                if s.evidence_id:
                    status_label = "VERIFIED_COMPLIANT"
                    just = f"Verified {s.state} state in {s.system_id} using evidence {s.evidence_id}."
                else:
                    status_label = "FUTURE_VERIFICATION (Post-Execution Check)"
                    just = f"Must confirm {s.resource_id} is {s.state} after remediation."

            plan.audit_trail.append({
                "step_no": s.step_no,
                "phase": s.phase,
                "operation": s.operation,
                "system_id": s.system_id,
                "resource_id": s.resource_id,
                "target_state": s.state,
                "evidence_id": s.evidence_id or "(Future Action / Check)",
                "policy_rule": matched_act.policy_rule_id if matched_act else "N/A",
                "status": status_label,
                "justification": just
            })

        # Check for unreadable / unresolved evidence
        if unresolved_evidence:
            plan.additional_investigations.extend(unresolved_evidence)
        if not findings and audit_result.checks_failed:
            for failure in audit_result.checks_failed:
                plan.additional_investigations.append(f"Unresolved compliance factor: {failure}")

        return plan

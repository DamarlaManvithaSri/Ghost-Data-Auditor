"""
Unit tests for Remediation Planner and Deletion Verification Reporting.
Tests:
1. Active sync process (dependency order 1, process deactivation before record deletion).
2. Retained transaction record (guardrail: never destroy records required to be retained).
3. Historical email in an export (downstream purge grounded in identity lineage).
4. Already-completed deletion (COMPLETE status with evidence-backed verification checks only).
5. Person who never requested deletion (NOT_APPLICABLE status with empty steps and zero actions).
"""

import unittest
import pandas as pd
from src.audit_engine.models import (
    AuditStep,
    AuditPhase,
    DeletionVerdict,
    CaseAuditResult
)
from src.policy import PolicyRegistry, DeletionRule
from src.identity import ResolvedIdentity, IdentityLink, LinkConfidence, IdentifierType
from src.remediation import (
    RemediationPlanner,
    RemediationAction,
    RemediationPlan,
    DeletionVerificationReport
)


class TestRemediationPlanner(unittest.TestCase):
    def setUp(self):
        # Fictional deletion rules
        self.rules_df = pd.DataFrame([
            {"rule_id": "rule_01", "data_category": "USER_PROFILE", "required_action": "DELETE", "condition": "Always"},
            {"rule_id": "rule_05", "data_category": "ACCOUNT_TOMBSTONE", "required_action": "REDACT", "condition": "Preserve user_id only"},
            {"rule_id": "rule_10", "data_category": "FINANCIAL_LEDGER", "required_action": "RETAIN", "condition": "Tax compliance period"},
            {"rule_id": "rule_12", "data_category": "SECURITY_AUDIT_LOG", "required_action": "RETAIN", "condition": "Security audit window"},
            {"rule_id": "rule_15", "data_category": "ACTIVE_DATA_FLOW", "required_action": "DELETE", "condition": "Active sync process"},
            {"rule_id": "rule_18", "data_category": "MARKETING_OPT_OUT", "required_action": "DELETE", "condition": "Downstream marketing export"},
            {"rule_id": "rule_20", "data_category": "ANALYTICS_PROFILE", "required_action": "ANONYMIZE", "condition": "Aggregated analytics"}
        ])
        self.policy = PolicyRegistry(rules_df=self.rules_df)
        self.planner = RemediationPlanner(policy_registry=self.policy)

    def test_active_sync_process(self):
        """
        Test 1: Active Sync Process
        Verifies that an active synchronization flow is categorized as Dependency Order 1
        (DISABLE_DATA_FLOW before data store deletion), paired with VERIFY_DATA_FLOW_DISABLED,
        and never claimed as executed automatically.
        """
        audit_res = CaseAuditResult(
            case_id="case_sync_01",
            deletion_status=DeletionVerdict.INCOMPLETE,
            email="alice.sync@mock.com",
            user_id="user_sync_01",
            steps=[
                AuditStep(
                    step_no=1,
                    phase=AuditPhase.FINDING.value,
                    system_id="pipeline_orchestrator",
                    resource_id="data_flow_4021",
                    operation="REPORT_ACTIVE_DATA_FLOW",
                    state="ACTIVE",
                    evidence_id="act_sync_ev_01"
                ),
                AuditStep(
                    step_no=2,
                    phase=AuditPhase.FINDING.value,
                    system_id="account_service",
                    resource_id="account_sync_01",
                    operation="REPORT_REMAINING_RECORD",
                    state="PRESENT",
                    evidence_id="db_replica_ev_02"
                )
            ]
        )

        plan = self.planner.build_plan(case_id="case_sync_01", audit_result=audit_res)

        self.assertEqual(plan.deletion_status, DeletionVerdict.INCOMPLETE)
        self.assertEqual(len(plan.actions), 2)

        # 1. Action 1 must be the sync process deactivation (Priority 1)
        sync_action = plan.actions[0]
        self.assertEqual(sync_action.resource_id, "data_flow_4021")
        self.assertEqual(sync_action.operation, "DISABLE_DATA_FLOW")
        self.assertEqual(sync_action.target_state, "DISABLED")
        self.assertEqual(sync_action.dependency_order, 1)
        self.assertEqual(sync_action.dependencies, []) # Root prerequisite
        self.assertEqual(sync_action.verification_operation, "VERIFY_DATA_FLOW_DISABLED")
        self.assertEqual(sync_action.verification_state, "DISABLED")
        self.assertFalse(sync_action.is_executed) # Safety check: not executed automatically

        # 2. Action 2 must be the primary account deletion (Priority 3), depending on sync deactivation
        account_action = plan.actions[1]
        self.assertEqual(account_action.resource_id, "account_sync_01")
        self.assertEqual(account_action.operation, "DELETE_RECORD")
        self.assertEqual(account_action.dependency_order, 3)
        self.assertIn(sync_action.action_id, account_action.dependencies)

        # 3. Steps must be consecutively numbered and ordered FINDING -> REMEDIATION -> VERIFICATION
        step_phases = [s.phase for s in plan.ordered_steps]
        self.assertEqual(
            step_phases,
            [
                AuditPhase.FINDING.value, AuditPhase.FINDING.value,
                AuditPhase.REMEDIATION.value, AuditPhase.REMEDIATION.value,
                AuditPhase.VERIFICATION.value, AuditPhase.VERIFICATION.value
            ]
        )
        self.assertEqual([s.step_no for s in plan.ordered_steps], [1, 2, 3, 4, 5, 6])

        # 4. Remediation and future verification steps must have evidence_id == ""
        rem_and_ver = [s for s in plan.ordered_steps if s.phase in [AuditPhase.REMEDIATION.value, AuditPhase.VERIFICATION.value]]
        for step in rem_and_ver:
            self.assertEqual(step.evidence_id, "")

    def test_retained_transaction_record(self):
        """
        Test 2: Retained Transaction Record
        Verifies policy guardrail: never recommend destroying records required to be retained.
        When a financial transaction is compliant, it is verified with VERIFY_RECORD_PRESENT.
        When it has excess PII, only REDACT is recommended, never DELETE.
        """
        # Case A: Compliant retained ledger record
        audit_res_compliant = CaseAuditResult(
            case_id="case_ledger_01",
            deletion_status=DeletionVerdict.COMPLETE,
            email="bob.ledger@mock.com",
            user_id="user_bob_02",
            steps=[
                AuditStep(
                    step_no=1,
                    phase=AuditPhase.VERIFICATION.value,
                    system_id="billing_service",
                    resource_id="financial_tx_9011",
                    operation="VERIFY_RECORD_PRESENT",
                    state="PRESENT",
                    evidence_id="ev_billing_log_01"
                )
            ]
        )
        plan_compliant = self.planner.build_plan("case_ledger_01", audit_res_compliant)
        self.assertEqual(plan_compliant.action_count, 0)
        self.assertEqual(len(plan_compliant.ordered_steps), 1)
        self.assertEqual(plan_compliant.ordered_steps[0].operation, "VERIFY_RECORD_PRESENT")
        self.assertEqual(plan_compliant.ordered_steps[0].state, "PRESENT")
        self.assertEqual(plan_compliant.ordered_steps[0].evidence_id, "ev_billing_log_01")

        # Case B: Incomplete case where financial record has exposed direct PII (name/email)
        audit_res_pii = CaseAuditResult(
            case_id="case_ledger_02",
            deletion_status=DeletionVerdict.INCOMPLETE,
            email="bob.ledger@mock.com",
            user_id="user_bob_02",
            steps=[
                AuditStep(
                    step_no=1,
                    phase=AuditPhase.FINDING.value,
                    system_id="billing_service",
                    resource_id="financial_tx_9011",
                    operation="REPORT_EXPOSED_PII",
                    state="PRESENT",
                    evidence_id="ev_billing_log_01"
                )
            ]
        )
        plan_pii = self.planner.build_plan("case_ledger_02", audit_res_pii)
        action = plan_pii.actions[0]

        # Guardrail: Must REDACT excess direct identifiers, NEVER DELETE the financial record!
        self.assertEqual(action.operation, "REDACT_RECORD")
        self.assertNotEqual(action.operation, "DELETE_RECORD")
        self.assertEqual(action.target_state, "REDACTED")
        self.assertEqual(action.verification_operation, "VERIFY_RECORD_REDACTED")

    def test_historical_email_in_export(self):
        """
        Test 3: Historical Email in an Export
        Verifies that a former email found in an analytical/marketing export file
        triggers a downstream remediation action (Dependency Order 2), paired with
        VERIFY_RECORD_ABSENT, and linked to former email lineage evidence.
        """
        audit_res = CaseAuditResult(
            case_id="case_export_hist",
            deletion_status=DeletionVerdict.INCOMPLETE,
            email="carol.new@mock.com",
            user_id="user_carol_03",
            steps=[
                AuditStep(
                    step_no=1,
                    phase=AuditPhase.FINDING.value,
                    system_id="marketing_service",
                    resource_id="export_marketing_2025_q1",
                    operation="REPORT_REMAINING_RECORD",
                    state="PRESENT",
                    evidence_id="ev_marketing_csv_09"
                )
            ]
        )

        plan = self.planner.build_plan("case_export_hist", audit_res)
        self.assertEqual(plan.deletion_status, DeletionVerdict.INCOMPLETE)
        self.assertEqual(len(plan.actions), 1)

        action = plan.actions[0]
        self.assertEqual(action.resource_id, "export_marketing_2025_q1")
        self.assertEqual(action.operation, "DELETE_RECORD")
        self.assertEqual(action.target_state, "ABSENT")
        self.assertEqual(action.dependency_order, 2) # Downstream store order
        self.assertEqual(action.verification_operation, "VERIFY_RECORD_ABSENT")

        # Verify audit trail links to evidence
        trail = plan.audit_trail
        finding_trail = next(t for t in trail if t["phase"] == AuditPhase.FINDING.value)
        self.assertEqual(finding_trail["evidence_id"], "ev_marketing_csv_09")

    def test_already_completed_deletion(self):
        """
        Test 4: Already-Completed Deletion
        Verifies that a case where deletion is verified compliant yields COMPLETE,
        generates 0 remediation actions, and contains ONLY evidence-backed verification steps.
        """
        audit_res = CaseAuditResult(
            case_id="case_comp_01",
            deletion_status=DeletionVerdict.COMPLETE,
            email="david.complete@mock.com",
            user_id="user_david_04",
            steps=[
                AuditStep(
                    step_no=1,
                    phase=AuditPhase.VERIFICATION.value,
                    system_id="account_service",
                    resource_id="account_004",
                    operation="VERIFY_RECORD_ABSENT",
                    state="ABSENT",
                    evidence_id="ev_readback_log_04"
                ),
                AuditStep(
                    step_no=2,
                    phase=AuditPhase.VERIFICATION.value,
                    system_id="security_service",
                    resource_id="security_audit_004",
                    operation="VERIFY_RECORD_PRESENT",
                    state="PRESENT",
                    evidence_id="ev_sec_audit_log_04"
                )
            ]
        )

        plan = self.planner.build_plan("case_comp_01", audit_res)

        self.assertEqual(plan.deletion_status, DeletionVerdict.COMPLETE)
        self.assertEqual(plan.action_count, 0)
        self.assertFalse(plan.requires_remediation)
        self.assertEqual(len(plan.ordered_steps), 2)
        self.assertTrue(all(s.phase == AuditPhase.VERIFICATION.value for s in plan.ordered_steps))
        self.assertTrue(all(len(s.evidence_id) > 0 for s in plan.ordered_steps))

        # Check report generation
        md_report = DeletionVerificationReport.generate_markdown_report(plan)
        self.assertIn("✅ Verdict: COMPLETE (Verified Compliant)", md_report)
        self.assertIn("ev_readback_log_04", md_report)
        self.assertIn("ev_sec_audit_log_04", md_report)

    def test_person_who_never_requested_deletion(self):
        """
        Test 5: Person Who Never Requested Deletion
        Verifies that a non-deletion request (e.g. data export or invoice copy)
        is classified as NOT_APPLICABLE, produces empty steps [], zero remediation actions,
        and avoids suggesting destructive actions.
        """
        audit_res = CaseAuditResult(
            case_id="case_na_01",
            deletion_status=DeletionVerdict.NOT_APPLICABLE,
            email="eve.export@mock.com",
            user_id="user_eve_05",
            steps=[],
            rationale="Customer requested invoice download without authorizing account or data deletion."
        )

        plan = self.planner.build_plan("case_na_01", audit_res)

        self.assertEqual(plan.deletion_status, DeletionVerdict.NOT_APPLICABLE)
        self.assertEqual(plan.action_count, 0)
        self.assertEqual(plan.ordered_steps, [])
        self.assertFalse(plan.requires_remediation)

        # Output JSON must be strictly "[]"
        self.assertEqual(audit_res.get_steps_json(), "[]")

        # Report must clearly explain no deletion authorized
        md_report = DeletionVerificationReport.generate_markdown_report(plan)
        self.assertIn("NOT_APPLICABLE", md_report)
        self.assertIn("No Deletion Authorized", md_report)
        self.assertNotIn("DELETE_RECORD", md_report)

    def test_report_generation_and_safety_guarantee(self):
        """
        Test 6: Safety Guarantee & Report Structure
        Verifies that both Markdown and dictionary reports contain explicit safety guarantees,
        traceable audit trail entries, and distinctions between recommended and executed actions.
        """
        audit_res = CaseAuditResult(
            case_id="case_safety_01",
            deletion_status=DeletionVerdict.INCOMPLETE,
            email="frank.safety@mock.com",
            user_id="user_frank_06",
            steps=[
                AuditStep(
                    step_no=1,
                    phase=AuditPhase.FINDING.value,
                    system_id="account_service",
                    resource_id="account_006",
                    operation="REPORT_REMAINING_RECORD",
                    state="PRESENT",
                    evidence_id="ev_replica_06"
                )
            ]
        )
        plan = self.planner.build_plan("case_safety_01", audit_res)

        # Markdown Report checks
        md = DeletionVerificationReport.generate_markdown_report(plan)
        self.assertIn("Safety Guarantee", md)
        self.assertIn("Read-Only Inspection Mode", md)
        self.assertIn("automatic external deletions", md)
        self.assertIn("RECOMMENDED (Pending Execution)", md)

        # Dictionary checks
        summary = DeletionVerificationReport.generate_summary_dict(plan)
        self.assertEqual(summary["case_id"], "case_safety_01")
        self.assertEqual(summary["deletion_status"], "INCOMPLETE")
        self.assertEqual(summary["total_actions"], 1)
        self.assertEqual(summary["actions"][0]["is_executed"], False)
        self.assertIn("READ_ONLY", summary["safety_guarantee"])


if __name__ == "__main__":
    unittest.main()

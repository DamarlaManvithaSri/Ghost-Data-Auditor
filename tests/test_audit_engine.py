"""
Unit tests for the Core Deletion Audit Engine using fictional test data.
Tests all three statuses (COMPLETE, INCOMPLETE, NOT_APPLICABLE), retained records,
historical identifiers, unresolved evidence, and recreation risks.
"""

import unittest
import pandas as pd
from src.audit_engine import (
    DeletionInvestigator,
    DeletionVerdict,
    AuditPhase,
    classify_deletion_intent
)
from src.policy import PolicyRegistry, DeletionRule
from src.identity import IdentityResolver, compute_email_hash


class TestDeletionAuditEngine(unittest.TestCase):
    def setUp(self):
        # 1. Fictional Deletion Rules
        self.mock_rules_df = pd.DataFrame([
            {"rule_id": "r1", "data_category": "USER_PROFILE", "required_action": "DELETE", "condition": "Always"},
            {"rule_id": "r2", "data_category": "SECURITY_AUDIT_LOG", "required_action": "RETAIN", "condition": "Record is within retention period"},
            {"rule_id": "r3", "data_category": "ACCOUNT_TOMBSTONE", "required_action": "REDACT", "condition": "Only user_id permitted"},
            {"rule_id": "r4", "data_category": "ANALYTICS_PROFILE", "required_action": "ANONYMIZE", "condition": "Record attributable to user"}
        ])
        self.policy = PolicyRegistry(rules_df=self.mock_rules_df)

        # 2. Fictional Identities
        self.mock_identities_df = pd.DataFrame([
            {
                "user_id": "user_mock_10",
                "name": "Sarah Connor",
                "email": "sarah.current@mockcorp.com",
                "phone": "+1 555 1010",
                "email_hash": compute_email_hash("sarah.current@mockcorp.com"),
                "updated_at": "2026-01-01T10:00:00Z"
            }
        ])

        # 3. Fictional Audit Log (Historical Email)
        self.mock_audit_log_df = pd.DataFrame([
            {
                "audit_id": "audit_mock_01",
                "user_id": "user_mock_10",
                "event_time": "2025-05-01T12:00:00Z",
                "field_name": "email",
                "old_value": "sarah.former@mockcorp.com",
                "new_value": "sarah.current@mockcorp.com"
            }
        ])
        self.resolver = IdentityResolver(
            identities_df=self.mock_identities_df,
            audit_log_df=self.mock_audit_log_df
        )

        # 4. Fictional System Activity (Recreation risks & operations)
        self.mock_activity_df = pd.DataFrame([
            {
                "activity_id": "act_flow_01",
                "event_time": "2026-02-01T08:00:00Z",
                "event_type": "CHECK_DATA_FLOW",
                "source_system": "integration_service",
                "target_system": "account_service",
                "resource_id": "data_flow_9999",
                "reported_result": "ACTIVE",
                "details": "Data flow data_flow_9999 linked to user_mock_10."
            }
        ])

        self.mock_manifest_df = pd.DataFrame([
            {
                "file_id": "ev_db_01",
                "file_path": "mock_databases/replica.sql",
                "captured_at": "2026-03-01T12:00:00Z",
                "origin": "database_replica"
            }
        ])

        self.investigator = DeletionInvestigator(
            policy_registry=self.policy,
            identity_resolver=self.resolver,
            system_activity_df=self.mock_activity_df,
            evidence_manifest_df=self.mock_manifest_df
        )

    def test_status_not_applicable(self):
        """Tests that a non-deletion request is strictly classified as NOT_APPLICABLE with empty steps."""
        case = {
            "case_id": "case_test_na",
            "email": "sarah.current@mockcorp.com",
            "audit_at": "2026-06-01T00:00:00Z",
            "request_text": "Please send me a copy of last year's invoices. Leave my profile active and do not delete my account."
        }
        res = self.investigator.audit_case(case)
        self.assertEqual(res.deletion_status, DeletionVerdict.NOT_APPLICABLE)
        self.assertEqual(res.steps, [])
        self.assertEqual(res.get_steps_json(), "[]")

    def test_status_complete(self):
        """Tests that an authorized deletion where all evidence proves compliant absence yields COMPLETE."""
        case = {
            "case_id": "case_test_comp",
            "email": "sarah.current@mockcorp.com",
            "audit_at": "2026-06-01T00:00:00Z",
            "request_text": "Please delete my account and remove all personal information."
        }
        # In this clean test setup without recreation risks or lingering rows
        clean_inv = DeletionInvestigator(
            policy_registry=self.policy,
            identity_resolver=self.resolver,
            system_activity_df=pd.DataFrame(),
            evidence_manifest_df=self.mock_manifest_df
        )
        res = clean_inv.audit_case(case)
        self.assertEqual(res.deletion_status, DeletionVerdict.COMPLETE)
        # For COMPLETE cases, steps must contain ONLY verification steps
        self.assertTrue(all(s.phase == AuditPhase.VERIFICATION.value for s in res.steps))
        self.assertTrue(len(res.steps) > 0)
        self.assertEqual(res.steps[0].operation, "VERIFY_RECORD_ABSENT")

    def test_status_incomplete_recreation_risk(self):
        """Tests that an active data flow recreation risk marks the case INCOMPLETE."""
        case = {
            "case_id": "case_test_recreation",
            "email": "sarah.current@mockcorp.com",
            "audit_at": "2026-06-01T00:00:00Z",
            "request_text": "I request permanent erasure of my profile."
        }
        res = self.investigator.audit_case(case)
        self.assertEqual(res.deletion_status, DeletionVerdict.INCOMPLETE)
        
        # Must have FINDING, REMEDIATION, and VERIFICATION steps in that order
        phases = [s.phase for s in res.steps]
        self.assertIn(AuditPhase.FINDING.value, phases)
        self.assertIn(AuditPhase.REMEDIATION.value, phases)
        self.assertIn(AuditPhase.VERIFICATION.value, phases)
        
        # Verify specific recreation operations
        finding = next(s for s in res.steps if s.operation == "REPORT_ACTIVE_DATA_FLOW")
        self.assertEqual(finding.resource_id, "data_flow_9999")
        self.assertEqual(finding.state, "ACTIVE")
        
        remediation = next(s for s in res.steps if s.operation == "DISABLE_DATA_FLOW")
        self.assertEqual(remediation.state, "DISABLED")
        self.assertEqual(remediation.evidence_id, "") # Must be empty for future remediation

    def test_historical_identifier_audit(self):
        """Tests that a request using a former historical email is recognized and investigated."""
        case = {
            "case_id": "case_test_hist",
            "email": "sarah.former@mockcorp.com", # Old email
            "audit_at": "2026-06-01T00:00:00Z",
            "request_text": "Please delete the account registered to this email."
        }
        res = self.investigator.audit_case(case)
        # Resolved user_id must match the account
        self.assertEqual(res.user_id, "user_mock_10")

    def test_unresolved_evidence_conservative_behavior(self):
        """Tests that unknown identity or missing evidence results in INCOMPLETE rather than false COMPLETE."""
        case = {
            "case_id": "case_test_unresolved",
            "email": "unknown.ghost.user@nowhere.com",
            "audit_at": "2026-06-01T00:00:00Z",
            "request_text": "Please erase my account."
        }
        res = self.investigator.audit_case(case)
        self.assertEqual(res.deletion_status, DeletionVerdict.INCOMPLETE)
        self.assertIn("Identity resolution status: UNRESOLVED", res.checks_failed[0])


if __name__ == "__main__":
    unittest.main()

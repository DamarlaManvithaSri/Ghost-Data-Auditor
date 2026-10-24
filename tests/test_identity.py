"""
Unit tests for the Identity Resolution Engine using fictional test data.
Never uses or hardcodes actual challenge dataset records.
"""

import unittest
import pandas as pd
from src.identity import (
    IdentityResolver,
    IdentifierType,
    LinkConfidence,
    CrossSystemIdentitySearcher,
    compute_email_hash
)
from src.ingestion import EvidenceManager


class TestIdentityResolution(unittest.TestCase):
    def setUp(self):
        # 1. Create purely fictional identity snapshot
        self.mock_identities = pd.DataFrame([
            {
                "user_id": "user_mock_01",
                "name": "Alex Mercer",
                "email": "alex.mercer@mockmail.com",
                "phone": "+1 555 0101",
                "email_hash": compute_email_hash("alex.mercer@mockmail.com"),
                "updated_at": "2026-03-01T10:00:00Z"
            },
            {
                "user_id": "user_mock_02",
                "name": "Jordan Lee",
                "email": "jordan.current@mockmail.com",
                "phone": "+44 20 7946 0999",
                "email_hash": compute_email_hash("jordan.current@mockmail.com"),
                "updated_at": "2026-04-15T12:00:00Z"
            }
        ])

        # 2. Create purely fictional audit log history
        self.mock_audit_log = pd.DataFrame([
            {
                "audit_id": "audit_mock_101",
                "user_id": "user_mock_02",
                "event_time": "2025-06-10T14:30:00Z",
                "field_name": "email",
                "old_value": "jordan.former@mockmail.com",
                "new_value": "jordan.current@mockmail.com"
            },
            {
                "audit_id": "audit_mock_102",
                "user_id": "user_mock_02",
                "event_time": "2025-08-20T09:15:00Z",
                "field_name": "phone",
                "old_value": "+44 20 7946 0000",
                "new_value": "+44 20 7946 0999"
            },
            {
                "audit_id": "audit_mock_103",
                "user_id": "user_mock_02",
                "event_time": "2026-09-01T10:00:00Z", # Future event relative to cutoff
                "field_name": "email",
                "old_value": "jordan.current@mockmail.com",
                "new_value": "jordan.future@mockmail.com"
            }
        ])

        self.resolver = IdentityResolver(
            identities_df=self.mock_identities,
            audit_log_df=self.mock_audit_log
        )

    def test_resolve_current_identity(self):
        """Tests finding a customer by their current active email."""
        identity = self.resolver.resolve("alex.mercer@mockmail.com")
        self.assertEqual(identity.status, "RESOLVED")
        self.assertEqual(identity.user_id, "user_mock_01")
        self.assertIn("alex.mercer@mockmail.com", identity.get_emails())
        self.assertIn("+15550101", identity.get_phones())
        self.assertIn(compute_email_hash("alex.mercer@mockmail.com"), identity.get_hashes())

        # Check link provenance
        user_id_link = next(l for l in identity.links if l.identifier_type == IdentifierType.USER_ID)
        self.assertEqual(user_id_link.confidence, LinkConfidence.CONFIRMED)
        self.assertEqual(user_id_link.source_file, "user_identities.csv")

    def test_resolve_historical_email(self):
        """Tests that a deletion request with an old, former email resolves to the user's account."""
        identity = self.resolver.resolve("jordan.former@mockmail.com")
        self.assertEqual(identity.status, "RESOLVED")
        self.assertEqual(identity.user_id, "user_mock_02")
        
        # Both current and former emails must be present in dossier
        self.assertIn("jordan.former@mockmail.com", identity.historical_identifiers[IdentifierType.EMAIL.value])
        self.assertIn("jordan.current@mockmail.com", identity.current_identifiers[IdentifierType.EMAIL.value])

        # Former email must be marked is_historical=True
        hist_link = next(l for l in identity.links if l.identifier_value == "jordan.former@mockmail.com")
        self.assertTrue(hist_link.is_historical)
        self.assertEqual(hist_link.source_file, "user_audit_log.csv")

    def test_temporal_cutoff_enforcement(self):
        """Verifies that audit log entries occurring after audit_at are strictly ignored."""
        # audit_cutoff is before the 2026-09-01 event
        cutoff = "2026-08-01T00:00:00Z"
        identity = self.resolver.resolve("jordan.current@mockmail.com", audit_cutoff_time=cutoff)
        
        self.assertEqual(identity.status, "RESOLVED")
        # Future email must NOT be present
        self.assertNotIn("jordan.future@mockmail.com", identity.get_emails())

    def test_conflict_detection_when_shared(self):
        """Verifies that if multiple distinct user accounts claim the same email, it flags CONFLICT."""
        conflicting_identities = pd.DataFrame([
            {"user_id": "user_A", "email": "disputed@mockmail.com", "phone": "111", "email_hash": "h1"},
            {"user_id": "user_B", "email": "disputed@mockmail.com", "phone": "222", "email_hash": "h2"}
        ])
        resolver_conflict = IdentityResolver(
            identities_df=conflicting_identities,
            audit_log_df=pd.DataFrame()
        )
        identity = resolver_conflict.resolve("disputed@mockmail.com")
        self.assertEqual(identity.status, "CONFLICT")
        self.assertTrue(len(identity.conflicts) > 0)
        self.assertIn("Ambiguous identity", identity.conflicts[0])

    def test_no_merge_on_common_name(self):
        """Verifies that similar or shared names do not merge accounts."""
        names_identities = pd.DataFrame([
            {"user_id": "user_X", "name": "Sam Taylor", "email": "sam.x@mockmail.com"},
            {"user_id": "user_Y", "name": "Sam Taylor", "email": "sam.y@mockmail.com"}
        ])
        resolver_names = IdentityResolver(identities_df=names_identities)
        res_x = resolver_names.resolve("sam.x@mockmail.com")
        res_y = resolver_names.resolve("sam.y@mockmail.com")
        self.assertEqual(res_x.user_id, "user_X")
        self.assertEqual(res_y.user_id, "user_Y")
        self.assertNotEqual(res_x.user_id, res_y.user_id)

    def test_cross_system_search_with_mock_evidence(self):
        """Tests scanning multi-format evidence for all resolved identifiers."""
        mgr = EvidenceManager()
        # Ingest fictional database export
        sql_content = b"INSERT INTO replica_orders VALUES ('ord_999', 'user_mock_01', 'EUR 50.00');\n"
        mgr.ingest_bytes("db_orders_replica.sql", sql_content)

        # Ingest fictional server log
        log_content = b"2026-03-02 [AUDIT] Outbound notification sent to alex.mercer@mockmail.com\n"
        mgr.ingest_bytes("notifications.log", log_content)

        identity = self.resolver.resolve("alex.mercer@mockmail.com")
        searcher = CrossSystemIdentitySearcher(mgr)
        hits = searcher.search_customer_records(identity)

        self.assertEqual(len(hits), 2)
        sql_hit = next(h for h in hits if h.file_name == "db_orders_replica.sql")
        self.assertEqual(sql_hit.matched_identifier_type, "USER_ID")
        self.assertEqual(sql_hit.matched_value, "user_mock_01")

        log_hit = next(h for h in hits if h.file_name == "notifications.log")
        self.assertEqual(log_hit.matched_identifier_type, "EMAIL")
        self.assertEqual(log_hit.matched_value, "alex.mercer@mockmail.com")


if __name__ == "__main__":
    unittest.main()

"""
Automated unit & integration tests for the Evidence Ingestion layer.
Runs locally to verify parser resilience and error handling.
"""

import unittest
from src.ingestion import EvidenceManager, IngestionStatus

class TestEvidenceIngestion(unittest.TestCase):
    def setUp(self):
        self.manager = EvidenceManager()

    def test_valid_csv_parsing(self):
        csv_data = b"user_id,email,status\nuser_01,test@example.com,active\nuser_02,demo@example.com,deleted"
        f = self.manager.ingest_bytes("users.csv", csv_data)
        self.assertEqual(f.status, IngestionStatus.SUCCESS)
        self.assertEqual(f.record_count, 2)
        self.assertEqual(f.metadata["row_count"], 2)
        self.assertEqual(f.metadata["column_count"], 3)
        self.assertIn("user_id", f.metadata["columns"])
        self.assertEqual(f.records[0].source_ref.location_index, 1)

    def test_empty_csv_parsing(self):
        f = self.manager.ingest_bytes("empty.csv", b"")
        self.assertEqual(f.status, IngestionStatus.EMPTY)
        self.assertEqual(f.record_count, 0)

    def test_malformed_csv_parsing(self):
        # Line 2 has an unescaped bad quote that breaks CSV parsing
        bad_csv = b'user_id,email\nuser_01,"bad quote unclosed\nuser_02,ok'
        f = self.manager.ingest_bytes("corrupted.csv", bad_csv)
        # Should be handled gracefully (either skipped bad lines or caught as MALFORMED)
        self.assertIn(f.status, [IngestionStatus.SUCCESS, IngestionStatus.MALFORMED, IngestionStatus.PARTIAL_SUCCESS])

    def test_valid_json_parsing(self):
        json_data = b'[{"user_id": "u1", "action": "delete"}, {"user_id": "u2", "action": "retain"}]'
        f = self.manager.ingest_bytes("audit.json", json_data)
        self.assertEqual(f.status, IngestionStatus.SUCCESS)
        self.assertEqual(f.record_count, 2)
        self.assertEqual(f.records[0].source_ref.location_index, 1)

    def test_malformed_json_parsing(self):
        bad_json = b"{ unquoted_key: 123, broken syntax }"
        f = self.manager.ingest_bytes("bad.json", bad_json)
        self.assertEqual(f.status, IngestionStatus.MALFORMED)
        self.assertIn("Malformed JSON", f.status_message)

    def test_jsonl_parsing_with_skipped_lines(self):
        jsonl_data = b'{"line": 1}\n{broken json line}\n{"line": 3}\n'
        f = self.manager.ingest_bytes("stream.jsonl", jsonl_data)
        self.assertEqual(f.status, IngestionStatus.PARTIAL_SUCCESS)
        self.assertEqual(f.record_count, 2)
        self.assertEqual(len(f.warnings), 1)

    def test_text_and_log_parsing(self):
        log_data = b"2026-10-01 10:00:00 [INFO] Sync started\n2026-10-01 10:05:00 [WARN] Timeout on replica\n"
        f = self.manager.ingest_bytes("runtime.log", log_data)
        self.assertEqual(f.status, IngestionStatus.SUCCESS)
        self.assertEqual(f.record_count, 2)
        self.assertEqual(f.records[1].source_ref.location_index, 2)

    def test_duplicate_file_detection(self):
        data = b"colA,colB\n1,2\n"
        f1 = self.manager.ingest_bytes("file_a.csv", data)
        f2 = self.manager.ingest_bytes("file_b.csv", data)
        self.assertEqual(f1.status, IngestionStatus.SUCCESS)
        self.assertEqual(f2.status, IngestionStatus.SUCCESS)
        self.assertTrue(f2.metadata.get("is_duplicate"))
        self.assertEqual(f2.metadata.get("duplicate_of"), "file_a.csv")

    def test_search_records(self):
        data = b"id,user_email\n1,target_person@company.com\n2,other@company.com"
        self.manager.ingest_bytes("accounts.csv", data)
        matches = self.manager.search_records("target_person")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].source_ref.to_display_string(), "accounts.csv (Row 1)")

if __name__ == "__main__":
    unittest.main()

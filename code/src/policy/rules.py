"""
Deletion Policy Rules Parser & Registry.
Inspects deletion_rules.csv, maps resource categories to policy requirements,
and reports ambiguous or missing policy definitions.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import pandas as pd


@dataclass
class DeletionRule:
    """Represents a single parsed deletion rule from deletion_rules.csv."""
    rule_id: str
    data_category: str
    condition: str
    required_action: str  # DELETE, REDACT, ANONYMIZE, RETAIN
    raw_row: Dict[str, Any]


class PolicyRegistry:
    """
    Registry that inspects and indexes deletion rules.
    Detects column names dynamically and reports policy gaps or ambiguities.
    """
    def __init__(self, rules_df: Optional[pd.DataFrame] = None):
        self.rules: Dict[str, DeletionRule] = {}
        self.category_to_rule: Dict[str, DeletionRule] = {}
        self.missing_fields: List[str] = []
        self.ambiguities: List[str] = []

        if rules_df is not None:
            self._load_from_df(rules_df)
        else:
            self._load_from_file()

    def _load_from_file(self):
        path = os.path.join(os.getcwd(), "dataset", "deletion_rules.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                self._load_from_df(df)
            except Exception as e:
                self.ambiguities.append(f"Failed to load deletion_rules.csv: {str(e)}")
        else:
            self.missing_fields.append("dataset/deletion_rules.csv file not found on disk.")

    def _load_from_df(self, df: pd.DataFrame):
        # Dynamically discover column names without assuming exact casing or naming
        col_map = {}
        for col in df.columns:
            clean_col = col.strip().lower()
            if "rule" in clean_col and "id" in clean_col:
                col_map["rule_id"] = col
            elif "category" in clean_col:
                col_map["data_category"] = col
            elif "action" in clean_col:
                col_map["required_action"] = col
            elif "cond" in clean_col:
                col_map["condition"] = col

        # Check for missing essential columns
        expected_cols = ["rule_id", "data_category", "required_action", "condition"]
        for exp in expected_cols:
            if exp not in col_map:
                self.missing_fields.append(f"Missing expected policy column: '{exp}'.")

        # Report policy ambiguities inherent in the supplied policy schema
        self._check_schema_ambiguities(df, col_map)

        # Parse rows into DeletionRule objects
        for _, row in df.iterrows():
            r_id = str(row.get(col_map.get("rule_id", "rule_id"), f"rule_{len(self.rules) + 1}")).strip()
            cat = str(row.get(col_map.get("data_category", "data_category"), "")).strip().upper()
            action = str(row.get(col_map.get("required_action", "required_action"), "")).strip().upper()
            cond = str(row.get(col_map.get("condition", "condition"), "")).strip()

            rule_obj = DeletionRule(
                rule_id=r_id,
                data_category=cat,
                condition=cond,
                required_action=action,
                raw_row=row.to_dict()
            )
            self.rules[r_id] = rule_obj
            self.category_to_rule[cat] = rule_obj

    def _check_schema_ambiguities(self, df: pd.DataFrame, col_map: Dict[str, str]):
        """Identifies ambiguous or missing governance details in the policy file."""
        cols = set(col_map.keys())

        # Ambiguity 1: System ID mapping
        if "system_id" not in df.columns and "system" not in df.columns:
            self.ambiguities.append(
                "Policy does not provide explicit 'system_id' column mapping data categories to owning services (e.g. account_service, search_service). Mappings must be inferred from system activity and resource prefixes."
            )

        # Ambiguity 2: Explicit retention durations
        if "retention_duration" not in df.columns:
            self.ambiguities.append(
                "Policy specifies condition 'Record is within the supplied retention period' for SECURITY_AUDIT_LOG, but lacks explicit numeric duration in the policy table. Specific retention cutoff must be extracted from record payload."
            )

        # Ambiguity 3: Tombstone permitted fields
        self.ambiguities.append(
            "ACCOUNT_TOMBSTONE required action is REDACT with condition 'only stable internal user_id is needed', but prohibited fields (name, email, phone, email_hash) are specified in documentation rather than explicit policy columns."
        )

    def get_rule_for_category(self, category: str) -> Optional[DeletionRule]:
        """Looks up the rule by exact or normalized data category."""
        return self.category_to_rule.get(category.upper().strip())

    def match_resource_category(self, resource_id: str, system_id: Optional[str] = None) -> str:
        """
        Determines the data category for a given resource_id and system_id.
        """
        res_lower = resource_id.lower()
        sys_lower = (system_id or "").lower()

        if res_lower.startswith("account_") or sys_lower == "account_service":
            # Could be USER_PROFILE or ACCOUNT_TOMBSTONE
            if "tombstone" in res_lower:
                return "ACCOUNT_TOMBSTONE"
            return "USER_PROFILE"
        elif res_lower.startswith("tombstone_"):
            return "ACCOUNT_TOMBSTONE"
        elif res_lower.startswith("search_") or sys_lower == "search_service":
            return "SEARCH_INDEX_ENTRY"
        elif res_lower.startswith("cache_") or sys_lower == "cache_service":
            return "CACHE_ENTRY"
        elif res_lower.startswith("support_") or sys_lower == "support_platform":
            if "attachment" in res_lower:
                return "SUPPORT_ATTACHMENT"
            return "SUPPORT_MESSAGE"
        elif res_lower.startswith("analytics_") or sys_lower == "analytics_platform":
            return "ANALYTICS_PROFILE"
        elif res_lower.startswith("telemetry_"):
            return "PRODUCT_TELEMETRY"
        elif res_lower.startswith("export_") or sys_lower == "export_service":
            return "USER_EXPORT"
        elif res_lower.startswith("marketing_") or sys_lower == "marketing_platform":
            return "MARKETING_PROFILE"
        elif res_lower.startswith("email_") or sys_lower == "email_delivery_service":
            return "EMAIL_DELIVERY_LOG"
        elif res_lower.startswith("audit_") or sys_lower == "security_service":
            return "SECURITY_AUDIT_LOG"
        elif res_lower.startswith("legal_") or sys_lower == "legal_service":
            return "LEGAL_HOLD_RECORD"
        elif res_lower.startswith("backup_") or sys_lower == "backup_service":
            return "BACKUP_ARCHIVE"
        elif res_lower.startswith("data_flow_") or sys_lower == "integration_service":
            return "ACTIVE_DATA_FLOW"

        return "UNKNOWN_CATEGORY"

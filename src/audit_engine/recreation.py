"""
Data Recreation Risk & Active Data Flow Inspector.
Detects synchronization loops, ETL pipelines, import jobs, and backup restore paths
capable of recreating customer data that was deleted from primary systems.
"""

from typing import Dict, List, Set, Any, Optional
import pandas as pd
from .models import AuditStep, AuditPhase


class RecreationRiskDetector:
    """
    Inspects system activity and evidence to detect active processes that can recreate deleted data.
    """
    def __init__(self, system_activity_df: Optional[pd.DataFrame] = None):
        self.activity_df = system_activity_df

    def detect_recreation_risks(
        self,
        user_id: str,
        associated_resources: Set[str],
        audit_cutoff_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scans for active synchronization pipelines or unblocked backup restore paths
        linked to the user's resources.

        Returns a list of detected risk descriptors.
        """
        risks = []
        if self.activity_df is None or self.activity_df.empty:
            return risks

        # Find activities involving the user's resources up to audit_at
        user_activities = self.activity_df[self.activity_df["resource_id"].isin(associated_resources)]

        for _, row in user_activities.iterrows():
            event_time = str(row.get("event_time", ""))
            if audit_cutoff_time and event_time and event_time > audit_cutoff_time:
                continue

            event_type = str(row.get("event_type", "")).upper()
            resource_id = str(row.get("resource_id", ""))
            source_sys = str(row.get("source_system", ""))
            target_sys = str(row.get("target_system", ""))
            result = str(row.get("reported_result", "")).upper()
            act_id = str(row.get("activity_id", ""))

            # 1. Check for Active Data Flows (e.g. data_flow_xxxx)
            if resource_id.startswith("data_flow_") or event_type in ["SYNC_RECORD", "CHECK_DATA_FLOW"]:
                # Check if it was successfully disabled before audit_at
                disabled_events = self.activity_df[
                    (self.activity_df["resource_id"] == resource_id) &
                    (self.activity_df["event_type"] == "DISABLE_DATA_FLOW") &
                    (self.activity_df["reported_result"] == "SUCCESS")
                ]
                if audit_cutoff_time:
                    disabled_events = disabled_events[disabled_events["event_time"] <= audit_cutoff_time]

                if disabled_events.empty:
                    risks.append({
                        "risk_type": "ACTIVE_DATA_FLOW",
                        "system_id": target_sys or source_sys or "integration_service",
                        "resource_id": resource_id,
                        "finding_op": "REPORT_ACTIVE_DATA_FLOW",
                        "finding_state": "ACTIVE",
                        "remediation_op": "DISABLE_DATA_FLOW",
                        "remediation_state": "DISABLED",
                        "verify_op": "VERIFY_DATA_FLOW_DISABLED",
                        "verify_state": "DISABLED",
                        "evidence_id": act_id,
                        "details": f"Active synchronization flow {resource_id} is running and can recreate deleted customer data."
                    })

            # 2. Check for Restore Risks (e.g. backup_xxxx)
            elif resource_id.startswith("backup_") or event_type in ["RESTORE_BACKUP", "CHECK_RESTORE_ACCESS"]:
                # Check if restore was successfully blocked before audit_at
                blocked_events = self.activity_df[
                    (self.activity_df["resource_id"] == resource_id) &
                    (self.activity_df["event_type"] == "BLOCK_RESTORE") &
                    (self.activity_df["reported_result"] == "SUCCESS")
                ]
                if audit_cutoff_time:
                    blocked_events = blocked_events[blocked_events["event_time"] <= audit_cutoff_time]

                if blocked_events.empty:
                    risks.append({
                        "risk_type": "RESTORE_RISK",
                        "system_id": target_sys or source_sys or "backup_service",
                        "resource_id": resource_id,
                        "finding_op": "REPORT_RESTORE_RISK",
                        "finding_state": "ACTIVE",
                        "remediation_op": "BLOCK_RESTORE",
                        "remediation_state": "BLOCKED",
                        "verify_op": "VERIFY_RESTORE_BLOCKED",
                        "verify_state": "BLOCKED",
                        "evidence_id": act_id,
                        "details": f"Backup snapshot {resource_id} has unblocked restore paths that can bring back deleted user data."
                    })

        return risks

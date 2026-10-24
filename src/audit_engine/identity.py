"""
Identity Resolution Engine Adapter.
Connects the audit engine to the underlying identity resolver.
"""

from typing import Dict, Any, Optional
import pandas as pd
from src.identity import IdentityResolver, ResolvedIdentity


def resolve_user_identities(
    seed_email: str,
    identities_df: Optional[pd.DataFrame] = None,
    audit_log_df: Optional[pd.DataFrame] = None,
    audit_cutoff_time: Optional[str] = None
) -> ResolvedIdentity:
    """
    Recovers all known identifiers associated with a customer:
    - Stable user_id
    - Current and historical emails
    - Associated phone numbers
    - SHA-256 email hashes
    - Full provenance tracking links

    Args:
        seed_email: The email address or user_id provided in the deletion request.
        identities_df: Current identity snapshot dataframe.
        audit_log_df: Historical identity changes audit log.
        audit_cutoff_time: Optional audit_at cutoff timestamp.

    Returns:
        ResolvedIdentity dossier with verified links and timeline.
    """
    resolver = IdentityResolver(
        identities_df=identities_df,
        audit_log_df=audit_log_df
    )
    return resolver.resolve(seed_email, audit_cutoff_time=audit_cutoff_time)

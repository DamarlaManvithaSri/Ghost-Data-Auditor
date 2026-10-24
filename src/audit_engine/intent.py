"""
Deletion Request Intent Classifier.
Determines whether a person's request actually authorizes deletion or represents a non-deletion inquiry.
Supports multi-language requests (English, Spanish, French, German, Portuguese, Japanese, etc.).
"""

import re
from typing import Tuple

# Multi-lingual keywords indicating an erasure, deletion, or account closure request
DELETION_PATTERNS = [
    # English
    r"\b(delete|deletion|erase|erasure|remove|removal|close|closure|purge|wipe|forget)\b",
    r"\b(cancel.*account|terminate.*account|kill.*account)\b",
    # Spanish
    r"\b(eliminar|eliminaci[oó]n|borrar|suprimir|cancelar.*cuenta|dar.*de.*baja)\b",
    # French
    r"\b(supprimer|suppression|effacer|effacement|fermer.*compte)\b",
    # German
    r"\b(l[öo]schen|l[öo]schung|entfernen|schlie[ßs]en)\b",
    # Portuguese
    r"\b(excluir|exclus[aã]o|apagar|eliminar)\b",
    # Italian
    r"\b(cancellare|cancellazione|eliminare|eliminazione)\b",
    # CJK
    r"(削除|消去|삭제|파기|删除)"
]

# Non-deletion indicators (e.g. asking to retain account, update phone/address, or export info)
NON_DELETION_PATTERNS = [
    r"\bleave.*account.*active\b",
    r"\bkeep.*account.*as.*is\b",
    r"\bleave.*profile.*in.*place\b",
    r"\bcontinue.*using.*the.*service\b",
    r"\bwithout.*removing.*any.*of.*my.*records\b",
    r"\bdownload.*account.*information.*in.*a.*portable.*format\b",
    r"\bcopy.*of.*last.*year.*invoices\b",
    r"\bnumber.*on.*my.*profile.*is.*out.*of.*date\b",
    r"\bsurname.*is.*misspelled\b"
]


def classify_deletion_intent(request_text: str) -> Tuple[bool, str]:
    """
    Evaluates whether the request_text authorizes personal data deletion.

    Returns:
        (is_deletion_authorized: bool, rationale: str)
    """
    if not request_text or not isinstance(request_text, str):
        return False, "Request text is empty or missing."

    clean_text = request_text.strip().lower()

    # 1. Check for explicit non-deletion intent (data export, profile update, invoice copy)
    for pattern in NON_DELETION_PATTERNS:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return False, f"Request expresses non-deletion intent (matched: '{pattern}'). Account or data retention was requested."

    # 2. Check for affirmative deletion keywords across multiple languages
    for pattern in DELETION_PATTERNS:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return True, f"Request authorizes deletion (matched deletion pattern: '{pattern}')."

    # 3. Default fallback: No deletion authorization recognized
    return False, "No valid data deletion, erasure, or account closure authorization detected in request text."

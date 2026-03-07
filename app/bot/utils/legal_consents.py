from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import User

LEGAL_CONSENTS_VERSION = "2026-03-07"


def has_required_legal_consents(user: "User") -> bool:
    return bool(
        user.privacy_policy_accepted_at
        and user.terms_of_use_accepted_at
        and user.personal_data_consent_accepted_at
        and user.legal_consents_version == LEGAL_CONSENTS_VERSION
    )

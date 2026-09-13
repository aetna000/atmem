from __future__ import annotations

from enum import Enum
import re


class LocalRole(str, Enum):
    VIEWER = "viewer"
    INVESTIGATOR = "investigator"
    EVIDENCE_COLLECTOR = "evidence_collector"
    ADMINISTRATOR = "administrator"


_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
def normalize_username(value: str) -> str:
    username = str(value or "").strip().lower()
    if not _USERNAME.fullmatch(username):
        raise ValueError(
            "username must be 3-64 lowercase ASCII letters, digits, '.', '_' or '-', and begin with a letter or digit"
        )
    return username


def validate_password(password: str, username: str) -> None:
    del username
    value = str(password or "")
    if not value:
        raise ValueError("password cannot be empty")

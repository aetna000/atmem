"""Content-free Home restore/adoption binding for opt-in feedback authority.

This detects the supported Home workflows, not arbitrary whole-Home rollback.
The operating system and trusted owner still control the Home and its keys.
"""
from hashlib import sha256
import json

from atmem.core.canonical import canonical_json
from atmem.feedback.store import FeedbackError


def home_restore_binding(feedback):
    from atmem.home.layout import HomeLayout
    try:
        path = HomeLayout(feedback.evidence.home_root).path("runtime/home-mode.json")
    except ValueError:
        raise FeedbackError("restore_state_unavailable") from None
    try:
        with path.open("rb") as stream:
            raw = stream.read(16385)
    except FileNotFoundError:
        return None
    except OSError:
        raise FeedbackError("restore_state_unavailable") from None
    try:
        value = json.loads(raw)
        if (len(raw) > 16384 or type(value) is not dict
                or value.get("format") != "atmem-home-runtime-mode-v1"
                or value.get("mode") not in ("restore_read_only", "adopted_writable")):
            raise ValueError("unknown Home restore state")
        identity = value.get("binding_id") if value["mode"] == "adopted_writable" else value.get("restore_id", value.get("updated_at"))
        if type(identity) is not str or not 0 < len(identity) <= 256:
            raise ValueError("missing restore identity")
        return {"mode":value["mode"], "binding_sha256":sha256(canonical_json({
            "mode":value["mode"], "identity":identity, "instance_id":value.get("instance_id")}).encode()).hexdigest()}
    except (ValueError, TypeError, UnicodeError):
        raise FeedbackError("restore_state_unavailable") from None


def check_home_restore_binding(feedback, tx):
    current = home_restore_binding(feedback)
    saved = tx.get("restore_binding", "home")
    if current is not None and current["mode"] == "restore_read_only":
        raise FeedbackError("restore_requires_adoption")
    expected = current["binding_sha256"] if current is not None else None
    if expected != (saved["binding_sha256"] if saved is not None else None):
        raise FeedbackError("restore_reconciliation_required")

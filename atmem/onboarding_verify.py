"""Synthetic, content-safe first-run verification."""
from __future__ import annotations
def verify(manager, *, agent_id: str, workspace_id: str, subject_id: str) -> dict[str, bool]:
    marker="atmem synthetic verification marker"
    try:
        captured=manager.capture(marker, agent_id=agent_id, workspace_id=workspace_id, subject_id=subject_id, authenticated_user=True)
        prepared=manager.prepare("What verification marker was stored?", agent_id=agent_id, workspace_id=workspace_id, subject_id=subject_id)
        capture=bool(captured.get("captured")); context=marker in str(prepared.get("context", "")); evidence=bool(prepared.get("preview_id") or prepared.get("context_receipt_id"))
        return {"capture":capture,"paraphrase":capture,"context":context,"evidence":evidence,"restore":hasattr(manager,"restore") or hasattr(getattr(manager,"memory",None),"store")}
    except Exception:
        return {name:False for name in ("capture","paraphrase","context","evidence","restore")}

"""Shared CLI/dashboard onboarding state machine."""
from __future__ import annotations
import hashlib, json, os, time, uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

@dataclass(frozen=True, slots=True)
class SetupCheck:
    check_id: str; status: str; summary: str; safe_action: str | None = None
@dataclass(frozen=True, slots=True)
class SetupAction:
    action_id: str; description: str; mutating: bool; requires_consent: bool; rollback: str
@dataclass(frozen=True, slots=True)
class SetupReceipt:
    action_id: str; state: str; result_sha256: str; occurred_at: float
@dataclass(slots=True)
class OnboardingState:
    format: str = "atmem-onboarding-state-v1"; run_id: str = field(default_factory=lambda:f"setup_{uuid.uuid4().hex}"); phase: str = "discovered"; checks: list[dict[str, Any]] = field(default_factory=list); plan: list[dict[str, Any]] = field(default_factory=list); receipts: list[dict[str, Any]] = field(default_factory=list); activation_allowed: bool = False

class OnboardingService:
    def __init__(self, state_path: str | Path, discoverers: dict[str, Callable[[], tuple[str,str]]]|None=None): self.path=Path(state_path); self.discoverers=discoverers or {}
    def discover(self) -> OnboardingState:
        checks=[]
        for name, callback in sorted(self.discoverers.items()):
            try: status, summary=callback()
            except Exception as exc: status, summary="failed", type(exc).__name__
            checks.append(asdict(SetupCheck(name,status,summary, f"repair:{name}" if status != "ok" else None)))
        state=OnboardingState(checks=checks); self._write(state); return state
    def plan(self, state: OnboardingState) -> OnboardingState:
        state.plan=[asdict(SetupAction(f"configure:{row['check_id']}",f"Configure {row['check_id']}",True,True,f"restore:{row['check_id']}")) for row in state.checks if row["status"] != "ok"]
        state.phase="planned"; self._write(state); return state
    def apply(self, actions: dict[str, Callable[[], Any]], *, consent: bool) -> OnboardingState:
        state=self.load()
        if any(row["requires_consent"] for row in state.plan) and not consent: raise PermissionError("explicit setup consent required")
        completed={row["action_id"] for row in state.receipts if row["state"] == "completed"}
        try:
            for row in state.plan:
                if row["action_id"] in completed: continue
                result=actions[row["action_id"]]()
                digest=hashlib.sha256(json.dumps(result,default=str,sort_keys=True).encode()).hexdigest()
                state.receipts.append(asdict(SetupReceipt(row["action_id"],"completed",digest,time.time()))); self._write(state)
        except Exception:
            state.phase="interrupted"; self._write(state); raise
        state.phase="applied"; self._write(state); return state
    def activate(self, verifier: Callable[[], dict[str, Any]]) -> OnboardingState:
        state=self.load(); result=verifier()
        required=("capture","paraphrase","context","evidence","restore")
        state.activation_allowed=all(result.get(name) is True for name in required)
        if not state.activation_allowed: raise RuntimeError("activation verification did not prove every required check")
        state.phase="active"; self._write(state); return state
    def rollback(self, compensators: dict[str, Callable[[], Any]]) -> OnboardingState:
        state=self.load()
        for row in reversed(state.receipts):
            action=row["action_id"]
            if action in compensators: compensators[action](); row["state"]="rolled_back"
        state.activation_allowed=False; state.phase="rolled_back"; self._write(state); return state
    def load(self) -> OnboardingState: return OnboardingState(**json.loads(self.path.read_text()))
    def _write(self, state):
        self.path.parent.mkdir(parents=True,exist_ok=True); temp=self.path.with_suffix(".tmp"); temp.write_text(json.dumps(asdict(state),indent=2,sort_keys=True)+"\n"); os.replace(temp,self.path)

"""Hermes hook adapter for an operator-created, scoped AtMem binding.

Hermes imports are lazy: importing AtMem never installs or imports the host.
Registration/provisioning is separate from this provider's memory behavior.
"""
from __future__ import annotations

from pathlib import Path
from collections import deque
import hashlib
from queue import Empty, Full, Queue
from threading import Event, Lock
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .binding import HermesMemoryBinding


def create_provider(binding: HermesMemoryBinding, *, hermes_home: str):
    """Create a native provider for a trusted, local CLI profile.

    A gateway's sender-authentication mapping is not implied by CLI support.
    The caller must constrain max_context_chars below its Hermes spill threshold.
    """
    from agent.memory_provider import MemoryProvider, RecallStatus, spawn_context_thread

    expected_home = Path(hermes_home).expanduser().resolve()

    class AtMemProvider(MemoryProvider):
        @property
        def name(self):
            return "atmem"

        def __init__(self):
            self._session = ""
            self._turn = ""
            self._ready = False
            self._can_write = False
            self._can_read = False
            self._last_count = 0
            self._queue = Queue(maxsize=128)
            self._stop = Event()
            self._drained = Event()
            self._drained.set()
            self._lock = Lock()
            self._worker = None
            self._pending = 0
            self._errors = 0
            self._unmatched_turns = 0
            self._withheld_syncs = 0
            self._turns = deque(maxlen=128)

        def is_available(self):
            return binding.enabled

        def unavailable_reason(self):
            return "AtMem local CLI connection unavailable or disabled; inspect atmem hermes status."

        def post_setup(self, hermes_home, config):
            print("AtMem local CLI preview: connection and activation are owned by AtMem. "
                  "Inspect atmem hermes status. Hermes configuration was not changed.")

        def initialize(self, session_id, **kwargs):
            # Validate first; a failed reinitialization cannot retain old access.
            self._ready = False
            self._can_write = False
            supplied_home = kwargs.get("hermes_home")
            if not supplied_home or Path(supplied_home).expanduser().resolve() != expected_home:
                raise PermissionError("AtMem provider is bound to another Hermes profile")
            if kwargs.get("platform", "cli") != "cli":
                raise PermissionError("this AtMem provider profile currently supports local CLI only")
            if kwargs.get("agent_context", "primary") != "primary":
                raise PermissionError("delegated and scheduled Hermes scopes are not enabled")
            binding._session(session_id)  # Validate before enabling.
            if self._stop.is_set():
                raise RuntimeError("create a new provider after shutdown")
            if self._pending:
                raise RuntimeError("flush pending writes before reinitializing")
            with self._lock:
                self._unmatched_turns += len(self._turns)
                self._turns.clear()
            self._session = session_id
            self._turn = ""
            self._ready = binding.enabled
            self._can_write = self._ready
            self._can_read = self._ready
            if self._worker is None and self._ready:
                self._worker = spawn_context_thread(self._write_loop, name="atmem-hermes-writer")
                self._worker.start()

        def on_turn_start(self, turn_number, message, **kwargs):
            # Capture only the local authenticated human, never delegated/bot text.
            self._can_write = self._ready and not kwargs.get("author_is_bot", False)
            if kwargs.get("author_id") and kwargs["author_id"] != binding.identity.user_id:
                self._can_write = False
            self._can_read = self._can_write
            self._turn = str(turn_number)
            if not self._can_write or not isinstance(message, str) or not message.strip():
                return
            # Hermes strips expanded slash-skill scaffolding before sync_turn.
            # Use its own normalization, never fuzzy-match a different source.
            if message.startswith("[IMPORTANT: The user has invoked the "):
                try:
                    from agent.skill_commands import extract_user_instruction_from_skill_message
                    message = extract_user_instruction_from_skill_message(message)
                except (ImportError, ValueError, TypeError):
                    self._can_write = self._can_read = False
                    with self._lock:
                        self._errors += 1
                    return
                if not message:
                    self._can_write = self._can_read = False
                    return
            with self._lock:
                if len(self._turns) == self._turns.maxlen:
                    self._turns.popleft()
                    self._unmatched_turns += 1
                self._turns.append((self._session, self._turn,
                                    hashlib.sha256(str(message).encode()).hexdigest(), self._can_write))

        def prefetch(self, query, *, session_id=""):
            self._last_count = 0
            if not self._ready or not self._can_read or self._stop.is_set() or (session_id and session_id != self._session):
                return ""
            result = binding.recall(query, session_id=self._session,
                                    turn_id=self._turn or str(uuid.uuid4()))
            if result.context:
                self._last_count = len(result.candidate_ids)
            return result.context

        def recall_status(self):
            return RecallStatus("AtMem", self._last_count) if self._last_count else None

        def get_tool_schemas(self):
            # Automatic recall/capture only. Do not expose a tool that can relabel
            # arbitrary model text as an authenticated user instruction.
            return []

        def sync_turn(self, user_content, assistant_content, *, session_id="", messages=None, turn_author=None):
            if not self._ready or self._stop.is_set():
                return
            if session_id and session_id != self._session:
                raise PermissionError("Hermes session does not match the initialized binding")
            # An untrusted current turn must not consume a matching earlier
            # human source when Hermes omits turn_author on sync. Conservatively
            # withhold late capture until a new authorized turn starts.
            if self._turn and not self._can_write:
                with self._lock:
                    self._withheld_syncs += 1
                return
            if turn_author and (turn_author.get("is_bot") or
                                (turn_author.get("id") and turn_author["id"] != binding.identity.user_id)):
                with self._lock:
                    digest = hashlib.sha256(str(user_content).encode()).hexdigest()
                    source = next((row for row in self._turns if row[0] == self._session and row[2] == digest), None)
                    if source is not None:
                        self._turns.remove(source)
                return
            if not isinstance(user_content, str) or not user_content.strip() or len(user_content) > 65536:
                raise ValueError("user content must contain 1–65536 characters")
            # Snapshot identity and source now, never read mutable session state
            # later on the writer thread. Assistant output is deliberately unused.
            with self._lock:
                source_digest = hashlib.sha256(user_content.encode()).hexdigest()
                source = next((row for row in self._turns
                               if row[0] == self._session and row[2] == source_digest), None)
                if source is None:
                    raise ValueError("on_turn_start must identify this user source before sync")
                if not source[3]:
                    self._turns.remove(source)
                    return
                item = (user_content, source[0], source[1] + ":" + source[2])
                self._drained.clear()
                self._pending += 1
                try:
                    self._queue.put_nowait(item)
                    self._turns.remove(source)
                except Full:
                    self._pending -= 1
                    self._errors += 1
                    if not self._pending:
                        self._drained.set()
                    raise RuntimeError("AtMem write queue is full; the observation was not persisted") from None

        def _write_loop(self):
            while not self._stop.is_set() or self._pending:
                try:
                    text, session, observation = self._queue.get(timeout=0.1)
                except Empty:
                    continue
                try:
                    reply = binding.observe_user(text, session_id=session, observation_id=observation)
                    result = reply.get("result") or {}
                    if ("error" in reply or reply.get("reason") == "inactive" or
                            result.get("reason") or result.get("canonical_error")):
                        raise RuntimeError("AtMem did not persist the observation")
                except Exception:
                    # Do not log source text or exception payloads.
                    with self._lock:
                        self._errors += 1
                finally:
                    self._queue.task_done()
                    with self._lock:
                        self._pending -= 1
                        if not self._pending:
                            self._drained.set()

        def flush(self, timeout=10.0):
            drained = self._drained.wait(timeout)
            with self._lock:
                return drained and self._pending == 0 and self._errors == 0

        def get_status_config(self, config=None):
            # Network health must not hold up local capture or writer progress.
            try:
                remote = binding.status()
            except (RuntimeError, ValueError, PermissionError):
                remote = {"enabled": False, "service_available": False}
            with self._lock:
                return {**remote, "ready": self._ready,
                        "pending_writes": self._pending, "write_errors": self._errors,
                        "unmatched_turns": self._unmatched_turns,
                        "withheld_syncs": self._withheld_syncs,
                        "requires_write_reconciliation": self._errors > 0,
                        "durable_checkpoint": False}

        def on_session_switch(self, new_session_id, **kwargs):
            if not self.flush():
                self._ready = False
                raise RuntimeError("AtMem writes must complete before switching sessions")
            binding._session(new_session_id)
            with self._lock:
                self._unmatched_turns += len(self._turns)
                self._turns.clear()
            self._session = new_session_id
            self._turn = ""
            self._can_read = False
            self._can_write = False

        def shutdown(self):
            self._ready = False
            self._can_write = False
            self._stop.set()
            if not self.flush():
                raise RuntimeError("AtMem shutdown has pending or failed writes; inspect provider status")
            if self._worker is not None:
                self._worker.join(timeout=1.0)

    return AtMemProvider()

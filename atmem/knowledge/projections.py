"""Scoped, atomic rich-code projections in the existing encrypted Code store.

Workers never get store keys. Interrupted jobs cannot replace the last complete
generation; that generation is still withheld when its source is stale.
"""
import base64
import os
import re
import stat
from hashlib import sha256
from pathlib import Path

from atmem.code.contracts import CodeScope
from atmem.code.formation import memory_subject_id
from atmem.code.graph import CodeGraph, _git, _EXCLUDED, _TEXT_EXTENSIONS
from atmem.knowledge.contracts import SourceSnapshot, stable_digest, source_path
from atmem.knowledge.code.extractor import parse_artifacts
from atmem.knowledge.code.mapping import map_facts
from atmem.extract.validation import screen_content
from atmem.knowledge.source_text import source_text, SourceTextEncodingError
from atmem.knowledge.code.source_policy import SOURCE_POLICY, eligible_source

# Match the already sandboxed worker's input envelope. Strict identity captures
# retain their smaller default; graph indexing admits a complete larger snapshot,
# never an arbitrary prefix or a task-selected subset of a repository.
INDEX_SOURCE_BYTES = 24_000_000
INDEX_FILE_LIMIT = 5000
DISCOVERY_FILE_LIMIT = 50_000


def _omission_counts(counts):
    return tuple(counts.get(key, 0) for key in ('file_budget', 'source_encoding'))


class SourceFileBudgetExceeded(ValueError):
    """A regular file is outside the authorized per-file content envelope."""


def read_authorized_file(root: Path, name: str, maximum: int) -> bytes:
    """Descriptor-relative no-follow reads; never traverse a swapped symlink."""
    source_path(name)
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise NotImplementedError("rich source capture requires a qualified no-follow file reader on this platform")
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = name.split("/")
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("eligible source is not regular")
            if before.st_size > maximum:
                raise SourceFileBudgetExceeded("eligible source exceeds file budget")
            with os.fdopen(os.dup(descriptor), "rb") as stream:
                data = stream.read(maximum + 1)
            after = os.fstat(descriptor)
            if (len(data) > maximum or before.st_size != len(data) or
                    (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size)):
                raise ValueError("source changed during authorized read")
            return data
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)


class CodeKnowledge:
    def __init__(self, application, scope: CodeScope):
        if scope.subject_id != application.subject_id:
            raise PermissionError("knowledge subject mismatch")
        application.authorize(scope.project_id)
        self.app, self.scope = application, scope
        self.graph = CodeGraph(application, scope.project_id)

    @classmethod
    def from_store(cls, store, scope):
        """Internal freshness boundary; does not release a second encryption key."""
        class StoreBoundary:
            subject_id = scope.subject_id
            def __init__(self):
                self.store = store
            def authorize(self, project_id):
                if not store.code_project_exists(self.subject_id, project_id):
                    raise PermissionError("knowledge project is not authorized")
        return cls(StoreBoundary(), scope)

    def authorize(self, scope):
        self.app.authorize(self.scope.project_id)
        if scope != self.scope:
            raise PermissionError("knowledge scope mismatch")

    def capture(self, root: str, configuration_sha256: str, *, max_file_bytes=262144, max_source_bytes=6_000_000,
                omit_oversized_files=False, omit_invalid_text=False):
        if type(max_file_bytes) is not int or not 1 <= max_file_bytes <= 2_000_000 or type(max_source_bytes) is not int or not 1 <= max_source_bytes <= 64_000_000:
            raise ValueError("invalid authorized source capture budget")
        if type(omit_oversized_files) is not bool or type(omit_invalid_text) is not bool:
            raise ValueError("explicit source omission policy required")
        self.authorize(self.scope)
        path = self.graph._root(root)
        revision = _git(path, "rev-parse", "HEAD")
        names = sorted(set(_git(path, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")) - {""})
        if len(names) > DISCOVERY_FILE_LIMIT:
            raise ValueError("repository discovery file budget exceeded")
        files, exclusions, total, eligible_count = {}, {}, 0, 0
        for name in names:
            relative = Path(name)
            if (any(part in _EXCLUDED or part.startswith(".") for part in relative.parts)
                    or relative.name in {"mcp-arch.yaml", "enola-intent.yaml"}):
                exclusions["ignored_configuration_or_hidden"] = exclusions.get("ignored_configuration_or_hidden", 0) + 1
                continue
            source_path(name)
            target = path / name
            from atmem.knowledge.code.applicability import _CONFIG_NAMES
            if not eligible_source(name) and target.name not in _CONFIG_NAMES:
                exclusions["unsupported_extension"] = exclusions.get("unsupported_extension", 0) + 1
                continue
            eligible_count += 1
            if eligible_count > INDEX_FILE_LIMIT:
                raise ValueError("eligible repository file budget exceeded")
            if not target.exists() and not target.is_symlink():
                exclusions["deleted_source"] = exclusions.get("deleted_source", 0) + 1
                continue
            if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(path):
                raise ValueError("source path changed or escaped repository")
            try:
                data = read_authorized_file(path, name, max_file_bytes)
            except SourceFileBudgetExceeded:
                if not omit_oversized_files:
                    # Execution-identity and other strict callers must never
                    # acquire a partial source identity through this correction.
                    raise
                # Match the existing CodeGraph's bounded, explicit rejection;
                # never truncate a declaration or read above the authorized cap.
                exclusions["file_budget"] = exclusions.get("file_budget", 0) + 1
                continue
            try:
                text = source_text(name, data)
            except SourceTextEncodingError:
                if not omit_invalid_text:
                    raise
                exclusions['source_encoding'] = exclusions.get('source_encoding', 0) + 1
                continue
            if not screen_content(text, trusted=True).admissible:
                exclusions["secret_screen"] = exclusions.get("secret_screen", 0) + 1
                continue
            total += len(data)
            if total > max_source_bytes:
                raise ValueError("protected source-generation budget exceeded")
            files[name] = data
        if _git(path, "rev-parse", "HEAD") != revision:
            raise ValueError("source revision changed during capture")
        snapshot = SourceSnapshot(self.scope, "worktree-" + sha256(str(path).encode()).hexdigest(), revision,
                                  tuple((name, sha256(data).hexdigest()) for name, data in sorted(files.items())), configuration_sha256)
        return snapshot, files, exclusions

    def _key(self, snapshot):
        return memory_subject_id(self.scope) + ":" + snapshot.worktree_id

    def index(self, root: str, worker):
        self.authorize(self.scope)
        if not self.app.settings(self.scope.project_id)["graph_enabled"]:
            raise PermissionError("enable project graph indexing first")
        configuration = stable_digest({"worker_image": worker.image_id, "source_policy": SOURCE_POLICY})
        snapshot, files, exclusions = self.capture(root, configuration, max_source_bytes=INDEX_SOURCE_BYTES,
                                                  omit_oversized_files=True, omit_invalid_text=True)
        key = self._key(snapshot)
        prior = self.app.store.code_document(self.app.subject_id, self.scope.project_id, "knowledge-generation", key)
        if (prior and prior["snapshot_id"] == snapshot.snapshot_id
                and _omission_counts(prior.get("excluded_counts", {})) == _omission_counts(exclusions)):
            return {"status": "unchanged", "snapshot_id": snapshot.snapshot_id, "generation": prior["generation"]}
        job = {"format": "atmem-code-extraction-job-v1", "scope": self.scope.to_dict(),
               "snapshot_id": snapshot.snapshot_id, "status": "pending", "image_id": worker.image_id}
        self.app.store.put_code_document(self.app.subject_id, self.scope.project_id, "knowledge-job", key, job)
        artifacts = worker.extract(snapshot, files, authorize=self.authorize)
        facts, receipt, insights = parse_artifacts(artifacts)
        from atmem.knowledge.code.extractor import insight_facts
        mapped = map_facts(snapshot, facts + insight_facts(insights), source_bytes=files)
        # Full original artifacts retained protected, not replaced by hashes.
        value = {"format": "atmem-code-knowledge-generation-v1", "scope": self.scope.to_dict(),
                 "snapshot": snapshot.to_dict(), "snapshot_id": snapshot.snapshot_id,
                 "generation": (prior["generation"] + 1 if prior else 1), "configuration_sha256": configuration,
                 "objects": [o.to_dict() for o in mapped["objects"]],
                 "relations": [r.to_dict() for r in mapped["relations"]],
                 "property_variants": mapped["property_variants"], "conflicts": mapped["conflicts"], "source_locations": mapped["source_locations"],
                 "source_bytes": {name: base64.b64encode(data).decode() for name, data in files.items()},
                 "artifacts": {name: base64.b64encode(raw).decode() for name, raw in (
                     ("facts.jsonl", artifacts.facts_jsonl), ("receipt.json", artifacts.receipt_json), ("insights.json", artifacts.insights_json))},
                 "receipt": receipt, "insights": insights, "excluded_counts": exclusions,
                 "coverage": "pinned Enola; inspect extraction receipt and unsupported cells"}
        from atmem.knowledge.code.delta import generation_delta
        value["repository"] = {"id": "repository-" + snapshot.worktree_id.removeprefix("worktree-"),
                               "name": "repository", "last_delta": generation_delta(prior, value)}
        # A successfully published graph must fit the public query boundary.
        # Never publish a generation which every subsequent query will reject.
        from atmem.knowledge.code.queries import validate_graph_size
        validate_graph_size(value)
        with self.app.store.transaction():
            self.authorize(self.scope)
            current, _, current_exclusions = self.capture(root, configuration, max_source_bytes=INDEX_SOURCE_BYTES,
                                                         omit_oversized_files=True, omit_invalid_text=True)
            latest = self.app.store.code_document(self.app.subject_id, self.scope.project_id, "knowledge-generation", key)
            if (current != snapshot or _omission_counts(current_exclusions) != _omission_counts(exclusions)
                    or latest != prior):
                raise ValueError("source or projection changed before publication")
            self.app.store.put_code_document(self.app.subject_id, self.scope.project_id, "knowledge-generation", key, value)
            self.app.store.put_code_document(self.app.subject_id, self.scope.project_id, "knowledge-job", key, {**job, "status": "complete"})
            self.app.store.append_audit_event(subject_id=self.app.subject_id, event_type="code.knowledge_published", actor="atmem",
                                             payload={"project_id": self.scope.project_id, "snapshot_id": snapshot.snapshot_id,
                                                      "generation": value["generation"]})
        return {"status": "published", "snapshot_id": snapshot.snapshot_id, "generation": value["generation"],
                "objects": len(value["objects"]), "relations": len(value["relations"]), "excluded_counts": exclusions}

    def current(self, root: str):
        path = self.graph._root(root)
        worktree = "worktree-" + sha256(str(path).encode()).hexdigest()
        key = memory_subject_id(self.scope) + ":" + worktree
        from atmem.store.code_documents import CodeDocumentEncodingError
        try:
            value = self.app.store.code_document(self.app.subject_id, self.scope.project_id, "knowledge-generation", key)
        except CodeDocumentEncodingError:
            return None
        if not value:
            return None
        stored = SourceSnapshot.from_dict(value["snapshot"])
        # Shared lanes can be used by another agent, but private lanes cannot.
        if memory_subject_id(stored.scope) != memory_subject_id(self.scope):
            raise PermissionError("projection lane mismatch")
        try:
            snapshot, _, exclusions = self.capture(root, value["configuration_sha256"], max_source_bytes=INDEX_SOURCE_BYTES,
                                                   omit_oversized_files=True, omit_invalid_text=True)
        except (FileNotFoundError, ValueError, UnicodeError):
            # Unreadable or racing admitted source never becomes current
            # evidence. Explicit graph omission counts are checked below.
            return None
        if _omission_counts(exclusions) != _omission_counts(value.get("excluded_counts", {})):
            return None
        if snapshot.files != stored.files or snapshot.revision != stored.revision or snapshot.worktree_id != stored.worktree_id:
            return None
        self.authorize(self.scope)
        return value

    def context(self, root: str, task: str, *, budget: int):
        from atmem.knowledge.code.packing import pack_generation
        value = self.current(root)
        if value is None or budget <= 0:
            return {"content": "", "evidence": None, "status": "not_current"}
        content = pack_generation(value, task, budget=budget)
        latest = self.current(root)
        if latest is None or latest["snapshot_id"] != value["snapshot_id"]:
            return {"content": "", "evidence": None, "status": "source_changed"}
        return {"content": content, "status": "current", "coverage": value["coverage"],
            "excluded_counts": value["excluded_counts"], "evidence": {
            "root": str(self.graph._root(root)), "files": dict(value["snapshot"]["files"]),
            "revision": value["snapshot"]["revision"], "knowledge_snapshot_id": value["snapshot_id"],
            "scope": self.scope.to_dict(), "configuration_sha256": value["configuration_sha256"]}}

"""Retain context bytes while distinguishing preparation and host delivery."""

from __future__ import annotations

from hashlib import sha256
from typing import Callable
from pathlib import Path

from atmem.code.application import digest
from atmem.code.contracts import CodeContextPackage, CodeContextRequest
from atmem.code.formation import memory_subject_id


def graph_current(store, request, graph):
    """Pure source check shared by cached replay and final submission."""
    if graph.get('knowledge_snapshot_id'):
        from atmem.knowledge.projections import CodeKnowledge
        generation = CodeKnowledge.from_store(store, request.scope).current(graph['root'])
        if generation is None or generation['snapshot_id'] != graph['knowledge_snapshot_id']:
            raise PermissionError('rich structure changed before submission')
    from atmem.code.identity import repository_key, _git
    root = Path(graph['root']).resolve(strict=True)
    binding = store.code_project_binding(request.scope.subject_id, repository_key(root))
    if binding is None or binding['project_id'] != request.scope.project_id or _git(root, 'rev-parse', 'HEAD') != graph['revision']:
        raise PermissionError('code graph revision changed before submission')
    for name, expected in graph['files'].items():
        target = root / name
        if (target.is_symlink() or not target.resolve().is_relative_to(root) or not target.is_file()
                or target.stat().st_size > 262144 or sha256(target.read_bytes()).hexdigest() != expected):
            raise PermissionError('code graph file changed before submission')


class CodeReceipts:
    def __init__(self, store) -> None:
        if store.path != ":memory:" and store.policy.state != "encrypted":
            raise RuntimeError("Code receipts require encrypted AtMem storage")
        self.store = store

    def prepare(self, request: CodeContextRequest, package: CodeContextPackage, *, host: str, graph_evidence: dict | None = None,
                repository_root: str | None = None, index_only: bool = False) -> dict:
        if request.request_id != package.request_id:
            raise ValueError("context request binding mismatch")
        from atmem.extract.validation import screen_content
        from atmem.memory import _screenable_metadata
        if any(not screen_content(value, trusted=True).admissible
               for value in _screenable_metadata({"request": request.to_dict(), "package": package.to_dict(),
                                                   "repository_root": repository_root, "graph_evidence": graph_evidence})):
            raise PermissionError("context evidence failed secret screening")
        sources = []
        for record_id in package.memory_ids:
            record = self.store.get_record(memory_subject_id(request.scope), record_id)
            if record is None or record["status"] != "active":
                raise PermissionError("context source is no longer active")
            sources.append({"id": record_id, "sha256": digest(record)})
        row = {"format": "atmem-code-context-evidence-v1", "request": request.to_dict(),
               "package": package.to_dict(), "host": host, "state": "prepared",
               "sources": sources, "assurance": None, "observations": [],
               "capture_coverage": "partial", "reconstruction_status": "not_reconstructable"}
        if graph_evidence is not None:
            row["graph_evidence"] = graph_evidence
        if index_only:
            row['presentation'] = 'unchecked_experience_index'
        if repository_root is not None:
            row["repository_root"] = str(Path(repository_root).resolve(strict=True))
        existing = self.store.code_document(request.scope.subject_id, request.scope.project_id, "exposure", request.request_id)
        if existing is not None:
            if existing["request"] != row["request"] or existing["package"] != row["package"] or existing["host"] != host:
                raise ValueError("context request ID replay conflict")
            return existing
        self.store.put_code_document(request.scope.subject_id, request.scope.project_id, "exposure", request.request_id, row)
        return row

    def submitted(self, request: CodeContextRequest, package: CodeContextPackage, *, host: str) -> dict:
        with self.store.transaction():
            row = self.prepare(request, package, host=host)
            graph = row.get("graph_evidence")
            if graph:
                graph_current(self.store, request, graph)
            for source in row["sources"]:
                current = self.store.get_record(memory_subject_id(request.scope), source["id"])
                if current is None or current["status"] != "active" or digest(current) != source["sha256"]:
                    raise PermissionError("context changed before submission")
                from atmem.code.context import source_current
                if row.get('presentation') != 'unchecked_experience_index' and not source_current(self.store, request, current, row.get("repository_root")):
                    raise PermissionError("repository changed before context submission")
            if row["state"] == "prepared":
                row.update(state="submitted", assurance="submitted")
                self.store.put_code_document(request.scope.subject_id, request.scope.project_id, "exposure", request.request_id, row)
            return row

    def acknowledge(self, request: CodeContextRequest, *, host: str, content_sha256: str,
                    observation: dict, verify: Callable[[dict], bool]) -> dict:
        """A host verifier supplies acknowledgement evidence, never a client-selected assurance."""
        with self.store.transaction():
            row = self.store.code_document(request.scope.subject_id, request.scope.project_id, "exposure", request.request_id)
            if row is None or row["state"] != "submitted" or row["host"] != host:
                raise PermissionError("no matching submitted context")
            if row["package"]["content_sha256"] != content_sha256 or not verify(observation):
                raise PermissionError("host acknowledgement could not be verified")
            row["assurance"] = "host_acknowledged"
            row["observations"].append({"kind": "host_acknowledgement", "evidence": observation})
            self.store.put_code_document(request.scope.subject_id, request.scope.project_id, "exposure", request.request_id, row)
            return row

    def observe_model_input(self, request: CodeContextRequest, *, model_input: str,
                            observation: dict, verify: Callable[[dict, str], bool]) -> dict:
        with self.store.transaction():
            row = self.store.code_document(request.scope.subject_id, request.scope.project_id, "exposure", request.request_id)
            if row is None or row["state"] != "submitted":
                raise PermissionError("no matching submitted context")
            content = row["package"]["content"]
            if not content or content not in model_input or not verify(observation, model_input):
                raise PermissionError("independent model input observation failed")
            row["assurance"] = "model_input_observed"
            row["observations"].append({"kind": "model_input", "evidence": observation,
                                        "model_input_sha256": sha256(model_input.encode()).hexdigest()})
            self.store.put_code_document(request.scope.subject_id, request.scope.project_id, "exposure", request.request_id, row)
            return row

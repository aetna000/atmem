"""Isolated installed-package worker for the Spec 053 comparison.

Launch with an explicit interpreter and -I. Never imports the checkout package.
Only the application authorizes the dedicated public-history import.
"""
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys

from atmem import Memory
import atmem.memory
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart
from atmem.context_engine.contracts import ContextRequestV3
from atmem.service.household import HouseholdApplication


def main(request):
    package_root = Path(atmem.memory.__file__).parent
    digest = sha256()
    for source in sorted(package_root.rglob("*.py")):
        digest.update(str(source.relative_to(package_root)).encode() + b"\0")
        digest.update(source.read_bytes() + b"\0")
    identity = {"version": version("atmem"), "module": atmem.memory.__file__,
                "package_python_sha256": digest.hexdigest(),
                "memory_module_sha256": sha256(Path(atmem.memory.__file__).read_bytes()).hexdigest()}
    if identity["version"] != request["expected_version"]:
        raise ValueError("installed package version mismatch")
    scope = AuthorityScope("comparison-owner", "comparison-agent", "comparison-workspace")
    principal = "comparison-public-history"
    database = Path(request["database"])
    authority = {"principal_id": principal, **scope.to_dict(), "scopes": ["history_import:review"]}
    if request["command"] == "build":
        if database.exists():
            raise ValueError("fresh memory database required")
        HouseholdApplication.initialize(database, encrypted=True, backend="file")
    memory = Memory(database, auto_vectors=False, review_authorities=(authority,))
    try:
        if memory.policy.state != "encrypted":
            raise ValueError("encrypted experiment memory required")
        if request["command"] == "build":
            for index, item in enumerate(request["history"]):
                episode = "history-" + str(index)
                if isinstance(item, dict):
                    source_parts = [("text", "user_message", item["question"])] + [
                        ("tool", "tool_output", json.dumps(o, ensure_ascii=False, sort_keys=True))
                        for o in item["observations"]]
                else:
                    source_parts = [("tool", "tool_output", item)]
                parts = tuple(EpisodePart(part_id="part-" + str(i), ordinal=i,
                    kind=kind, source_type=source, content=text,
                    content_sha256="sha256:" + sha256(text.encode()).hexdigest())
                    for i, (kind, source, text) in enumerate(source_parts))
                memory.form_context_episode(EpisodeIngestRequest(
                    episode_id=episode, idempotency_key=episode, scope=scope,
                    parts=parts,
                    binding_method="host_asserted", binding_assurance="host_asserted",
                    source_observation_granularity="sentence"), history_import_principal=principal)
            memory.freeze_context_engine(scope)
            return {"identity": identity, "generation": memory.context_generation(scope)}
        if request["command"] != "context":
            raise ValueError("unknown worker command")
        generation = memory.context_generation(scope)
        package = memory.prepare_context_v3(ContextRequestV3(
            context_id="context-" + request["case_id"], request_id="request-" + request["case_id"],
            scope=scope, query=request["query"], profile_id="context-fast", mode="active",
            generation=generation["canonical_generation"], turn_id="turn-" + request["case_id"]))
        if memory.context_generation(scope) != generation:
            raise ValueError("canonical memory changed during final evaluation")
        return {"identity": identity, "generation": generation, "package": package.to_dict()}
    finally:
        memory.close()


if __name__ == "__main__":
    print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))

"""Installed-product structural coverage controls, no solver/model invocation.

Uses pinned upstream public regression sources, not user projects or training
data. All extraction runs through AtMem's actual offline pinned worker. Results
and original artifacts are retained through the protected benchmark service.
"""
import argparse
import ast
import base64
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from atmem.code.application import CodeApplication
from atmem.code.identity import CodeIdentity
from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.worker import ExtractionWorker
from atmem.knowledge.code.mcp import CodeKnowledgeMCP
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.pilot import installed_matches

SERENA_PIN = "2cb6cabc100539a1364bc243b543e664f0fa8f43"
COGNEE_PIN = "f154b32a9e544dac73e7ddf2010327cf9988edcd"
ENOLA_PIN = "f2bf59913016ec4fe05ca9ce228f95d6616e1da5"
EXTRACTION_CASES = ("openapi_sample", "asyncapi_multirepo", "py_grpc_multirepo", "python_flask_sample",
    "go_gin_sample", "hcl_sample", "ansible_sample", "ts_orm_sample", "csharp_aspnet_sample", "php_laravel_sample")
FAMILIES = {"python": {".py"}, "typescript": {".ts", ".tsx"}, "go": {".go"},
    "cpp": {".cpp", ".h", ".hpp"}, "csharp": {".cs"}, "java": {".java"}, "kotlin": {".kt"},
    "php": {".php"}, "ruby": {".rb"}, "rust": {".rs"}, "scala": {".scala"}, "swift": {".swift"},
    "dart": {".dart"}, "terraform": {".tf"}, "ansible": {".yml", ".yaml"}, "markdown": {".md"}}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], env={"PATH": "/usr/bin:/bin",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})


def sources(serena, cognee, enola=None):
    if git(serena, "rev-parse", "HEAD").decode().strip() != SERENA_PIN:
        raise ValueError("pinned Serena public regression sources required")
    if git(cognee, "rev-parse", "HEAD").decode().strip() != COGNEE_PIN:
        raise ValueError("pinned Cognee public regression sources required")
    files = {}
    from atmem.extract.validation import screen_content
    for family, suffixes in FAMILIES.items():
        prefix = "test/resources/repos/" + family + "/"
        names = git(serena, "ls-tree", "-r", "--name-only", SERENA_PIN, prefix).decode().splitlines()
        selected = []
        for name in sorted(names):
            if Path(name).suffix not in suffixes or "diagnostic" in name:
                continue
            raw = git(serena, "show", SERENA_PIN + ":" + name)
            if len(raw) > 12000 or not screen_content(raw.decode("utf-8"), trusted=True).admissible:
                continue
            selected.append((name, raw))
            if len(selected) == 2:
                break
        if not selected:
            raise ValueError("no admitted upstream control source for " + family)
        for name, raw in selected:
            files["languages/" + family + "/" + name[len(prefix):]] = raw
    prefix = "cognee/tests/test_data/code_repo_fixture/"
    for name in git(cognee, "ls-tree", "-r", "--name-only", COGNEE_PIN, prefix).decode().splitlines():
        files["upstream/" + name[len(prefix):]] = git(cognee, "show", COGNEE_PIN + ":" + name)
    if enola is not None:
        if git(enola, "rev-parse", "HEAD").decode().strip() != ENOLA_PIN:
            raise ValueError("pinned Enola contract fixture sources required")
        from atmem.knowledge.code.source_policy import eligible_source
        for case in EXTRACTION_CASES:
            prefix = "internal/engine/testdata/repos/" + case + "/"
            for name in git(enola, "ls-tree", "-r", "--name-only", ENOLA_PIN, prefix).decode().splitlines():
                relative = name[len(prefix):]
                if any(part.startswith(".") for part in Path(relative).parts) or Path(relative).name in {"mcp-arch.yaml", "enola-intent.yaml"} or not eligible_source(relative):
                    continue
                raw = git(enola, "show", ENOLA_PIN + ":" + name)
                if len(raw) <= 12000 and screen_content(raw.decode("utf-8"), trusted=True).admissible:
                    files["contracts/" + case + "/" + relative] = raw
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("serena", "cognee", "work-root", "state-root", "wheel"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--enola", type=Path)
    args = parser.parse_args()
    if args.work_root.exists() or args.state_root.exists():
        raise ValueError("fresh qualification paths required; never overwrite evidence")
    if args.state_root.is_relative_to(Path("/Volumes")):
        raise ValueError("protected evidence and keys must remain internal")
    installed_matches(args.wheel, sha256(args.wheel.read_bytes()).hexdigest())
    files = sources(args.serena, args.cognee, args.enola)
    args.state_root.mkdir(mode=0o700, parents=True)
    args.work_root.mkdir(mode=0o700)
    scope = EvidenceScope("benchmark", "local-operator", "code-index-parity-20261018")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    run = "code-index-parity-20261018-v1"
    vault = ReplayEvidence(args.state_root / "vault", vault_id=run, scope=scope)
    def save(kind, payload):
        vault.capture(run_id=run, kind=kind, payload=payload, principal=principal)
    save("qualification.frozen", {"source_pins": {"serena": SERENA_PIN, "cognee": COGNEE_PIN, "enola": ENOLA_PIN if args.enola else None},
        "files": {name: {"sha256": sha256(raw).hexdigest(), "bytes_base64": base64.b64encode(raw).decode()} for name, raw in files.items()},
        "serena_resources_license": git(args.serena, "show", SERENA_PIN + ":LICENSES/MIT.txt").decode(),
        "enola_license": git(args.enola, "show", ENOLA_PIN + ":LICENSE").decode() if args.enola else None,
        "wheel_sha256": sha256(args.wheel.read_bytes()).hexdigest(), "image_id": args.image_id,
        "script_source": Path(__file__).read_text(), "model_calls": 0,
        "classification": "upstream_regression_source_extraction_control_not_agent_benchmark"})
    for name, raw in files.items():
        target = args.work_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    git(args.work_root, "init")
    git(args.work_root, "add", ".")
    git(args.work_root, "-c", "user.name=Qualification", "-c", "user.email=qualification@localhost", "commit", "-m", "Pinned upstream control sources")
    database = args.state_root / "knowledge.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    try:
        bound = CodeIdentity(memory.store).resolve(args.work_root, subject_id="qualification", profile_id="shared", agent_id="codex")
        app = CodeApplication(memory, subject_id="qualification")
        app.settings(bound.project_id, {"graph_enabled": True})
        knowledge = CodeKnowledge(app, bound)
        index = knowledge.index(str(args.work_root), ExtractionWorker(args.image_id))
        generation = knowledge.current(str(args.work_root))
        save("qualification.indexed", {"index": index, "generation": generation})
        server = CodeKnowledgeMCP(app, bound, str(args.work_root))
        relation = next(row for row in generation["relations"] if row["target_id"] and row["kind"] == "calls")
        operations = {"query_facts": {"limit": 5}, "explore": {"id": relation["source_id"]},
            "traverse": {"node_ids": [relation["source_id"]], "max_depth": 20, "max_nodes": 20},
            "find_path": {"source_id": relation["source_id"], "target_id": relation["target_id"]},
            "impact_analysis": {"target_id": relation["target_id"], "max_nodes": 20},
            "architecture": {"max_nodes": 20}, "insights": {"limit": 2}, "delta": {}}
        answers = {}
        for operation, options in operations.items():
            answer = server.query("code_search", {"operation": operation, "arguments": options, "budget": 131072})
            if answer["status"] != "current" or answer["result"]["operation"] != operation:
                raise RuntimeError("installed operation withheld: " + operation)
            answers[operation] = answer
        # Compare actual extracted-state queries to methods compiled directly
        # from the immutable upstream blob, not another adapted implementation.
        from atmem.knowledge._vendor import code_retriever as incorporated
        from atmem.knowledge.code.queries import graph_input
        original = git(args.cognee, "show", COGNEE_PIN + ":cognee/modules/retrieval/code_retriever.py").decode()
        cls = next(n for n in ast.parse(original).body if isinstance(n, ast.ClassDef) and n.name == "CodeRetriever")
        cls.bases = []
        namespace = vars(incorporated).copy()
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), "pinned-upstream-real-state", "exec"), namespace)
        upstream = namespace["CodeRetriever"]
        nodes, edges = graph_input(generation)
        graph = incorporated._CodeGraphSnapshot(nodes, edges)
        for operation, options in operations.items():
            query = upstream(operation=operation, **options)
            expected = getattr(query, "_" + operation)(graph, "")
            if query.diagram_format:
                expected["diagram"] = incorporated.render_result_diagram(expected, query.diagram_format)
            if answers[operation]["result"] != expected:
                raise RuntimeError("pinned upstream query differential failed: " + operation)
        languages = Counter()
        for row in generation["objects"]:
            if row["kind"] == "symbol":
                for anchor in row["anchors"]:
                    parts = Path(anchor["path"]).parts
                    if parts[0] == "languages":
                        languages[parts[1]] += 1
        summary = {"index": index, "symbol_families": dict(languages), "families_without_symbols": sorted(set(FAMILIES) - set(languages)),
            "object_kinds": dict(Counter(row["kind"] for row in generation["objects"])),
            "operations": list(answers), "path_found": answers["find_path"]["result"]["found"],
            "findings_returned": answers["insights"]["result"]["total"],
            "upstream_query_differentials": list(answers), "model_calls": 0, "freshness_checks": {}}
        assert knowledge.index(str(args.work_root), ExtractionWorker(args.image_id))["status"] == "unchanged"
        name = "upstream/main.py"
        (args.work_root / name).write_bytes(files[name] + b"\n# qualification freshness check\n")
        for operation, options in operations.items():
            status = server.query("code_search", {"operation": operation, "arguments": options})["status"]
            if status != "not_current":
                raise RuntimeError("stale evidence exposed for " + operation)
            summary["freshness_checks"][operation] = status
        updated = knowledge.index(str(args.work_root), ExtractionWorker(args.image_id))
        delta = server.query("code_search", {"operation": "delta", "budget": 131072})["result"]["repositories"][0]["delta"]
        if updated["generation"] != 2 or delta["previous_snapshot_id"] != index["snapshot_id"] or delta["files_changed"] != 1:
            raise RuntimeError("real edit/reindex delta failed")
        old = args.work_root / "upstream/inventory/pricing.py"
        old.rename(old.with_name("pricing_renamed.py"))
        renamed = knowledge.index(str(args.work_root), ExtractionWorker(args.image_id))
        answer = server.query("code_search", {"operation": "query_facts", "arguments": {"file": "upstream/inventory/pricing.py"}})
        if renamed["generation"] != 3 or answer["result"]["total"] != 0:
            raise RuntimeError("renamed source retained current graph facts")
        summary["maintenance"] = {"edit_generation": updated["generation"], "edit_delta": delta,
            "rename_generation": renamed["generation"], "old_file_current_hits": answer["result"]["total"]}
        save("qualification.completed", {"summary": summary, "answers": answers})
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        save("qualification.failed", {"error_type": type(exc).__name__, "error": str(exc), "model_calls": 0})
        raise
    finally:
        memory.close()


if __name__ == "__main__":
    main()

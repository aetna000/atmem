"""Real installed/extractor localization diagnostic, disjoint from Click.

No model dispatch, fixture extractor, memory formation or hidden outcome input.
"""
import argparse
import base64
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import subprocess

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication
from atmem.code.receipts import CodeReceipts
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.freeze import digest
from benchmarks.code_replay.grade import write_new_tree
from benchmarks.code_replay.history import ProductLane
from benchmarks.code_replay.pilot import installed_matches


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "state-root", "evidence-root", "interpreter", "wheel"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--image-id", required=True)
    p.add_argument("--run-id", default="implementation-localization-p2-logging")
    p.add_argument("--require-call-context", action="store_true")
    p.add_argument("--require-usage", action="store_true")
    p.add_argument("--require-progressive", action="store_true")
    p.add_argument("--require-focused", action="store_true")
    args = p.parse_args()
    wheel_hash = sha256(args.wheel.read_bytes()).hexdigest()
    installed_matches(args.wheel, wheel_hash)
    library = args.interpreter / "lib/python3.12"
    files = {name: (library / name).read_bytes() for name in ("logging/__init__.py", "logging/handlers.py", "LICENSE.txt")}
    if args.require_usage:
        # Actual CPython v3.12.12 test source; Git blob identity is pinned,
        # retained and verified, not an invented positive-control fixture.
        blob_id = "5112c2e7d60f0baadabe21686fa5392d32391c3b"
        blob = json.loads(subprocess.check_output(["gh", "api", f"repos/python/cpython/git/blobs/{blob_id}"], timeout=30))
        raw = base64.b64decode(blob["content"])
        if sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != blob_id:
            raise ValueError("public test source identity differs")
        files["tests/test_logging.py"] = raw
    args.root.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_new_tree(args.root, files)
    env = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    for command in (("git", "init", str(args.root)), ("git", "-C", str(args.root), "add", "."),
                    ("git", "-C", str(args.root), "-c", "user.name=Replay", "-c", "user.email=replay@localhost", "commit", "-m", "Pinned public Python logging source")):
        subprocess.run(command, env=env, capture_output=True, check=True)
    args.state_root.mkdir(parents=True, exist_ok=False)
    database = args.state_root / "localization.db"
    HouseholdApplication.initialize(database, encrypted=True)
    memory = Memory(database, auto_vectors=False)
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    run_id = args.run_id
    receipts = []
    try:
        lane = ProductLane(memory, args.root, environment_sha256=digest({"corpus": "CPython-3.12.12-logging"}), experience=False)
        for number, (task, expected) in enumerate((
            ("Inspect logging.getLogger(name) and how existing loggers are looked up.", "getLogger"),
            ("Inspect Logger.error(msg) and the implementation that emits an error record.", "error"),
            ("Inspect FileHandler.close() and how its stream is closed.", "close")), 1):
            result = lane.prepare(run_id=f"{run_id}-{number}", task=task, image_id=args.image_id)
            content = result["package"].content
            localized = bool(re.search(r"(?m)^\d+:\s+(?:async )?def\s+" + expected + r"\s*\(", content))
            call_context = (not args.require_call_context or expected != "error" or
                            bool(re.search(r"(?m)^\d+:\s+def\s+_log\s*\(", content)))
            usage = not args.require_usage or "[AtMem existing test tests/test_logging.py:" in content
            receipts.append({"task": task, "expected_symbol": expected, "localized": localized,
                             "call_context_localized": call_context, "usage_localized": usage, "context": content,
                             "exposure": result["exposure"], "index": result["index"]})
            if not localized or not call_context or not usage or result["package"].memory_ids:
                raise RuntimeError("real-source implementation localization failed: " + expected)
        progressive = None
        if args.require_progressive:
            from benchmarks.code_replay.progressive_probe import probe_mcp
            progressive = {"current": probe_mcp(lane, focused=args.require_focused)}
        # A real source edit must withhold old context and refuse its prepared
        # submission, not merely attach the old snapshot's identifier.
        target = args.root / "logging/__init__.py"
        target.write_bytes(files["logging/__init__.py"] + b"\n# source-currentness negative control\n")
        stale = lane.knowledge.context(str(args.root), "FileHandler.close()", budget=8192)
        refused = False
        try:
            CodeReceipts(memory.store).submitted(result["request"], result["package"], host="codex")
        except PermissionError:
            refused = True
        passed = not stale["content"] and refused
        if args.require_progressive:
            progressive["stale"] = probe_mcp(lane, stale=True, focused=args.require_focused)
        vault.capture(run_id=run_id, kind="localization.qualified", principal=principal,
            payload={"passed": passed, "corpus": "CPython 3.12.12 logging modules", "license": "PSF LICENSE.txt retained",
                     "source_sha256": {k: sha256(v).hexdigest() for k, v in files.items()},
                     "source_base64": {k: base64.b64encode(v).decode() for k, v in files.items()},
                     "progressive": progressive,
                     "wheel_sha256": wheel_hash, "image_id": args.image_id, "receipts": receipts,
                     "stale_context_withheld": not stale["content"], "stale_submission_refused": refused,
                     "model_calls": 0, "exposure_assurance": "prepared_only_no_model_or_host_submission"})
        if not passed:
            raise RuntimeError("source-currentness negative control failed")
        print(json.dumps({"passed": passed, "localized_symbols": len(receipts), "stale_withheld": True,
                          "model_calls": 0, "wheel_sha256": wheel_hash, "evidence_run": run_id}), flush=True)
    except BaseException as exc:
        vault.capture(run_id=run_id, kind="localization.failed", principal=principal,
                      payload={"reason": str(exc), "receipts": receipts, "wheel_sha256": wheel_hash})
        raise
    finally:
        memory.close()


if __name__ == "__main__":
    main()

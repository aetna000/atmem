"""Run with python -I from the installed wheel, never importing repo modules."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import time

import atmem
from atmem.code.application import CodeApplication
from atmem.code.identity import CodeIdentity
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.worker import ExtractionWorker
from atmem.knowledge.code.queries import query_current
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    if "/site-packages/atmem/" not in str(Path(atmem.__file__).resolve()):
        raise RuntimeError("installed artifact required, not repository import")
    if args.database.exists():
        raise ValueError("fresh benchmark database required")
    HouseholdApplication.initialize(args.database, encrypted=True)
    memory = Memory(args.database, auto_vectors=False)
    try:
        scope = CodeIdentity(memory.store).resolve(args.root, subject_id="benchmark-operator", profile_id="shared", agent_id="codex")
        app = CodeApplication(memory, subject_id="benchmark-operator")
        app.settings(scope.project_id, {"graph_enabled": True})
        knowledge = CodeKnowledge(app, scope)
        start = time.monotonic()
        indexed = knowledge.index(str(args.root), ExtractionWorker(args.image_id))
        index_ms = int((time.monotonic() - start) * 1000)
        queried = query_current(knowledge, str(args.root), operation="query_facts", config={"kind": "symbol", "limit": 5})
        context = knowledge.context(str(args.root), "progressbar update finish position", budget=4096)
        source = Path(atmem.__file__).resolve().parent / "knowledge/projections.py"
        print(json.dumps({"installed_module": str(atmem.__file__), "projection_module_sha256": sha256(source.read_bytes()).hexdigest(),
                          "index": indexed, "index_ms": index_ms, "query_status": queried["status"],
                          "query_total": queried.get("result", {}).get("total"), "context_bytes": len(context["content"].encode()),
                          "context_status": context["status"], "source_status": knowledge.current(str(args.root))["coverage"],
                          "published_release": False, "agent_task_trial": False}))
    finally:
        memory.close()


if __name__ == "__main__":
    main()

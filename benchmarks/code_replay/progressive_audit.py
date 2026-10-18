"""Audit retained real host MCP responses; never trust the solver's summary."""
from hashlib import sha256
import json
from pathlib import Path

from atmem.knowledge.contracts import source_path


def audit(events):
    def one(kind):
        found = [e["envelope"]["payload"] for e in events if e["envelope"]["event_type"] == kind]
        if len(found) != 1:
            raise ValueError("exactly one retained host event required: " + kind)
        return found[0]
    started, diagnostic = one("mcp.host_started"), one("mcp.host_diagnostic")
    config = one("mcp.host_configuration")["config"]
    root = Path(config["args"][config["args"].index("--root") + 1]).resolve(strict=True)
    if root.name != "atmem-click-workspace" or not root.parent.name.startswith("session-") or not root.parent.parent.name.startswith("AtMemReplayRAM-"):
        raise ValueError("dedicated replay project required")
    if not started["probe"]["passed"] or not diagnostic["source_unchanged"] or diagnostic["native_canary_marker_leaked"]:
        raise ValueError("source or independent native barrier control failed")
    search, explore, sources, refusals, packs = [], [], [], [], []
    for item in diagnostic["completed_mcp_items"]:
        if item["server"] != "atmem_code":
            raise ValueError("wrong MCP server")
        if item["status"] == "failed":
            if item["tool"] == "code_source" and item["arguments"]["path"] == "../denied-canary.txt" and "Code query refused" in str(item["result"]):
                refusals.append(item)
                continue
            raise ValueError("unexpected MCP failure")
        answer = json.loads(item["result"]["content"][0]["text"])
        if answer["status"] != "current":
            raise ValueError("positive response not current")
        if item["tool"] == "code_search":
            search.append(answer)
        elif item["tool"] == "code_explore":
            explore.append((item["arguments"], answer))
        elif item["tool"] == "code_source":
            path = source_path(answer["path"])
            raw = (root / path).read_bytes()
            expected_hash = started["source_sha256"].get(path)
            if expected_hash != sha256(raw).hexdigest() or answer["source_sha256"] != expected_hash:
                raise ValueError("source fingerprint differs")
            args = item["arguments"]
            start, count = args.get("start_line", 1), args.get("line_count", 30)
            if answer["content"] != "\n".join(raw.decode().splitlines()[start - 1:start - 1 + count]) or "def getLogger(" not in answer["content"]:
                raise ValueError("actual returned implementation bytes differ")
            sources.append(answer)
        elif item["tool"] == "code_context":
            from atmem.memory import Memory
            from atmem.knowledge.code.packing import pack_generation
            database = config["args"][config["args"].index("--db") + 1]
            subject = config["args"][config["args"].index("--subject") + 1]
            project = config["args"][config["args"].index("--project-id") + 1]
            memory = Memory(database, auto_vectors=False)
            try:
                generation = next(g for g in memory.store.code_documents(subject, project, "knowledge-generation") if g["snapshot_id"] == answer["snapshot_id"])
                args = item["arguments"]
                expected = pack_generation(generation, args["query"], budget=args.get("budget", 4096))
                if answer["content"] != expected or answer["content_sha256"] != sha256(expected.encode()).hexdigest() or "def getLogger(" not in expected:
                    raise ValueError("actual focused context differs")
                packs.append(answer)
            finally:
                memory.close()
    if not search or not explore or not sources or not refusals:
        raise ValueError("missing observed positive/negative MCP response")
    if "code_context" in config["enabled_tools"] and not packs:
        raise ValueError("focused host source response absent")
    ids = {node["id"] for answer in search for node in answer["symbols"]}
    if any(args["id"] not in ids for args, _ in explore):
        raise ValueError("explore did not use an actual search result")
    snapshots = {answer["snapshot_id"] for answer in [*search, *(a for _, a in explore), *sources, *packs]}
    if len(snapshots) != 1:
        raise ValueError("mixed returned snapshots")
    return {"passed": True, "actual_source_bytes_verified": True, "scope_refusal_observed": True,
            "independent_native_read_barrier_passed": True, "source_unchanged": True,
            "model_native_canary_attempt": "not_visible_in_retained_cli_events_do_not_claim_verified",
            "assurance": "observed_mcp_responses_and_independent_shell_probe_not_complete_cli_system_capture"}

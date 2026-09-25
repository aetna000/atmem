"""Run with python -m atmem.continuity.example; no benchmark dependency."""
import argparse
import json
import os
from pathlib import Path

from .client import AtFlowsObserver, ContinuityClient, RecoveryBlocked
from .tools import DirectoryPublisher


def main():
    parser = argparse.ArgumentParser(description="Publish a document with governed restart safety")
    parser.add_argument("action", choices=["prepare", "run"])
    parser.add_argument("--url", default="http://127.0.0.1:8768")
    parser.add_argument("--token-env", default="ATMEM_EVIDENCE_TOKEN")
    parser.add_argument("--workflow-key")
    parser.add_argument("--workflow-id")
    parser.add_argument("--document", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--atflows-url")
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        parser.error(f"set {args.token_env} to a scoped credential before running")
    observer = None
    if args.atflows_url:
        observer_token = os.environ.get("ATFLOWS_CONTINUITY_TOKEN")
        if not observer_token:
            parser.error("set ATFLOWS_CONTINUITY_TOKEN for the configured observer")
        observer = AtFlowsObserver(args.atflows_url, observer_token)
    client = ContinuityClient(args.url, token, observer=observer)
    if args.action == "prepare":
        if not args.document or not args.workflow_key or not args.output:
            parser.error("prepare requires --document, --output and --workflow-key")
        document = args.document.read_text(encoding="utf-8")
        if len(document.encode("utf-8")) > 131072:
            parser.error("document exceeds the publisher's 128 KiB limit")
        workflow = client.create(args.workflow_key, [{"name": "publish", "tool": "publish_document",
            "arguments": {"text": document, "destination": str(args.output.expanduser().resolve())},
            "capability": "query", "timeout_seconds": 30}])
        print(json.dumps({"workflow_id": workflow["workflow_id"], "enabled": workflow["enabled"],
                          "next": "Review and enable in Decisions > Resume work before running."}))
        return
    if not args.workflow_id or not args.output:
        parser.error("run requires --workflow-id and --output")
    try:
        results = client.run(args.workflow_id, {"publish_document": DirectoryPublisher(args.output).tool()})
        print(json.dumps({"completed": results, "observation_errors": client.observation_errors,
                          "observation_error_count": client.observation_error_count}))
    except RecoveryBlocked as exc:
        print(json.dumps({"stopped_safely": str(exc), "next": "Inspect this workflow in Decisions > Resume work."}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()

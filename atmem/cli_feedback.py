"""Explicit-store CLI for the opt-in governed document service."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from atmem.contracts.feedback import OutcomeRecord, RetrievalProfileCandidate, RuleCandidate, identifier
from atmem.evidence.service import EvidenceService
from atmem.feedback.service import FeedbackService
from atmem.feedback.store import FeedbackError
from atmem.knowledge.rag.contracts import RagQuery
from atmem.knowledge.rag.service import RagService
from atmem.mcp.governed import GovernedMCPServer
from atmem.private_paths import private_path


def main(argv=None):
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    parser = argparse.ArgumentParser(prog="atmem rag", description="Opt-in scoped document retrieval. Configure sources/grants through the owner SDK first.")
    parser.add_argument("--root", required=True, help="Existing EvidenceService root; no default user store")
    parser.add_argument("--vault-id", required=True)
    parser.add_argument("--credential-file", required=True, help="Owner-private file containing an application token; never a tool argument")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--memory-db", help="Explicit existing encrypted canonical memory, required for behavior proposals")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "sources", "capabilities"):
        commands.add_parser(name)
    restore = commands.add_parser("reconcile-restore", help="Owner-only quarantine after Home adoption; does not reactivate anything")
    restore.add_argument("--restore-id", required=True)
    restore.add_argument("--confirm", required=True, help="Repeat the restore ID to confirm disabling restored authority")
    search = commands.add_parser("search")
    search.add_argument("--source", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--key", required=True)
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--jurisdiction")
    search.add_argument("--as-of")
    inspect = commands.add_parser("inspect")
    for name in ("receipt", "document", "chunk"):
        inspect.add_argument("--" + name, required=True)
    outcome = commands.add_parser("outcome")
    outcome.add_argument("--id", required=True)
    quality = commands.add_parser("quality")
    quality.add_argument("--schedule", required=True)
    for name in ("report", "propose-rule", "propose-profile"):
        command = commands.add_parser(name)
        command.add_argument("--file", required=True, help="Bounded JSON contract; scope must match application binding")
        command.add_argument("--key", required=True)
    args = parser.parse_args(argv)
    memory = None
    try:
        path = Path(args.credential_file)
        root = Path(args.root).expanduser().resolve()
        identifier(args.vault_id)
        if not path.is_file() or not private_path(path) or path.stat().st_size > 513:
            raise FeedbackError("private_credential_file_required")
        # Avoid initializing keys/accounts when the caller mistypes a root.
        if not (root / "protected-evidence.db").is_file():
            raise FeedbackError("existing_store_required")
        if not (root.parent / ".evidence-accounts" / (args.vault_id + ".json")).is_file():
            raise FeedbackError("existing_store_required")
        credential = path.read_text().strip()
        evidence = EvidenceService(root, vault_id=args.vault_id)
        feedback = FeedbackService(evidence)
        if args.command == "reconcile-restore":
            if args.confirm != args.restore_id:
                raise FeedbackError("confirmation_required")
            from atmem.feedback.recovery import FeedbackRecovery
            principal = feedback._principal(credential)
            scope = feedback._scope(principal, args.agent, args.workspace)
            value = FeedbackRecovery(feedback).reconcile_after_restore(credential, scope, restore_id=args.restore_id)
            print(json.dumps(value, ensure_ascii=False))
            return 0
        session = feedback.bind(credential, agent_id=args.agent, workspace_id=args.workspace)
        if args.memory_db:
            if not Path(args.memory_db).is_file():
                raise FeedbackError("existing_memory_required")
            from atmem import Memory
            with feedback._authorized(session, "propose"):
                memory = Memory(args.memory_db, auto_vectors=False)
            if memory.policy.state != "encrypted":
                raise FeedbackError("encrypted_memory_required")
            feedback.memory = memory
        rag = RagService(feedback)
        if "search" in feedback.capabilities(session)["operations"]:
            rag.attach_local(session)
        if args.command == "serve":
            GovernedMCPServer(feedback, rag, session).serve()
            return 0
        if args.command == "sources":
            value = rag.sources(session)
        elif args.command == "capabilities":
            value = feedback.capabilities(session)
        elif args.command == "inspect":
            value = rag.inspect(session, receipt_id=args.receipt, document_id=args.document, chunk_id=args.chunk)
        elif args.command == "outcome":
            value = feedback.outcome(session, args.id, include_attributions=True)
        elif args.command == "quality":
            value = feedback.quality(session, schedule_id=args.schedule)
        elif args.command in ("report", "propose-rule", "propose-profile"):
            path = Path(args.file)
            if path.stat().st_size > 262144:
                raise FeedbackError("input_budget_exhausted")
            contract = json.loads(path.read_text())
            if args.command == "report":
                value = feedback.report_outcome(session, OutcomeRecord.from_dict(contract), idempotency_key=args.key)
            else:
                if memory is None:
                    raise FeedbackError("existing_memory_required")
                from atmem.extract.review import ReviewService
                from atmem.feedback.review import propose
                cls = RuleCandidate if args.command == "propose-rule" else RetrievalProfileCandidate
                value = propose(ReviewService(memory), feedback, session, cls.from_dict(contract), idempotency_key=args.key)
        else:
            value = rag.search(session, RagQuery(args.source, args.query, args.limit, args.jurisdiction, args.as_of), idempotency_key=args.key)
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except FeedbackError as error:
        print(json.dumps({"error": error.code}), file=sys.stderr)
        return 2
    except (ValueError, OSError, RuntimeError):
        # Startup errors go to stderr so stdio remains protocol-only.
        import sys
        print("AtMem governed service unavailable: check explicit store, private credential and scope grant.", file=sys.stderr)
        return 2
    finally:
        if memory is not None:
            memory.close()


if __name__ == "__main__":
    raise SystemExit(main())

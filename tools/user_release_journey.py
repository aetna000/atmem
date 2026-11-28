"""Installed-user release journey; operational evidence, never learning proof.

Run with Python -I outside the checkout after installing the candidate wheel[code].
All data/services belong to a fresh explicit directory. Never uses an existing Home.
Detailed child logs stay private; the receipt contains no account credentials.
"""
import argparse
from hashlib import sha256
from importlib.metadata import metadata, version
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import urllib.request

EXPECTED = "2.3.16"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--wheel-sha256", required=True)
    parser.add_argument("--study-example", type=Path, required=True)
    args = parser.parse_args()
    root = args.workdir.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("fresh isolated journey directory required")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in tuple(os.environ):
        if (name.startswith(("ATMEM_", "ATBOT_", "OPENAI_", "ANTHROPIC_", "OPENROUTER_"))
                or name == "OPEN_ROUTER"):
            os.environ.pop(name, None)
    os.environ.update(ATMEM_HOME=str(root / "AtMem Home"),
        ATFLOWS_STATE_DIR=str(root / "flows-instances"), DATA_DIR=str(root / "flows-data"),
        ATFLOW_RUNTIME_DIR=str(root / "flows-runtime"),
        PYTHONUTF8="1",
        PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    from atmem.private_paths import protect_private_path
    protect_private_path(root)
    receipt = {"format": "atmem-installed-user-journey-v1", "version": version("atmem"),
        "system": platform.system(), "os_release": platform.release(), "architecture": platform.machine(),
        "python": platform.python_version(), "checks": [], "claim": "operational_test_only; no learning claim"}
    started = time.monotonic()

    def command(name, arguments, *, expected=0, as_json=False, timeout=180):
        receipt["active_step"] = name
        result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        log = root / (name + ".log")
        log.touch(mode=0o600)
        protect_private_path(log)
        log.write_text(result.stdout + "\nSTDERR\n" + result.stderr, encoding="utf-8")
        if result.returncode != expected:
            raise RuntimeError(name + " failed; inspect private log")
        return json.loads(result.stdout) if as_json else result.stdout

    def cli(name, *parts, **kwargs):
        executable = Path(sys.executable).with_name("atmem.exe" if os.name == "nt" else "atmem")
        return command(name, [str(executable), *parts], **kwargs)

    def passed(name, **details):
        receipt["checks"].append({"name": name, "passed": True, **details})
        print(json.dumps({"step": name, "passed": True}), flush=True)

    try:
        import atmem
        assert receipt["version"] == EXPECTED
        assert "Development Status :: 5 - Production/Stable" in metadata("atmem").get_all("Classifier", [])
        receipt["release_channel"] = "stable"
        assert "site-packages" in str(Path(atmem.__file__).resolve())
        digest = sha256(args.wheel.read_bytes()).hexdigest()
        assert digest == args.wheel_sha256
        receipt["wheel_sha256"] = digest
        assert version("atmem-atbot") == "0.1.1" and version("atflows") == "0.1.8"
        command("dependencies", [sys.executable, "-m", "pip", "check"])
        assert EXPECTED in cli("version", "--version")
        study = Path(sys.executable).with_name("atmem-memory-study.exe" if os.name == "nt" else "atmem-memory-study")
        command("study_help", [str(study), "--help"])
        cli("rag_help", "rag", "--help")
        passed("installed_identity_and_dependencies")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        init = cli("initialize", "init", "--no-open", "--json", "--port", str(port), as_json=True, timeout=240)
        assert init["dashboard"]["running"]
        assert init["atflows"]["running"] and init["atflows"]["managed_by_atmem"]
        assert init["atbot"]["running"] or init["atbot"]["fallback_selected"]
        passed("initialize_local_services", atbot_running=init["atbot"]["running"],
               deterministic_fallback=init["atbot"]["fallback_selected"])
        status = cli("status", "status", "--json", as_json=True)
        assert status["dashboard"]["running"] and status["atflows"]["running"]
        for label, url in [("dashboard", init["dashboard"]["url"]), ("atflows", init["atflows"]["dashboard_url"])]:
            assert url.startswith("http://127.0.0.1:")
            with urllib.request.urlopen(url, timeout=20) as response:
                assert response.status == 200 and response.read(1024)
        passed("loopback_dashboard_and_atflows_http", bun_version=status["atflows"]["bun_version"],
               bun_managed=status["atflows"]["bun_managed_by_atmem"])
        database = root / "encrypted memory.db"
        cli("encrypted_household", "household", "init", str(database), "--encrypted", "--backend", "file")
        protection = cli("encrypted_status", "household", "status", str(database), "--json", as_json=True)
        assert protection["state"] == "encrypted"
        cli("remember", "remember", str(database), "release-user", "My preferred editor is Vim.", "--session", "release-journey")
        recalled = cli("recall", "recall", str(database), "release-user", "preferred editor", as_json=True)
        assert recalled and "Vim" in recalled[0]["content"]
        check = cli("integrity", "verify", str(database), "--incremental", as_json=True)
        assert check["valid"] is True
        assert b"preferred editor" not in database.read_bytes()
        passed("encrypted_memory_persists_across_processes")

        from atmem.contracts.feedback import FeedbackScope
        from atmem.evidence.service import EvidenceService
        from atmem.feedback.service import FeedbackService
        from atmem.knowledge.rag.contracts import RagHit, RagSource
        from atmem.knowledge.rag.service import RagService
        from atmem.knowledge.rag.sqlite import SQLiteRagProvider
        feature_home = root / "feature-home"
        evidence = EvidenceService(feature_home / "control", vault_id="user-journey", home_root=feature_home)
        accounts = evidence.create_demo_accounts(subject_id="journey")
        owner, reader = accounts[2], accounts[1]
        feedback = FeedbackService(evidence)
        scope = FeedbackScope("local", "journey", "release-agent", "release-space")
        feedback.grant_agent(owner["token"], scope, principal_id=reader["principal_id"],
            operations=("read", "search", "inspect"), expires_at=int(time.time()) + 600)
        source = RagSource("release-notes", scope, "sqlite-vault", "journey-notes", "rev-1", "none")
        provider = SQLiteRagProvider(feedback)
        rag = RagService(feedback)
        rag.register(owner["token"], source, provider)
        text = "The release test project code is CEDAR-2315."
        hit = RagHit(source.source_id, scope, source.revision, "release-note", "code", "Journey note",
            "urn:atmem:release-journey", "line-1", text, sha256(text.encode()).hexdigest())
        provider.put_documents(owner["token"], source, (hit,))
        token_file = root / "reader-token"
        token_file.touch(mode=0o600)
        protect_private_path(token_file)
        token_file.write_text(reader["token"])
        binding = ["rag", "--root", str(feature_home / "control"), "--vault-id", "user-journey",
            "--credential-file", str(token_file), "--agent", scope.agent_id, "--workspace", scope.workspace_id]
        result = cli("document_search", *binding, "search", "--source", source.source_id,
            "--query", "CEDAR-2315", "--key", "journey-search", as_json=True)
        assert result["hits"][0]["text"] == text and result["memory_admitted"] is False
        inspected = cli("document_inspect", *binding, "inspect", "--receipt", result["receipt_id"],
            "--document", "release-note", "--chunk", "code", as_json=True)
        assert inspected["hit"]["text"] == text
        denied_binding = list(binding)
        denied_binding[denied_binding.index(scope.workspace_id)] = "other-space"
        cli("wrong_scope_denied", *denied_binding, "sources", expected=2)
        assert b"CEDAR-2315" not in (feature_home / "control/protected-evidence.db").read_bytes()
        token_file.unlink()
        passed("owner_scoped_encrypted_documents_and_denial")
        command("study_contract", [sys.executable, "-I", str(args.study_example)], timeout=90)
        passed("encrypted_study_contract_zero_model_calls")
        receipt["passed"] = True
    except Exception as error:
        receipt.update(passed=False, failure_type=type(error).__name__, failure=str(error),
                       failed_step=receipt.get("active_step"))
        raise
    finally:
        cleanup = []
        try:
            from atmem.control.atbot_service import AtBotServiceManager
            AtBotServiceManager().stop()
            cleanup.append("own_atbot_stopped")
        except Exception as error:
            cleanup.append("atbot_cleanup_" + type(error).__name__)
        try:
            from atmem.atflows_service import status as flows_status, _stop_managed_instance
            if flows_status().get("managed_by_atmem"):
                _stop_managed_instance()
            cleanup.append("own_atflows_stopped")
        except Exception as error:
            cleanup.append("atflows_cleanup_" + type(error).__name__)
        try:
            cli("stop_dashboard", "dashboard", "daemon", "stop", "--json")
            cleanup.append("own_dashboard_stopped")
        except Exception as error:
            cleanup.append("dashboard_cleanup_" + type(error).__name__)
        receipt["cleanup"] = cleanup
        cleanup_failed = any("cleanup_" in item for item in cleanup)
        if cleanup_failed:
            receipt["passed"] = False
        receipt["seconds"] = time.monotonic() - started
        (root / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt), flush=True)
        if cleanup_failed:
            raise RuntimeError("task-owned service cleanup failed; see receipt")


if __name__ == "__main__":
    main()

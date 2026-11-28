"""Qualify cross-host tools, source revision replay and a real pytest outcome in an isolated project."""

import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic

from atmem.agent_team.local import LocalAgents, MODEL_DIGEST
from atmem.control.agent_team import history
from tools.team_qualification.hosts import host_call
from tools.team_qualification.workspace import Project, QUESTION


def test_result(project, run):
    fixture = project.root / "test_route.py"
    fixture.write_text(
        "import json\nfrom pathlib import Path\n\ndef test_route():\n"
        '    value = json.loads(Path(__file__).with_name("route.json").read_text())\n'
        '    assert value == "AX-745"\n'
    )
    (project.root / "route.json").write_text(json.dumps(run["answer"]))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_route.py", "--junitxml=report.xml"],
        cwd=project.root,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    assert result.returncode in (0, 1), result.stdout
    return {
        "kind": "test",
        "reference": "test_route.test_route",
        "classname": "test_route",
        "test_name": "test_route",
        "junit": (project.root / "report.xml").read_text(),
        "step_id": run["steps"][-1]["step_id"],
    }


def invoke_model(agents, role, question, text):
    answer = agents.invoke(role, question, text)
    assert answer.quote, "Model abstained during host qualification"
    return {
        "quote": answer.quote,
        "usage": {
            "model": agents.model,
            "model_calls": 1,
            "input_tokens": answer.input_tokens,
            "output_tokens": answer.output_tokens,
        },
    }


def qualified_project(project, agents):
    def archived(key):
        return history(project.manager, lambda: project.session, {"action": "get", "run_id": key})

    def run_task(request, previous=None):
        start = monotonic()
        tools = []

        def call(host, op, args):
            result, tool = host_call(project, host, op, args)
            tools.append([host, tool])
            return result

        prepared = call("openclaw", "review", {"question": QUESTION})
        review = invoke_model(agents, "reviewer", QUESTION, prepared["passages"][0]["text"])
        review.update({key: prepared[key] for key in ("generation", "evidence_sha256")})
        offer = {
            "question": QUESTION,
            "request_id": request,
            "recipient": "team:hermes:reviewer",
            "review": review,
            "reader_model": agents.model,
        }
        if previous:
            offer["rerun_of"] = previous
        run = call("openclaw", "offer", offer)
        assert run["outcome"] == "offered"
        if not previous:
            project.restart()
            assert any(r["run_id"] == run["run_id"] for r in call("hermes", "inbox", {})["runs"])
        key = {"run_id": run["run_id"]}
        delivery = call("hermes", "receive", key)
        assert delivery["reviewer_quote"] == review["quote"]
        reader = invoke_model(agents, "reader", QUESTION, delivery["reviewer_quote"])
        result = call("hermes", "complete", {**key, "delivery_id": delivery["delivery_id"], **reader})
        assert result["outcome"] == "answered"
        wall = round((monotonic() - start) * 1000)
        details = archived(run["run_id"])
        evidence = test_result(project, details)
        final = history(
            project.manager, lambda: project.session, {"action": "attach", **key, "outcome": evidence}
        )
        source = history(
            project.manager,
            lambda: project.session,
            {"action": "source", **key, "step_id": final["steps"][-1]["step_id"], "source_index": 0},
        )
        assert source["status"] == "verified"
        return {
            "tools": tools,
            "wall_including_host_startup_ms": wall,
            "run": final,
            "source_excerpt": source,
        }

    before = run_task("before-correction")
    assert before["run"]["outcomes"][0]["status"] == "failed"
    project.remember("routing-v2", "My Atlas routing code is AX-745.")
    after = run_task("after-correction", before["run"]["run_id"])
    assert after["run"]["outcomes"][0]["status"] == "passed"
    assert before["run"]["source_ids"] == ["routing-v1"] and after["run"]["source_ids"] == ["routing-v2"]
    return before, after


def qualify_adapters(project):
    from atmem.agent_team.client import TeamClient

    sender = TeamClient.from_file(project.paths["openclaw"], "openclaw")
    results = []
    for host, agent in (("mcp", "observer"), ("pydantic-ai", "typed"), ("langgraph", "graph")):
        run = sender.call(
            "offer", {"question": QUESTION, "request_id": host, "recipient": "team:" + host + ":" + agent}
        )
        received, first = host_call(project, host, "receive", {"run_id": run["run_id"]})
        assert "AX-745" in received["passages"][0]["text"]
        res, last = host_call(
            project,
            host,
            "complete",
            {"run_id": run["run_id"], "delivery_id": received["delivery_id"], "quote": "AX-745"},
        )
        assert res["outcome"] == "answered"
        results.append(
            {
                "host": host,
                "tools": [first, last],
                "run_id": run["run_id"],
                "answer": "AX-745",
                "outcome": res["outcome"],
                "tool_selection": "deterministic fixture",
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="atmem-portable-project-") as root:
        os.environ["ATMEM_HOME"] = str(Path(root) / "atmem-home")
        project = Project(root)
        project.serve()
        try:
            for host in ("openclaw", "hermes", "mcp", "pydantic-ai", "langgraph"):
                project.bind(host)
            agents = LocalAgents()
            agents.ensure_available()
            before, after = qualified_project(project, agents)
            print("Real OpenClaw / Hermes tool pairs and JUnit transition passed.", flush=True)
            adapters = qualify_adapters(project)
            from atmem.agent_team.client import TeamClient

            client = TeamClient.from_file(project.paths["hermes"], "hermes")
            revocation = project.manager.evidence_service().revoke(
                project.owner, principal_id="team:hermes:reviewer"
            )
            try:
                client.call("receive", {"run_id": before["run"]["run_id"]})
            except PermissionError:
                assert revocation
            else:
                raise AssertionError("Revoked recipient accessed the run")
            result = {
                "model_digest": MODEL_DIGEST,
                "openclaw": subprocess.check_output(["openclaw", "--version"], text=True).strip(),
                "hermes": subprocess.check_output(
                    ["git", "-C", str(Path.home() / ".hermes/hermes-agent"), "rev-parse", "HEAD"], text=True
                ).strip(),
                "packages": {p: version(p) for p in ("mcp", "langgraph", "pydantic-ai-slim")},
                "broker_reopened_between_offer_and_receive": True,
                "revoked_host": "denied",
                "original": before,
                "corrected": after,
                "adapters": adapters,
            }
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            if args.screenshot:
                from tools.team_qualification.browser import verify_dashboard

                verify_dashboard(project, after["run"]["run_id"], args.screenshot)
        finally:
            project.close()


if __name__ == "__main__":
    main()

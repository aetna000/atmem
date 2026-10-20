import ast
import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from benchmarks.code_replay.external_qualification import worker_command
from benchmarks.code_replay.grade import write_new_tree
from benchmarks.code_replay.public_test_bridge import patch_bootstrap, server_bootstrap


def load(monkeypatch, name, filename):
    spec = importlib.util.spec_from_file_location(name, Path("benchmarks/code_replay") / filename)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.setitem(sys.modules, "atmem_native_tree", SimpleNamespace(write_new_tree=write_new_tree))
    public = load(monkeypatch, "atmem_public_validation", "public_test_worker.py")
    patch = load(monkeypatch, "atmem_patch_fixture", "public_patch_worker.py")
    helpers = SimpleNamespace(pytest_arguments=public.pytest_arguments, worker_command=worker_command)
    monkeypatch.setitem(sys.modules, "atmem_public_test_helpers", helpers)
    mcp = load(monkeypatch, "atmem_test_mcp_fixture", "public_test_mcp.py")
    return public, patch, helpers, mcp


def test_patch_statistics_use_nul_paths_not_shell_or_loose_text(modules):
    _, patch, _, _ = modules
    assert patch.patch_paths(b"1\t1\tsrc/marshmallow/a.py\0") == ["src/marshmallow/a.py"]
    assert patch.patch_paths(b"1\t0\ttests/with space.py\0") == ["tests/with space.py"]


@pytest.mark.parametrize("bad", [b"1\t0\t../../private.py\0", b"1\t0\t.git/config\0", b"-\t-\tsrc/marshmallow/a.py\0", b"1\t0\tREADME.md\0", b"1\t0\t\0old\0new\0"])
def test_unsafe_binary_renamed_and_out_of_scope_paths_refused(modules, bad):
    with pytest.raises(ValueError):
        modules[1].patch_paths(bad)


@pytest.mark.parametrize("changed", [False, True])
def test_submitted_patch_is_applied_to_private_base_copy_not_agent_workspace(modules, monkeypatch, tmp_path, capsys, changed):
    public, patch, _, _ = modules
    raw = b"value = 1\n"
    payload = {"format": "atmem-public-patch-tests-v1", "base_commit": public.BASE,
        "public_base_files_base64": {"src/marshmallow/a.py": base64.b64encode(raw).decode()},
        "public_base_modes": {"src/marshmallow/a.py": "100644"},
        "patch": "diff --git a/src/marshmallow/a.py b/src/marshmallow/a.py\n--- a/src/marshmallow/a.py\n+++ b/src/marshmallow/a.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n" if changed else "",
        "pytest": {"paths": ["tests"], "keyword": None, "max_failures": 0}}
    monkeypatch.setattr(patch, "Path", lambda _: tmp_path / "public-patch")
    def public_main():
        request = json.load(sys.stdin)
        candidate = base64.b64decode(request["candidate_files_base64"]["src/marshmallow/a.py"])
        assert candidate == (b"value = 2\n" if changed else raw)
        print(json.dumps({"exit_code": 0, "output_base64": ""}))
    monkeypatch.setattr(public, "main", public_main)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    patch.main()
    result = json.loads(capsys.readouterr().out)
    assert "not_current_agent_worktree" in result["assurance"]
    assert "tested_candidate_files_base64" in result


@pytest.mark.parametrize("arguments", [{"root": "/private"}, {"patch": "x" * 262145}, {"paths": ["tests/../../private"]}, {"max_failures": True}])
def test_mcp_request_cannot_select_authority_paths_or_unbounded_job(modules, arguments):
    with pytest.raises(ValueError):
        modules[3].options(arguments)


def test_tool_displays_bounded_output_but_retains_full_result_and_no_mutation_tools(modules, monkeypatch):
    _, _, helpers, mcp = modules
    raw = b"PUBLIC_TEST_OUTPUT\n" * 1000
    backend = {"exit_code": 0, "worker": {"exit_code": 1, "original_git_object_store_removed": True,
        "evaluator_material_received": False, "output_base64": base64.b64encode(raw).decode(), "output_truncated": False,
        "patch_sha256": __import__("hashlib").sha256(b"").hexdigest(), "candidate_sha256": "a" * 64,
        "tested_candidate_files_base64": {"source.py": "full bytes never padded into model response"}}}
    calls = []
    helpers.execute_worker = lambda *args: calls.append(args) or backend
    class Evidence:
        def __init__(self, *args, **kwargs): self.events = []
        def capture(self, **kwargs): self.events.append(kwargs); return {"object_id": "fixture-object"}
    monkeypatch.setattr(mcp, "ReplayEvidence", Evidence)
    preset = {"image": "swebench/sweb.eval.x86_64.fixture@sha256:" + "a" * 64, "worker_source": "pass", "worker_sha256": __import__("hashlib").sha256(b"pass").hexdigest(),
        "source": {"base_commit": "b" * 40, "files_base64": {}, "modes": {}}, "run_id": "fixture-public-tests", "evidence_root": "fixture-root"}
    server = mcp.PublicTestMCP(preset)
    answer = server.run_tests({})
    assert answer["status"] == "executed" and answer["test_exit_code"] == 1
    assert answer["display_truncated"] and len(answer["output_tail"].encode()) == 12000
    assert server.evidence.events[-1]["payload"]["result"] == backend
    assert len(calls) == 1 and "tested_candidate_files_base64" not in answer
    assert [tool["name"] for tool in server._tool_definitions()] == ["run_public_tests"]
    assert server._call_tool(8, "remember", {})["error"]["code"] == -32602
    server.calls = 20
    assert server._call_tool(9, "run_public_tests", {})["error"]["code"] == -32602
    refusal = server.handle({"jsonrpc": "2.0", "id": 11, "method": "tools/call",
        "params": {"name": "run_public_tests", "arguments": {"root": "/not-authorized"}}})
    assert refusal["error"]["code"] == -32602
    assert [row["kind"] for row in server.evidence.events[-2:]] == ["public_tests.mcp_request", "public_tests.mcp_response"]
    def fail(*args, **kwargs): raise RuntimeError("private detail must not be reflected")
    server.calls = 0
    server.record = fail
    error = server._call_tool(10, "run_public_tests", {})
    assert error["error"]["code"] == -32603 and "private detail" not in json.dumps(error)
    assert len(calls) == 1  # evidence failure before dispatch fails closed


def test_bootstraps_have_python39_grammar_and_no_duplicated_public_source_in_argv():
    source = patch_bootstrap()
    ast.parse(source, feature_version=(3, 9))
    assert "public_patch_worker.py" in source and "atmem_public_validation" in source
    server = server_bootstrap("/dev/shm/operator-only/public-preset.json")
    ast.parse(server, feature_version=(3, 9))
    assert "PublicTestMCP(json.loads(Path(" in server
    assert len(server.encode()) < 60000


def test_explicit_local_image_binding_does_not_accept_other_images():
    image='sha256:'+'a'*64
    program=server_bootstrap('/private/preset.json',local_image_id=image,result_transport='lzma-v2',compact_argv=True)
    tree=ast.parse(program,feature_version=(3,9))
    loop=next(n for n in tree.body if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple))
    helper=next(source for name,source in ast.literal_eval(loop.iter) if name=='atmem_public_test_helpers')
    namespace={};exec(helper,namespace)
    name='atmem-reference-control-'+'b'*32
    command=namespace['worker_command'](image,name,'print(1)')
    assert image in command and command[command.index('--network')+1]=='none'
    assert 'exact bounded operator program identity required' in command[-1]
    for bad in ['sha256:'+'c'*64,'mutable:tag','swebench/sweb.eval.x86_64.fixture@sha256:'+'d'*64]:
        with pytest.raises(ValueError):namespace['worker_command'](bad,name,'')
    ast.parse(patch_bootstrap(result_transport='lzma-v2'),feature_version=(3,9))
    with pytest.raises(ValueError):server_bootstrap('/private/preset',local_image_id='mutable:tag')

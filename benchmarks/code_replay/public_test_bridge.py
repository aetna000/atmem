"""Frozen operator bootstraps for common public tests, never private grading."""
import ast
import re
from pathlib import Path

from benchmarks.code_replay.public_test_control import public_modules, public_task_settings
from benchmarks.code_replay.windows_transport import controller_source


def modules_bootstrap(modules, entry, *, settings=None):
    return ("import sys,types\n"
        "for name in ('benchmarks','benchmarks.code_replay'):\n"
        " module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module\n"
        "for name,source in " + repr(modules) + ":\n"
        " module=types.ModuleType(name);sys.modules[name]=module\n"
        + (" module.__dict__.update(" + repr(settings) + ")\n" if settings else "") +
        " exec(compile(source,name+'.py','exec'),module.__dict__)\n" + entry)


def patch_bootstrap(task=None, *, operator_registration=None, runtime_manifest=None, result_transport=None):
    if result_transport not in (None,'lzma-v2'):
        raise ValueError('explicit supported patch result transport required')
    root = Path(__file__).parent
    modules = public_modules(runtime_projection=runtime_manifest is not None) + [("atmem_public_validation", (root / "public_test_worker.py").read_text())]
    worker = (root / "public_patch_worker.py").read_text()
    settings = public_task_settings(task, operator_registration=operator_registration, runtime_manifest=runtime_manifest)
    final_globals=repr({"__name__":"__main__",**settings})
    if result_transport:
        modules.append(('benchmarks.code_replay.result_transport',(root/'result_transport.py').read_text()))
        final_globals=final_globals[:-1]+",'print':sys.modules['benchmarks.code_replay.result_transport'].result_printer(compression='lzma-v2')}"
    return modules_bootstrap(modules, "exec(compile(" + repr(worker) + ",'public_patch_worker.py','exec')," + final_globals + ")\n", settings=settings)


def server_bootstrap(preset_path, task=None, *, operator_registration=None, runtime_manifest=None,
                     local_image_id=None, result_transport=None, compact_argv=False):
    if type(compact_argv) is not bool:
        raise ValueError('explicit operator argv profile required')
    if result_transport not in (None,'lzma-v2'):
        raise ValueError('explicit supported public server result transport required')
    if local_image_id is not None and (type(local_image_id) is not str or re.fullmatch('sha256:[0-9a-f]{64}',local_image_id) is None):
        raise ValueError('exact operator-verified local image required')
    root = Path(__file__).parent
    def function(filename, name):
        source = (root / filename).read_text()
        matches = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(matches) != 1:
            raise ValueError("existing bounded helper required")
        return ast.get_source_segment(source, matches[0])
    helpers = (controller_source() + "\nimport re\nfrom pathlib import PurePosixPath\n"
        + function("external_qualification.py", "worker_command") + "\n"
        + function("public_test_worker.py", "pytest_arguments") + "\n")
    if local_image_id is not None:
        placeholder='swebench/sweb.eval.x86_64.operator-local@sha256:'+'0'*64
        helpers+=("\n_registry_worker_command=worker_command\n"
            "def worker_command(image,name,source):\n"
            " if image!="+repr(local_image_id)+":raise ValueError('image differs from qualified operator binding')\n"
            " placeholder="+repr(placeholder)+"\n"
            " command=_registry_worker_command(placeholder,name,source)\n"
            " command[command.index(placeholder)]=image\n"
            " return command\n")
    if compact_argv:
        helpers+=("\nimport lzma\nfrom hashlib import sha256\n"
            +function('program_transport.py','compact_program')+"\n"
            "_unpacked_worker_command=worker_command\n"
            "def worker_command(image,name,source):\n"
            " return _unpacked_worker_command(image,name,compact_program(source))\n")
    if result_transport:
        helpers+=("\n_plain_execute_worker=execute_worker\n"
            "def execute_worker(command,payload,name):\n"
            " import sys,base64\n"
            " row=_plain_execute_worker(command,payload,name)\n"
            " if row.get('exit_code')==0 and not row.get('reason') and row.get('raw_output_truncated') is False:\n"
            "  raw=base64.b64decode(row['raw_output_base64'],validate=True)\n"
            "  if len(raw)!=row['output_bytes']:raise ValueError('worker output byte count differs')\n"
            "  row['worker']=sys.modules['benchmarks.code_replay.result_transport'].decode_result(raw)\n"
            " return row\n")
    modules = [("atmem_public_test_helpers", helpers),
        ("benchmarks.code_replay.atmem_bridge", (root / "atmem_bridge.py").read_text()),
        ("benchmarks.code_replay.public_test_mcp", (root / "public_test_mcp.py").read_text())]
    if result_transport:
        modules.insert(0,('benchmarks.code_replay.result_transport',(root/'result_transport.py').read_text()))
    # Large public source maps stay in an operator-only preset file, not an
    # argv-sized literal or a model-visible tool description.
    entry = ("import json\nfrom pathlib import Path\n"
        "from benchmarks.code_replay.public_test_mcp import PublicTestMCP\n"
        "PublicTestMCP(json.loads(Path(" + repr(str(preset_path)) + ").read_text())).serve()\n")
    return modules_bootstrap(modules, entry, settings=public_task_settings(task, operator_registration=operator_registration, runtime_manifest=runtime_manifest))

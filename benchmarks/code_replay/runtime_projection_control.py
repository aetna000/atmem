"""Opt-in operator binding for source/runtime qualification, not a new grader."""
from hashlib import sha256
from pathlib import Path
import re

from benchmarks.code_replay.eligibility_binding import SOURCE_PROFILES


def projected_control_source(source, registration):
    bases = {}
    for identity, binding in registration["bindings"].items():
        repo = identity.rsplit("-", 1)[0].replace("__", "/")
        if (repo not in SOURCE_PROFILES or len(binding) != 2
            or re.fullmatch("[0-9a-f]{40}", binding[0]) is None
            or tuple(map(tuple, registration["source_profiles"][identity])) != SOURCE_PROFILES[repo]):
            raise ValueError("fixed operator base/source binding required")
        previous = bases.setdefault(binding[0], SOURCE_PROFILES[repo])
        if previous != SOURCE_PROFILES[repo]:
            raise ValueError("ambiguous base source scope")
    if not bases:
        raise ValueError("operator base bindings required")
    marker = '\nif __name__ == "__main__":\n'
    if source.count(marker) != 1:
        raise ValueError("review private worker main boundary")
    addition = (
        "\n# Explicit operator-only source/runtime projection v2.\n"
        "from benchmarks.code_replay.runtime_fixtures import tracked_projection\n"
        "from benchmarks.code_replay.source_policy import SourcePolicy\n"
        "PROJECTION_BASES = " + repr(bases) + "\n"
        "_strict_tracked_base = tracked_base\n"
        "RUNTIME_MANIFEST = None\n"
        "def tracked_base(base):\n"
        "    global RUNTIME_MANIFEST\n"
        "    if base not in PROJECTION_BASES:\n"
        "        raise ValueError('base outside operator projection registration')\n"
        "    roots, tests = PROJECTION_BASES[base]\n"
        "    listing = subprocess.check_output(['git','-C','/testbed','ls-tree','-r','-z',base])\n"
        "    _, RUNTIME_MANIFEST, summary = tracked_projection('/testbed',listing,\n"
        "        SourcePolicy(roots,test_roots=tests),writers_stopped=True)\n"
        "    return summary\n"
    )
    result = source.replace(marker, addition + marker)
    return result, {
        "format": "atmem-operator-source-runtime-projection-v2",
        "prior_worker_sha256": sha256(source.encode()).hexdigest(),
        "projected_worker_sha256": sha256(result.encode()).hexdigest(),
        "registration_source": addition, "base_profiles": bases,
        "upstream_grading_logic_changed": False,
    }


def projection_modules():
    directory = Path(__file__).parent
    return [
        ("benchmarks.code_replay.source_policy", (directory / "source_policy.py").read_text()),
        ("benchmarks.code_replay.runtime_fixtures", (directory / "runtime_fixtures.py").read_text()),
        ("benchmarks.code_replay.result_transport", (directory / "result_transport.py").read_text()),
    ]


def projection_program(source, *, diagnostic=False):
    """Self-contained trusted-worker program; receives no model-selected policy."""
    if type(diagnostic) is not bool:
        raise ValueError("operator diagnostic selector must be boolean")
    ending = ("import json\n"
        "job=json.load(sys.stdin)\n"
        "summary=control['tracked_base'](job['base_commit'])\n"
        "emit(json.dumps({'instance_id':job['instance_id'],'summary':summary,\n"
        " 'runtime_manifest':control['RUNTIME_MANIFEST'],'repo_code_executed':False,\n"
        " 'tests_run':False,'model_calls':0}),flush=True)\n") if diagnostic else ""
    namespace = {"__name__": "atmem_projection_diagnostic" if diagnostic else "__main__"}
    return (
        "import sys,types\n"
        "for name in ('benchmarks','benchmarks.code_replay'):\n"
        " module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module\n"
        "for name,source in " + repr(projection_modules()) + ":\n"
        " module=types.ModuleType(name);sys.modules[name]=module\n"
        " exec(compile(source,name+'.py','exec'),module.__dict__)\n"
        "emit=sys.modules['benchmarks.code_replay.result_transport'].result_printer()\n"
        "control=" + repr(namespace) + "\n"
        "control['print']=emit\n"
        "exec(compile(" + repr(source) + ",'projected_control.py','exec'),control)\n"
        + ending
    )

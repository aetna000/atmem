"""No-inference dependency/import preflight for every released grading config."""
import argparse
from collections import Counter
import hashlib
from importlib import import_module, metadata
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, '/Volumes/AtMemDolphin/upstream')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from packaging.requirements import Requirement
    from harness.submission import read_release
    from graders.explicit import validate_checks
    from graders.markdown_bullets import matches_bullets
    from benchmarks.dolphinbench.gateway import save_new

    versions = {}
    for package in ('pyyaml', 'packaging', 'tiktoken', 'markdown-it-py'):
        versions[package] = metadata.version(package)
    app = json.loads(subprocess.check_output([
        '/private/tmp/atmem-dolphin-apps-v3-20261021/bin/python', '-I', '-c',
        'import json;from importlib.metadata import version;print(json.dumps({p:version(p) for p in ("pydantic","mcp")}))'], text=True))
    for line in Path('/Volumes/AtMemDolphin/upstream/requirements.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        requirement = Requirement(line)
        installed = {**versions, **app}[requirement.name.lower()]
        assert installed in requirement.specifier, (requirement.name, installed)
    for module in ('explicit', 'judge_recording', 'llm_judge', 'markdown_bullets', 'mechanical'):
        import_module('graders.' + module)
    assert matches_bullets('- one\n- two', {'exact_items': 2, 'only_bullets': True})
    assert not matches_bullets('not bullets', {'exact_items': 2, 'only_bullets': True})
    checks, tasks = Counter(), 0
    for persona in read_release(Path('/Volumes/AtMemDolphin/upstream')).values():
        for spec in persona['tests']:
            config = spec['grade']['config']
            assert config['check_version'] == 2
            validate_checks(config['assertions'])
            checks.update(c['type'] for c in config['assertions'])
            tasks += 1
    assert tasks == 600
    record = metadata.distribution('markdown-it-py').read_text('RECORD')
    receipt = {'format': 'complete-grader-environment-preflight-v1', 'interpreter': sys.executable,
        'local_versions': versions, 'simulated_app_versions': app, 'validated_task_configs': tasks,
        'check_types': dict(checks), 'markdown_parser_smoke': True,
        'markdown_distribution_record_sha256': hashlib.sha256(record.encode()).hexdigest(),
        'inference_or_grading_calls': 0, 'prompts_and_rubrics_changed': False}
    save_new(args.output, receipt)
    print(json.dumps({'passed': True, 'validated_task_configs': tasks,
                      'markdown_parser': versions['markdown-it-py'], 'inference_calls': 0}), flush=True)


if __name__ == '__main__':
    main()

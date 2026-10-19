"""Four matched read-tool configurations; one attempt each, no tuning loop."""
import json
import os
from pathlib import Path


def main(controlled=False):
    name = 'click-pruner-controlled-20261020' if controlled else 'click-pruner-fourway-20261020'
    root = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks') / name
    os.environ['ATMEM_HOME'] = str(root / 'atmem-home')
    from benchmarks.code_replay import claude_click_study as study
    gpu = Path(os.environ.get('ATMEM_PRUNER_GPU_ROOT', '/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swe-pruner-gpu-20261020-fallback'))
    if not gpu.is_dir():
        gpu = gpu.with_name('swe-pruner-gpu-20261020')
    qualification = json.loads((gpu / 'qualification.json').read_text())
    if (qualification['runtime']['attention'] != 'flash_attention_2' or qualification['runtime']['adaptations']
            or len(qualification['cases']) != 2):
        raise ValueError('real-source unmodified GPU qualification required before dispatch')
    endpoint = json.loads((gpu / 'endpoint.json').read_text())
    command = ['ssh', '-T', '-i', str(gpu / 'ssh_key'), '-o', 'IdentitiesOnly=yes',
               '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o',
               'UserKnownHostsFile=' + str(gpu / 'known_hosts'), '-o', 'ConnectTimeout=10',
               '-p', str(endpoint['ssh_port']), 'root@' + endpoint['ssh_host'],
               '/venv/main/bin/python -u /workspace/atmem-swe-pruner/server.py']
    study.ROOT = root
    study.RAM = Path('/Volumes/AtMemReplayRAM-20261017-Localization') / name
    study.RAM.mkdir(mode=0o700, exist_ok=True)
    study.WHEEL = Path('/private/tmp/atmem-code-curation-acceptance-20261019/atmem-2.3.8-py3-none-any.whl')
    study.WHEEL_SHA = '0b94af55cf202c4624f47859c122af8dc51491af7b172c0344912aa001d93533'
    study.RUN = name
    study.main(curated=True, require_graph_consult=False,
        protocol_path=Path(__file__).parents[2] / ('specs/043-click-historical-replay/pruner-controlled-20261020.md'
            if controlled else 'specs/043-click-historical-replay/pruner-fourway-20261020.md'),
        arms=('atmem', 'atmem_pruner') if controlled else ('native', 'cognee', 'atmem', 'atmem_pruner'),
        source_reader={'command': command, 'require_source_consult': controlled})


if __name__ == '__main__':
    main()

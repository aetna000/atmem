"""Stage an isolated byte-verified copy; never mutate the original benchmark."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil

from .readiness import pin, read, save, sha


def stage(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    home = source / 'v3-full-r2-product-home'
    baseline = source / 'campaign-atmem-v3-full-r2-20261021'
    memory = baseline / 'memory'
    # Keep originals closed/unchanged; canonical verification follows the copy.
    originals = {str(p): sha(p) for p in memory.glob('*/memory.db')}
    if len(originals) != 3:
        raise ValueError('Three original memory databases required')
    shutil.copytree(home, output / 'home')
    shutil.copytree(memory, output / 'memory')
    shutil.copytree(source / 'retrieval-2310-source-part-indexes', output / 'indexes')
    shutil.copytree(baseline / 'checkpoints', output / 'checkpoints')
    for path, expected in originals.items():
        persona = Path(path).parent.name
        if sha(path) != expected or sha(output / 'memory' / persona / 'memory.db') != expected:
            raise ValueError('Original or copied memory changed during staging')
    os.environ['ATMEM_HOME'] = str(output / 'home')
    from atmem.control.state import load_state, write_state
    for persona in ('morgan', 'alex', 'riley'):
        path = output / 'memory' / persona / 'state.json'
        state = load_state(path)
        prior = Path(state.control_dir)
        # Location metadata changes only; authority IDs and encrypted payloads
        # are preserved. Use the supported state serializer/digest, not hand edits.
        control = path.parent / 'control' / prior.name
        if not control.is_dir():
            raise ValueError('Copied control authority is absent')
        write_state(path, replace(state, control_dir=str(control)))
        config = control / 'generic-adapter.json'
        value = read(config)
        value['memory_db'] = str(path.parent / 'memory.db')
        config.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
        config.chmod(0o600)
    from .driver import AtMemHost
    verified = []
    for persona in ('morgan', 'alex', 'riley'):
        host = AtMemHost(output / 'memory', persona, memory_engine='context-v3')
        try:
            host.verify_checkpoint(read(output / 'checkpoints' / (persona + '.json')))
            verified.append(persona)
        finally:
            host.stop()
    save(output / 'staging.json', {'schema': 'dolphin-isolated-memory-copy-v1',
         'original_memory_files': [{'path': p, 'sha256': h} for p, h in originals.items()],
         'copied_memory_checkpoints_match': verified, 'source_home': str(home),
         'destination_home': str(output / 'home'), 'originals_modified': False,
         'location_metadata_rebased_with_product_serializer': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage(args.source, args.output)
    print(json.dumps({'staged': True, 'checkpoint_personas_verified': 3, 'model_calls': 0}))


if __name__ == '__main__':
    main()

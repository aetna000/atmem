"""Keep uncertain interactions and independent app evidence intact on restart."""
from pathlib import Path
import shutil

from .readiness import pin, read, save


class InteractionJournal:
    def __init__(self, directory, apps):
        self.directory = Path(directory)
        self.apps = apps
        # Intent is durable before entering the agent or app bridge.
        save(self.directory / 'intent.json', {'schema': 'dolphin-interaction-intent-v1',
             'state': str(Path(apps['env']['DOLPHINBENCH_STATE_PATH']).resolve()),
             'log': str(Path(apps['env']['DOLPHINBENCH_LOG_PATH']).resolve())})

    def snapshot(self, *, completed=False):
        artifacts = []
        for key, name in [('DOLPHINBENCH_STATE_PATH', 'state.json'),
                          ('DOLPHINBENCH_LOG_PATH', 'calls.jsonl')]:
            source = Path(self.apps['env'][key])
            if source.exists():
                target = self.directory / name
                # Snapshot only once: a second call cannot relabel prior evidence.
                with target.open('xb') as output, source.open('rb') as stream:
                    shutil.copyfileobj(stream, output)
                    output.flush()
                    import os
                    os.fsync(output.fileno())
                artifacts.append(pin(target))
        save(self.directory / 'outcome.json', {'completed': completed, 'artifacts': artifacts,
             'unknown_actions_must_not_be_replayed': not completed})


def protected_runner_class(base):
    class ProtectedRunner(base):
        def _apps(self, phase, persona, item_id, spec):
            workspace = self.directory / 'apps' / persona / ('ingestion' if phase == 'ingestion' else item_id)
            if phase == 'tests' and workspace.exists() and any(workspace.iterdir()):
                raise ValueError('Existing app evidence must be reconciled before setup; refusing log/state reset')
            return super()._apps(phase, persona, item_id, spec)
    return ProtectedRunner

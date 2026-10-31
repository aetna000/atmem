"""Hermes directory plugin binding for the AtMem action guard.

``stage(home)`` writes ``plugins/atmem-action-guard`` (this file as the plugin
entry plus a copy of ``atmem.action_guard``) so the host needs no AtMem import.
Enable it with ``plugins.enabled: [atmem-action-guard]``. Hooks used:

- ``pre_llm_call``: classify the request; inject the request-specific route note.
- ``pre_tool_call``: refuse local detours around a configured connected app and,
  once per write tool, hold the write for a remembered-constraints check.
- ``post_tool_call``: record accepted/failed writes and verified route failures.
- ``transform_llm_output``: append an explicit NOT COMPLETED notice when an
  action was requested but no connected application confirmed a write; write
  one outcome record per turn.

Hermes has no stop hook for non-code turns, so the guard cannot force another
model step after a final answer; it reports the outcome instead.
"""
import json
import os
import shutil
from pathlib import Path

PLUGIN = 'atmem-action-guard'
MANIFEST = f'''name: {PLUGIN}
version: "1.0.0"
description: "AtMem deterministic action routing, commit checkpoint and completion check for connected application tools."
author: "AtMem"
provides_hooks:
  - pre_llm_call
  - pre_tool_call
  - post_tool_call
  - transform_llm_output
'''


def stage(home, *, settings=None):
    """Write the plugin into a Hermes home; returns its directory. Never overwrites."""
    target = Path(home) / 'plugins' / PLUGIN
    if target.exists():
        raise FileExistsError('AtMem action guard plugin is already staged: ' + str(target))
    target.mkdir(parents=True)
    (target / 'plugin.yaml').write_text(MANIFEST)
    shutil.copyfile(__file__, target / '__init__.py')
    shutil.copyfile(Path(__file__).parents[2] / 'action_guard.py', target / 'action_guard.py')
    (target / 'settings.json').write_text(json.dumps({'checkpoint': True, 'route_context': True,
                                                     **(settings or {})}, sort_keys=True))
    return target


def _load_policy():
    try:
        from . import action_guard as policy  # staged copy beside this file
    except ImportError:
        from atmem import action_guard as policy
    return policy


def _visible_tool_names():
    try:
        from tools.registry import registry
        return set(registry.get_all_tool_names())
    except Exception:
        return set()


class _Binding:
    def __init__(self, directory, policy):
        settings_path = directory / 'settings.json'
        settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
        home = Path(os.environ.get('HERMES_HOME') or directory.parents[1])
        state = Path(settings.get('state_dir') or home / '.atmem' / 'action-guard')
        self.records = state / 'outcomes.jsonl'
        self.route_context = settings.get('route_context', True)
        self.policy = policy
        self.guard = policy.ActionGuard(route_memory=policy.RouteMemory(settings.get('route_memory')
                                        or state / 'route-memory.json'), checkpoint=settings.get('checkpoint', True))

    def pre_llm_call(self, session_id='', user_message=None, is_first_turn=False, turn_id='', **_):
        text = user_message if isinstance(user_message, str) else json.dumps(user_message, default=str)
        self.guard.begin_turn(session_id, text, _visible_tool_names())
        context = self.guard.turn_context(session_id) if self.route_context else ''
        return {'context': context} if context else None

    def pre_tool_call(self, tool_name='', args=None, session_id='', **_):
        for name, _arguments in self.policy.unwrap(tool_name, args or {}):
            self.guard.observe_visible(session_id, [name])
        decision = self.guard.before_call(session_id, tool_name, args or {})
        if decision.action == 'block':
            return {'action': 'block', 'message': decision.message}
        return None

    def post_tool_call(self, tool_name='', args=None, result=None, session_id='', **_):
        self.guard.after_call(session_id, tool_name, args or {}, result)

    def transform_llm_output(self, response_text='', session_id='', turn_id='', **_):
        notice = self.guard.completion_notice(session_id)
        record = self.guard.finish(session_id)  # releases the finalized turn state
        record.update(session_id=session_id, turn_id=turn_id)
        try:
            self.records.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.records, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(descriptor, 'a') as output:
                output.write(json.dumps(record, sort_keys=True) + '\n')
        except OSError:
            pass
        return (response_text.rstrip() + '\n\n' + notice) if notice and response_text else None


def register(ctx):
    binding = _Binding(Path(__file__).resolve().parent, _load_policy())
    for hook in ('pre_llm_call', 'pre_tool_call', 'post_tool_call', 'transform_llm_output'):
        ctx.register_hook(hook, getattr(binding, hook))
    return binding

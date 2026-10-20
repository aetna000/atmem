"""Inspect delivered-line coverage of the agent's final patch, without reruns.

This is a post-run diagnostic, not an oracle for packing, proof of necessity,
training labels or a new correctness score. Omitted source ranges do not count.
"""
import argparse
import json
import os
from pathlib import Path
import re
from benchmarks.code_replay.swebench_pilot import vault


def supplied_lines(content):
    current, lines = None, {}
    for line in content.splitlines():
        header = re.match(r'\[AtMem (?:structure|existing test) (.+?):\d+-\d+;', line)
        if header:
            current = header[1]
            continue
        source = re.match(r'(\d+): (.*)', line)
        if current and source:
            lines[(current, int(source[1]))] = source[2]
    return lines


def replaced_lines(patch):
    current, old, lines = None, None, []
    for line in patch.splitlines():
        if line.startswith('diff --git '):
            current, old = None, None
        elif line.startswith('--- a/'):
            current = line[len('--- a/'):]
        elif line.startswith('@@ '):
            match = re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@', line)
            old = int(match[1]) if match else None
        elif current and old is not None:
            if line.startswith('-'):
                lines.append((current, old, line[1:])); old += 1
            elif line.startswith(' '):
                old += 1
    return lines


def compare(content, patch):
    supplied = supplied_lines(content)
    replaced = replaced_lines(patch)
    return {'rendered_source_lines': len(supplied), 'agent_replaced_old_lines': len(replaced),
            'exact_replaced_old_lines_supplied': sum(supplied.get((path, number)) == text for path, number, text in replaced),
            'replaced_locations': [{'path': path, 'line': number, 'supplied_exactly': supplied.get((path, number)) == text}
                                   for path, number, text in replaced]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = json.loads((args.root / 'results.json').read_text())
    if result['status'] not in {'completed', 'stopped'}:
        raise ValueError('terminal campaign required')
    manifest = json.loads((args.root / 'manifest.json').read_text())
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    service, principal = vault(args.root)
    rows = []
    for case in manifest['selected']:
        events = [event['envelope'] for event in service.inspect(principal, case['instance_id'])]
        for event in events:
            if event['event_type'] != 'trial.context_prepared':
                continue
            arm = event['payload']['arm']
            pack = json.loads(event['payload']['response']['result']['content'][0]['text'])
            captured = [e['payload'] for e in events if e['event_type'] == 'trial.captured' and e['payload']['arm'] == arm]
            if len(captured) != 1:
                continue
            terminal = next(row for row in result['rows'] if row['instance_id'] == case['instance_id'] and row['arm'] == arm)
            rows.append({'instance_id': case['instance_id'], 'arm': arm, 'task_pass': terminal.get('task_pass'),
                         **compare(pack['content'], captured[0]['patch']['patch'])})
    report = {'rows': rows, 'interpretation': 'Post-run rendered-line diagnostic against agent patches, not reference patches; '
        'does not establish minimal necessary evidence or prove that a supplied line was used. '
        'No input to packing, training or the frozen confirmation profile.'}
    (args.root / 'context-line-diagnostic.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()

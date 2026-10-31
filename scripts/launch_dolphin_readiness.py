"""Launch only pinned installed-product pilot/full configuration; no model override."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.dolphinbench.readiness import admit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--stage', choices=('pilot', 'full'), default='pilot')
    parser.add_argument('--confirm-full-run', action='store_true')
    parser.add_argument('--resume-epoch', action='store_true')
    parser.add_argument('--canary', help='run one frozen-selection task (pilot admission) into a fresh output')
    args = parser.parse_args()
    if args.canary and (args.stage != 'pilot' or args.resume_epoch):
        parser.error('A canary uses pilot admission and a fresh output')
    if args.stage == 'full' and not args.confirm_full_run:
        parser.error('A full 600-task campaign requires explicit --confirm-full-run')
    condition = admit(args.condition, args.receipts, args.stage)
    if args.resume_epoch:
        if args.stage == 'full':
            from benchmarks.dolphinbench.full_recovery_020 import verify_epoch
        else:
            from benchmarks.dolphinbench.pilot_recovery import verify_epoch
        verify_epoch(args.output, args.condition)
    bindings = condition['bindings']
    root = Path(__file__).resolve().parents[1]
    bootstrap = ('import sys,runpy;sys.path.append(' + repr(bindings['controller_site']) + ');'
                 'import atmem,atbot;sys.path.insert(0,' + repr(str(root)) + ');'
                 'runpy.run_module("benchmarks.dolphinbench.pilot_readiness",run_name="__main__")')
    environment = {**os.environ, 'ATMEM_HOME': bindings['atmem_home'], 'PYTHONDONTWRITEBYTECODE': '1'}
    environment.pop('PYTHONPATH', None)
    subprocess.run([bindings['product_python'], '-I', '-u', '-c', bootstrap,
                    '--condition', str(args.condition.resolve()), '--receipts', str(args.receipts.resolve()),
                    '--output', str(args.output.resolve()), '--env-file', str(args.env_file.resolve()),
                    '--options', condition['inputs']['options']['path'], '--stage', args.stage,
                    *(['--resume-epoch'] if args.resume_epoch else []),
                    *(['--canary', args.canary] if args.canary else [])],
                   check=True, env=environment, cwd=root)


if __name__ == '__main__':
    main()

"""Run tests with installed AtMem pinned before pytest applies repo import paths."""
from pathlib import Path
import sys


def main():
    import atmem
    from atmem.adapters.hermes.service import HermesService
    import inspect
    root = Path(__file__).resolve().parents[1]
    installed = Path(atmem.__file__).resolve()
    service = Path(inspect.getsourcefile(HermesService)).resolve()
    if installed.is_relative_to(root) or service.is_relative_to(root):
        raise RuntimeError('Launch this helper with the installed interpreter and -I')
    print(f'Installed AtMem: {installed}', flush=True)
    print(f'Installed Hermes service: {service}', flush=True)
    import pytest
    raise SystemExit(pytest.main(['-o', 'pythonpath=', *sys.argv[1:]]))


if __name__ == '__main__':
    main()

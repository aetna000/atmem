"""One predeclared current-curation diagnostic; never auto-retry model trials."""
from hashlib import sha256
import os
from pathlib import Path


def main():
    root = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-curation-threeway-qualified-20261019')
    # Key paths are fixed at import: set the isolated home before product imports.
    # The first preparation failed this check with zero model dispatches; retain it.
    os.environ['ATMEM_HOME'] = str(root / 'atmem-home')
    from benchmarks.code_replay import claude_click_study as study
    study.ROOT = root
    study.RAM = Path('/Volumes/AtMemReplayRAM-20261017-Localization/curation-threeway-qualified-20261019')
    study.RAM.mkdir(mode=0o700, exist_ok=True)
    study.WHEEL = Path('/private/tmp/atmem-code-curation-acceptance-20261019/atmem-2.3.8-py3-none-any.whl')
    study.WHEEL_SHA = '0b94af55cf202c4624f47859c122af8dc51491af7b172c0344912aa001d93533'
    if sha256(study.WHEEL.read_bytes()).hexdigest() != study.WHEEL_SHA:
        raise ValueError('qualified current artifact changed')
    study.RUN = 'click-curation-threeway-20261019'
    study.main(curated=True, require_graph_consult=False,
               protocol_path=Path(__file__).parents[2] / 'specs/043-click-historical-replay/curation-threeway-20261019.md')


if __name__ == '__main__':
    main()

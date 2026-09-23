# Quickstart: Memory Integrity Qualification

This is the planned clean-room workflow. Exact fork URL, commit, wheel digest,
seed and run ID are filled from the implemented manifest before publication.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install atmem==2.3.5
python -m pip install -r requirements.lock
python -m pytest
python -m runner.run --system atmem --attacks all --trials 1
python -m runner.run --system atmem --attacks all --trials 100
```

Then regenerate and validate the report using the benchmark fork's documented
report/publication commands. A canonical run must fail readiness if AtMem is
editable, the benchmark tree is dirty, the attack/configuration digest differs,
trial identities are missing or duplicated, or checksums do not verify.

Never point the adapter at `~/.atmem` and never load a developer `.env` file.


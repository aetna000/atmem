# Your first memory

## Prerequisites
Use Python 3.10–3.13 in a virtual environment. This exercise uses synthetic data,
does not contact a model, and does not enable agent injection.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install atmem==2.3.5
```

On Windows, activate with `.venv\Scripts\activate` instead.

## Store and retrieve
Run this Python example. Its temporary database disappears when the block finishes.

```python
from tempfile import TemporaryDirectory
from pathlib import Path
from atmem import Memory

with TemporaryDirectory() as directory:
    memory = Memory(Path(directory) / "demo.db", auto_vectors=False)
    try:
        memory.remember("demo-user", "My preferred editor is Vim.", session_id="demo")
        records = memory.recall("demo-user", "preferred editor", limit=5)
        assert any("Vim" in record["content"] for record in records)
        assert memory.recall("other-user", "preferred editor") == []
        print("Memory found; another subject cannot retrieve it.")
    finally:
        memory.close()
```

Expected output: `Memory found; another subject cannot retrieve it.`
This demonstrates embedded memory retrieval, not proof that a model received context.
`auto_vectors=False` isolates the basic example; normal persistent use can keep
the default vector sidecar enabled.

## Open the dashboard
For a persistent local installation, outside this disposable example:

```bash
atmem init
atmem dashboard
```

Keep the Administrator temporary password printed by initialization, sign in and
change it. The dashboard is local, not the public documentation website.
See [accounts and evidence](evidence.md).

## Connect your agent
Choose [an integration](integrations.md). Start in shadow mode, verify identity,
capture and delivery readiness, then explicitly activate. Optional intelligence
setup is explained in [AtBot](atbot.md).

## If it fails
An import error usually means the active Python environment differs from the one
where you installed AtMem. Check `python -m pip show atmem`.
An empty result is not permission to broaden scope: inspect subject identity,
record lifecycle and [retrieval configuration](../retrieval-quality.md).

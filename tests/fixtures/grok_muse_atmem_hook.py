"""Only for isolated tests: use the fixture's key file, never the owner's key."""
import contextlib
import io
from pathlib import Path
import runpy
import sys

# Pin the same checkout as the parent test before importing any AtMem module.
# A global installed package may otherwise be loaded first; inserting the hook
# script's checkout later cannot replace an already imported package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import atmem.core.keys

atmem.core.keys.DEFAULT_KEY_PATH = Path(sys.argv.pop(1))
script = sys.argv.pop(1)
data = sys.stdin.buffer.read()
Path("code-hook-input.json").write_bytes(data)
sys.stdin = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
output = io.StringIO()
errors = io.StringIO()
try:
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        runpy.run_path(script, run_name="__main__")
finally:
    Path("code-hook-output.json").write_text(output.getvalue(), encoding="utf-8")
    Path("code-hook-stderr.txt").write_text(errors.getvalue(), encoding="utf-8")
    print(output.getvalue(), end="")
    print(errors.getvalue(), end="", file=sys.stderr)

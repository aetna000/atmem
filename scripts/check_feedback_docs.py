#!/usr/bin/env python3
"""Compare documented governed tools/protocols with executable inventory."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atmem.mcp.governed import GUARDED_TOOLS, PROPOSAL_TOOLS, TOOLS, VERSIONS


def check(text):
    errors = []
    try:
        inventory = text.split("<!-- governed-tool-inventory:start -->", 1)[1].split("<!-- governed-tool-inventory:end -->", 1)[0]
    except IndexError:
        return ["missing explicit tool inventory"]
    documented = re.findall(r"^\| `([^`]+)` \|", inventory, re.MULTILINE)
    actual = {tool["name"] for tool in TOOLS+GUARDED_TOOLS+PROPOSAL_TOOLS}
    if len(documented) != len(set(documented)) or set(documented) != actual:
        errors.append("tool inventory differs from implemented tools")
    if any(version not in text for version in VERSIONS):
        errors.append("missing supported protocol version")
    for boundary in ("local stdio", "outside this server", "not automatically admitted", "Owner", "unknown"):
        if boundary not in text:
            errors.append("missing documented boundary: "+boundary)
    if "not a released" not in text or "remaining" not in text and "remain" not in text:
        errors.append("missing development/remaining-work status")
    return errors


def main():
    errors = check((ROOT/"docs/governed-rag-and-mcp.md").read_text())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Governed tool inventory, protocol versions and documented boundaries match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

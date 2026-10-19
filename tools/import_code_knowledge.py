"""Reproduce the narrow licensed code-query import from a pinned Cognee checkout.

This is a mechanical source incorporation, not a runtime dependency or download.
Only pure snapshot/query algorithms and the textual renderer are retained.
"""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess


PIN = "f154b32a9e544dac73e7ddf2010327cf9988edcd"
QUERY = "cognee/modules/retrieval/code_retriever.py"
DIAGRAM = "cognee/modules/retrieval/code_graph_diagram.py"
ENOLA = "cognee/tasks/code_graph/enola.py"
HELPERS = {
    "_json_key", "_normalize_value", "_normalize_properties", "_as_strings", "_bounded_int",
    "_offset", "_confidence", "_optional_bool", "_direction", "_node_type", "_node_types",
    "_scalar_text", "_short_names", "_match_tier",
}
CONSTANTS = {
    "CODE_NODE_TYPES", "_KIND_BY_TYPE", "_TYPE_BY_KIND", "_OPERATIONS",
    "_ARCHITECTURE_DEFAULT_TYPES", "_ARCHITECTURE_SKIPPED_EDGE_TYPES", "_TYPE_SYMBOL_KINDS",
    "_CODE_EXTENSIONS", "_MISSING", "_INTERNAL_EDGE_PROPERTIES",
}
HEADER = f'''# Copyright 2024 Topoteretes UG. (haftungsbeschränkt).
# SPDX-License-Identifier: Apache-2.0
# Incorporated from Cognee {PIN}; modified by AtMem.
# Mechanical modifications: remove backend/cache/LLM integration and use an
# explicitly supplied in-memory authorized snapshot. See third_party/cognee/.
'''


def source(checkout: Path, path: str) -> str:
    return subprocess.run(["git", "-C", str(checkout), "show", f"{PIN}:{path}"],
                          check=True, capture_output=True, text=True).stdout


def transform(raw: str) -> str:
    tree = ast.parse(raw)
    # Preserve upstream spelling: Python 3.12's ast.unparse can introduce
    # PEP-701 f-strings that no longer parse on supported Python 3.10/3.11.
    body = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            body.append(node)
        elif isinstance(node, ast.ImportFrom) and not (node.module or "").startswith("cognee"):
            body.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in CONSTANTS for t in node.targets):
            body.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in HELPERS:
            if node.name in {'_normalize_value', '_scalar_text'}:
                # Preserve original conversion/formatting, adding an optional
                # constructor-local memo only for explicitly shared metadata.
                original = ast.get_source_segment(raw, node)
                original = original.replace('def ' + node.name + '(', 'def ' + node.name + '_uncached(', 1)
                adapter = 'normalize_shared' if node.name == '_normalize_value' else 'scalar_shared'
                body.append(original + '\n\ndef ' + node.name + '(value):\n    return ' + adapter
                            + '(value, ' + node.name + '_uncached)\n')
            else:
                body.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "_CodeGraphSnapshot":
            body.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "CodeRetriever":
            members = [m for m in node.body if not isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                       or m.name not in {"_snapshot", "get_retrieved_objects"}]
            body.append("class CodeRetriever:\n" + "\n\n".join(
                "\n".join(raw.splitlines()[
                    min([m.lineno] + [d.lineno for d in getattr(m, "decorator_list", [])]) - 1:m.end_lineno])
                for m in members) + '''
    def execute(self, nodes, edges, query="", *, shared_metadata=()):
        with shared_metadata_scope(shared_metadata):
            snapshot = _CodeGraphSnapshot(nodes, edges)
        result = getattr(self, "_" + self.operation)(snapshot, query)
        if self.diagram_format is not None:
            result["diagram"] = render_result_diagram(result, self.diagram_format)
        return result
''')
    additions = '''
from .code_graph_diagram import DIAGRAM_FORMATS, render_result_diagram
from ..code.normalization import shared_metadata_scope, normalize_shared, scalar_shared
class CodeSearchValidationError(ValueError):
    pass
class CodeSeedNotFoundError(CodeSearchValidationError):
    pass
'''
    insertion = next((i for i, node in enumerate(body) if not isinstance(node, (ast.Import, ast.ImportFrom))), len(body))
    body[insertion:insertion] = [additions]
    result = HEADER + '# Additional AtMem adapter: construction-local shared-metadata work reuse; query algorithms unchanged.\n' + "\n\n".join(
        node if isinstance(node, str) else ast.get_source_segment(raw, node) for node in body) + "\n"
    ast.parse(result, feature_version=(3, 10))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    vendor = root / "atmem/knowledge/_vendor"
    legal = root / "third_party/cognee"
    raw = source(args.checkout, QUERY)
    diagram = source(args.checkout, DIAGRAM)
    enola_raw = source(args.checkout, ENOLA)
    enola_parts = []
    for node in ast.parse(enola_raw).body:
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {
                "_ENOLA_ID_LENGTH", "_HEX_DIGITS", "_RELATION_TYPE_KEYS", "_RELATION_TARGET_KEYS"}
                for t in node.targets)) or (isinstance(node, ast.FunctionDef) and node.name in {
                    "is_enola_id", "relation_target_id", "normalize_relation", "_synthesize_insight_facts"}):
            part = ast.get_source_segment(enola_raw, node)
            if isinstance(node, ast.FunctionDef) and node.name == "_synthesize_insight_facts":
                before = 'open(insights_path, "r", encoding="utf-8")'
                if part.count(before) != 1:
                    raise ValueError("review upstream insight artifact access")
                part = part.replace(before, 'insights_path.open("r", encoding="utf-8")')
            enola_parts.append(part)
    rendered = {
        vendor / "__init__.py": '"""Licensed pure algorithms; callers must authorize inputs first."""\n',
        vendor / "code_retriever.py": transform(raw),
        vendor / "code_graph_diagram.py": HEADER + diagram,
        vendor / "enola_contract.py": HEADER + "from typing import Any\nfrom pathlib import Path\nimport json\nimport logging\nlogger = logging.getLogger(__name__)\n\n" + "\n\n".join(enola_parts) + "\n",
        legal / "LICENSE": source(args.checkout, "LICENSE"),
        legal / "NOTICE.md": source(args.checkout, "NOTICE.md"),
    }
    inventory = {
        "upstream": "https://github.com/topoteretes/cognee", "revision": PIN,
        "license": "Apache-2.0", "source_sha256": {
            QUERY: sha256(raw.encode()).hexdigest(), DIAGRAM: sha256(diagram.encode()).hexdigest(),
            ENOLA: sha256(enola_raw.encode()).hexdigest()},
        "changes": ["AST-selected pure helpers, snapshot and query methods", "backend/TTL cache removed",
                    "exception base changed to ValueError", "explicit snapshot execute boundary added",
                    "renderer retained", "upstream insight conversion retained; open adapted to read-only in-memory artifact.open",
                    "explicit shared metadata may reuse normalization/formatting during snapshot construction only; no cross-query cache",
                    "AtMem wrapper must enforce scope, freshness, storage and budgets"],
        "parity_claim": False,
    }
    rendered[legal / "import-manifest.json"] = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    for path, content in rendered.items():
        if args.check:
            if not path.is_file() or path.read_text() != content:
                raise SystemExit(f"import differs: {path.relative_to(root)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print("Pinned source import verified" if args.check else "Pinned pure source incorporated; no parity claim")


if __name__ == "__main__":
    main()

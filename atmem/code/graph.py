"""Optional Python syntax index, stored with the encrypted canonical database."""

from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path
import subprocess
import re

from atmem.code.application import CodeApplication, digest
from atmem.code.identity import repository_key
from atmem.extract.validation import screen_content


INDEX_VERSION = "python-ast-v1"
_EXCLUDED = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", "vendor"}
_TEXT_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".c", ".h", ".cpp", ".cs", ".rb", ".swift", ".md", ".txt", ".json", ".toml", ".yaml", ".yml"}


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False, timeout=10)
    if result.returncode:
        raise ValueError("code graph requires a Git repository")
    return result.stdout.decode("utf-8", errors="strict").strip()


class _Symbols(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.stack: list[str] = []
        self.nodes: list[dict] = []

    def _definition(self, node, kind: str) -> None:
        qualified = ".".join([*self.stack, node.name])
        self.nodes.append({"path": self.path, "symbol": qualified, "kind": kind,
                           "line": node.lineno, "end_line": node.end_lineno})
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node) -> None:
        self._definition(node, "function")

    def visit_AsyncFunctionDef(self, node) -> None:
        self._definition(node, "async_function")

    def visit_ClassDef(self, node) -> None:
        self._definition(node, "class")

    def visit_Import(self, node) -> None:
        for alias in node.names:
            self.nodes.append({"path": self.path, "symbol": alias.name, "kind": "import", "line": node.lineno})

    def visit_ImportFrom(self, node) -> None:
        for alias in node.names:
            self.nodes.append({"path": self.path, "symbol": "." * node.level + (node.module or "") + "." + alias.name,
                               "kind": "import", "line": node.lineno})

    def visit_Call(self, node) -> None:
        target = ast.unparse(node.func) if isinstance(node.func, (ast.Name, ast.Attribute)) else ""
        if target:
            self.nodes.append({"path": self.path, "symbol": target, "kind": "call_reference", "line": node.lineno,
                               "caller": ".".join(self.stack), "resolution": "syntax_only"})
        self.generic_visit(node)


class CodeGraph:
    def __init__(self, application: CodeApplication, project_id: str) -> None:
        self.app, self.project = application, project_id
        self.app.authorize(project_id)

    def _root(self, root: str) -> Path:
        path = Path(root).expanduser().resolve(strict=True)
        binding = self.app.store.code_project_binding(self.app.subject_id, repository_key(path))
        if binding is None or binding["project_id"] != self.project:
            raise PermissionError("repository is not bound to this project")
        return path

    def index(self, root: str, *, max_files: int = 5000) -> dict:
        path = self._root(root)
        if not self.app.settings(self.project)["graph_enabled"]:
            raise PermissionError("enable graph indexing in project settings first")
        names = _git(path, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
        if len(names) > max_files:
            raise ValueError("repository exceeds graph file budget")
        files, nodes, unsupported, rejected = {}, [], set(), []
        for name in sorted(set(names)):
            relative = Path(name)
            if not name or any(part in _EXCLUDED or part.startswith(".env") for part in relative.parts):
                continue
            if not screen_content(name, trusted=True).admissible:
                continue
            target = path / relative
            if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(path):
                continue
            if target.suffix != ".py":
                unsupported.add(target.suffix or "no_extension")
                if target.suffix not in _TEXT_EXTENSIONS:
                    continue
            if target.stat().st_size > 262144:
                rejected.append({"path": name, "reason": "file_budget"})
                continue
            content = target.read_bytes()
            try:
                text = content.decode("utf-8")
                if not screen_content(text, trusted=True).admissible:
                    rejected.append({"path": name, "reason": "secret_screen"})
                    continue
                tree = ast.parse(text, filename=name) if target.suffix == ".py" else None
            except (UnicodeDecodeError, SyntaxError):
                rejected.append({"path": name, "reason": "parse_error"})
                continue
            visitor = _Symbols(name)
            if tree is not None:
                visitor.visit(tree)
            else:
                visitor.nodes.append({"path": name, "symbol": name, "kind": "file", "line": 1,
                                      "language_support": "file_only"})
            file_digest = sha256(content).hexdigest()
            files[name] = file_digest
            nodes.extend({**node, "source_sha256": file_digest} for node in visitor.nodes)
        value = {"format": "atmem-code-graph-v1", "index_version": INDEX_VERSION,
                 "git_revision": _git(path, "rev-parse", "HEAD"), "branch": _git(path, "rev-parse", "--abbrev-ref", "HEAD"),
                 "files": files, "nodes": nodes, "unsupported_languages": sorted(unsupported), "rejected": rejected}
        self.app.store.put_code_document(self.app.subject_id, self.project, "graph", "current", value)
        return {"indexed_files": len(files), "symbols": len(nodes), "git_revision": value["git_revision"],
                "unsupported_languages": sorted(unsupported), "rejected": rejected, "index_sha256": digest(value)}

    def query(self, root: str, query: str = "", *, limit: int = 20) -> dict:
        path = self._root(root)
        if not 1 <= limit <= 100:
            raise ValueError("graph result limit must be between 1 and 100")
        if not self.app.settings(self.project)["graph_enabled"]:
            return {"status": "disabled", "nodes": []}
        value = self.app.store.code_document(self.app.subject_id, self.project, "graph", "current")
        if value is None:
            return {"status": "not_indexed", "nodes": []}
        branch_changed = (_git(path, "rev-parse", "HEAD") != value["git_revision"] or
                          _git(path, "rev-parse", "--abbrev-ref", "HEAD") != value["branch"])
        stale = []
        current_names = _git(path, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
        rejected_names = {row["path"] for row in value["rejected"]}
        additions = [name for name in current_names if Path(name).suffix in _TEXT_EXTENSIONS and name not in value["files"]
                     and name not in rejected_names and not any(part in _EXCLUDED or part.startswith(".env") for part in Path(name).parts)]
        for name, expected in value["files"].items():
            target = path / name
            if (target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(path)
                    or target.stat().st_size > 262144 or sha256(target.read_bytes()).hexdigest() != expected):
                stale.append(name)
        nodes = [] if branch_changed else [node for node in value["nodes"] if node["path"] not in stale
                                           and query.lower() in (node["symbol"] + " " + node["path"]).lower()]
        return {"status": "stale" if branch_changed or stale or additions else "current", "nodes": nodes[:limit],
                "indexed_revision": value["git_revision"], "stale_files": stale,
                "new_files": len(additions),
                "unsupported_languages": value["unsupported_languages"], "resolution": "Python syntax; dynamic calls unresolved"}

    def context(self, root: str, task: str, *, budget: int) -> dict:
        result = self.query(root, "", limit=100)
        if result["status"] != "current" or budget <= 0:
            return {"content": "", "evidence": None}
        terms = {term.lower() for term in re.findall(r"[A-Za-z_][A-Za-z0-9_./]*", task) if len(term) > 2}
        value = self.app.store.code_document(self.app.subject_id, self.project, "graph", "current")
        ranked = sorted(value["nodes"], key=lambda node: -sum(term in (node["symbol"] + " " + node["path"]).lower() for term in terms))
        chunks, files = [], {}
        for node in ranked:
            if not any(term in (node["symbol"] + " " + node["path"]).lower() for term in terms):
                continue
            text = f"[Code structure {node['path']}:{node['line']}; {node['source_sha256']}] {node['kind']}: {node['symbol']}\n"
            if len(("".join(chunks) + text).encode()) > budget:
                continue
            chunks.append(text)
            files[node["path"]] = node["source_sha256"]
        return {"content": "".join(chunks), "evidence": {"root": str(Path(root).resolve()), "files": files,
                                                                "revision": result["indexed_revision"]}}

"""Task-ranked, byte-bounded source evidence; no model, oracle or code execution.

Graph IDs stay in the protected generation. Human-facing references use source
locations and names. Excerpts never claim omitted code is complete.
"""
import ast
import base64
from collections import Counter
from hashlib import sha256
import math
from pathlib import PurePosixPath
import re

from atmem.knowledge.code.queries import graph_input
from atmem.knowledge._vendor.code_retriever import CodeRetriever
from atmem.knowledge.source_text import source_text

_STOP = set("a an and are as at be been both but by can could currently do does existing for from has have if in including instead into is it its must normally not of on or ordinary preserve rather should still than that the their then these this to use user value values when while with without".split())


def words(text):
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return {w.casefold() for w in re.findall(r"[^\W_]+", text) if len(w) > 2 and w.casefold() not in _STOP}


def _query_term_weights(task):
    """Keep query content distinct from Markdown subsection labels.

    No vocabulary is discarded. Literal fenced code, H1/H2 titles, standalone
    headings and terms repeated in body text retain their ordinary weight.
    """
    terms = words(task)
    content = []
    fence = None
    for line in task.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            content.append(line)
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}[ \t]*", line):
                fence = None
            continue
        if marker:
            delimiter = marker.group(1)
            fence = (delimiter[0], len(delimiter))
            content.append(line)
        elif not re.match(r"^ {0,3}#{3,6}(?:[ \t]+|$)", line):
            content.append(line)
    body_terms = words("\n".join(content))
    if not body_terms:
        return {term: 1.0 for term in terms}
    return {term: 1.0 if term in body_terms else 0.25 for term in terms}

def _query_source_locations(task, sources):
    """Resolve source-URL line hints against verified source only; never fetch."""
    from urllib.parse import unquote, urlsplit
    locations = {}
    for ordinal, match in enumerate(re.finditer(r"https?://[^\s<>()\"'`]+", task)):
        if ordinal >= 8:
            break
        value = match.group(0).rstrip(".,;:!?")
        if len(value) > 4096:
            continue
        try:
            parsed = urlsplit(value)
            if not parsed.netloc or parsed.username is not None or parsed.password is not None:
                continue
            path = unquote(parsed.path, errors="strict")
        except (ValueError, UnicodeError):
            continue
        if "\\" in path or "\x00" in path or any(part in {".", ".."} for part in path.split("/")):
            continue
        fragment = re.fullmatch(r"L([1-9]\d{0,8})(?:-L?([1-9]\d{0,8}))?", parsed.fragment)
        if fragment is None:
            continue
        first = int(fragment.group(1)); last = int(fragment.group(2) or first)
        matches = [name for name in sources if path.endswith("/" + name)]
        if not matches:
            continue
        name = max(matches, key=lambda name: (len(name), name))
        if not 1 <= first <= last <= len(sources[name]):
            continue
        span = (first, last)
        if span not in locations.setdefault(name, []):
            locations[name].append(span)
    return locations

def _query_literal_targets(task, sources, eligible):
    """Nominate existing symbols from static key declarations, not runtime truth."""
    keys = set(re.findall(r"(?<![\w-])--([^\W\d][\w-]{1,127})(?![\w-])", task))
    for fragment in re.findall(r"(?<!`)`([^`\r\n]+)`(?!`)", task):
        match = re.fullmatch(r"(?:--)?([^\W\d][\w-]{1,127})(?:\s*=[^\r\n]*)?", fragment.strip())
        if match:
            keys.add(match.group(1))
    if not keys or len(keys) > 32:
        return {}
    targets = {key: set() for key in keys}
    def key_of(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value[2:] if node.value.startswith("--") else node.value
        return None
    for path, lines in sources.items():
        text = "\n".join(lines)
        if not any(key in text for key in keys):
            continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            continue
        definitions = Counter(n.name for n in tree.body
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        rebound = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                rebound.update(a.asname or a.name.split(".")[0] for a in node.names)
        assignments = Counter()
        for statement in tree.body:
            names = statement.targets if isinstance(statement, ast.Assign) else [statement.target] if isinstance(statement, ast.AnnAssign) else []
            assignments.update(n.id for n in names if isinstance(n, ast.Name))
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)) and isinstance(statement.value, ast.Dict):
                names = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                if not names or any(not isinstance(n, ast.Name) or assignments[n.id] != 1 for n in names):
                    continue
                registry = statement.value
                counts = Counter(key_of(k) for k in registry.keys)
                for key_node, value in zip(registry.keys, registry.values):
                    key = key_of(key_node)
                    if key not in keys or counts[key] != 1 or not isinstance(value, ast.Name):
                        continue
                    function = functions.get(value.id)
                    if (function is None or definitions[value.id] != 1 or value.id in rebound
                            or function.lineno >= statement.lineno):
                        continue
                    target = (path, function.lineno, function.name)
                    if target in eligible:
                        targets[key].add((*target, 8000))
            if (isinstance(statement, ast.ClassDef) and definitions[statement.name] == 1
                    and statement.name not in rebound):
                target = (path, statement.lineno, statement.name)
                if target not in eligible:
                    continue
                for declaration in statement.body:
                    if not isinstance(declaration, (ast.Assign, ast.AnnAssign)):
                        continue
                    value = declaration.value
                    declared = value.keys if isinstance(value, ast.Dict) else [
                        item.elts[0] for item in value.elts
                        if isinstance(item, (ast.Tuple, ast.List)) and len(item.elts) == 2
                    ] if isinstance(value, (ast.Tuple, ast.List)) else []
                    for key_node in declared:
                        key = key_of(key_node)
                        if key in keys:
                            targets[key].add((*target, 6000))
    result = {}
    for values in targets.values():
        if len(values) > 8:
            continue
        for path, line, name, priority in values:
            target = (path, line, name)
            result[target] = max(result.get(target, 0), priority)
    return result


def _compound_terms(identifier, query_terms):
    """Expand fully segmented compact parts, never incidental substrings."""
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", identifier).casefold()
    allowed = sorted({term for term in query_terms if len(term) >= 4}, key=lambda t: (-len(t), t))
    result = set()
    for part in re.findall(r"[^\W_]+", normalized):
        if not 8 <= len(part) <= 256:
            continue
        paths = {0: ()}
        for start in range(len(part)):
            if start not in paths:
                continue
            for term in allowed:
                if part.startswith(term, start):
                    end = start + len(term)
                    candidate = (*paths[start], term)
                    if end not in paths or len(candidate) > len(paths[end]):
                        paths[end] = candidate
        segmented = paths.get(len(part), ())
        if len(set(segmented)) >= 2:
            result.update(segmented)
    return result


def _definitions(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return {}
    return {n.lineno: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _query_aliases(task):
    """Observed imports in query code are location hints, never executed code."""
    fragments = re.findall(r"(?ms)^[ \t]*```(?:python3?|py|pycon)?[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*\r?$", task)
    bindings, rebound = {}, set()
    wildcard = False
    for fragment in [task, *fragments]:
        lines = fragment.splitlines()
        if any(line.lstrip().startswith(">>> ") for line in lines):
            fragment = "\n".join(line.lstrip()[4:] for line in lines
                                 if line.lstrip().startswith((">>> ", "... ")))
        try:
            tree = ast.parse(fragment)
        except (SyntaxError, ValueError, RecursionError):
            continue
        for item in ast.walk(tree):
            if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
                rebound.add(item.id)
            elif isinstance(item, ast.arg):
                rebound.add(item.arg)
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                rebound.add(item.name)
            elif isinstance(item, ast.ExceptHandler) and item.name:
                rebound.add(item.name)
            elif isinstance(item, (ast.MatchAs, ast.MatchStar)) and item.name:
                rebound.add(item.name)
            elif isinstance(item, (ast.Import, ast.ImportFrom)) and item not in tree.body:
                rebound.update(a.asname or a.name.split(".")[0] for a in item.names)
        for item in tree.body:
            if isinstance(item, ast.Import):
                for alias in item.names:
                    if alias.asname:
                        bindings.setdefault(alias.asname, set()).add((alias.name, None))
            elif isinstance(item, ast.ImportFrom):
                if any(a.name == "*" for a in item.names):
                    wildcard = True
                if item.module and not item.level:
                    for alias in item.names:
                        if alias.asname and alias.name != "*":
                            bindings.setdefault(alias.asname, set()).add((item.module, alias.name))
    if wildcard:
        return {}
    return {name: next(iter(values)) for name, values in bindings.items()
            if len(values) == 1 and name not in rebound}


def _query_call_names(task):
    """Prose parentheses are not calls; parse actual spaced code as data."""
    names = set(re.findall(r"(?<![\w.])\b([A-Za-z_]\w*)\(", task))
    fragments = [task, *re.findall(r"(?<!`)`([^`\r\n]+)`(?!`)", task)]
    fence, code = None, []
    for line in task.splitlines():
        if fence is not None:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}[ \t]*", line):
                fragments.append("\n".join(code))
                fence, code = None, []
            else:
                code.append(line)
        else:
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if marker:
                delimiter = marker.group(1)
                fence = (delimiter[0], len(delimiter))
    if fence is not None:
        fragments.append("\n".join(code))
    for fragment in fragments:
        lines = fragment.splitlines()
        if any(line.lstrip().startswith(">>> ") for line in lines):
            fragment = "\n".join(line.lstrip()[4:] for line in lines
                                 if line.lstrip().startswith((">>> ", "... ")))
        try:
            tree = ast.parse(fragment)
        except (SyntaxError, ValueError, RecursionError):
            continue
        names.update(node.func.id for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name))
    return names

def _references(task):
    qualified = {(prefix.rstrip(".").split(".")[-1], name)
                 for prefix, name in re.findall(r"\b((?:[A-Za-z_]\w*\.)+)([A-Za-z_]\w*)", task)}
    bare = _query_call_names(task)
    bare |= set(re.findall(r"\b[A-Za-z]\w*_[A-Za-z_]\w*\b", task))
    original = set(qualified)
    for alias, (module, member) in _query_aliases(task).items():
        if member and alias in bare:
            qualified.update((owner, member) for owner in {module.split(".")[0], module.rsplit(".", 1)[-1]})
        namespace = module + ("." + member if member else "")
        for owner, target in original:
            if owner == alias:
                qualified.update((resolved, target) for resolved in {
                    namespace.split(".")[0], namespace.rsplit(".", 1)[-1]})
    return qualified, bare


def _named(name, references):
    qualified, bare = references
    pieces = name.rsplit(".", 1)
    leaf = pieces[-1]
    owners = set(re.split(r"[/.:]", pieces[0])) if len(pieces) == 2 else set()
    return (leaf in bare
            or any(leaf == target and owner in owners for owner, target in qualified))


def _window(body, terms, maximum=2800):
    """Selected exact lines with visible gaps, never a purported full function."""
    lines = body.splitlines()
    chosen = set(range(min(10, len(lines))))
    hits = sorted(range(len(lines)), key=lambda i: (-len(words(lines[i]) & terms), i))
    for i in hits[:4]:
        if words(lines[i]) & terms:
            chosen.update(range(max(0, i - 2), min(len(lines), i + 4)))
    chosen.update(range(max(0, len(lines) - 8), len(lines)))
    selected, used, previous = [], 0, -1
    for i in sorted(chosen):
        marker = "[source lines omitted]\n" if i != previous + 1 else ""
        addition = marker + lines[i] + "\n"
        if used + len(addition.encode()) > maximum:
            break
        selected.append(addition)
        used += len(addition.encode())
        previous = i
    if previous < len(lines) - 1:
        selected.append("[remaining source lines omitted]\n")
    return "".join(selected)


def _excerpt(lines, node, start, end):
    """Keep signatures and implementation; explicitly mark docstring omissions."""
    indices = list(range(start, end + 1))
    omitted = set()
    if node and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
        doc = node.body[0]
        if doc.end_lineno - doc.lineno >= 4:
            omitted = set(range(doc.lineno, doc.end_lineno + 1))
    result = []
    for line in indices:
        if line in omitted:
            if line == min(omitted):
                result.append(f"{line}: [docstring omitted; source available at this location]")
            continue
        result.append(f"{line}: {lines[line - 1]}")
    return "\n".join(result), bool(omitted)


def _cleanup_sites(node):
    """Source call sites, not a claim that any cleanup executed or succeeded."""
    if node is None:
        return ""
    stack, statements = list(node.body), []
    while stack:
        item = stack.pop()
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        statements.append(item)
        stack.extend(ast.iter_child_nodes(item))
    if not any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in statements):
        return ""
    sites = []
    for item in statements:
        if isinstance(item, ast.Try) and item.finalbody:
            calls = [n for statement in item.finalbody for n in ast.walk(statement)
                     if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))]
            for n in calls[:4]:
                try:
                    name = ast.unparse(n.func)
                except (ValueError, RecursionError):
                    continue
                if len(name) <= 160:
                    sites.append(f"{name}@{n.lineno}")
    sites = list(dict.fromkeys(sites))
    return "Static finally-block call sites (not observed execution): " + ", ".join(sites[:6]) + "\n" if sites else ""


def _assertion_groups(node, lines):
    """Syntactic same-block call/assignment/assertion links, not runtime proof."""
    numbered = {int(m[1]): i for i, line in enumerate(lines)
                if (m := re.match(r"(\d+):", line))}
    groups = []
    def indices(statement):
        return {numbered[n] for n in range(statement.lineno, statement.end_lineno + 1)
                if n in numbered}
    def block(statements):
        bindings = {}
        for statement in statements:
            if isinstance(statement, ast.Assert):
                names = {n.id for n in ast.walk(statement.test) if isinstance(n, ast.Name)}
                producers = [bindings[name] for name in sorted(names & bindings.keys())]
                if producers:
                    groups.append(indices(statement) | set().union(*(indices(p) for p in producers)))
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings.pop(target.id, None)
                        if isinstance(statement.value, ast.Call):
                            bindings[target.id] = statement
            # Analyze nested control-flow blocks separately. Never descend into
            # a nested function/class or carry speculative bindings across it.
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for _, value in ast.iter_fields(statement):
                    if isinstance(value, list) and value and all(isinstance(s, ast.stmt) for s in value):
                        block(value)
            if isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
                                      ast.With, ast.AsyncWith, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bindings.clear()
    if node is not None:
        block(node.body)
    return groups


def _usage_window(body, terms, *, maximum, node=None):
    """Fit exact numbered lines, preserving signature/assertions and visible gaps.

    These are source excerpts, not executable slices or observed test outcomes.
    Count UTF-8 bytes including every omission marker before adding a line.
    """
    lines = body.splitlines()
    if not lines or maximum <= 0:
        return ""
    def render(indices):
        parts, previous = [], -1
        for index in sorted(indices):
            if index != previous + 1:
                parts.append("[source lines omitted]\n")
            parts.append(lines[index] + "\n")
            previous = index
        if previous != len(lines) - 1:
            parts.append("[source lines omitted]\n")
        return "".join(parts)
    signature = next((i for i, line in enumerate(lines) if re.match(r"\d+:\s*(?:async )?def\s", line)), 0)
    assertions = [i for i, line in enumerate(lines) if re.match(r"\d+:\s*assert\s", line)]
    order = [signature, *assertions[-4:], *range(signature + 1, min(len(lines), signature + 4))]
    order += sorted(range(len(lines)), key=lambda i: (-len(words(lines[i]) & terms), i))
    groups = _assertion_groups(node, lines)
    protected = set().union(*groups) if groups else set()
    chosen = set()
    for group in groups:
        trial = chosen | group
        if len(render(trial).encode()) <= maximum:
            chosen = trial
    for index in dict.fromkeys(order):
        if index in protected:
            continue
        trial = chosen | {index}
        if len(render(trial).encode()) <= maximum:
            chosen = trial
    return render(chosen) if chosen else ""


def _usage_examples(sources, definitions, terms, *, budget, entry_name=""):
    """Existing test source, not oracle labels, execution or invented graph facts.

    The caller already validated every source digest against the authorized
    snapshot. Extractors may omit tests from their graph while retaining those
    files in the protected source generation.
    """
    choices = []
    for path, nodes in definitions.items():
        parts = PurePosixPath(path).parts
        is_test = any(p in {"test", "tests"} for p in parts)
        is_example = "examples" in parts
        if (not is_test and not is_example) or "typing" in parts:
            continue
        for node in nodes.values():
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or (is_test and not node.name.startswith("test_")):
                continue
            name_hits = words(node.name) & terms
            called = {n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
                      for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}
            call_hits = set().union(*(words(name) for name in called)) & terms if called else set()
            # Prefer a demonstrated call to the localized API over generic
            # vocabulary such as "update", "default" or "value" in other tests.
            direct = bool(entry_name and (entry_name in called or entry_name in words(node.name)))
            if not direct and len(name_hits) < 2:
                continue
            score = 100 * direct + 8 * len(name_hits) + 3 * len(call_hits)
            if not score:
                continue
            start = min(node.lineno, *(d.lineno for d in node.decorator_list)) if node.decorator_list else node.lineno
            body, omitted = _excerpt(sources[path], node, start, node.end_lineno)
            kind = "existing test" if is_test else "usage example"
            choices.append((-score, path, start, node.end_lineno, node.name, kind, body, omitted, node))
    for _, path, start, end, name, kind, body, omitted, node in sorted(choices, key=lambda c: c[:6]):
        coverage = "source; docstring omitted" if omitted else "complete source"
        header = f"[AtMem {kind} {path}:{start}-{end}; {name}; {coverage}; not executed]\n"
        chunk = header + body + "\n"
        if len(body.encode()) <= 1400 and len(chunk.encode()) <= budget:
            return chunk
        header = f"[AtMem {kind} {path}:{start}-{end}; {name}; partial source; omitted lines available; not executed]\n"
        fitted = _usage_window(body, terms, maximum=min(1400, budget - len(header.encode())), node=node)
        if fitted:
            return header + fitted
    return ""


def pack_generation(generation, task, *, budget):
    if type(budget) is not int or budget < 0 or budget > 65536:
        raise ValueError("invalid source context byte budget")
    # Validate every object/edge before any content is emitted. The caller owns
    # current-source authorization/revalidation before and after this pure step.
    nodes, edges = graph_input(generation)
    available = {key: value for key, value in nodes}
    terms = words(task)
    explicit = _references(task)
    if not terms or budget == 0:
        return ""
    hashes = dict(generation["snapshot"]["files"])
    for obj in generation["objects"]:
        for anchor in obj["anchors"]:
            if hashes.get(anchor["path"]) != anchor["content_sha256"]:
                raise ValueError("structural anchor differs from authorized source")
    sources, definitions = {}, {}
    for name, encoded in generation["source_bytes"].items():
        raw = base64.b64decode(encoded, validate=True)
        if name not in hashes or sha256(raw).hexdigest() != hashes[name]:
            raise ValueError("source evidence differs from authorized snapshot")
        text = source_text(name, raw)
        sources[name] = text.splitlines()
        definitions[name] = _definitions(text) if name.endswith(".py") else {}
    locations = _query_source_locations(task, sources)
    candidates = []
    for key, value in nodes:
        path, line = value.get("file_path"), value.get("line")
        if path not in sources or type(line) is not int or not 1 <= line <= len(sources[path]):
            continue
        is_symbol = value.get("type") == "CodeSymbol"
        node = definitions[path].get(line) if is_symbol else None
        # Some extractors anchor a decorated definition at its first decorator.
        if is_symbol and node is None:
            node = next((n for n in definitions[path].values() if any(d.lineno == line for d in n.decorator_list)), None)
        end = node.end_lineno if node else value.get("end_line") or line
        start = min([node.lineno, *(d.lineno for d in node.decorator_list)]) if node else line
        end = max(start, min(end, len(sources[path])))
        content, omitted = _excerpt(sources[path], node, start, min(end, start + 239))
        # Qualified extractor names repeat the module and owner class for every
        # method. Do not let that repeated vocabulary crowd out local symbols.
        pieces = value["name"].rsplit(".", 1)
        label_terms = words(pieces[-1])
        # Compact identifiers require complete word segmentation. Incidental
        # substrings such as proper/property and rated/decorated are not names.
        label_terms |= _compound_terms(pieces[-1], terms)
        owner_terms = words(pieces[0].rsplit(".", 1)[-1]) if len(pieces) > 1 else set()
        content_terms = words(content)
        candidates.append({"id": key, "path": path, "start": start, "end": end, "name": value["name"],
                           "body": content, "label": label_terms, "owner": owner_terms, "terms": content_terms,
                           "explicit": is_symbol and _named(value["name"], explicit),
                           "omitted": omitted, "partial": end > start + 239,
                           "class": isinstance(node, ast.ClassDef), "node": node,
                           "location_span": end - start if node is not None and any(
                               start <= first <= last <= end for first, last in locations.get(path, ())) else None})
    frequency = Counter(t for row in candidates for t in (row["label"] | row["terms"]))
    query_weights = _query_term_weights(task)
    weights = {t: query_weights[t] * (1 + math.log(1 + len(candidates) / (1 + frequency[t]))) for t in terms}
    literal_targets = _query_literal_targets(task, sources, {
        (r["path"], r["node"].lineno, r["node"].name) for r in candidates
        if r["node"] is not None and r["name"].rsplit(".", 1)[-1] == r["node"].name})
    explicit_paths = {r["path"] for r in candidates if r["explicit"]}
    def lexical(row):
        if row["location_span"] is not None and (row["explicit"] or row["path"] not in explicit_paths):
            return 20000 + 1000 / (1 + row["location_span"])
        if row["explicit"]:
            parameters = set()
            if isinstance(row["node"], (ast.FunctionDef, ast.AsyncFunctionDef)):
                parameters = {a.arg for a in (*row["node"].args.posonlyargs, *row["node"].args.args, *row["node"].args.kwonlyargs)}
            return 10000 + 50 * len(parameters & terms)
        score = sum(weights[t] * (8 if t in row["label"] else .5 if t in row["owner"] else 1)
                    for t in terms if t in row["label"] or t in row["terms"] or t in row["owner"])
        literal_priority = literal_targets.get((row["path"], row["node"].lineno, row["node"].name)) if row["node"] is not None else None
        if literal_priority:
            return literal_priority + min(score, 100)
        # A complete method is usually more actionable than its whole class.
        return score * (0.4 if row["class"] else 1)
    # Nominate bounded related bodies with the incorporated upstream traversal,
    # not a second graph engine. Graph IDs stay out of the rendered context.
    executable = [r for r in candidates if r["node"] is not None and lexical(r) > 0]
    executable.sort(key=lambda r: (-lexical(r), r["path"], r["start"]))
    priorities, class_maps = {}, set()
    roots = executable[:1]
    if roots:
        root = roots[0]
        priorities[root["id"]] = 12000
        related = CodeRetriever(operation="explore", id=root["id"], direction="both",
                                relation_types=["calls"], max_depth=2, max_nodes=12).execute(nodes, edges)
        for fact in related.get("nodes", []):
            if fact["id"] != root["id"]:
                priorities[fact["id"]] = max(0, 9000 - 1000 * fact.get("depth", 1))
        # Static import bindings fill a common extractor gap: a function-local
        # import called by a graph neighbour. This nominates source, not a new
        # authoritative graph edge, and never resolves arbitrary attributes.
        for caller in [r for r in candidates if r["id"] in priorities and
                       isinstance(r["node"], (ast.FunctionDef, ast.AsyncFunctionDef))]:
            tree = ast.parse("\n".join(sources[caller["path"]]))
            bindings = {}
            for item in [*tree.body, *ast.walk(caller["node"])]:
                if isinstance(item, ast.ImportFrom) and item.module:
                    for alias in item.names:
                        module_path = item.module.replace(".", "/") + ".py"
                        if item.level:
                            parent = PurePosixPath(caller["path"]).parent
                            for _ in range(item.level - 1):
                                parent = parent.parent
                            module_path = str(parent / module_path)
                        bindings[alias.asname or alias.name] = (module_path, alias.name, bool(item.level))
            calls = {n.func.id for n in ast.walk(caller["node"])
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            for called in calls & bindings.keys():
                module_path, original, relative = bindings[called]
                for callee in candidates:
                    if (isinstance(callee["node"], (ast.FunctionDef, ast.AsyncFunctionDef)) and
                        callee["name"].rsplit(".", 1)[-1] == original and
                        (callee["path"] == module_path if relative else
                         callee["path"] == module_path or callee["path"].endswith("/" + module_path))):
                        priorities[callee["id"]] = max(priorities.get(callee["id"], 0),
                                                     max(0, priorities[caller["id"]] - 500))
        # A referenced class provides a compact declaration map; select its
        # task-relevant methods rather than a huge arbitrary class crop.
        referenced = {n.func.id for n in ast.walk(root["node"])
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        imports = {}
        try:
            module = ast.parse("\n".join(sources[root["path"]]))
            import_nodes = [*module.body, *ast.walk(root["node"])]
            for n in import_nodes:
                if isinstance(n, ast.ImportFrom):
                    imports.update({a.asname or a.name: (n.module or "").split(".")[-1] for a in n.names})
        except (SyntaxError, ValueError, RecursionError):
            pass
        def referenced_class(row):
            leaf = row["name"].rsplit(".", 1)[-1]
            if leaf not in referenced:
                return False
            if leaf in imports:
                return imports[leaf] in re.split(r"[/.:]", row["name"])
            return row["path"] == root["path"] or row["id"] in priorities
        classes = [r for r in candidates if r["class"] and (referenced_class(r) or r is root)]
        owner = next((r for r in candidates if r["class"] and root["name"].rsplit(".", 1)[0] == r["name"]), None)
        if owner is not None and owner not in classes:
            class_maps.add(owner["id"])
            priorities[owner["id"]] = 10500
        for cls in classes[:1]:
            class_maps.add(cls["id"])
            priorities[cls["id"]] = 11000
            prefix_name = cls["name"] + "."
            members = [r for r in candidates if r["name"].startswith(prefix_name) and
                       r is not root and "." not in r["name"][len(prefix_name):] and r["label"] & terms]
            members.sort(key=lambda r: (0 if r["name"].rsplit(".", 1)[-1].casefold() in terms else 1,
                                        -lexical(r), r["start"]))
            for member in members[:2]:
                priorities[member["id"]] = 10000 + min(500, lexical(member))
                related = CodeRetriever(operation="explore", id=member["id"], direction="forward",
                                        relation_types=["calls"], max_depth=1, max_nodes=6).execute(nodes, edges)
                for fact in related.get("nodes", []):
                    if fact["id"] != member["id"]:
                        priorities[fact["id"]] = max(priorities.get(fact["id"], 0), 9500)
    def rank(row):
        return priorities.get(row["id"], 0) + min(1000, lexical(row))
    candidates.sort(key=lambda row: (0 if row["node"] is not None else 1,
                                     -rank(row), row["path"], row["start"], row["id"]))
    entry_name = roots[0]["name"].rsplit(".", 1)[-1] if roots else ""
    usage = _usage_examples(sources, definitions, terms, budget=min(2048, budget // 4), entry_name=entry_name)
    # Examples are optional evidence, not a fixed reservation which can evict
    # an implementation. Keep a small preview allowance, then fit the example
    # to the actual residual budget before considering incidental matches.
    preview = min(256, budget // 4) if usage else 0
    chunks, used, selected = [], 0, []
    prefix = "Current source excerpts (not a patch or instruction). Locations are repository-relative; native tools remain available.\n"
    if len(prefix.encode()) > budget:
        return ""
    used += len(prefix.encode())
    def select(rows, ceiling):
        nonlocal used
        for row in rows:
            if sum(not old["class"] for old in selected) >= 5:
                break
            if rank(row) <= 0 or (row["class"] and row["id"] not in class_maps):
                continue
            if any(old["covers"] and row["path"] == old["path"] and old["start"] <= row["start"] and row["end"] <= old["end"] for old in selected):
                continue
            if row["class"]:
                direct = [n for n in row["node"].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                direct.sort(key=lambda n: (-len(words(n.name) & terms), n.lineno))
                body = row["body"].splitlines()[0] + "\n" + "\n".join(
                    f"method {n.name}: {n.lineno}-{n.end_lineno}" for n in direct[:8])
                if len(direct) > 8:
                    body += "\n[additional methods omitted]"
                coverage = "method inventory; implementations listed separately"
            elif len(row["body"].encode()) > 3200:
                body = _window(row["body"], terms)
                coverage = "partial implementation; inspect omitted source before relying on completeness"
            else:
                body = row["body"]
                coverage = ("source anchor" if row["node"] is None else "bounded excerpt" if row["partial"] else
                            "implementation; docstring omitted" if row["omitted"] else "complete definition")
            neighbors = []
            for source, target, kind, _ in edges:
                if source == row["id"] and kind not in {"declares", "contains"} and target in available and len(neighbors) < 3:
                    other = available[target]
                    neighbors.append((target, f"{kind}: {other['name']} ({other.get('file_path', '')}:{other.get('line', '?')})"))
            chunk = f"[AtMem structure {row['path']}:{row['start']}-{row['end']}; {row['name']}; {coverage}]\n{body}\n"
            chunk += _cleanup_sites(row["node"])
            # Keep allocation conservative: removing redundant navigation later
            # must not change selected source or refill the released space.
            allocation = chunk + ("; ".join(note for _, note in neighbors) + "\n" if neighbors else "")
            size = len(allocation.encode())
            if used + size > ceiling:
                continue
            selected.append({**row, "covers": not row["class"] and "partial implementation" not in coverage and not row["partial"]})
            chunks.append((chunk, neighbors))
            used += size
    primary = [row for row in candidates if priorities.get(row["id"], 0) > 0]
    select(primary, budget - preview)
    usage = _usage_examples(sources, definitions, terms, budget=min(2048, budget - used), entry_name=entry_name)
    used += len(usage.encode())
    select((row for row in candidates if priorities.get(row["id"], 0) == 0), budget)
    covered = {row["id"] for row in selected if row["covers"] and row["node"] is not None}
    rendered = []
    for chunk, neighbors in chunks:
        notes = [note for target, note in neighbors if target not in covered]
        rendered.append(chunk + ("; ".join(notes) + "\n" if notes else ""))
    return prefix + "".join(rendered) + usage if chunks else ""

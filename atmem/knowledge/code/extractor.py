"""Strict, in-memory reader of pinned Enola artifacts.

Uses incorporated upstream identity/relation normalization; deliberately rejects
corrupt/missing receipts instead of upstream's warning-and-continue behavior.
This parser does not authorize a source or start a subprocess.
"""
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
import json

from atmem.knowledge._vendor.enola_contract import is_enola_id, normalize_relation
from atmem.knowledge.contracts import FACT_KINDS, source_path, text


def insight_facts(insights):
    """Reuse upstream finding conversion without writing a plaintext temp file.

    Writer fact IDs in evidence remain authoritative for resolution. Derived
    findings get stable scoped writer identities; no name-only link guessing.
    The original insights artifact and extraction receipt remain unchanged.
    """
    from atmem.knowledge._vendor.enola_contract import _synthesize_insight_facts
    payload = json.dumps(insights, ensure_ascii=False, allow_nan=False)
    text(payload, "insights", 2_000_000)
    class MemoryArtifact:
        def __truediv__(self, name):
            if name != "insights.json":
                raise ValueError("unsupported in-memory artifact")
            return self
        def is_file(self):
            return True
        def open(self, mode, encoding):
            if mode != "r" or encoding != "utf-8":
                raise ValueError("read-only artifact required")
            return StringIO(payload)
    result = _synthesize_insight_facts(MemoryArtifact())
    for fact in result:
        fact.update(repo="repository", file="")
        fact["id"] = sha256("\0".join((fact["repo"], fact["kind"], fact["name"], "")).encode()).hexdigest()[:32]
    return result


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def strict_json(raw):
    def reject(_):
        raise ValueError("nonfinite JSON value")
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject)


@dataclass(frozen=True)
class ExtractionArtifacts:
    facts_jsonl: bytes
    receipt_json: bytes
    insights_json: bytes = b"[]"


def parse_artifacts(artifacts: ExtractionArtifacts, *, max_bytes=32_000_000, max_facts=50000):
    if not isinstance(artifacts, ExtractionArtifacts) or any(type(v) is not bytes for v in (
            artifacts.facts_jsonl, artifacts.receipt_json, artifacts.insights_json)):
        raise ValueError("artifact bytes required")
    if sum(map(len, (artifacts.facts_jsonl, artifacts.receipt_json, artifacts.insights_json))) > max_bytes:
        raise ValueError("extraction artifact budget exceeded")
    receipt = strict_json(artifacts.receipt_json)
    if not isinstance(receipt, dict) or type(receipt.get("format_version")) is not int or receipt["format_version"] != 1:
        raise ValueError("unsupported or missing extraction receipt")
    if receipt.get("enola_version") != "0.4.26" or receipt.get("extractor_version") != "v287":
        raise ValueError("unpinned extractor version")
    if receipt.get("providers"):
        raise ValueError("external extraction providers are not permitted")
    facts = []
    relation_count = 0
    for line in artifacts.facts_jsonl.splitlines():
        if not line.strip():
            continue
        if len(facts) >= max_facts:
            raise ValueError("fact budget exceeded")
        fact = strict_json(line)
        if not isinstance(fact, dict) or not is_enola_id(fact.get("id")):
            raise ValueError("fact requires writer identity")
        if not isinstance(fact.get("kind"), str) or fact["kind"] not in FACT_KINDS:
            raise ValueError("unsupported fact kind")
        text(fact.get("name"), "fact name", 2000)
        text(fact.get("repo"), "repository label", 256)
        file = fact.get("file", "")
        if not isinstance(file, str):
            raise ValueError("invalid fact source path")
        # Pinned Enola also uses '.' for derived root-module dependency
        # rollups. Mapping still requires the explicit rollup properties and
        # admitted directory evidence; it is never treated as a source file.
        if file and not (file == "." and fact["kind"] in {"module", "dependency"}):
            source_path(file)
        identity = "\0".join((fact["repo"], fact["kind"], fact["name"], file))
        if sha256(identity.encode()).hexdigest()[:32] != fact["id"]:
            raise ValueError("writer identity mismatch")
        relations = fact.get("relations", [])
        if not isinstance(relations, list):
            raise ValueError("invalid relations")
        # Root modules and high-fan-out public APIs legitimately exceed 2,048
        # relations on one writer fact. Bound the entire artifact instead;
        # traversal depth/result bounds are still enforced at query time.
        relation_count += len(relations)
        if relation_count > 500_000:
            raise ValueError("extraction relation budget exceeded")
        for relation in relations:
            if normalize_relation(relation) is None:
                raise ValueError("invalid relation")
            if "target_id" in relation and not is_enola_id(relation["target_id"]):
                raise ValueError("invalid resolved identity")
        # Screen all semantic fields, not only names; no props bypass.
        text(json.dumps(fact, ensure_ascii=False), "fact", 4_000_000)
        facts.append(fact)
    if type(receipt.get("fact_count")) is not int or receipt["fact_count"] != len(facts):
        raise ValueError("extraction fact count mismatch")
    hashes = receipt.get("output_hashes", {})
    if not isinstance(hashes, dict):
        raise ValueError("invalid output hashes")
    for name, raw in (("facts.jsonl", artifacts.facts_jsonl), ("insights.json", artifacts.insights_json)):
        if name in hashes:
            if not isinstance(hashes[name], str) or hashes[name].removeprefix("sha256:") != sha256(raw).hexdigest():
                raise ValueError("artifact hash mismatch")
    insights = strict_json(artifacts.insights_json)
    if not isinstance(insights, list):
        raise ValueError("invalid insights artifact")
    text(json.dumps(receipt, ensure_ascii=False), "receipt", 262144)
    text(json.dumps(insights, ensure_ascii=False), "insights", 2_000_000)
    return facts, receipt, insights

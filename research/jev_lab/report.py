"""Dependency-light HTML/SVG report for JEV-Lab."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _bar(label: str, value: float, color: str, x: int, y: int, width: int = 260) -> str:
    safe = max(0.0, min(1.0, float(value)))
    return f'<text x="{x}" y="{y}" fill="#cfd4ff" font-size="14">{html.escape(label)}</text><rect x="{x}" y="{y+10}" width="{width}" height="18" rx="9" fill="#252b48"/><rect x="{x}" y="{y+10}" width="{safe*width:.1f}" height="18" rx="9" fill="{color}"/><text x="{x+width+12}" y="{y+25}" fill="#fff" font-size="14">{safe:.3f}</text>'


def render(result: dict[str, Any]) -> str:
    baseline = result["metrics"]["baseline"]
    jev = result["metrics"]["jev"]
    mode = html.escape(str(result["mode"]).upper())
    rows = "".join(f'<tr><td>{html.escape(row["case_id"])}</td><td>{html.escape(row["query"])}</td><td>{html.escape(str(row["baseline_rank"][0]))}</td><td>{html.escape(str(row["jev_rank"][0] if row["jev_rank"] else "—"))}</td><td>{html.escape(str(row["authority_decision"] or "withheld"))}</td></tr>' for row in result["records"])
    svg = f'''<svg viewBox="0 0 900 390" role="img" aria-label="Jev and AtMem experiment charts"><defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#7c5cff"/><stop offset="1" stop-color="#20d6a2"/></linearGradient><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#20d6a2"/></marker></defs><rect width="900" height="390" rx="24" fill="#11152a"/><text x="40" y="46" fill="#fff" font-size="24" font-weight="700">Jev × AtMem · governed memory judgment</text><text x="40" y="72" fill="#aeb6d8" font-size="14">Same candidates · advisory model · local authority remains final</text>{_bar("Baseline MRR@5", baseline["mrr_at_5"], "#7c5cff", 50, 120)}{_bar("Jev MRR@5", jev["mrr_at_5"], "#20d6a2", 50, 180)}{_bar("Baseline top-1", baseline["top1_accuracy"], "#7c5cff", 50, 240)}{_bar("Jev top-1", jev["top1_accuracy"], "#20d6a2", 50, 300)}<g transform="translate(510 112)"><circle cx="100" cy="90" r="70" fill="#202642" stroke="url(#g)" stroke-width="8"/><text x="100" y="84" text-anchor="middle" fill="#fff" font-size="18">AtMem</text><text x="100" y="108" text-anchor="middle" fill="#aeb6d8" font-size="13">authority gate</text><path d="M0 90H-70M200 90H270" stroke="#20d6a2" stroke-width="3" marker-end="url(#arrow)"/><text x="-160" y="75" fill="#cfd4ff" font-size="13">Jev nomination</text><text x="205" y="75" fill="#cfd4ff" font-size="13">approved context</text><text x="20" y="205" fill="#ffcc66" font-size="13">ineligible candidates withheld</text><text x="20" y="240" fill="#aeb6d8" font-size="13">agreement: {result["metrics"]["agreement_rate"]:.3f}</text><text x="20" y="262" fill="#aeb6d8" font-size="13">transport: {float(result["transport"].get("latency_ms", 0.0)):.1f} ms</text></g></svg>'''
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>AtMem Jev Lab</title><style>body{{margin:0;background:#090c18;color:#e9ebff;font:15px system-ui,sans-serif}}main{{max-width:1100px;margin:32px auto;padding:0 24px}}.hero{{padding:28px;border-radius:24px;background:linear-gradient(135deg,#21194d,#102f3c);box-shadow:0 16px 50px #0008}}h1{{font-size:38px;margin:0 0 8px}}.pill{{display:inline-block;padding:7px 12px;border-radius:999px;background:#20d6a2;color:#071b18;font-weight:700}}.card{{margin-top:22px;padding:18px;border-radius:18px;background:#13182b;border:1px solid #2a3357}}svg{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #2b3455}}th{{color:#aeb6d8}}code{{color:#9cdcff}}</style></head><body><main><section class="hero"><span class="pill">{mode} · SYNTHETIC ONLY</span><h1>Jev helps AtMem judge candidates—AtMem still decides.</h1><p>One reproducible experiment showing advisory relevance scoring, explicit authority gates, and inspectable evidence.</p><p><code>model={html.escape(str(result["model"]))}</code> · <code>dataset={html.escape(str(result["dataset_sha256"])[:16])}…</code></p></section><section class="card">{svg}</section><section class="card"><h2>Decision trace</h2><p>Every row shows baseline order, Jev order, and the candidate AtMem finally allowed into context.</p><table><thead><tr><th>Case</th><th>Query</th><th>Baseline first</th><th>Jev first</th><th>AtMem decision</th></tr></thead><tbody>{rows}</tbody></table></section><section class="card"><h2>What this proves—and does not</h2><p>Jev is an advisory evaluator over nominated candidates. Scope, lifecycle, eligibility, and final context delivery remain AtMem responsibilities. This report contains synthetic data only and is not a claim about production user memory.</p></section></main></body></html>'''


def write_report(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(result), encoding="utf-8")
    output.with_suffix(".json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

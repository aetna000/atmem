"""Structural evidence qualification; never treats reference existence as truth."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re


def expand_reference(value: str) -> tuple[str, ...]:
    """Expand explicit source-ID lists/ranges without guessing missing sessions."""
    if not isinstance(value, str):
        raise ValueError("evidence reference must be text")
    result = []
    for part in re.split(r"[;,]\s*(?=(?:D\d+\s*:|\d{4}-\d{2}-\d{2}:))", value.strip()):
        part = part.strip()
        match = re.fullmatch(r"D(\d+)\s*:\s*(\d+)\s*-\s*(?:D(\d+)\s*:\s*)?(\d+)[.;]?", part)
        if match:
            day, start, end_day, end = match.groups()
            if (end_day and end_day != day) or not 0 <= int(end)-int(start) <= 1000:
                raise ValueError("ambiguous or unbounded evidence range")
            result.extend(f"D{day}:{i}" for i in range(int(start), int(end)+1))
            continue
        match = re.fullmatch(r"D(\d+)\s*:\s*(\d+)[.;]?", part)
        result.append(f"D{match[1]}:{match[2]}" if match else part)
    return tuple(result)


def qualify_realtalk(root: Path) -> dict:
    counts: Counter = Counter()
    excluded = []
    for path in sorted((root / "data").glob("Chat_*.json")):
        data = json.loads(path.read_text())
        evidence = {}
        for key, turns in data.items():
            if re.fullmatch(r"session_\d+", key):
                for turn in turns:
                    identity = turn.get("dia_id")
                    if identity in evidence:
                        raise ValueError("duplicate conversation evidence ID")
                    evidence[identity] = turn
        for index, qa in enumerate(data.get("qa", [])):
            counts["total"] += 1
            reason = None
            refs = qa.get("evidence")
            if isinstance(refs, list) and refs:
                try:
                    expanded = [item for ref in refs for item in expand_reference(ref)]
                    if expanded != refs:
                        counts["records_with_explicit_reference_normalization"] += 1
                    refs = expanded
                except ValueError:
                    reason = "ambiguous_reference_format"
            if not isinstance(refs, list) or not refs:
                reason = "missing_evidence"
            elif any(ref not in evidence for ref in refs):
                reason = "unresolved_evidence"
            elif any(not evidence[ref].get("clean_text") for ref in refs):
                reason = "empty_text_or_image_only_evidence"
            elif not qa.get("question") or not qa.get("answer"):
                reason = "missing_question_or_answer"
            if reason:
                counts[reason] += 1
                excluded.append({"file": path.name, "qa_index": index, "reason": reason})
            else:
                counts["references_resolved"] += 1
    if not counts["total"]:
        raise ValueError("no REALTALK questions")
    return {"corpus": "realtalk", "counts": dict(counts), "exclusions": excluded,
            "semantic_adjudication": "pending", "dispatch_qualified": False}


def qualify_rhelm(root: Path) -> dict:
    counts: Counter = Counter()
    excluded = []
    for path in sorted((root / "data/QA_final").glob("low_score_qa_*.jsonl")):
        persona = path.name.removeprefix("low_score_qa_").removesuffix("_all_validated.jsonl")
        sessions = {}
        for source in (root / "data/conversations" / persona).glob("*.json"):
            if source.name.startswith("."):
                continue  # macOS AppleDouble sidecars are not corpus records.
            data = json.loads(source.read_text())
            sessions[str(data["date"])] = {str(turn["turn"]): turn for turn in data["conversation"]}
        attachments = {p.name: p for p in (root / "data/attachments" / persona).glob("*")
                       if p.is_file() and not p.name.startswith(".")}
        email_dates = {match[1] for p in (root / "data/emails" / persona).glob("*.txt")
                       if (match := re.search(r"_email_(\d{4}_\d{2}_\d{2})\.txt$", p.name))}
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            qa = json.loads(line)
            counts["total"] += 1
            reason = None
            refs = qa.get("supporting_evidence")
            if isinstance(refs, list) and refs:
                refs = [item for ref in refs for item in expand_reference(ref)]
            if not isinstance(refs, list) or not refs:
                reason = "missing_evidence"
            for ref in refs or []:
                match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}):(\d+)", ref)
                if match:
                    day, turn = match.groups()
                    if turn not in sessions.get(day, {}):
                        reason = "unresolved_conversation_reference"
                    elif date.fromisoformat(day) > date.fromisoformat(qa["question_date"]):
                        reason = "future_evidence"
                else:
                    filename, separator, section = ref.partition(":")
                    email = re.fullmatch(r"Emails_(\d{4}-\d{2}-\d{2})", filename)
                    if email and email[1].replace("-", "_") in email_dates and separator and section.strip():
                        counts["external_references_requiring_section_review"] += 1
                        if date.fromisoformat(email[1]) > date.fromisoformat(qa["question_date"]):
                            reason = "future_evidence"
                    elif filename not in attachments or not separator or not section.strip():
                        reason = "unresolved_external_reference"
                    else:
                        # Section entailment requires independent semantic review.
                        counts["external_references_requiring_section_review"] += 1
            if not qa.get("question") or not qa.get("answer"):
                reason = "missing_question_or_answer"
            if reason:
                counts[reason] += 1
                excluded.append({"file": path.name, "id": qa.get("id"), "reason": reason})
            else:
                counts["references_resolved"] += 1
    if not counts["total"]:
        raise ValueError("no RHELM questions")
    return {"corpus": "rhelm", "counts": dict(counts), "exclusions": excluded,
            "semantic_adjudication": "pending", "dispatch_qualified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", choices=["rhelm", "realtalk"])
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    result = (qualify_rhelm if args.corpus == "rhelm" else qualify_realtalk)(args.root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

"""Import a single engineering result and bind it to a specific execution step."""

from urllib.parse import urlsplit
from xml.etree import ElementTree

from .archive import digest, now
from atmem.core.canonical import sha256_hex


def _label(value, limit=300):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or not value.isprintable():
        raise ValueError("A bounded, printable reference is required.")
    return value.strip()


def outcome(body, run, username):
    allowed = {"kind", "reference", "status", "url", "junit", "classname", "test_name", "step_id"}
    if not isinstance(body, dict) or set(body) - allowed:
        raise ValueError("Unexpected engineering outcome field.")
    kind, reference = body.get("kind"), _label(body.get("reference"))
    if kind not in {"test", "ticket", "pull_request", "incident"}:
        raise ValueError("Unknown engineering outcome kind.")
    step_id = body.get("step_id")
    if not step_id or not any(step.get("step_id") == step_id for step in run["steps"]):
        raise ValueError("Select an existing step in this run.")
    url = body.get("url", "")
    if url:
        parsed = urlsplit(_label(url, 2048))
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("An HTTPS source URL is required.")
    item = {"kind": kind, "reference": reference, "step_id": step_id, "url": url}
    if "junit" in body:
        xml = body["junit"]
        if (
            kind != "test"
            or not isinstance(xml, str)
            or len(xml.encode()) > 256_000
            or "<!DOCTYPE" in xml.upper()
            or "<!ENTITY" in xml.upper()
        ):
            raise ValueError("Invalid or oversized JUnit report.")
        classname, name = _label(body.get("classname")), _label(body.get("test_name"))
        try:
            doc = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            raise ValueError("Malformed JUnit report.") from exc
        if doc.tag not in {"testsuite", "testsuites"}:
            raise ValueError("Expected a JUnit testsuite or testsuites document.")
        matches = [
            test
            for test in doc.iter("testcase")
            if test.get("classname") == classname and test.get("name") == name
        ]
        if len(matches) != 1:
            raise ValueError("The JUnit report must contain exactly one matching test.")
        tags = {child.tag for child in matches[0]}
        status = "failed" if tags & {"error", "failure"} else "skipped" if "skipped" in tags else "passed"
        item.update(
            status=status,
            verification="imported_junit",
            classname=classname,
            test_name=name,
            report_sha256=sha256_hex(xml.encode()),
        )
    else:
        status = _label(body.get("status"), 48)
        item.update(status=status, verification="human_reported")
    return {
        **item,
        "outcome_id": "result_" + digest(item)[:32],
        "recorded_by": username,
        "recorded_at": now(),
    }


def compare(original, rerun):
    def value(run, field):
        if field in {"input_tokens", "output_tokens"} and not run.get("usage_complete"):
            return None
        return run.get(field)

    return [
        {"metric": field, "before": value(original, field), "after": value(rerun, field)}
        for field in (
            "outcome",
            "answer",
            "input_tokens",
            "output_tokens",
            "cost_microusd",
            "estimated_reader_cost_microusd",
            "reported_reader_cost_microusd",
            "reader_cost_delta_microusd",
            "elapsed_ms",
        )
    ]

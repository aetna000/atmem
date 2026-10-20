"""Read-only attribution of retained failures; never regrade or exclude rows."""
import base64
from hashlib import sha256
from pathlib import PurePosixPath
import sys


def audit_trial(events):
    def one(kind):
        values = [e["envelope"]["payload"] for e in events if e["envelope"]["event_type"] == kind]
        if len(values) != 1:
            raise ValueError("exactly one retained " + kind + " required")
        return values[0]
    terminal, attempt = one("trial.completed"), one("agent.attempt")
    result = terminal["result"]
    output = base64.b64decode(terminal["grade_output_base64"], validate=True)
    changes = attempt["patch_source_bytes"]
    if len(changes) > 128:
        raise ValueError("bounded changed-source audit required")
    errors, identities = [], {}
    for name, encoded in changes.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not name.startswith("src/click/") or path.suffix != ".py":
            raise ValueError("retained permitted source patch required")
        if encoded is None:
            continue
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 1_000_000:
            raise ValueError("changed-source byte limit")
        identities[name] = sha256(raw).hexdigest()
        try:
            # Compile only: never execute or import candidate code. Do not
            # inherit this auditor's future flags into the candidate program.
            compile(raw, name, "exec", dont_inherit=True)
        except SyntaxError as exc:
            errors.append({"path": name, "line": exc.lineno, "offset": exc.offset,
                           "exception_type": type(exc).__name__, "message": exc.msg})
    corroborated = bool(errors and b"SyntaxError" in output and any(e["path"].encode() in output for e in errors))
    classification = ("candidate_syntax_error_corroborated_by_grader" if corroborated else
        "changed_source_syntax_error_requires_attribution" if errors else
        "environment_flag_requires_separate_investigation" if result["infra_invalid"] else
        "passed" if result["functional_pass"] else "candidate_or_checks_failure")
    return {"run_id": result["run_id"], "classification": classification,
        "recorded_infra_invalid": result["infra_invalid"], "recorded_functional_pass": result["functional_pass"],
        "changed_source_syntax_errors": errors, "source_sha256": identities,
        "grade_output_sha256": sha256(output).hexdigest(),
        "auditor_python": list(sys.version_info[:3]), "candidate_code_executed": False,
        "historical_score_changed": False, "exclude_from_denominator": False,
        "assurance": "retained_candidate_compile_and_grader_output_not_full_environment_diagnosis"}

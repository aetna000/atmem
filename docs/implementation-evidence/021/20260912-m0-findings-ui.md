# M0 evidence-linked findings and existing UI — 2026-09-12

AtMem `2.3.0b1` translates verified Black Box facts into deterministic,
bounded findings for the existing Activity/Evidence workspace. It does not add
an incident navigation area, model-generated diagnosis or executable
remediation.

Technical gates establish that:

- observed tool errors and failed flights remain `observed_failure`;
- missing completion and capture loss remain `missing_evidence` or
  `evidence_gap`, never proof of a successful or failed external outcome;
- a later success for the same authenticated tool-call identity creates a
  `recovered_error` in `superseded` state while both original events remain;
- every finding carries a stable identity/revision, timestamp-bearing exact
  event reference, assurance label, inspection guidance and
  `external_outcome=unknown`;
- cross-subject execution lookup returns the same 404 as a missing execution
  and does not touch memory state;
- finding controls are native keyboard buttons and pivot to exact evidence in
  the existing view.

`tests/test_incident_resolution.py`, `tests/test_dashboard.py`, the incident
cases in `tests/test_execution_capture.py`, and affected control-plane/browser
fixtures passed. Success, error, gap and recovery are deterministic fixtures;
the installed OpenClaw success and timeout evidence is recorded separately in
the [Spec 020 journal](../020/20260912-m0-investigation-preview.md).

No independent operator cohort was run. The engineering preview therefore
does not claim measured usability; Spec 021 T024 remains open.

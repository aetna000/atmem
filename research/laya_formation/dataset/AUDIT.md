# Independent non-sealed audit

The reviewer receives only `audits/nonsealed-packet.json` and this procedure.
They must not receive `nonsealed-answer-key.json`, repository generator code, or
sealed-test material. The packet contains 400 deterministic, blinded rows with
at least 60 examples for every high-risk tag required by Spec 041.

1. The release operator creates a response template with `python -m
   research.laya_formation.dataset.review_audit template --packet
   nonsealed-packet.json --output review.json`.
2. The independent reviewer sets a stable reviewer ID and ISO-8601 `signed_at`,
   chooses exactly one listed choice for every row, and records any critical
   privacy, credential, licensing, scope, or target-correctness concern in that
   row's `critical_findings` list. They retain `answer_key_accessed: false`.
3. The reviewer creates a private Ed25519 key outside the repository, signs with
   `python -m research.laya_formation.dataset.review_audit sign --review
   review.json --private-key reviewer-key.pem --output review.signed.json`, and
   transfers only the signed review. The private key is never copied into the
   repository or artifact root.
4. Only after receipt does the release operator score with `python -m
   research.laya_formation.dataset.review_audit score --packet
   nonsealed-packet.json --answer-key nonsealed-answer-key.json --review
   review.signed.json --output audit-result.json`.

The scorer rejects missing/duplicate rows, unknown choices, packet substitution,
answer-key membership differences, a false independence attestation, and an
invalid or altered Ed25519 signature. Passing requires at least 400 reviewed
rows, at least 99 percent exact target correctness, and zero critical findings.
Failure invalidates staging/training until the source issue is corrected and a
fresh dataset and audit packet are generated.

# Recovery review disposition

Claude Opus 5.5 was invoked with `--effort medium --tools '' --permission-mode plan`.
Raw reviews are retained under `review/opus-5.5-medium-recovery-*.json`.
Reviews distinguish in-progress snapshots from final verification; none is a
third-party benchmark attestation. One supplemental review hit its session limit;
a follow-up after the stated reset completed normally, using the same model.

## Addressed

- Exact finite numeric equality preserves booleans/strings/large integer precision;
  raw source responses and original argument representations remain retained.
- Native-provider shutdown proof is required only for the mode that actually used
  that provider. System-context delivery uses the original explicit delivery proof.
- MCP metadata exemptions are explicit. Independent logged calls/results remain
  checked. Original023/085 and interrupted129 were verified offline by the worker.
- Source histories, API/gateway/ledger coverage, completed results, budget rows,
  exclusive execution/grade intents and epoch provenance are preserved.
- Trusted parent independently checks science, allowed source differences, raw
  receipts/artifact pins, budget inheritance/cap and exact inherited result bytes.
  Controller/validators/descriptor/bundle/proofs/task configuration are pinned.
- Parent checks run before launch, after the child exits, and at independent
  validation. Launch records are bound to their specific parent contract.
- Partial offline preparation is preserved; a different output is used for a safe
  new import, with no earlier workload launch. Uncertain work is never reset.
- Expired receipt sets require fresh actual qualification on a retry. Validation
  remains freshness-gated; the original 24h rule is not silently bypassed.
- Unknown supervisor states fail closed; installed running/supervising/repairing/
  recovering states are recognized explicitly.
- All three actual runtime binaries were inspected: Mach-O arm64-only. Administrative
  Intel Python does not silently select an Intel slice of a universal runtime.
- Bundle referent hashes and launch-contract identity are verified; blank log lines
  are skipped before JSON parsing. Input manifest paths are absolute resolved pins.

## Limits

Repair authorization is bounded to the documented implementation scope. Generic
reconstruction of a new, interrupted side effect is not assumed. Source revisions
are disclosed; original grades and actions cannot be rerolled. Hosted model
inference is not claimed bit-identical. Parent tests and real qualification remain
necessary after the code review.

An additional offline normalizer audit matched 468 of 517 archived traced tasks;
49 legacy trajectories were rejected and 83 had no backend trace. None of the 49
is in the selected 20. A sampled rejected case used malformed legacy `tool_call`
wrappers; this does not classify all49 or establish compatibility with all 600.
The new isolated profile excludes that wrapper. This diagnostic is not a score or
a reason to remove any task from a future600 campaign.

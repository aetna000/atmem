# Production memory benchmark tasks

## Foundation

- [x] [T001] Add strict benchmark manifest schema, source/license metadata, and claim gates.
- [x] [T002] Add ranking, evidence coverage, latency, throughput, and resource metrics.

## LoCoMo adapter

- [x] [T003] Implement official LoCoMo loader with format and evidence-ID validation.
- [x] [T004] Implement real AtMem ingestion and recall mapping for LoCoMo turns.
- [x] [T005] Implement LoCoMo CLI, raw JSON output, Markdown summary, and refusal/downgrade behavior.

## Staged datasets and quality

- [x] [T006] Add LongMemEval and BEAM staged manifests with acquisition and readiness documentation.
- [x] [T007] Add tests for digest mismatch, partial corpus claims, metrics, evidence mapping, and no implicit egress.
- [x] [T008] Run the full focused regression suite and document the first real LoCoMo result with honest limitations.

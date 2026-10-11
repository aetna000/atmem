# Security and Evidence Threat Model

## Assets and trust boundaries

Canonical memory, immutable source evidence, authority scope, lifecycle state,
generation and policy remain trusted only after reload through AtMem. Dataset
rows, Laya/Jev/Qwen output, AtBot output, downloaded weights, Hugging Face
metadata and benchmark results are untrusted inputs. Local accelerators, SSH
hosts and rented compute are execution environments, not authority stores.

## Threats and required controls

| Threat | Control | Blocking evidence |
| --- | --- | --- |
| Prompt or evidence injection asks the model to mutate memory | Typed finite questions contain no mutation capability; canonical service revalidates | forged-operation and injection tests |
| Cross-scope opaque ID reuse | Request IDs are bound to scope and generation; unknown/stale IDs fail closed | cross-subject/workspace/generation tests |
| Invented quote, offset or normalized value | AtMem computes source spans and digests; unsupported value escalates/reviews | exact-range and unsupported-value tests |
| Deleted/revoked candidate races | Reload immediately before disposition | deletion/revocation race tests |
| Silent tokenizer truncation changes evidence | Shared packer preserves question/choices and emits explicit range loss | byte-parity and overflow tests |
| Malicious or corrupt model artifact | Immutable revision, file inventory, Safetensors-only, digest and clean-load gate | download/scan/reload receipt |
| Training-data poisoning or oracle error | Executable oracle, independent validators, group splits and stratified audits | audit and invariant reports |
| Sealed-test leakage | Labels inaccessible to training; firewalled post-freeze audit; correction invalidates the version | split/access tests and signed review |
| Credential exfiltration | Environment/interactive secret only; no values in arguments/logs/artifacts; secret scan | planted-secret regression |
| Remote benchmark disclosure | Explicit egress approval and dataset-license check; minimum authorized payload | no-egress preflight and request digest |
| Moving Jev identity | Reject alias-only snapshots and response-model mismatch | pinned-model preflight |
| Rental persistence/data remanence | Synthetic/public inputs only, off-instance checkpoint sync, verified recovery and teardown | compute receipt |
| Misleading synthetic claim | Claim tier is machine validated and synthetic reports are visibly labeled | report-schema tests |

## Logging policy

Product logs may contain request IDs, schema/model/calibration digests, reason
codes, durations, token counts and outcome categories. They must not contain
source text, choices containing user content, credentials or provider payloads.
Full authorized decision evidence belongs in AtMem's protected evidence system,
not ordinary logs.

## Failure policy

Malformed output, nonfinite scores, missing choices, revision mismatch,
calibration mismatch, overflow, timeout, denied egress or provider failure can
only select deterministic fallback, explicit review or withholding. None may
implicitly accept, widen scope or reuse stale output.

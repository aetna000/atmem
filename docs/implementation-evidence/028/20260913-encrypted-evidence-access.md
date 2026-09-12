# Spec 028 source verification — encrypted evidence and privileged access

**Date**: 13 September 2026
**Scope**: source tree for the unreleased `2.3.0b1` preview
**Result**: initial vertical slice verified; complete Spec 028 and release acceptance remain open

## Verified source behavior

- Protected evidence capture defaults to `full`: exact data and semantic metadata
  are sealed as opaque AES-256-GCM objects with fresh 96-bit nonces.
- Ordered text, image, audio and video fixture bytes survive an authorized AtMem
  read byte-for-byte and planted exact content is absent from the protected SQLite
  store and control-directory scan.
- `metadata` mode removes exact content, preserves encrypted descriptors and marks
  reconstruction false. `off` stores neither a protected object nor a legacy Black
  Box projection for the new event.
- The closed role matrix is enforced before evidence decryption: Viewer can view
  and search; Investigator adds reconstruction and recipient-encrypted export;
  Evidence Collector adds plaintext export and administration operations. Plaintext
  export requires the exact `EXPORT <run_id>` confirmation.
- Three explicitly created development identities authenticate through encrypted
  account records; evidence roles are not selected by an HTTP request header.
- The OpenClaw durable execution spool is AES-256-GCM encrypted and its hook journey
  captures exact prompt/context/model/tool values and bounded inbound attachment
  bytes into the protected vault.
- The Settings interface uses one collapsed Evidence protection row and a focused
  drawer rather than a page-sized form.

## Commands and observed results

```text
python -m py_compile atmem/evidence/*.py atmem/control/manager.py \
  atmem/control/web.py atmem/control/server.py atmem/service/application.py atmem/cli.py
python -m json.tool docs/capabilities.json
python -m json.tool atmem/schemas/v1/capabilities.json
pytest -q tests/test_evidence_protection.py tests/test_dashboard.py
  18 passed in 5.44s
pytest -q tests/test_http_api.py::test_evidence_accounts_enforce_view_reconstruct_and_plaintext_export
  1 passed in 1.98s
pytest -q tests/test_blackbox.py
  41 passed in 2.65s
pytest -q tests/test_documentation.py tests/test_release_metadata.py \
  tests/test_spec_task_inventory.py tests/test_sdk_packaging.py
  28 passed in 1.97s
npm run build
npm run typecheck
node test/execution-spool.mjs
node test/hooks.mjs
  passed
```

Additional post-migration gates passed: 79 protected-evidence/Black Box/control-
store/execution/dashboard tests in 14.82 seconds; 18 control-evidence/execution
tests in 14.73 seconds; 41 delegated-context tests in 3.44 seconds; 30 HTTP,
documentation, metadata and packaging tests in 93.61 seconds; and the complete
OpenClaw build, typecheck and test suite against OpenClaw 2026.9.3.

## Cryptographic profile exercised

- Content encryption: `cryptography` AES-256-GCM. The focused suite includes
  round-trip, ciphertext tamper rejection and the NIST SP 800-38D 256-bit empty
  plaintext/AAD known-answer value.
- Portable recipient bundle: optional `pqcrypto==1.0.0` ML-KEM-768 and ML-DSA-65,
  with round-trip, ciphertext tamper and missing-provider fail-closed checks.
- `pqcrypto` describes its implementations as clean and portable but not formally
  audited. This evidence makes no FIPS 140 or independent implementation-validation
  claim.

## Open limitations and release blockers

- Existing control-plane SQLite stores migrate to an application-encrypted container,
  but other historical memory, mirror, backup or externally configured stores have
  not all passed verified cleanup. Product-wide FR-002 protection is therefore not
  claimed for every upgraded installation.
- The development profile uses mode-0600 external evidence and identity keys.
  Application lock/unlock, resumable wrapping-key rotation and per-run key rewrapping
  are implemented; production OS keychain, TPM/secure-enclave and KMS/HSM providers
  remain unavailable.
- The vault decrypts and scans objects for queries; scale indexes, encrypted search,
  capacity/backpressure measurements and artifact chunk streaming remain open.
- Attachment capture currently buffers within the adapter's declared 100 MiB bound;
  chunked streaming and concurrent-load matrices remain open.
- Plaintext CLI/API export materializes the authorized payload in process memory;
  the normative no-staging streaming export profile and interruption cleanup gate
  remain open.
- The exact-content CLI/API/MCP boundary is present, but complete dashboard media
  rendering and the installed fresh-process dead-agent reconstruction gate remain
  open.
- No release tag, GitHub release, PyPI artifact or npm publication was created or
  verified by this work.

## Consumer-hardware measurement

Measured locally on the development Mac profile with Python 3.12.2. The declared
2.3 preview ceiling is 100 MiB per original artifact.

| Exact text fixture | Capture | Authorized read | Python traced peak | Vault size after fixture |
| --- | ---: | ---: | ---: | ---: |
| 1 MiB | 0.020 s | 0.006 s | 2.3 MiB | 1.0 MiB |
| 100 MiB (declared maximum) | 1.087 s | 0.306 s | 225.0 MiB | 101.1 MiB |

The complete benchmark process reached approximately 444 MiB resident/peak memory.
These measurements demonstrate the current buffered profile; they do not substitute
for future chunked streaming, concurrent-load or additional-platform measurements.

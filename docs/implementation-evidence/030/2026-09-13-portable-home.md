# Spec 030 implementation evidence — 2026-09-13

## Implemented boundary

- Versioned canonical AtMem Home with CLI/environment/default precedence,
  home-relative durable defaults and symlink/escape refusal.
- Content-free public manifest, structural verification, active-writer detection
  and a verified quiescent snapshot command.
- Streaming AES-256-GCM content-addressed artifact vault with atomic writes,
  deduplication, authenticated reads, tamper detection and bounded-memory hashing.
- Exact ordered evidence materialization for text, links, documents, images, audio
  and video. OpenClaw captures current media, managed inbound references,
  staging-time originals and supported legacy aliases without directory guessing.
- Read-only copied-home restore, copied Administrator login, Administrator adoption,
  session rotation and immutable adoption receipt.
- Discover/preflight/copy/verify/switch/commit migration journal, resume at every
  boundary, uncommitted rollback and unconditional source preservation.
- Compact authenticated dashboard Home health/verify/adopt/migration guidance plus
  CLI JSON/human forms.

## Focused verification

```text
python -m pytest -q tests/test_home.py tests/test_http_api.py tests/test_dashboard.py
27 passed (before final selected-home routing case was added)

python tools/release_metadata.py --tag v2.3.0
AtMem 2.3.0 / bridge 2.3.0 / npm latest / prerelease false
```

`test_dead_agent_multimodal_home_reconstructs_without_source_dependencies` creates
an Administrator and exact ordered text, URL, document, image, audio and video
evidence, copies only the AtMem Home, deletes the source and reconstructs every
byte from the copy. Its raw-file scan rejects planted credentials, prompt, URL and
binary signatures.

`test_legacy_migration_resumes_after_every_journal_boundary` interrupts discover,
preflight, copy, verify and switch separately, then resumes to commit without
changing the source. Separate coverage verifies rollback and live-writer rejection.

`test_non_default_home_routes_durable_component_defaults` starts a fresh process
with a non-default `ATMEM_HOME` and checks control, identity keys, AtBot, dashboard,
delegated-provider and provider-adapter defaults remain beneath that root.

## Honest limits

- The local design is single-writer and has no cloud sync or concurrent
  multi-primary merge.
- Snapshot requires a stopped dashboard writer; this release does not claim an
  online SQLite backup across independently running host writers.
- Indexes are explicitly rebuildable and adoption marks them for rebuild. Exact
  evidence browsing does not depend on them; automatic cross-platform vector
  rebuild remains an operational follow-up.
- Streaming/deduplication behavior is tested with bounded fixtures rather than
  physically allocating a 10 GiB test artifact.
- OpenClaw can retain exact model-delivered media only when its hook supplies those
  bytes. Otherwise AtMem retains the safe host-managed original and labels the
  model representation unavailable.

Final gates: `1540 passed` in the source suite; `42 passed` in the focused
AtBot/framework/provider suite; the deterministic benchmark passed all 24 cases.
Both Python distributions passed twine and sdist rebuild. A clean environment
installed AtMem 2.3.0 plus AtBot 0.1.0a6 with no broken requirements and passed the
installed package, delegated contract and HMAC transport smokes. Persisted-state
fixtures created by 2.1.0, 2.2.3, 2.2.4, 2.2.5 and 2.2.6 all upgraded, preserved
memory/control identity and verified encrypted logical control schema v6.

OpenClaw 2.3.0 build/typecheck/hooks/smoke/prepack passed. The live latest host was
2026.9.4 and its reviewed declaration fixture passed the finite compatibility gate.

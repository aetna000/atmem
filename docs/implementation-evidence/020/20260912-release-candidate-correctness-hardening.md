# M0 release-candidate correctness hardening — 2026-09-12

Candidate versions: AtMem `2.3.0b1`, OpenClaw bridge
`openclaw-memory-atmem@2.3.0-beta.1`, AtBot `0.1.0a6`. The installed host was
OpenClaw `2026.9.1` on macOS. This is local development evidence, not a
published-release claim.

## Corrected boundaries

- Producer-sequenced deliveries now require one complete producer tuple, a
  stable event ID and an ISO-8601 UTC event time with millisecond precision.
  Legacy unsequenced events may still use AtMem ingest time. Parent and retry
  references cannot exist without their required execution and attempt IDs.
- Replay identity no longer depends on a server-generated timestamp. A
  conflicting position is durably classified and retained in the conflict
  index, but is not described as accepted evidence. The OpenClaw spool removes
  such a terminally classified conflict without claiming its body entered the
  evidence chain.
- The public MCP and CLI recording surfaces expose the full delivery envelope.
  Timeline rows retain producer and receive time separately; the dashboard
  displays both and flags an observed delta above five minutes as possible
  clock skew or delayed delivery.
- Modern execution paging cannot fall through into legacy run-ID rows after
  reaching a page boundary. Dashboard delivery totals use database aggregates
  rather than loading entire delivery, conflict and gap tables.
- OpenClaw-specific run classification and progress-card equivalence live in
  an adapter profile. Gap events populate the gap projection, runtime coverage
  uses the coverage contract, execution projections use the status classifier,
  identifiers normalize whitespace and URL-encoded execution IDs resolve.
- Upgrade notes now state that persona injection is default-off and direct
  support for automatic recall is default-on. They also state that a bounded,
  redacted error reason may be derived from a tool result.

## Automated verification

The focused execution, identity, HTTP and control-plane slices passed 61 tests.
The complete Python regression run passed **1,489 tests** in 122.23 seconds;
the only output was an upstream `pydantic_graph` deprecation warning. The
declared optional Mem0 gate used `mem0ai==2.0.20` in the repository virtual
environment and passed its three tests.

The OpenClaw bridge passed TypeScript build, typecheck, its full unit suite and
all installed-style smoke journeys. Packaging reran those prepack gates. The
Python wheel/sdist build and installed-wheel smoke gate passed. Release
metadata resolved to AtMem `2.3.0b1`, bridge `2.3.0-beta.1`, npm tag `beta`,
and prerelease `true`.

Artifact SHA-256 values:

- wheel: `715ecd52a1b21d5707937e3a5d1177fbacb377b02d2ea54230527fe9033bb736`
- sdist: `c11fbea471b04b0d6863c2e68b333bfcca9cc8496c7da05a99a9f2e445d12df8`
- OpenClaw archive: `cacdd5fc9a2e61332d0ab049e6b37f894576d3bf68699a3bcdf3b8c0a0b641f9`

## Installed local verification

The corrected archive was installed into the user's local OpenClaw extension
directory and the loopback gateway restarted successfully. Plugin inspection
reported `memory-atmem` loaded from the archive at version `2.3.0-beta.1`.
The AtMem dashboard was restored at `http://127.0.0.1:8768/`.

Real OpenClaw run `715141b1-b829-4681-ab2a-4887e8692214` returned exactly
`ATMEM_CORRECTNESS_OK`. Its five retained current-contract events had complete
producer identity, contiguous sequence 1–5, millisecond UTC event times,
separate receive times, valid timeline-chain integrity, structurally complete
coverage, no findings and verdict `completed_successfully`. At the verification
snapshot the delivery projection contained 24 durable deliveries, zero
conflicts and zero reported gaps; the overall evidence chain contained 922
valid events. Historical events were preserved.

AtBot remained a separate, non-authoritative companion. It was intentionally
configured to local Ollama `qwen3:4b`; `atmem atbot doctor` reported all eight
checks true with local egress only. Evidence capture and acceptance do not
depend on AtBot availability.

## Limits

Only the installed OpenClaw profile was exercised here. Producer time is
host-reported; AtMem exposes receive time and skew rather than asserting that
the host clock is true. Coverage is declared from the adapter profile and
observed events because the evidence store does not yet retain the runtime
adapter version. Black Box stores digests and bounded metadata, not raw prompts,
responses, tool parameters/results, secrets or chain-of-thought. It does not
prove semantic correctness or external-world outcomes. No package, tag or
GitHub release was published by this verification.

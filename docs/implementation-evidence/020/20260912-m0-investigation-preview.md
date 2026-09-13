# M0 durable investigation preview — 2026-09-12

Candidate versions: AtMem `2.3.0b1`, OpenClaw bridge
`openclaw-memory-atmem@2.3.0-beta.1`, AtBot `0.1.0a6`. The installed host
was OpenClaw `2026.9.1` (`ad6fe23`) on macOS, with local Ollama
`qwen3:1.7b` used for the final real turn. This is development evidence, not a
published-release claim.

## Implemented boundary

- A host-neutral `ExecutionIdentity` accepts authenticated scope and only
  supplied session, job, execution, parent, attempt, retry, run, turn, tool and
  step references. The independent M0 profile never infers a task or parent.
- The OpenClaw bridge assigns a persistent producer instance, a new process
  epoch and increasing producer sequence. Its owner-local atomic spool is
  capacity- and age-bounded; it removes an event only after AtMem returns
  `durably_accepted`.
- Control schema v6 atomically appends accepted events to the signed Black Box
  chain and its delivery index. Same-position/same-byte replay is idempotent;
  conflicting bytes are retained separately. Indexed reads require the
  authorized subject and do not join canonical memory.
- Projections expose event time separately from receive time, explicit links,
  missing producer sequences and incomparable cross-producer order. Derived
  delivery/conflict/gap indexes can be pruned without rewriting signed source
  evidence.

## Automated evidence

`tests/test_execution_identity.py`, `tests/test_execution_capture.py` and the
OpenClaw `execution-spool.mjs` gate cover closed parsing, scope refusal,
restart/replay, duplicates, conflicts, capacity loss, retention, explicit
parent/retry links, zero memory activation and a virtual 40-minute run. The
affected Python slice passed 55 tests together with incident, dashboard and
v4/v5-to-v6 migration coverage. The complete bridge build, typecheck, unit
suite and installed-style smoke journeys passed.

The final repository-wide fallback-path run passed 1,484 tests in 150.29
seconds. The affected execution, incident, dashboard, HTTP, task-adapter,
documentation and control-plane rerun passed 106 tests. A prior full run found
the capabilities-schema omission and an unindexed legacy `OR` lookup; both were
fixed before these final runs. The only remaining output was an upstream
Pydantic AI event-loop deprecation warning.

The final 100,000-delivery benchmark returned a 100-event first page with
`lookup_p95_ms=2.448`, accepted-event `write_p95_ms=0.382`, and a
72,744,960-byte SQLite file. The lookup stays below the M0 200 ms p95 budget;
these local measurements are not a cross-machine performance claim.

The final packed bridge archive was 39.5 kB with npm shasum
`e068097ff7dcfb4ddac75227f0d668aef3144fb0` and SHA-256
`16038b085dbac1ff281e5a4bece39a651733aa3b535812679ae1ed628bbf33c9`.
The final AtMem wheel SHA-256 was
`a962914a2c301bbd9671a725925bb1f6020e6634bbce5fc7f498feb2e3a221c1`.

## Installed OpenClaw evidence

The candidate archive was installed into an isolated OpenClaw state directory;
the user's global bridge and gateway were not changed. Recall, memory capture
and model-visible AtMem tools were false while control-plane evidence was true.
Real gateway run `b149b037-baa7-4bf8-9fa9-3687fb95e990` returned exactly
`M0_OK` and retained six events with verdict `completed_successfully` and no
attention findings. Two separately retained real timeout runs have `failed`
verdicts; one exercised five successful read calls before the terminal timeout.
A timeout is not evidence that an external side effect did not happen.

Across the isolated host record, the evidence chain verified with no errors and
`raw_content_stored=false`. At the final snapshot it contained 34 durable
deliveries, zero conflicts and zero reported spool gaps. Synthetic fixtures,
not those real turns, provide the deliberate conflict, capacity-loss,
missing-sequence and recovered-retry cases.

After correcting explicit-false precedence in the bridge configuration, a
fresh gateway was started with `blackboxEnabled=false`. Real run
`013fb8e1-cfce-41f1-80ca-c2658944a565` returned `DISABLED_FIXED_OK`; retained
event count remained exactly 34 before and after. The option was restored to
true and configuration validation passed before the isolated gateway stopped.

AtBot was installed and used, but not trusted with evidence authority. Its
live local-Ollama eligible-candidate query selected the editor record and
withheld an unrelated city record; `atmem atbot doctor` then reported all eight
checks true. M0 capture, delivery acceptance and findings remain deterministic
when AtBot is unavailable.

## Limits

Only the OpenClaw profile has installed-host evidence. Historical gaps cannot
be reconstructed. Raw prompts, responses, parameters, results, secrets and
chain-of-thought are not retained by default. M0 does not prove semantic
correctness, external outcomes, root cause, task relationships, autonomous
retry/remediation or human usability.

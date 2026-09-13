# Selective automatic context and precise time — 2026-09-09

Inspected local OpenClaw 2026.9.1 and AtMem run
`100623e9-9baf-4092-ac0e-695971cb0c06`. The flight contains one context disposition,
one model input, one model output and a successful terminal event. Its one
1,233-character context block names nine unique records: seven unconditional
persona records plus two recalled procedural records, with zero overlap. This
was excessive context selection, not nine repeated injection hooks.

Persona selection sorted stable slots and recent facts without query relevance.
The two recall candidates scored highly through relative FTS normalization even
though each matched only one of eight query terms. The original request was a
local shopping search; the overlapping list-related procedural advice did not
support that request. No private memory contents are reproduced here.

Two web_fetch completions reported errors with no result. The corresponding host
transcript confirms HTTP 403 errors wrapped in OpenClaw's untrusted-content
security notice. The first-line-only diagnostic extractor retained the notice,
not the HTTP status. These are actual failed tool steps in a completed run,
separate from the earlier progress-card envelope discrepancy.

Changes:

- Automatic bridge recall now opts into the existing calibrated direct-support
  gate. Manual search and the engine's legacy default remain available.
- Bridge/setup persona defaults off; explicit opt-in is respected. Persona IDs
  are excluded from recall when enabled. Component counts and selection profile
  are retained in context evidence. No memories are deleted.
- Known wrapped HTTP errors retain only the status prefix. Unknown wrappers
  provide no invented reason; historical notice-only diagnostics are described
  as unavailable. Historical evidence is not rewritten.
- Successful runs with tool errors display completion plus a failed-step action.
  Tool errors remain red in detail; evidence gaps remain amber; run failures and
  invalid integrity remain failures. No automatic recovery or answer correctness
  claim is made.
- Stored timestamps already use ISO 8601 UTC with microseconds. Preserve these
  exact signed values. UI adds local seconds, milliseconds and timezone, with
  original UTC available in details. No timestamp migration or rounding of
  historical records occurs.

Validation and activation:

- 120 affected Python tests passed: Black Box (41), recall evidence/MCP (17),
  control plane/layers/retrieval quality (62). UTC tests include exact-second
  timestamps, for which the clock helper now explicitly emits six fractional
  digits instead of allowing ISO auto-formatting to omit the fraction.
- Bridge build, typecheck and full `npm test` passed. Real bridge hook → MCP
  checks cover selective defaults, useful recall and persona deduplication.
- Browser gate passed live updates, error/step separation, retained evidence
  details, reconnect, background toggle and four routes at 390px without overflow.
  Deterministic timezone tests include Sydney winter/summer and UTC conversion.
- Final installed AtMem 2.2.6 wheel SHA-256:
  `a4461b154db1dc656fb1113b5d95367f467347b27045872998653823d8a29920`.
  Bridge 2.2.6 archive npm shasum:
  `7111445124611cfaf931e1cfbc53e2ba5582d121`.
- Local OpenClaw configuration explicitly sets `persona.enabled=false` and
  `recall.requireDirectSupport=true`. These change context selection only;
  records remain available. Explicitly setting persona back to true restores
  always-on persona behavior; false direct-support mode restores rank-only recall.
- Dashboard and gateway restarted. Installed bridge files match the tested build;
  an isolated installed-engine check withholds the weak-match fixture while
  retaining relevant recall. Served dashboard contains the final UI markers.
  Temporary browser preview stopped.

No new live agent conversation was launched. The local incident is real-host
inspection; synthetic selection, bridge RPC and browser tests are distinct
acceptance classes. This is a local development installation, not a published
release. Historical errors and hashes remain unchanged; clearer presentation
must not be mistaken for retroactively captured diagnostics.

# Spec 003 — 2.2.6 host identity and tool correlation fixes

- Source base: `740c5c89d63c5d95bc69ee28ccec0cb14368f28d`, branch `storizon`.
- Tree: dirty before and after this work. Existing packaging-test changes,
  `todo.md`, `.vscode/sessions.json`, `RandD/` and `tmp/` were preserved.
  This is local source/artifact validation, not a reviewed clean release commit.
- Scope: FR-034–FR-037, adapter/core portions of SC-014/SC-016;
  T050a, T052a, T053 complete. T049, T050, T051, T052 retain pending real-host gates.
- First captured UTC timestamp during verification: `2026-09-09T04:36:58Z`.
  Earlier source-edit and per-command start timestamps were not captured; no
  exact start time is claimed for those commands. Journal completed: `2026-09-09T04:45:22.360464+00:00`.
- Python 3.12.2, Node 26.5.0, pytest 9.1.1, TypeScript 5.6;
  AtMem/bridge 2.2.6, AtBot 0.1.0a6; Pydantic AI slim
  1.107.5, LangChain 1.3.11, LangGraph 1.2.7.
- Resolved OpenClaw development dependency: 2026.9.3. Global CLI:
  OpenClaw 2026.9.1 (`ad6fe23`), Claude Code 2.1.236. Version inspection only;
  no new real model turn or private Storizon request was executed.

## Changes and acceptance boundary

The default owner gate still refuses absent/false ownership. Legacy
`requireOwner: false` alone now refuses rather than forwarding a configured
user identity without isolation checks. An explicit `localOperator` assertion
requires exact agent/workspace/session generation plus host CLI origin and run
ID, and rejects channel-originated and explicit non-owner turns. Isolation is
an operator trust assertion; host metadata must come from the host, never model
text. Hosts missing these fields remain unsupported. The earlier reported local
fixture must be rerun against this stricter configuration.

Tool hooks retain context-supplied invocation IDs when event IDs are absent.
The verifier matches requests and completions in both directions by invocation,
turn, session, agent, workspace, subject, canonical tool name and event order.
Reused IDs and unmatched completions cannot establish closure. Raw observations
remain intact; conflicts use the existing `conflicting_completions` report field.
Missing completions stay `incomplete_evidence`; observed terminal errors can
close evidence as `completed_with_tool_errors`.

No HMAC profile, signed v1 payload, package version or persisted schema changed.
Historical verification entries remain unchanged. This entry extends the
historical synthetic Amendment A/B evidence recorded in Spec 003 tasks; it does
not supersede the operator's independent results.

## Commands and results

- `python -m pytest tests/test_blackbox.py tests/test_delegated_context.py tests/test_delegated_control.py tests/test_delegated_transport.py -q`: **131 passed**, 12.63 s.
- `npm run prepack --prefix integrations/openclaw`: **passed** build, typecheck,
  manifest, recorded hook-context compatibility, setup, hooks, new identity
  matrix, task tools, all 3 positive/20 negative delegated vectors and smoke.
- `node integrations/openclaw/test/delegated-journey.mjs`: **passed** after
  extending the journey to read/exec completion/error/missing/cross-turn cases.
- `python -m pytest -q`: **1453 passed**, no skips, 107.24 s; one third-party
  Pydantic event-loop deprecation warning. This suite includes pre-existing
  workspace packaging-test edits; it is not a clean-commit CI result.
- `python tools/release_metadata.py --tag v2.2.6`: **passed** aligned 2.2.6
  Python/bridge versions, stable `latest` npm channel, non-prerelease metadata.
- `python -m build --outdir ARTIFACT_DIR`: **passed** wheel/sdist build.
- `npm pack --ignore-scripts --pack-destination ARTIFACT_DIR` from
  `integrations/openclaw`: **passed** following the successful prepack gates.
- `python -m twine check ARTIFACT_DIR/atmem-2.2.6-py3-none-any.whl ARTIFACT_DIR/atmem-2.2.6.tar.gz`: **passed**.
- New isolated venv: `python -m venv ARTIFACT_DIR/venv`; its Python ran
  `-m pip install --disable-pip-version-check ARTIFACT_DIR/atmem-2.2.6-py3-none-any.whl`,
  `-m pip check`, `tools/smoke_installed_package.py` and
  `tools/smoke_delegated_transport.py`: **all passed**, outside checkout with
  `PYTHONPATH` removed. UTC interval: 04:42:04.433233–04:42:17.055587 on 2026-09-09.
- Extracted npm tarball, copied only test harnesses and the provider helper into
  an isolated layout, then ran `node test/delegated-identity.mjs` and
  `node test/delegated-journey.mjs` with `ATMEM_TEST_PYTHON` and
  `ATMEM_TEST_COMMAND` set to that venv: **passed**, UTC interval
  04:42:47.127613–04:42:50.499752. The bridge and AtMem were real packaged artifacts;
  host events and provider decisions were synthetic. This does not establish
  live OpenClaw/Claude CLI or Storizon compatibility.
- Archive inspection: wheel verifier bytes match source; npm identity module
  matches compiled output and its manifest declares 2.2.6.
- `python tools/check_spec_tasks.py`: **passed**, 25 features / 621 tasks;
  source-subtask completion does not close the parent real-host acceptance gates.
- Scoped `git diff --check`: **passed**. Unrelated pre-existing `todo.md` EOF
  whitespace is outside this patch's checks.

Artifact directory (local, temporary): `/var/folders/yq/hy4_t8650sl77vkh7zvv97rc0000gn/T/atmem-003-artifacts-acqtsvpa`. Build/install logs remain there.
These validation artifacts were built before final evidence/task-status prose
updates; they are not publication artifacts for a final reviewed commit.

### Artifact SHA-256

- `atmem-2.2.6-py3-none-any.whl`: `0f78866c1e36045a1aff68de8f88096ebb6da1d40b55b91e412c3b04d6fb7e0d`
- `atmem-2.2.6.tar.gz`: `7261c827ef6066f67089e638aa46bfd0a50368a89f3ae9324f241c6b8cdea8f4`
- `openclaw-memory-atmem-2.2.6.tgz`: `f332490546fb2de61c409fd3a39b96bcb99dc29a3ad8e6c627974d73dbf8350d`

### Implementation and test SHA-256

- `atmem/control/blackbox.py`: `ea76763f2b3396c87707fa57ab2a5649b6466c2243aa46244dcc978065c4f1bb`
- `integrations/openclaw/index.ts`: `6b9a8805c725b37be86a2f562b6b985d7ba436a6a0281825bccbd459222958ed`
- `integrations/openclaw/src/types.ts`: `9f9ce28481f7e22d7868b847335af4ddaf6790bea995353959ef1b0f9b6169f7`
- `integrations/openclaw/src/delegated-identity.ts`: `af4949941f9d252876952dce7fa5472c7b82fc22c97dacf7318c55a75b48598d`
- `integrations/openclaw/openclaw.plugin.json`: `b5f0d130793de5e1b73171c8d61d32fe782a10d5c8000bfa03cef24f67e64b59`
- `integrations/openclaw/package.json`: `3ef434df50850adfe3db579514c412773f37873721467938e46d6269513038b0`
- `integrations/openclaw/test/hooks.mjs`: `519e4f751a0cc8716256f396e456958623c79747acfa53095e32448bd49ae6e3`
- `integrations/openclaw/test/delegated-identity.mjs`: `90063eaaf06709bb4af11f4f6fd9821cc12f04dc6626860900f3eccba065ba52`
- `integrations/openclaw/test/delegated-journey.mjs`: `f753d3641ca2f3949187563a07c1554d95783ab11da3397fced4c62ef3c662e9`
- `tests/test_blackbox.py`: `f0dec77d04388a7386eb02e1931ef0c2423a4c65690fb1acd442f99f4f70a804`

## Outstanding real-host evidence

The operator reports actual Storizon inject/withhold decisions with matching v2
receipts, exact context digests, one/zero deliveries and complete verified flights;
two real OpenClaw 2026.8.1 + Claude CLI text-only turns passed with an explicit
isolated local mapping. No shared HMAC mismatch was reported. These remain
operator-reported observations: saved commands, exact remaining versions,
receipt/flight artifacts and the private endpoint fixture were not supplied.
A path to those artifacts was requested during this work.

The operator also reports that missing `senderIsOwner` blocks the default CLI
path and that read/exec requests lacking completion observations correctly yield
`incomplete_evidence`. No authenticated shared-channel fixture is available here.
The installed 2026.9.1 CLI and 2026.9.3 declaration checks cannot substitute for
a live 2026.8.1 run. T049–T052 remain incomplete until their real-host acceptance
is performed; shared-channel identity and toolful lifecycle readiness remain
separate unverified gates. No release was committed, tagged, pushed or published.

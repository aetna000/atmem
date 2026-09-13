# Progress-card duplicate result investigation — 2026-09-09

Inspected installed OpenClaw 2026.9.1 source, the affected session's SQLite
transcript and the corresponding Codex rollout, reading only the relevant tool
result. The final progress-card call reported revision 3, three of three steps.

The tool implementation returns two `text` blocks and a `details` object. The
native post-tool relay forwards the response as two `input_text` blocks. Using
AtMem's stable JSON hash reproduces both recorded hashes exactly:

- Tool result: `e54c38cf6df1f1cad2142cd9e79b47ad671d1071f0e862e125028b9c05332661`
- Native response: `3e68cf47a1810f1b821b17c0eaae6ed118bfae847c13e47b8f3b3c762e8bd3ad`

This establishes format-only differences for that inspected pair. It does not
prove arbitrary successful duplicate results are equivalent. Source locations:
`openclaw-tools-BODVdJQD.js` (progress-card tool),
`native-hook-relay-BRGvN3HA.js` (post-tool response),
`hook-helpers-D11aAm0B.js` (completion hook), and
`builtin-openclaw-zQV8Wwjr.js` (runner completion hook).

The bridge now emits optional comparison metadata only for exact validated
progress-card shapes. Projection requires matching requests, two distinct shapes,
successful outcomes and the same comparison digest. Both raw records remain.
Historical hash-only records retain their verdict, with clearer amber wording
when both observations report success. No host code or signed history is patched.

Validation:

- All three flagged progress-card calls in the inspected run reproduced both
  recorded raw hashes from their corresponding transcript details.
- Python: `tests/test_blackbox.py` 39 passed; `tests/test_control_plane.py` 42 passed.
- TypeScript build/typecheck and full bridge `npm test` passed. Includes real
  bridge hooks → RPC → persisted projection, raw-digest preservation and negative
  comparison fixtures. Dependency contract checks resolve OpenClaw 2026.9.3;
  locally inspected/running host remains 2026.9.1.
- Dashboard syntax and diagnostic presentation fixtures passed; running HTTP
  page verified to serve the new successful-duplicate wording.
- Local AtMem 2.2.6 wheel installed, SHA-256
  `8397d6fff54a3b28f4734b6f849778125e0612644b1ff6d8bef6997b908b65f5`.
  Local bridge 2.2.6 archive installed, npm shasum
  `5974e852b728c751f57bc5c1a6ef02e4ecf2bdd7`. Installed bridge source files
  matched tested build; isolated installed Python exposes the comparison profile.
- Dashboard and OpenClaw gateway restarted successfully. Reload the dashboard
  once to load the new JavaScript; subsequent activity refresh remains automatic.

No new real agent task was launched. Historical signed records were not enriched
or rewritten, so their hash-only discrepancy can remain amber. The exact local
incident diagnosis above is separate from machine-verifiable historical capture
metadata. New matching captures can establish equivalence automatically.
No version changes, release publication, commit or push performed in this slice.

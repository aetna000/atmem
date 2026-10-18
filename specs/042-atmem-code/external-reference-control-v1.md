# First external parent/reference control — prospective v1

Use only the first fixed preflight task, marshmallow-code__marshmallow-1229,
its pinned subtree, and the immutable image already runtime-qualified. Do not
pull another image, replace a failed task, inspect hints or send hidden material
to any coding model. This is qualification, not a benchmark solve or tuning.

Fetch and verify the pinned regular evaluator blobs `eval.sh`, `gold.patch`,
`test.patch`, `tests.json` into INTERNAL protected evidence only. Retain the
MIT license and pinned upstream harness constants, Python log parsers and
grading source at commit 02e7a74ffd0b707aab73d203fe87bdc7c76afc8e. Never print
patches, test identities or raw private test logs to the model-facing tool
output. Only safe status/count/hash summaries may be returned.

Run exactly one parent and one gold-reference attempt in fresh labeled
containers, sequentially. Use no network/host mounts, drop capabilities, enable
no-new-privileges and use 1 CPU/1 GiB/128 PID limits. A writable disposable
container layer is required because the exact upstream script uses `/testbed`;
this is a separate evaluator role, not the solver sandbox. Keep a 64 MiB
noexec/nosuid/nodev `/tmp`, 180-second controller/120-second script bounds,
8 MiB output bound and 8 GiB minimum host free space. Remove only the exact
task-created containers; keep the cached immutable image.

Check the image's tracked source matches the pinned base before either patch.
The reference receives only the verified gold patch before executing the exact
upstream eval script. Parent receives none. Check the verified test patch is
embedded in that script; do not apply it twice or modify it for a desired score.

Reuse upstream constants, parser alias and grading function bodies. A dependency
wiring adapter may remove module import statements and supply the upstream
namespaces/standard library; retain original source hashes and document that
this is not a full installed upstream harness invocation. No function logic,
expected tests, status labels or source test bytes may be rewritten.

Qualification requires actual parsed parent F2P failure (not merely an absent
test), a nonempty expected F2P set, and reference resolution under upstream
F2P/P2P semantics with actual parsed results. Report P2P skips distinctly rather
than claiming all expected tests fully passed. Preserve both failed/successful
attempts, missing markers, parser/setup errors, timeouts and resource stops.
No adaptive rerun or model feedback. A failure leaves the task unqualified.

Record planned hashes/command before dispatch and retain exact private outputs
encrypted. Export only encrypted evidence to MEM; do not place plain gold/test
material in a public metadata directory. This control does not qualify other
tasks, solver tool exposure, complete model usage or token/latency benefit.

# External metadata/environment preflight v1

Prospective bounded work under `cross-repository-evaluation-plan.md`. No coding
model, hidden test execution, task replacement or performance claim occurs here.

Pin `SWE-bench/swe-bench-tasks` revision
`3d07b464b7b311a0cbfb5ed5b2d8a3b96f84a33d` and task-tree object
`39df60edb3d9e709c7f6c19516c1d4b1fa3a8d50`. Verify their relationship via the
Git tree API. Use only complete, untruncated, content-addressed metadata.

Freeze ordered candidate pools for marshmallow-code/marshmallow, psf/requests,
and pylint-dev/astroid. Order each pool by SHA-256 of seed, NUL, repository,
NUL, instance ID. Seed is `atmem-repository-disjoint-preflight-20261017-v1`.
Take exactly the first two identities per repository. Retain `selection.json`
before reading any selected recipe. Do not replace failed metadata/environments
with later pool entries in this preflight. No source/patch difficulty or model
outcome enters selection. This is a feasibility sample, not confirmation.

Fetch only regular `task.yaml` and `Dockerfile` blobs of at most 256 KiB each;
verify their Git blob identity and record SHA-256. YAML is safely loaded and
required task identity/base-commit fields are checked. No `gold.patch`,
`test.patch`, `hints.md`, `eval.sh` or problem statement is fetched by this stage.
Recipes are retained as data and NEVER executed on the owner host.

Report declared platform, mutable/unpinned image references, metadata failures,
and the selected tasks even when all runtime qualifications remain open. The
initial worker is Linux/aarch64, 2 CPUs and about 4 GiB RAM. macOS internal free
space is about 13 GiB. Check registry metadata and local resources before any
image pull/build; do not assume amd64 images run or silently rewrite recipes.
No new Docker images or scripts are executed merely to complete this stage.

Write public benchmark metadata only to a new MEM benchmark subdirectory; keep
operator evidence/key material internal until encrypted archive export. Existing
files are never overwritten, and duplicate invocations must not silently sample
new tasks. A metadata-verified task is explicitly NOT environment-qualified,
reference-qualified, solver-ready or a scored result.

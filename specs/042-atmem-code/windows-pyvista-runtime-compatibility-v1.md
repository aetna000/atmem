# PyVista evaluator runtime compatibility v1

Prospective environment correction before any confirmation inference, T083.
The forty-candidate pool, product wheel, source policies, prompts, test sets,
grade parser and strict qualification gates remain unchanged. Retain every
original-image result; never overwrite it with a derived-runtime result.

## Evidence and fixed dependency choice

Two read-only image diagnostics establish historical PyVista 0.39.dev0 with
VTK 9.4.2, setuptools 78.1.1 and wheel 0.45.1. Observed reference regressions
include missing dataset attributes; setup also attempts network downloads
for isolated build dependencies inside network-disabled workers.

PyVista maintainers explicitly advise VTK <9.4.0 for PyVista older than 0.44.2:
[maintainer guidance](https://github.com/pyvista/pyvista/discussions/6886).
Their [VTK 9.4 incompatibility tracker](https://github.com/pyvista/pyvista/issues/6731)
documents the compatibility boundary. This supports a dependency diagnosis,
not proof that changing VTK makes any task pass.

Freeze VTK **9.3.1**, the compatible version identified in this
[upstream discussion](https://github.com/pyvista/pyvista/discussions/7201),
for all eight original PyVista images before new tests. Do not sweep
versions or choose a dependency version based on private test scores. Resolve
the exact cp39 Linux x86_64 wheel from PyPI's version-specific metadata and pin
its filename, byte length and SHA-256. Retain the exact metadata response.

## Derived image and offline setup boundary

Use each original immutable image as its base. Change only the VTK installed
distribution to the pinned wheel. Verify the complete before/after installed
distribution inventories, rejecting unexpected version changes or missing
packages. Verify original repository source/runtime fingerprints unchanged.
Record the original image digest, derived local configuration digest, recipe,
full bounded build logs, package checks and wheel checksums.

Supply an immutable offline wheelhouse containing only that VTK wheel and
setuptools 78.1.1 / wheel 0.45.1 wheels, also PyPI-hash verified. Existing
installed build dependency versions must match before construction; do not
silently upgrade them. PIP_NO_INDEX=1 and the fixed local PIP_FIND_LINKS
directory let the unchanged upstream setup command resolve build dependencies
without network. No setup/test script, target source, gold patch, hidden test,
denominator, skip rule or timeout is rewritten. Unsupported extra dependencies
fail rather than trigger uncontrolled online installation.

Public dependency download is an operator-only preparation step, separate
from source/agent/test execution. All grading/public-test workers remain
network-disabled. No owner configuration, host package installation, private
credential mount, image push or broad Docker cleanup is allowed. Keep both
physical Windows and WSL free space above the existing 8 GiB guard. Builds
must have explicit CPU/memory/time/output bounds and unique benchmark targets.

Derived image use is an explicit operator option accepting only its verified
local content digest, not a mutable tag or model-selected image. Apply the
same derived image and runtime settings to both arms and all eight PyVista
eligibility candidates. First run no-model installed package/source controls,
then unchanged parent/reference and source/public/proposal controls. A derived
environment does not qualify a task unless every existing gate passes.

The other repositories retain their existing immutable images. Publish the
environment change prominently with any results; it is not a reproduction of
the original image environment and cannot repair its old failures retroactively.

## Terminal-pool eligibility correction (before inference)

All eight original build attempts are terminal: seven verified derived images;
4315 refused the before-inventory guard. Its original image already has VTK
9.3.1, setuptools 75.1.0 and wheel 0.44.0, unlike the two diagnostic images.
Do not rebuild it with different build dependencies or silently admit its
unchanged environment. Preserve that refusal as environment attrition.

The next stage requires all eight complete distinct build records and an exact
terminal summary, not eight successful builds. Only byte-verified successful
records enter tests. This corrects an orchestration prerequisite, not a test
gate. Subsequently the owner explicitly authorized three qualifying PyVista
tasks, retaining four in every other repository: nineteen tasks / 76 attempts.
That amendment is recorded in windows-confirmation-v2.md before solver inference.
All original failures remain reported; no replacement task, dependency sweep,
weakened eligibility gate or product change is authorized.

# Requests-1327 source projection v2

Retain the two V1 source-boundary stops at the 40 MB snapshot guard. A read-only
image inventory identifies 2,996 untracked `.eggs` dependency-cache files totaling
52,268,531 bytes. Tracked repository source is only 1,246,717 bytes. This cache
is not solver source and must not be copied into model workspaces or deleted
from the test environment to force capture through the guard.

Use explicit operator-only profile `selected-six-v2` on the same pinned task,
image/base, scripts, tests and reference patch. The older profile remains strict.
The identity-bound Requests runtime profile may exclude only top-level `.eggs/`
from evaluator source capture. First check the complete base Git path listing
and refuse if any excluded path is tracked. No arbitrary ignore patterns,
source/test exclusions, caller-selected paths or solver API are added. Default
stopped-workspace capture still includes hidden roots and refuses symlinks.

Keep the existing source-only mutation policy and all source checks. The cache
remains in the image, is not changed by assembly, and is not exported to the
solver. Recheck assembled bytes using the identical explicit projection. Other
image files remain captured; source and aggregate limits are unchanged. Fixed
parent/reference counts are 1 target and 31 regression checks. Run unchanged
and reference-as-proposal once, with no model calls, replacements or retries.

Preserve the original V1 failures and new raw streams in separate evidence.
Public export still requires exact original public Git blobs/modes, no history,
no untracked files and the tracked-source fingerprint. This profile does not
by itself qualify public testing, general source capture or model performance.

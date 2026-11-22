# Plan — baseline and exact-history pilot

## Baseline

Use the encrypted native SDK pattern from Spec 053. Import typed interaction
episodes into a fresh, temporary application store, freeze the `context-fast`
generation and call `Memory.prepare_context_v3` without an explicit engine.
The benchmark measures the context returned to a caller. A fixed lossy summary
represents the working window after compaction. The literal comparator searches
the ordered retained lines from the authorized scope, with newest matches first.
Both arms use separately frozen development and holdout histories and the same
4,096-byte output ceiling. The separate 512-byte run probes behavior when less
context fits. No provider, host capture or browser session is used.

Score the development baseline first. Save the exact fixture hash, per-case
results and elapsed time. Classify cases where evidence was never eligible
separately from captured evidence that was missed or returned together with
outdated evidence. Source IDs and synthetic labels can appear in reports.
Report the corpus and budget evidence before attributing any gain.

## Candidate

If a matched run exposes a recoverable gap or a context-cost advantage at
equivalent answer accuracy, build a bounded literal follow-up on the existing
application-authorized discovery session. Do not
duplicate the history store or change the default context engine. Use the
canonical source ranges and the existing disclosure and audit boundary. Prefer
a literal match over regex for the first pilot. Fail visibly when a search
cannot complete within its scan budget. Keep result selection separate from
claiming that the result answers a question.

Combine the baseline context and follow-up output under the same total byte
ceiling and count both retrieval calls. Test scope and lifecycle at the search
boundary. Freeze candidate behavior before opening holdout results. Compare exact
evidence coverage, stale co-delivery, forbidden disclosure and cost. Treat small
differences as diagnostic and report the raw counts.

## Consistency review

FR-001 and FR-002 are covered by isolated native SDK and comparator fixtures
with separate seeds. FR-003 maps to the machine-readable per-case report.
FR-004 uses the existing authorization and encrypted audit boundary and requires
negative tests. FR-005 requires the retained baseline report and a matched
holdout. No migration, default host activation, or plugin changes are required.

# V3 operator-only grading request retention correction

Recorded during the existing scored cohort, before any private grading phase.
This does not replace the frozen candidate, cohort, prompts, tests or protocol
endpoints. No model attempt is interrupted or retried.

A read-only sizing check constructs each unchanged-source grading dispatch
from its already frozen public base and private grader. It does not inspect
model answers, token outcomes or private grades. All three PyVista records
exceed the unchanged 16,000,000-byte protected-event bound:

| Identity | Unchanged dispatch bytes |
|---|---:|
| PyVista-4311 | 16,417,347 |
| PyVista-4329 | 16,440,869 |
| PyVista-4853 | 17,017,028 |

The other sixteen unchanged records fit. Actual model edits may change request
size; therefore the bounded retention helper checks every complete dispatch.
Do not raise the event bound, omit the request, discard a task or dispatch an
unretained request.

The original waiting postprocessor is first stopped through an exact pidfd.
The protected journal proves its only event is its initial plan, zero grading
phases have started, the grading run has no events, and the model cohort is
still active. Only that waiting process is then terminated. The model process
and all completed attempts remain untouched. The pause and reason are retained
as `external.v3_pregrading_transport_pause` in the original postprocessing run.

## Permitted change

- At or below the existing event bound, retain the original dispatch unchanged.
- Above it, retain the complete canonical dispatch in ordered 3,000,000-byte
  chunks through the existing authenticated evidence service. Each chunk binds
  its offset, total byte count and full-dispatch SHA-256. A small dispatch index
  references the exact receipts and states that the full request is retained.
- Keep the full-dispatch bound at 64 MB, consistent with the existing bounded
  operator transport. Oversized input fails closed, not by truncation.
- Preserve the actual subprocess request byte content, image, private grading
  program, source policy, command, candidate bytes, test selection, timeout and
  grading concurrency. This changes evidence framing only.

Resume is explicit and one-time. Its guard requires exactly the original plan
and the zero-phase pause, plus an empty private-grading run. It verifies that
the report/recovery modules are identical and that removing the new retention
helper leaves the original grading source with exactly one dispatch-retention
call changed. Any changed execution command, timeout, module set or previously
started phase blocks the amendment. The full amended implementation is retained
as `external.v3_postprocessing_pregrading_amended` before it waits for all 76
model attempts. The original plan is not overwritten.

Seventeen focused grading/finish/report/archive/transfer fixtures pass. They
include recovery of an over-16-MB dispatch byte for byte, per-event bounds,
unchanged small records, and rejection of a timeout or report-module change.
The actual journal confirms the amended waiter is live with zero phases begun.
This is not a private grade or a performance result. T062/T086 remain open.

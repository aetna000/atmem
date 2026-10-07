# Dolphin 5% removal-control diagnostic — 2026-10-08

This is a no-model, evaluator-side safety diagnostic on the frozen 30-task
development profile. It is not a DolphinBench accuracy score.

| Outcome | Cases |
|---|---:|
| Named pre-action missing-requirement block | 19 |
| Gate remained open after removal | 6 |
| Non-atomic removal target | 5 |
| Timeout, parse or provider failure | 0 |

Every credited block used a product-created obligation ID and description.
Evaluator-only expected evidence was used after the run to verify that the
description matched the removed fact; generic slot overlap no longer receives
credit. Every credited receipt recorded `model_invoked=false` and zero tool
calls.

The six open cases were `alex:074`, `alex:082`, `morgan:097`, `morgan:103`,
`morgan:138`, and `riley:119`. The five non-atomic cases were `alex:136`,
`morgan:045`, `morgan:071`, `morgan:082`, and `riley:044`. No failed case was
removed from the denominator. The external machine-readable receipt is under
`/private/tmp/atmem-dolphin-removal-named-obligation-diagnostic` for this local
run and must be archived to the benchmark evidence volume before qualification.

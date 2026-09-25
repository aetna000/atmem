# Fresh public retail pilot — registration before dispatch

Scope: exposed public task0, four configurations, one fresh no-fault conversation
per configuration, seed20260925. This is an engineering pilot, not a held-out
performance estimate. Recorded-response and installed crash gates precede it.
No selection of favorable outcomes, automatic reruns, product changes between
arms, or completion-rate claim from four observations.

Use the same qualified graph, pinned native agent/user prompts and tools, and
stock synchronous SQLite checkpoints. For this no-fault pilot the graph and
single-attempt logged provider transport run in the supervisor process; native
retail effects remain in the separate surviving tool process. No model broker,
response cache, checkpoint repair or recovery algorithm is introduced here.
The later paid process-fault phase requires a separately reviewed broker with
orphaned-response accounting; it is not silently covered by this registration.

Model: gpt-4.1-2025-04-14, temperature0, provider retries0, output2048, seedpinned,
streamfalse. Same settings for native NL grading. Step58/error5/totalmodelcalls60
per arm including grading; transport socket/idle timeout90s, trial deadline600s
checked before each model request. An in-flight request may finish after that
deadline; a trickling response is not bounded by a hard90s wall-clock promise.
Grading has a separate600s allowance and cannot erase a completed trajectory;
grading failure leaves its score missing. Calls remain under the same60-call cap.
One transport per arm serves its agent, simulator and grader. This is60calls per
arm, not60across four arms. The sharedUSD20ledger is the global spending bound.
All roles/arms use the existing cumulativeUSD20 ledger. ReserveUSD2.20 before
every dispatch, settle measured usage, retain full reserve on unknown cost.
Never reinitialize, refund, edit or replace priorUSD0.057324 spending records.
Record agent/simulator/grader separately; grading is not agent recovery cost.

Freeze hashes of public task, schemas, policy, prompts, code, package versions
and installed distribution RECORD files before the first call. Record all four
planned dispositions before execution. Arm metadata is accounting-only and must
not reach provider request bodies. Credential is read explicitly from authorized
env file without shell sourcing and never included in manifests or child config.
Public original requests/responses and exact native trajectories are retained.

All HTTP429/5xx/timeouts, accounting ambiguity, missing usage, model/tier drift,
and product/transport errors are reported as their original failure disposition.
No automatic reruns; uncertain spend halts further paid work. Remaining planned
arms are labelled not-run after a safety/budget stop. Normal conversation stopping
is not business success. Native DB and NL criteria are graded independently from
the original dataset; failure or missing grading is not imputed as a score.
Temperature0 does not imply determinism: differences are descriptive only.

Preflight requires room for four conservative single-call reservations (USD8.80).
This is not a guarantee of four completed conversations: reserving60 full-context
calls upfront per arm would exceed the authorizedUSD20. Actual call-by-call
reservations remain the hard cap; an incomplete schedule cannot support a
balanced comparison. Fixed arm order is registered and reported, not randomized.
Installed files must match every hashed RECORD entry and cannot be editable;
verify the same product/runtime files and benchmark source again after execution.
Diagnostic stack frame names/line numbers are retained without exception text or
locals, which can expose credential-bearing transport data.

AtFlows receives only its shipped observers' actual events. Experiment accounting
does not fill missing AtFlows charges or create product model instrumentation.
Report unknown prices and the instrumented tool boundary explicitly. No private
Home data, live customer actions, release, deployment or production gain claim.

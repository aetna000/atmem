# Spec053 evidence

Status: implementation verified before inference; no live comparison result yet.

The prior Spec052 study compared injected notes, not original versus updated AtMem.
It remains a failed intervention: revised5/20 versus no-memory7/20. Owner-authorized
trace inspection found original training accuracy1/10; note construction had no
correctness feedback. For strict final discordances, no-memory won3 and revision
won1; the revision's sole win was scalar formatting of an otherwise matching value.
One revision loss applied category restrictions absent from the requested task;
another used a store-name field for brand instead of inspecting brand attributes.
These observations support possible unverified-pattern contamination, not a causal
explanation for every failure. The held-out results must not be tuned away.

Actual installed worker checks: original2.3.14 from PyPI and candidate2.3.15b2 from
the retained wheel each initialized SQLCipher-encrypted memory, imported an observed
source, froze Context Engine V3 and returned the source through prepare_context_v3.
Both selected one source and reported sufficient; this is wiring only, not efficacy.
The core memory.py bytes were identical across those versions, underscoring that
the candidate changes the experimental instruction/derived-memory layer, not core
retrieval. The isolated original installation's pip check passed.

Before inference:21 targeted tests passed (4 new comparison-boundary tests plus17
existing adaptation tests). New tests exercised real encrypted durable failed-call
reservations, ciphertext canaries, pre-call deadline refusal, installed version/
checkout isolation and credential filtering, and absence of hidden targets/memory
in stateless model input. No test asserts an agent learned.

All cases106–120 are previously unused post-drift questions in one shared database.
The live run has a fixed all-zero first-three feasibility stop, no policy revision,
no repeat and no production or native-host claim. The third arm deliberately forces
the old rejected experimental candidate for comparison; no activation is authorized.

The first preflight stopped before any paid call because the supplied gold SQL for
case109 exceeded the 10-second reference-verifier limit. An independent 60-second
bounded read-only execution returned the published answer1145 in20.94seconds.
There was no dataset answer mismatch. All15 oracle values agree with the labels.
The verifier-only ceiling is now60seconds, frozen before inference; agent query
limits remain3seconds for every arm. No scoring rule or model result was changed.

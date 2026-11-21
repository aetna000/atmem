# Measured memory adaptation — experimental beta

AtMem 2.3.15 includes an explicitly invoked study runner and an owner-only SDK for
measuring a change to memory use. It records actual task outcomes against an
application-owned objective grader. It does not train model weights, automatically
improve a running agent, issue production qualification or activate instructions.
Existing memory, feedback, capture and host defaults retain their existing behavior.

## Install and inspect without spending

Use Python 3.10–3.13 in a separate environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install 'atmem[code]==2.3.15'
python -m pip check
atmem-memory-study --help
```

`--help`, `report` and `inspect` never call a model. See the model-free
[contract example](../examples/memory_adaptation_contract.py) in the release source.
Its fixtures exercise the actual encrypted store but cannot establish learning.

## What the runner compares

Every task starts with a fresh model context, fixed model/settings and the same
read-only SQLite tools and 15-query limit. Four final conditions are reported:

- No memory: no prior task information.
- Bounded transcript: equally sampled original training observations.
- Generic notes: one compact summary under fixed generic instructions.
- Revised notes: one training-derived revision of LOAD/OFFLOAD instructions and
  a summary from the exact same observed training evidence.

The intervention changes instructions and derived notes together. It does not
isolate writing from retrieval. These are fixed-agent native-style controls, not
measurements of native Codex/Claude/OpenClaw runtimes or AtMem's normal recall API.
The strongest simple baseline matters; outperforming only no-memory is insufficient.
In particular, generic notes are **not original AtMem**. The Spec052 pilot did not
measure an AtMem package against an older AtMem package. A separate Spec053
comparison exercises installed 2.3.14 and the candidate's actual encrypted
Context Engine V3 path, alongside no memory; its results must be reported separately.

That small matched SDK check used six independently authored public database tasks:
no memory: 6/6; installed AtMem 2.3.14: 6/6; candidate 2.3.15b2 with the frozen
experimental policy: 6/6. All 18 trials completed. The pilot made 17 model calls
versus 18 for original and 20 without memory, but both memory conditions used more tokens and API spend than
the stateless control. This establishes no accuracy gain or learning: all conditions
hit the six-task ceiling in one database lineage. It is not a native-host benchmark.
Earlier follow-up scores were invalidated as product comparisons after task-framing
and historical-question displacement defects were found in the research adapter;
their raw results and costs remain in Spec 053. Consumed questions were not rescored.

The three-arm comparison is a source-only research harness, separate from the
installed `atmem-memory-study` command. It requires isolated installed original and
candidate environments, pinned public databases, the owner's encrypted historical
study Home, and a sealed independently authored cohort; no dataset/target bundle is
distributed. Exact settings, source and cohort hashes, per-trial results, corrections
and limits are retained under `specs/053-matched-atmem-comparison`. It cannot activate
a policy or certify production qualification.

The study freezes corpus hashes, all case memberships, grader/implementation
identities, runtime settings and ceilings before inference. Train IDs1–10 generate
observations; validation IDs11–15 select between generic and one revision, requiring
higher objective reward with no accuracy regression. A tie retains generic. Both
policies and training-only memory snapshots are then frozen. Final IDs16–30 and
drift IDs101–105 cannot update notes, policies or selection. The revision is reported
even when rejected. No final-set-driven retries, tuning or replacement questions.

The benchmark's gold answers/SQL remain outside model inputs and memory writers.
A strict scalar grader uses actual outputs and independently verified gold SQL,
preserves differences from upstream's first-number parser, and assigns failed tasks
zero reward. Reward for a correct answer is `1 - exploratory_queries/15`.
Model labels, lesson exposure and retrieved passages are not success evidence.

## Prepare the public benchmark on a separate data volume

The adapted CL-Bench pilot needs about 830 MB for its two immutable SQLite files.
Do not download them into a normal AtMem Home. Choose your own external directory:

```sh
mkdir -p /path/to/external/clbench-db
cd /path/to/external/clbench-db
curl --fail --location --output products.db https://huggingface.co/datasets/continual-learning-bench/database-exploration/resolve/a0cc57eeb9a54f01c0490a1b46cb705b4e05aa19/products.db
curl --fail --location --output products_drifted.db https://huggingface.co/datasets/continual-learning-bench/database-exploration/resolve/a0cc57eeb9a54f01c0490a1b46cb705b4e05aa19/products_drifted.db
curl --fail --location --output questions.json https://raw.githubusercontent.com/pgasawa/continual-learning-bench/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/data/database_exploration/questions.json
curl --fail --location --output questions_post_drift.json https://raw.githubusercontent.com/pgasawa/continual-learning-bench/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26/data/database_exploration/questions_post_drift.json
```

The runner verifies every SHA256 and independently checks gold SQL before
inference. Code is Apache-2.0; the HF snapshot lacks an explicit dataset license
card and derives from Amazon Reviews 2023. Do not redistribute these downloaded
artifacts or treat this pilot as licensed production qualification. No model-weight
training is implemented. See [research/provenance](../specs/052-measured-memory-adaptation/research.md).

## Explicit paid execution

Set `OPENROUTER_API_KEY` in the process environment, or supply a private env file
with that variable (also accepts `OPEN_ROUTER`). Never paste credentials into the
manifest or commit them. The runner reads only the selected provider credential;
it does not source or execute the env file.

```sh
atmem-memory-study run \
  --data /path/to/external/clbench-db \
  --home /path/to/external/fresh-study-home \
  --allow-paid-public-benchmark
```

This authorizes public benchmark question/schema/query-result excerpts to leave
for the pinned OpenRouter/OpenAI `openai/gpt-6-luna` route. It is not permission to
send private customer data. Endpoint availability can change; no silent model or
provider fallback occurs. Instructions/settings cannot be changed within a study.

Hard ceilings: 800 calls, 2 million tokens, USD 3, 90 minutes and 32MiB conservative
serialized evidence reservations. Unknown calls retain their worst-case token/cost
charge. The evidence ceiling excludes encrypted container/history/filesystem
overhead, which is measured separately. HTTP timeouts use remaining time; late
responses cannot earn an accepted grade. No automatic paid retry or resume.

A model's malformed answer/action or truncated response is an observed failure.
Provider uncertainty, corrupt/locked storage or budget exhaustion stops the study
with an incomplete summary. Keep the failed study; do not rerun final cases until
a positive result appears. There is no bulk campaign or broad search loop.

## Retention, inspection and cleanup

A fresh dedicated experiment Home is mandatory; no regular Home, existing memory,
accounts or running agent is modified. Exact requests/responses, tool calls/results,
notes and grades use AtMem's encrypted scoped feedback ledger. This opts that fresh
vault into the existing feedback format 4. Readers without feedback-format 4 support must refuse it;
there is no in-place downgrade or new canonical-memory schema migration.

The dedicated `.study-access.json` contains the study credential with owner-only
file permissions. Keep the Home, identity/key directories and credential together
and private. Anyone with all keys and credentials can inspect it. Local credential
storage is not a remote multi-user authentication service.

```sh
atmem-memory-study report --home /path/to/external/fresh-study-home
atmem-memory-study inspect --home /path/to/external/fresh-study-home
```

`report` prints content-free metrics. `inspect` explicitly prints the authorized
full trial/model evidence and may include public dataset content; protect any
redirected output. Inspection creates an audit entry. Incomplete studies expose
phase, attempts and conservative resource charges. With no original agent logs,
the encrypted Home and keys still retain captured exact exchanges.

Keep the content-free preregistration/summary and evidence needed for review. When
finished, remove only the dedicated study Home, downloaded database files and
isolated environment you created. No service/container is launched by this runner.
Deleting that Home is not a claim to erase provider-retained copies.

## Trusted SDK boundary and limitations

`atmem.feedback.adaptation.AdaptationService` attaches to `FeedbackService`.
Only an owner-authorized fixed `FeedbackScope` can preregister, execute, inspect
or close a study. Applications register verifier code and pin its implementation;
agent input never supplies verifier results or activation authority. The SDK pins
and audits callbacks; it cannot prove arbitrary application callbacks are honest.
Models propose bounded text only. There is no MCP exposure of study administration.

The study can demonstrate a bounded observed difference or a failed intervention.
One database lineage, 20 final questions and one seed cannot establish reliable
general continual learning, superiority to Meta, production latency or broad
negative-transfer safety. Drift is a stratum, not an independent corpus. Statistical
uncertainty remains inconclusive. Meta's optimized harness and weight-distillation
scores use different conditions; its public project provides no implementation here
for a matched reproduction. Existing production feedback qualification stays
inconclusive regardless of this study's score.

## Recorded pilot outcome

The first source pilot rejected the revision. Final strict scores were7/20 without
memory,5/20 with transcript,6/20 with generic notes and5/20 with revised notes.
Both validation policies scored0/5, so generic was retained by the tie rule.
The already-recorded upstream parser scores were9/20,7/20,7/20 and6/20, respectively.
No scorer was changed after seeing final answers. The study costUSD0.07761425 for
497 calls across all phases; separate setup/protocol costs are documented in the
[complete evidence](../specs/052-measured-memory-adaptation/implementation-evidence.md).
This is a negative experimental result. It does not demonstrate reliable improvement.
Reference live validation is macOS/Python 3.12; other hosts and storage ACLs are
not newly qualified by this pilot. Downloaded DBs stay outside the encrypted Home;
the Home retains captured exchanges rather than an entire replayable DB snapshot.

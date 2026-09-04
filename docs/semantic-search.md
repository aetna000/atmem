# Semantic search

AtMem keeps canonical memory in SQLite and semantic vectors in a disposable
sidecar. A base installation automatically provides deterministic local
hashing, so canonical memory and lexical/hybrid recall remain useful without a
model runtime, network connection, or hosted provider. Semantic vectors never
authorize, admit, promote, or change a memory.

## Guided local setup

Install the optional runtime, then run the guided command:

```bash
python -m pip install "atmem[semantic]"
atmem semantic setup memories.db --subject user-1
```

AtMem detects memory, architecture, and any observed accelerator, shows
compatible checked-in catalog choices with approximate download sizes and
resource caveats, and allows a manual `--provider` and `--model` selection. The
catalog covers both the `ollama` runtime — which needs a running service but no
Python model runtime — and `sentence-transformers`.

Accelerator detection uses only platform and `PATH` evidence, so it reports
`metal`, `cuda`, `rocm`, or `none` without importing an optional runtime. On a
platform where physical memory cannot be measured, memory is reported as
unknown rather than zero and every recommendation is marked
`memory_unverified` — an unmeasurable machine gets a caveated list instead of
an empty one that would read as "no model fits this hardware".

AtMem will not let `sentence-transformers` download a selected model unless the
operator confirms interactively or supplies `--allow-download`. Requests to an
Ollama endpoint or a remote OpenAI-compatible endpoint require the separate
`--allow-egress` confirmation. Approval is recorded by provider, model, and a
secret-free configuration digest; API-key values are never recorded.

Setup reports the operator decisions it actually consumed in `decisions`, with
`decision_count` derived from that list rather than declared as a constant.

For automation, make every decision explicit:

```bash
atmem semantic setup memories.db --subject user-1 \
  --provider sentence-transformers \
  --model BAAI/bge-small-en-v1.5 \
  --allow-download --json
```

Setup builds a staged epoch, verifies its manifest and canonical coverage, and
runs a paraphrase smoke test. A manual representative paraphrase can be supplied
with `--smoke-query`. Refusing a download or egress leaves deterministic hashing
available and reports `cancelled`; it does not silently install or contact
anything.

## Health and recovery

The CLI and dashboard use the same health contract:

```bash
atmem semantic status memories.db --subject user-1
atmem semantic status memories.db --subject user-1 --json
atmem semantic verify memories.db --subject user-1
atmem semantic rebuild memories.db --subject user-1
```

Health is one of:

- `healthy`: model identity, dimensions, source digest, and coverage verify.
- `weak`: the safe deterministic hashing fallback is active.
- `missing`: no active epoch exists.
- `legacy`: the active epoch lacks enough identity or manifest evidence.
- `stale`: canonical content, lifecycle, generation, coverage, or the household
  policy the vectors were derived under changed.
- `incompatible`: model identity or dimensions do not match.
- `rebuilding`: an inactive checkpointed epoch is incomplete or resuming.

Each epoch records a digest of the household policy identity it was built
under. Only non-secret identifiers — encryption state, backend, and key id —
are hashed; key material never reaches the digest, the epoch, or any health
report. When the current policy no longer matches, health reports `stale` with
reason `policy_changed` and the derived vectors are marked for rebuild. Epochs
created before the digest existed record nothing and are left alone rather than
being reported as aged.

The dashboard’s Index health card shows the same provider, model, dimensions,
epoch, source digest, record count, reasons, and state-valid next actions.
Unsafe or incomplete epochs are never used as authority.

Rebuilds write batches into an inactive epoch and checkpoint each committed
batch. Retrying with the same model identity and unchanged canonical generation
resumes without embedding completed records again. Before activation, AtMem
locks canonical writes, rechecks generation, deletion, scope, content digests,
dimensions, and complete coverage, then switches the active epoch atomically.
An interruption, provider timeout, dimension change, or disk error leaves the
previous valid epoch active. If canonical memory changed, rerun `semantic
rebuild`; the stale partial epoch is retired when its replacement starts.

## Safe fallback and limitations

- `atmem search --mode semantic|hybrid` verifies the selected epoch before
  nomination and reloads every result from canonical memory.
- Deletion purges registered vector sidecars; policy or lifecycle drift makes
  health stale until repaired.
- Missing, stale, legacy, incompatible, or partial epochs are withheld. Use
  lexical search, or rebuild. Hashing remains local and deterministic but does
  not provide model-quality paraphrase understanding.
- Model availability, download time, tokenizer behavior, numerical output, and
  retrieval quality are third-party/runtime concerns. Approximate catalog sizes
  are planning guidance, not download guarantees.
- An empty authority store cannot build or smoke-test an epoch. Add an eligible
  canonical memory first.
- Semantic similarity is a nomination signal, not proof that a memory is true
  or relevant. Scope, lifecycle, exclusion, sensitivity, generation, and budget
  policy are still enforced before context construction.

The legacy `atmem index build|status|verify` commands remain available for
compatibility. New operator workflows should prefer `atmem semantic` because it
adds health vocabulary, consent, resumable rebuilding, and human guidance.

## Controlled usability protocol

Use a clean supported Python environment and a fake or pre-provisioned local
embedding provider so download duration is excluded:

1. Give the participant only `atmem semantic --help` and a database containing
   one eligible memory.
2. Ask them to choose a local recommendation, approve any required download,
   and complete setup.
3. Ask them to identify the active provider/model, epoch, record coverage, and
   source digest using either CLI or dashboard.
4. Ask them to run a representative paraphrase and verify the expected record.
5. Interrupt one rebuild, then ask them to diagnose and resume it.
6. Record elapsed time excluding downloads, decision count, smoke-test result,
   and whether undocumented assistance was required.

The release target is at least 90% completion within ten minutes, no more than
six user decisions, a passing paraphrase, and no undocumented assistance. The
automated fixture covers the same setup/build/health/smoke path and asserts the
reported decision count remains bounded.

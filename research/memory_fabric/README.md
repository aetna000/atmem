# Governed memory scheduling research

Status: **P0b exploratory local baseline**. A real local load runner exists, but
no production scheduler, authority state-machine proof or established overall
scheduling win exists in this folder.
See [Spec 033](../../specs/033-memory-fabric/spec.md) and its task list.

Latest: [Homa review and controlled results](../../specs/033-memory-fabric/homa-review.md).
The first dispatcher and its small pilots below are historical. The common
dispatcher comparison uses `homa_experiment.py`, with service-time debt in
`scheduling.py`. Seventy frozen trials did not establish a candidate meeting
short-latency and bulk-protection gates. The review documents local timing noise
and a shared-FTS-corpus effect invalidating static read oracles in write-heavy
trials. No research policy is recommended as a production speedup.

```bash
.venv/bin/python -m pytest -q tests/test_memory_fabric_protocol.py \
  tests/test_memory_fabric_local_baseline.py tests/test_memory_fabric_scheduling.py
.venv/bin/python -m research.memory_fabric.analyze_fairness \
  research/memory_fabric/results/homa-fairness-v2
.venv/bin/python -m research.memory_fabric.simulation
```

For a new independent suite, `run_fairness_suite freeze --root <new-directory>`
calibrates and freezes policy/workload/source settings, and `run --root` executes
them. Use the module prefix `python -m research.memory_fabric.run_fairness_suite`.
Existing frozen v2 results and source snapshots remain immutable evidence;
modifying parameters to fit those outcomes is not a held-out test.

Run from the repository root:

```bash
python -m pytest -q tests/test_memory_fabric_protocol.py
.venv/bin/python -m pytest -q tests/test_memory_fabric_local_baseline.py
.venv/bin/python -m research.memory_fabric.local_baseline \
  --distribution poisson --rate 80 --workers 1 --seed 17 \
  --output research/memory_fabric/results/example.json
# Research-only write-isolation controls (not production fixes):
.venv/bin/python -m research.memory_fabric.local_baseline \
  --distribution poisson --rate 80 --workers 2 --seed 17 \
  --serialize-writes --output research/memory_fabric/results/serialized.json
.venv/bin/python -m research.memory_fabric.local_baseline \
  --distribution poisson --rate 80 --workers 2 --seed 17 \
  --isolate-write-lane --output research/memory_fabric/results/isolated.json
# Direct local FIFO versus deadline/estimated-size dispatch at one worker:
.venv/bin/python -m research.memory_fabric.local_baseline \
  --distribution poisson --rate 80 --workers 1 --seed 37 --policy fifo \
  --output research/memory_fabric/results/fifo-example.json
.venv/bin/python -m research.memory_fabric.local_baseline \
  --distribution poisson --rate 80 --workers 1 --seed 37 \
  --policy fabric-deadline-size \
  --output research/memory_fabric/results/fabric-example.json
```

`protocol.py` provides seeded open-loop arrival offsets and a strict report
builder for supplied synthetic observations. It does not dispatch requests,
access AtMem, read environment/user homes, write files, or call models. It is
outside the installed `atmem*` package. Provenance is caller supplied and may
explicitly be unknown. There is no runtime activation switch because there is no
runtime integration.

Completed work is distinct from authorized, evidence-complete, output-verified,
on-time work. Unknown verification makes the corresponding goodput unavailable;
known successes remain a labeled lower bound. Per-lane results preserve that
distinction. Reports always label themselves synthetic and not valid comparative
performance evidence. Failed/expired/censored work stays in the denominator.

P0a accepts one authoritative terminal observation per request; raw transition
histories and event reduction belong to P1, not an arbitrary payload field here.
`service_until_terminal` measures logical termination, not necessarily the end
of physical resource consumption after cancellation. Physical worker lifetimes
will be measured separately in the real runner and lifecycle model.

The P0b runner uses a disposable synthetic AtMem home; no existing OpenClaw
session or user memory is read or changed. It executes real memory recall/writes
and encrypted evidence capture, including byte-exact recovery of generated image,
audio and (where ffmpeg is available) video fixtures. It measures open-loop
FIFO admission, queue wait and composed completion, not OpenClaw hook delivery.
Its full-memory open/close cost is included per operation, even for artifact
operations; this and vector sync must be isolated before attributing a stage.
Failures and refusals remain in the offered denominator. The protected evidence
record is counted only for completed operations; worker failures are in the raw
report, not silently treated as completed evidence. P0b has no release-time
authorization proof, so verified useful goodput is unknown, not 100%.

Raw pilot reports are in `results/`; see `specs/033-memory-fabric/research.md`
for the measured findings and limitations. Write isolation removes observed
concurrent vector-sync errors but worsens queueing/refusal in this pilot;
neither policy is a production fix or a demonstrated improvement. The
fixed-arrival pilot predates
source-digest reporting and is exploratory only. The Poisson reports include
runner/protocol source digests; the later seed-29 pair includes exception text
for synthetic-only failure diagnostics.

Next: investigate storage concurrency, add cold/warm and end-to-end hook
profiles, then correctness model and controlled scheduling experiments. Final
runs require hardware/runtime
identity, frozen workload and tuning manifests, generator-lag validity gates,
independent repeats and confidence intervals. None are implied by passing these
pilot tests. No paper speedup should be inferred from these numbers.

The one-worker `fabric-deadline-size` policy is an exploratory **dispatcher**
over unchanged AtMem, not a deployed Memory Fabric data layer. In five paired
local trials it improved interactive-recall p95 but worsened bulk and overall
p95; see `research.md`. It has no integrated release-time authorization or
OpenClaw delivery proof. The first paired files named `paired-80rps-*` used an
incorrect interactive/bulk label for writes and are excluded; use only the
`paired-lanefix-*` reports for this direct comparison.

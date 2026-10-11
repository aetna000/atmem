# Compute Qualification Protocol

No command in this protocol contains a password or token. Remote authentication
must use an interactive prompt or approved secret store. SSH must use a known-
hosts entry verified out of band and strict host-key checking; first-use blind
acceptance is prohibited.

## Common smoke workload

Use the same pinned code, base-model/data subset, seed, objective, batch policy
and checkpoint interval on each candidate. Exercise load, forward/backward,
checkpoint, process restart/resume, calibration and Safetensors reload. Record OS,
CPU/GPU/MPS identity, driver/runtime, Python/dependencies, elapsed/throughput,
peak and available memory, free/projected storage, artifact digests and errors.

A local candidate is viable only when:

- there is no unsupported operation, OOM or nonfinite value;
- measured peak leaves at least 20% device-memory headroom;
- free artifact storage is at least three times projected peak run storage;
- a new process resumes a checkpoint and reproduces the next step;
- both objective controls are projected to complete within 48 elapsed hours.

If both qualify, choose the lower reliable projected elapsed time. Run and record
both candidates even if the first qualifies.

The frozen workload is `training/smoke-workload.json`; its executable is
`research.laya_formation.training.smoke`. Run it from the repository root in an
isolated environment containing the source-locked Laya 0.4.2 dependencies:

```console
python -m research.laya_formation.training.smoke \
  --root /Volumes/MEM/AtMem-Laya-Formation \
  --output /Volumes/MEM/AtMem-Laya-Formation/training/smoke-mac \
  --device auto
```

The Windows invocation uses the same workload and an explicit Windows artifact
root. Exit status `0` means viable; exit status `2` means the workload completed
but one or more frozen viability gates failed. Other nonzero statuses are
execution failures. The JSON receipt, not the process exit status alone, is the
retained evidence.

## Windows SSH candidate

Verify the host key separately, then require `StrictHostKeyChecking=yes` and a
specific known-hosts file. Do not use password command-line helpers, URLs,
environment exports, shell history or logs. Prefer CUDA when the smoke verifies
it; otherwise record the CPU result. Copy only public/synthetic inputs and verify
all returned files by digest.

## Mac candidate

Try MPS, then CPU when MPS is unsupported. Heavy data and checkpoints belong at
`/Volumes/MEM/AtMem-Laya-Formation/`. If that mounted path is unavailable, the
full run is infeasible; do not silently place heavy artifacts in the repository
or home directory.

## Conditional Vast.ai candidate

Vast is forbidden until both local receipts are `infeasible`. Query live offers
at selection time. Require CUDA, at least 16 GiB VRAM, sufficient disk/network
and a provider reliability of at least `0.99`, frozen before the first live
selection query. Exclude offers reported as VM-deverified even when the parent
machine is verified. Rank the remaining offers by:

`expected_total = compute + continuous_storage + transfer + expected_retry_cost`

The hard ceiling is USD 20 with no automatic top-up. Spending requires explicit
owner approval. Interruptible capacity additionally requires a proven resume
test and checksum-verified checkpoint synchronization to owner-controlled
storage. Only public/synthetic data may leave local systems. After training,
recover and verify every retained artifact, record final cost, then destroy the
instance and verify it no longer appears active.

## Receipt states

Each candidate emits `not_run`, `viable`, `infeasible` or `failed` plus reason
codes and evidence digests. Vast eligibility requires Windows and Mac to be
`infeasible` or `failed` on the representative smoke; mere preference or a lower
hourly price is insufficient.

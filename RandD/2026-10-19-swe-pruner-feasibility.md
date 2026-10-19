# SWE-Pruner: local execution qualification, not a coding score

Status: **local backend qualification blocked; no end-to-end SWE-Pruner coding
result and no solver-token saving measured**. The three-arm Click comparison
is complete and reported separately in `2026-10-19-curation-threeway-results.md`.

## Exact experiment

Windows WSL, Quadro P2000 with 4,096 MiB reported by nvidia-smi. A separate
`/home/user/atmem-swe-pruner-20261019/venv` contains swe-pruner 0.1.1,
torch 2.8.0+cpu and transformers 4.57.1. No AtMem installation, owner Python
environment, model weights or production defaults were changed. No paid GPU
was rented and no data/model training took place.

The actual upstream model was downloaded from
[ayanami-kitasan/code-pruner](https://huggingface.co/ayanami-kitasan/code-pruner),
revision `863cee3198c715c9df1faa422a3490e0832bb734`; its card declares MIT.
Backbone configuration only: Qwen/Qwen3-Reranker-0.6B revision
`e61197ed45024b0ed8a2d74b80b4d909f1255473`. No separate backbone weights were
needed. The locally loaded model used float32 and SDPA CPU attention.
This is a fallback backend, not the upstream paper's GPU configuration.

The [upstream inference guide](https://github.com/Ayanami1314/swe-pruner/blob/public/swe-pruner/README.md)
specifies FlashAttention-2. Its documented CUDA backend supports Ampere, Ada
and Hopper, not this machine's older GPU architecture.
[FlashAttention support](https://github.com/Dao-AILab/flash-attention#nvidia-cuda-support).

## Results and stopping decision

1. The public `prune(PruneRequest(...))` wrapper padded a five-line diagnostic
   to 8,192 positions. Model loading took 1.315 seconds, but inference still had
   not returned 338.55 seconds after the loaded-model log. Stopped that exact
   owned model process and retained its log and stop receipt. This is a lower
   bound on this attempt's inference latency, not a completed timing average.
2. Tested a benchmark-only adaptation removing **only masked right padding**.
   No actual code/query tokens were removed, and weights, threshold and
   selection logic were unchanged. Compared against a 256-position reference
   on the same small diagnostic before allowing real Click source cases.
3. Reference: 10.149 seconds; trimmed: 4.598 seconds. Document score unchanged;
   maximum token-score change **0.00403249**, exceeding the predeclared 0.0001
   numerical-equivalence gate. Zero token threshold flips on this particular
   diagnostic does not establish equivalent decisions on other inputs.
4. Therefore rejected the adaptation. The two staged real historical Click
   source cases were **not executed**, and no coding agent was dispatched
   using this failed backend. Did not relax the gate to report a success.

The diagnosis is local execution feasibility, not proof that SWE-Pruner's
learned approach fails or that AtMem matches it. A supported GPU backend is
the next reference route; alternatively a portable implementation must first
pass its declared numerical/selection validation on a broader qualification
corpus. Do not add this backend to normal AtMem installs or infer that CPU
padding-trim latency is an end-to-end coding speedup.

Machine-readable evidence: `2026-10-19-swe-pruner-feasibility.json`.

Follow-up: the unmodified supported GPU route qualified on October 20. See
`2026-10-20-swe-pruner-results.md` for actual latency, both coding experiments,
negative end-to-end token-savings result, and completed rental teardown. The
CPU failure above is retained, not replaced or counted as a coding result.
Full logs, probe sources and staged public-source inputs are retained at
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swe-pruner-feasibility-20261019/`.

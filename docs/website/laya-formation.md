# Optional Laya formation

> **Not yet available for recommended use:** the earlier synthetic-trained
> checkpoint is superseded. The 2.3.9b1 Laya profile remains blocked until the
> authentic-conversation dataset and replacement model pass independent
> labeling, training and compatibility gates. Do not activate the old artifact.

AtMem 2.3.9b1 can use a pinned local Laya System One model to propose five
finite memory decisions: operation, memory class, evidence support, authorized
target and retrieval usefulness. The model never writes memory directly. AtMem
still checks source evidence, scope, policy, current generation and canonical
post-state before disposition.

The base installation remains deterministic and downloads no model. To opt in:

```bash
python -m pip install --upgrade --pre "atmem[laya-formation]==2.3.9b1"
atmem formation preview --download
atmem formation setup
# Or noninteractively:
atmem formation setup --profile laya --download --device auto --yes
atmem formation doctor
atmem formation activate --yes
atmem formation status
```

On Intel macOS, use Python 3.10-3.12 and install the x86_64-compatible
numerical stack before the optional AtMem extra:

```bash
python -m pip install --upgrade \
  "numpy==1.26.4" "scipy==1.13.1" "scikit-learn==1.5.2"
python -m pip install --upgrade --pre "atmem[laya-formation]==2.3.9b1"
```

This path pins PyTorch 2.2.2 and Transformers 4.57.6 through AtMem's platform
markers. It is tested with a real 384-dimensional multilingual embedding.

Preview is read-only. Setup downloads and verifies the exact public artifact but
leaves it inactive. Activation is a separate confirmed action. Roll back with:

```bash
atmem formation rollback --yes
```

Guided setup offers deterministic rules, local Laya, or local Laya with bounded
AtBot escalation. An automation can select the same choices with
`--profile deterministic`, `--profile laya`, or `--profile laya-escalation`.
After activation, ordinary CLI/API/MCP episode formation and Context Engine
formation run the five pinned finite questions against only captured source
ranges and active in-scope candidates. Ordinary formation retains the choices
as bounded proposals alongside the existing authoritative admission result.
Context Engine formation additionally validates the complete decision set and
may commit only a source-grounded view disposition. Both paths write decision
receipts to the append-only audit chain. Update/supersede proposals without one
concrete independently resolved target remain review cases. Exact source and
raw-state coverage are retained even when semantic admission is rejected. An
incomplete, abstained, inconsistent or unsupported model decision is
fail-closed: Context Engine keeps only the raw-state view pending review. A
runtime failure still takes the documented deterministic fallback.

The optional model is about 800 MB and adds Laya/PyTorch dependencies. Real CPU
and accelerator inference was verified on Apple-silicon macOS, Windows CUDA and
Linux CUDA, with CPU paths on all three. The normal Python wheel was tested on
Python 3.10–3.13. Intel macOS multilingual embedding execution was tested;
full Laya inference remains a release gate and is not yet claimed there.

On the frozen synthetic benchmark, the model improved exact state and strict
store-to-retrieve success over deterministic AtMem, but tied its lexical
retrieval MRR. It took about 272 ms per formation choice on the tested
Apple-silicon CPU versus about 2.3 ms for rules. Jev and Qwen comparisons are
inconclusive, and no production superiority claim is supported. Read the
[release evidence and exact limits](../releases/v2.3.9b1.md).

The later 100-observation OpenClaw operational replay did **not** confirm that
the current model is ready as a recommended default. It produced 94 review
outcomes, withheld all 25 intended stores under fail-closed policy, and added
about 1.49 seconds per episode on MPS. Deterministic formation therefore remains
the default while the model is recalibrated and re-evaluated. This replay is a
maintainer-run synthetic policy challenge, not an independent benchmark.

`atmem formation doctor` checks the exact optional runtime bounds before
activation. If an existing environment contains stale PyTorch or an unsupported
Transformers major version, use the repair command it reports rather than
activating the profile.

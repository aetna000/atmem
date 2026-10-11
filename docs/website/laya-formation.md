# Optional Laya formation

AtMem 2.3.9b1 can use a pinned local Laya System One model to propose five
finite memory decisions: operation, memory class, evidence support, authorized
target and retrieval usefulness. The model never writes memory directly. AtMem
still checks source evidence, scope, policy, current generation and canonical
post-state before disposition.

The base installation remains deterministic and downloads no model. To opt in:

```bash
python -m pip install --upgrade --pre "atmem[laya-formation]==2.3.9b1"
atmem formation preview --download
atmem formation setup --download --device auto --yes
atmem formation doctor
atmem formation activate --yes
atmem formation status
```

Preview is read-only. Setup downloads and verifies the exact public artifact but
leaves it inactive. Activation is a separate confirmed action. Roll back with:

```bash
atmem formation rollback --yes
```

The optional model is about 800 MB and adds Laya/PyTorch dependencies. Real CPU
and accelerator inference was verified on Apple-silicon macOS, Windows CUDA and
Linux CUDA, with CPU paths on all three. The normal Python wheel was tested on
Python 3.10–3.13. Intel macOS full-model inference was not tested.

On the frozen synthetic benchmark, the model improved exact state and strict
store-to-retrieve success over deterministic AtMem, but tied its lexical
retrieval MRR. It took about 272 ms per formation choice on the tested
Apple-silicon CPU versus about 2.3 ms for rules. Jev and Qwen comparisons are
inconclusive, and no production superiority claim is supported. Read the
[release evidence and exact limits](../releases/v2.3.9b1.md).

# OpenClaw lost-acknowledgement paper

LaTeX source for the 27 September 2026 functional qualification note.

Build from the repository root:

```sh
tectonic --keep-logs --outdir tmp/pdfs/openclaw-lost-ack RandD/papers/openclaw-lost-ack/main.tex
```

Evidence and reproduction are packaged under `output/huggingface-lost-ack/`.
Public destination: https://huggingface.co/datasets/atmem/memory-integrity-continuity/tree/main/openclaw-lost-ack-20260927

Nine final qualification runs passed: five bridge fault trials, three real OpenClaw gateway fault trials, one no-fault gateway control. Preserve the development failures and the explicit deterministic-model and post-write fault scope.

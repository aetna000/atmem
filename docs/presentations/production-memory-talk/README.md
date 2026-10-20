# Paving the road to production for agent memory

A 20-slide talk, with a full speaker transcript, on taking AI agents with
memory from experiments to governed production use with AtMem. It covers the
missing controls, the control-plane architecture, the rollout path, the
per-turn runtime contract, the host and operator MCP surfaces, shadow and active
modes, the AtBot authority boundary, framework adapters, the Agent Black Box,
governed task state, privacy, journaled restore, and benchmark evidence.

| File | Purpose |
| --- | --- |
| `index.html` | Self-contained viewer. Open it in a browser: arrow keys or click to move, **N** for speaker notes, **F** for full screen, `#7` in the URL jumps to slide 7. |
| `TRANSCRIPT.md` | The spoken script, one heading per slide. |
| `slides/*.html`, `deck.json` | Slide sources (one 1920×1080 `<section>` per file, notes in `<aside>`). |
| `build.py` | Regenerates `index.html` and `TRANSCRIPT.md` from the sources (standard library only). |

After editing a slide or its notes:

```bash
python docs/presentations/production-memory-talk/build.py
```

Facts, commands and figures come from the README and the guides under `docs/`.
The benchmark slide reports the frozen ~5% development samples with their
caveats; re-check it against the current release notes before presenting.

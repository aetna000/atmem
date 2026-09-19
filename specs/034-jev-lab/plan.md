# JEV-Lab implementation plan

## Technical context

Python 3.10–3.13, standard library only for the research runner and report.
The runner may import `atmem.Memory` only to prove the local candidate store is
usable; it must not change production APIs. HTTP uses `urllib.request` so the
offline path has no extra dependency. Artifacts are written under
`research/jev_lab/results/` (ignored local outputs) and a small checked-in
fixture may be used for tests.

## Architecture

1. `dataset.py` creates the fixed synthetic memories, queries, expected relevant
   IDs, authority constraints, and graph-like relationships from a seed.
2. `runner.py` computes deterministic lexical candidates, optionally calls Jev
   once with batched typed questions, applies local authority gates, and emits a
   versioned report model. The request body is synthetic and the API key is read
   only from `JEV_API`.
3. `report.py` renders a single HTML file with inline SVG bars, a decision-flow
   graphic, and a compact table; it escapes all values.
4. `cli.py` exposes `python -m research.jev_lab ...` with `--offline`, `--seed`,
   `--output`, `--model`, and `--cases`.

## Data and safety decisions

- No production database, agent session, or user content is read.
- The API key is never included in JSON, HTML, logs, exceptions, or subprocess
  arguments.
- The report stores digests of state, not raw API credentials. Synthetic memory
  text is acceptable in this research artifact because it is intentionally
  generated and clearly labelled.
- Jev output is an advisory score. A candidate with `eligible=false` cannot be
  returned even if Jev scores it highly.
- Live errors fall back to a clearly marked unavailable result; they do not
  silently become a live success.

## Validation

Run unit tests for dataset, request construction, parsing, authority gating, and
HTML escaping. Run the offline CLI and validate JSON schema fields, SVG presence,
and deterministic digest. If `JEV_API` is available, run one smoke request with
the pinned model and record only the returned model, HTTP status, and latency.

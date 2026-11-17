# Plan — Measured Memory Adaptation

## Context and architecture
Python 3.10–3.13, standard-library experiment code, existing FeedbackService owner
transactions and encrypted evidence container. No SDK dependency upgrades or new
canonical database. Public API in `atmem/feedback/adaptation.py`; executable pilot
in `atmem/benchmark/memory_adaptation.py` with a small script wrapper. Existing
crypto and SQLCipher dependencies are reused for retained evidence and tests.

Use a closed immutable manifest, generic/revised policy records, scoped durable
phase and attempt ledger. Application callbacks execute task agents and independent
graders; the agent receives only explicit public case input. Store full trace chunks
in bounded encrypted rows rather than oversized aggregate records. Policy code is
never generated or executed. State changes serialize in owner transactions; external
calls occur only after durable reservations commit. Pending operations are terminal
unknowns unless investigated; no paid automatic retry or silent resume.

Study phases: preregister -> training -> proposal -> validation -> selection lock
-> final evaluation -> closed report. One revision maximum. Selection never sees
final results; all four final arms are reported even if the revision loses.
Fixed train-only snapshots are compared to isolate reuse from test-set learning.

CLI pilot uses OpenRouter explicit model/endpoint and credentials by environment or
explicit env-file path; only the necessary provider key is read, never logged.
SQLite tools use immutable read-only connections, an authorizer, progress handler,
row/byte bounds, and no arbitrary shell, extension, attach or filesystem tool.
The grader is separate from model code and reads sealed expected values only.
Source benchmark code/DB are pinned and verified; adapted scoring and differences
from official CL-Bench are documented. No source benchmark dependency is installed.

## Research and evaluation decisions
Use Meta's proposal/evaluate/select separation, ACE's incremental bounded memory
principle, SoMem's return to original evidence, and CL-Bench's actual task reward.
Include raw evidence comparator because simple ICL can beat dedicated systems.
Only one model-generated revision, fixed hypothesis and no broad evolution.
Meta public project has no runnable implementation; do not pretend its instructions
or trained checkpoint were reproduced. See research.md for pinned primary sources.

Predeclare train IDs1–10 and validation11–15 from original DB; final16–30 plus
post-drift101–105. The implementer already viewed IDs1–3; they remain training.
No final task text/labels goes to candidate generator. One evaluation seed per arm,
interleaved arm order. Preserve episode clustering (shared database) and avoid
question-level confidence claims of independence. A pilot cannot satisfy powered
production acceptance. Two snapshots (~830MB) and code/evidence live on external
MEM0; maximum evidence32MiB, total provider800 calls/2M tokens/$3/90min. Stop on
lack of measured benefit rather than expanding. No forced positive conclusion.

## Verification and release
Meaningful adversarial service/CLI/tool tests; existing feedback and native memory
regressions; full applicable Python/AtBot/OpenClaw gates; wheel/sdist metadata and
installed-artifact smoke. Beta target2.3.15b2 with bridge2.3.15-beta.2, unchanged
AtBot0.1.1 and AtFlows0.1.8. Public review/merge before tag; separate private website
source-pin PR after public main exists; owner merge/deployment remain pending.

# Dataset research and acquisition policy

LoCoMo is published by SNAP Research with ten long conversations and annotated
QA/evidence in `data/locomo10.json`; its repository license is CC BY-NC 4.0.
The adapter therefore requires a user-provided local copy and records its
SHA-256 rather than redistributing it.

LongMemEval provides 500 questions across information extraction,
multi-session reasoning, knowledge updates, temporal reasoning, and abstention,
with S/M/oracle variants. It remains staged until an adapter can preserve its
official session and answer-scoring contract.

BEAM is a large-context workload with 100K/500K/1M/10M variants and rubric-based
judging. It is staged for the memory-fabric scheduling track because ingestion,
agentic answering, and judge costs must be measured separately.

Sources:

- https://github.com/snap-research/locomo
- https://github.com/xiaowu0162/LongMemEval
- https://github.com/mohammadtavakoli78/BEAM

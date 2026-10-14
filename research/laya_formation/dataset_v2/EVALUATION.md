# Formation v2 evaluation contract

This contract separates data qualification, checkpoint selection, regression testing, and
independent confirmation. Passing an earlier stage cannot be reported as passing a later one.

## Stage A: pre-training data qualification

The generated component must pass `qualify_training_data` before it can enter a training run:

- zero disposition labels in model-visible text or identifiers;
- all semantic families contain valid STORE/UPDATE/DUPLICATE counterfactuals;
- the three core counterfactuals keep evidence text identical and change only authorized
  candidate state;
- an evidence-only lexical classifier scores no more than 34% on those three core classes;
- a full-state shallow lexical classifier scores below 80% on group-held-out validation;
- semantic-family groups never cross train, validation, or calibration;
- exact and five-word-shingle contamination checks pass against every named regression or
  benchmark source;
- no test, benchmark, validation identity, or protected label is included in training.

The full-state lexical score includes legitimate policy signals such as an explicit request not
to retain something. It is a baseline the trained model must beat, not a claim that all lexical
signal is leakage.

## Stage B: checkpoint selection and calibration

Use generated validation data and the worker-disjoint LAPS transfer-validation partition for
checkpoint selection. Calibration may use only the declared calibration split. Report accuracy,
macro-F1, per-class precision/recall/F1, confusion matrices, coverage-risk curves, Brier score,
ECE, latency, and peak memory. Do not select a checkpoint or threshold from the test partitions.

The v2 learned artifact has one head: `disposition_v2`. Memory typing and exact update-target
resolution remain deterministic. This avoids the v1 failure in which five independent blocking
heads compounded errors and abstentions.

## Stage C: frozen transfer test

After code, checkpoint, question definition, and thresholds are hashed and frozen, open the
worker-disjoint LAPS transfer-test partition once. Required minimums:

- macro-F1 at least 0.80 over STORE/UPDATE/DUPLICATE;
- recall at least 0.75 for each represented class;
- at least 10 percentage points macro-F1 above the declared shallow baseline;
- results from three training seeds, with mean, standard deviation, and paired bootstrap 95%
  intervals retained in the run archive.

LAPS labels are silver extracted-preference annotations. Passing this stage demonstrates transfer
on naturally written preference dialogues; it does not establish performance on all memory or
safety classes.

## Stage D: operational regression

Run the frozen OpenClaw 100-item corpus without changing rules or thresholds. Because this corpus
was inspected and informed the training taxonomy, it is a regression test, not independent
evidence. Required release gates are:

- at least 80/100 exact disposition matches;
- at least 21/25 STORE and 12/15 UPDATE matches;
- zero semantic views for expected DO_NOT_STORE items;
- zero authoritative semantic views for REVIEW items;
- every abstention retains source evidence and fails closed;
- report p50/p95 latency and all receipts.

## Stage E: independent confirmation

Before a model-quality publication claim, obtain at least 500 previously inaccessible examples,
stratified to at least 100 per disposition. Two independent annotators label each example under a
preregistered rubric; disagreements are adjudicated. Report agreement before adjudication and
require Cohen's kappa of at least 0.80. Freeze and publish input hashes before opening labels.

The frozen model must achieve macro-F1 at least 0.80, recall at least 0.75 per class, and a harmful
false-STORE rate no greater than 2% across REVIEW and DO_NOT_STORE. Confidence intervals and all
failed cases must be retained. These thresholds are release gates, not results.

## Stage F: end-to-end memory evaluation

LoCoMo, LongMemEval, and LongMemEval-V2 evaluate end-to-end retention and retrieval, not merely a
formation classifier. Run deterministic AtMem and AtMem+Laya with identical ingestion order,
retriever, answer model, budgets, and seeds. LoCoMo remains evaluation-only because its published
license is CC BY-NC 4.0. LongMemEval and LongMemEval-V2 also remain evaluation-only to avoid
benchmark contamination. Report official metrics plus ingestion dispositions, update/duplicate
accuracy, retrieval evidence, failures, latency, and cost. Do not use any of these benchmark test
answers for training, calibration, prompting, or checkpoint selection.

# AtMem Laya Formation Dataset v1

Status: generator and bounded fixtures implemented; full external-volume export,
independent audit and Hugging Face staging are not yet complete.

This Apache-2.0 dataset is entirely synthetic. It contains fictional memory
formation states and five finite typed decisions per state: operation, memory
class, evidence support, target selection and retrieval usefulness. It contains
no production store, user history, credentials or public benchmark answers and
cannot support a production-quality claim.

The publishable profile contains at least 12,000 scenarios and 60,000 decisions.
Splits are assigned by template family and are independently checked for overlap
in fictional identity, template family, semantic chain and paraphrase cluster.
Train/validation/calibration support training and threshold selection. Sealed
test labels remain inaccessible until the model, calibration and analysis freeze.

Generate only on the approved mounted artifact root:

```console
python -m research.laya_formation.dataset.export
```

The command refuses a different root, a sub-minimum publishable count, a missing
`/Volumes/MEM` mount or missing Parquet support. Small test-root generation is
available only through the hidden test flag and is never publication evidence.

Before staging, the independent non-sealed audit must review at least 400 rows,
reach 99% target correctness and contain zero critical privacy, credential or
license findings. Each named high-risk tag contributes at least 60 examples.
A separate reviewer audits sealed content only after the model and analysis are
frozen; any required correction invalidates that dataset/model version.

Known limitations: synthetic templates cannot establish production performance;
English is the first profile; rare real-world ambiguity may be absent; and
oracle correctness still requires human audit despite executable invariants.

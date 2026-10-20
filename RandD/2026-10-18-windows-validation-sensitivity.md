# Windows validation sensitivity

Exploratory audit, not a new model run, grade, confirmation or gate change.
All ten native/tools pairs and both repeats remain included in the primary
result: 24.817175% fewer input tokens, 4/10 full-task passes each. Paired
outcomes: three both-pass, one native-only, one tools-only, five neither-pass.
The partial target-check loss remains in the main cohort report.

| Diagnostic omission (both repeats) | Remaining input reduction | Native/tools passes |
|---|---:|---:|
| Marshmallow-1229 | 16.335338% | 4/4 |
| Marshmallow-1810 | 33.324898% | 2/2 |
| Requests-1327 | 27.855408% | 4/4 |
| Astroid-1616 | 28.837192% | 3/2 |
| Astroid-934 | 9.312962% | 3/4 |

None replaces the primary result. Removing either Marshmallow-1229 or
Astroid-934 loses the 20% input gate; removing Astroid-1616 loses the task-pass
gate. Dropping all Astroid attempts leaves 14.591473% saving. Benefit depends
materially on the issues present.

Fixed seed `atmem-windows-validation-cluster-audit-20261018-v1`, 10,000 samples.
An entire issue/repository, both arms and all repeats, is resampled together;
pooled token ratios are recomputed, not averaged case percentages. Nominal
2.5/97.5 percentile ranges:

| Unit | Clusters | Input reduction range | Task-pass rate difference range |
|---|---:|---:|---:|
| Issue | 5 | −33.886682% to 42.580375% | −0.30 to 0.30 |
| Repository | 3 | −8.020365% to 31.878160% | Degenerate at zero |

Small cluster counts and post-validation candidate selection do not establish
equivalence, significance, causality or generalization. The repository quality
range is degenerate because aggregate pass counts match within each observed
repository, not because equivalence is proven. No significance claim is made.

Complete inputs, source, seed and results are retained in protected run
`external-windows-validation-uncertainty-v1-20261018`, linked to the original
comparison object. Unknown counters cannot enter this analysis. The locked new
candidate and fixed thresholds are unchanged; fresh confirmation remains needed.

# Base vs tuned Laya — sealed stateful comparison

> Agreement with blinded machine weak supervision; not human ground truth.

| Metric | Base Laya | Tuned Laya |
| --- | ---: | ---: |
| Fully correct transition | 18.36% | 73.79% |
| Operation accuracy | 25.11% | 80.54% |
| Operation macro-F1 | 9.18% | 23.37% |
| Target accuracy | 0.00% | 10.00% |
| Exact post-state accuracy | 94.15% | 93.65% |
| False-store count | 2.0000 | 15.0000 |
| Duplicate-creation count | 0.0000 | 0.0000 |
| Unsafe-mutation count | 10.0000 | 9.0000 |
| Brier score | 0.4957 | 0.1852 |
| ECE | 0.5653 | 0.4092 |

Paired fully-correct delta: 55.43 percentage points 
(paired bootstrap 95% CI: 53.18 to 57.63).

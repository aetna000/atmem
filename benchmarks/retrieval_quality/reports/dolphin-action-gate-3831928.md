# Dolphin 5% action-gate qualification — `3831928`

This is a reader-free safety qualification on the frozen 30-task development
slice. It is not a DolphinBench accuracy score and made no model, provider, or
tool calls.

## Result

| Control | Passed | Failed | Model calls | Tool calls |
|---|---:|---:|---:|---:|
| Complete restored evidence opens gate | 30 | 0 | 0 | 0 |
| One request-aligned fact removed blocks gate | 30 | 0 | 0 | 0 |

Every removal produced `blocked_missing_requirement`; the product receipt
named a request-derived missing obligation matching the independently held
evaluator requirement. No timeout, parse error, provider error, generic
abstention, or silent no-call was credited. The restored precheck proves this
candidate is not an always-blocking gate. Paid positive controls must still
show that Hermes is invoked and the expected tool call can occur.

## Frozen identity

- AtMem commit: `3831928`
- AtMem version: `2.3.8b6`
- Installed artifact: `sha256:5e9873d1c5f312b06e912dd374d3004655944bc2abce4fa3b406faca0fef83a9`
- Wheel: `sha256:d7341cfd786b45bf81add3583f1569b16f69fbca3c4aa8cf83b1e359ed033f95`
- Official Dolphin checkout: `81cb6f8405b40a9e76089cef650806a80af06ea2`
- Requirement manifest: `sha256:002894c0f9e0f8377164d0a9edbbb86a5e2119449e30a12f4934bd0bf8849650`
- Run config: `sha256:e3396609b7a3b6e9376c0de61637b17fb63bdef345938081acc5ae4a7debbf56`
- Restored receipt: `sha256:8aae402ea5404d63cacf16721dcda3d34ea102172ef83bae29c71b25dd819d7d`
- Removal receipt: `sha256:d0b19ab78172d9f2bc75db875ca901bfd1e3c1d2a836676a11976a9c13222dee`

The clean installed wheel rebuilt 13,539 source sessions into three encrypted,
active V3 generations. Their databases total 311,545,856 bytes; derived/source
ratios are 1.21x, 1.28x, and 1.21x, with zero duplicate source rows.

Artifacts are archived under
`/Volumes/MEM/atmem-benchmarks/feature-040/3831928/`.

## Per-task removal evidence

| Task | Removed requirement | Units | Outcome | Model invoked | Tool calls | Actual reason |
|---|---|---:|---|---:|---:|---|
| `alex:001` | `alex:001:fact:290` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:026` | `alex:026:fact:195` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:042` | `alex:042:fact:129` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:044` | `alex:044:fact:141` | 4 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:054` | `alex:054:fact:132` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:074` | `alex:074:fact:23` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:082` | `alex:082:fact:98` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:105` | `alex:105:fact:30` | 3 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:136` | `alex:136:fact:152` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `alex:147` | `alex:147:fact:269` | 3 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:011` | `morgan:011:fact:34` | 3 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:045` | `morgan:045:fact:298` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:063` | `morgan:063:fact:181` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:071` | `morgan:071:fact:57` | 3 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:079` | `morgan:079:fact:170` | 3 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:082` | `morgan:082:fact:279` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:097` | `morgan:097:fact:51` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:103` | `morgan:103:fact:119` | 4 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:138` | `morgan:138:fact:83` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `morgan:183` | `morgan:183:fact:32` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:022` | `riley:022:fact:358` | 3 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:044` | `riley:044:fact:192` | 4 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:045` | `riley:045:fact:297` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:062` | `riley:062:fact:76` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:088` | `riley:088:fact:289` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:119` | `riley:119:fact:389` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:126` | `riley:126:fact:423` | 4 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:162` | `riley:162:fact:27` | 2 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:163` | `riley:163:fact:71` | 1 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |
| `riley:165` | `riley:165:fact:380` | 3 | `blocked_missing_requirement` | false | 0 | `missing_requirement` |

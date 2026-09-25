# Installed-wheel replay regression, 25 September 2026

This reruns the four-arm recorded-response fault check after adding the worker's
optional live-provider boundary. The run used recorded responses, no paid calls.
The native public store actually accepted an exchange; the worker was killed
before its HTTP reply and resumed after the real 125-second wait.

| Configuration | Requests after restart | Further store changes | Outcome |
| --- | ---: | ---: | --- |
| Durable LangGraph | 1 | 0 | Native store rejected repeat; next model request has no recorded reply |
| With AtMem | 0 | 0 | Needs confirmation |
| With AtFlows | 1 | 0 | Native store rejected repeat; next model request has no recorded reply |
| With both | 0 | 0 | Needs confirmation |

These are repeated requests, not duplicate effects prevented. Safe blocking is
not successful task completion. This is one exposed public task and recorded
model responses, not a fresh autonomous or held-out improvement result.

`protocol.json` pins source files and installed package records. `summary.json`
contains all dispositions; compressed arm JSON contains exact native journals
and independent observations. `SHA256SUMS.json` authenticates those artifacts.
Source: tau2-bench commit `b7ea9074c1cba482b30687fecdb5c8425fd6f619`;
the upstream MIT license is retained in the preceding
[`003` bundle](../public-retail-fault-20260925-003/).

Launch the benchmark with the installed environment first on `sys.path`, not
with an editable AtMem checkout shadowing the wheel. This run used Python `-I`
from the isolated temporary directory and appended the benchmark repository
after installed site-packages. An earlier attempt004 stopped before executing
trials because checkout egg-info lacked RECORD; it is not a passing result.

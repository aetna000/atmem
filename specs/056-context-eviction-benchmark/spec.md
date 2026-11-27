# Context eviction benchmark

An OpenClaw user with a long coding session wants to send fewer redundant
tool results while retaining the full record of what happened. Contexture's
64% describes candidates in final histories. This feature measures which
parts of that opportunity are reachable with one conservative rule.

## Requirements

- FR-001. Replay a bounded corpus of ordered model requests. The control
  measures each supplied request as received. The candidate uses the same
  request with eligible tool result bodies replaced by short references.
- FR-002. Require two correlated, successful, exact file reads with identical
  arguments and text. Preserve the newer full result, the tool protocol,
  unrelated evidence, and the original requests. Honor a configurable grace
  window after the replacement arrives. Treat unverified evidence as ineligible.
- FR-003. Report estimated full-request token volume across all requests,
  final-history candidate volume, net savings after references, and per-session
  and per-request counts. Label the tokenizer, serialization, and corpus.
- FR-004. Provide synthetic controls for partial reads, changed contents,
  failed reads, and late duplicates. Accept normalized authorized traces
  for later measurement of the real workload.
- FR-005. Record an external Claude Code review in read-only mode.

## Success criteria

The fixture and report reproduce with no inference calls. The candidate
preserves every expected control. The report makes it possible to distinguish
final-history candidates from volume saved across requests. A user benefit
claim requires live paired task outcomes and provider usage on a recorded
host configuration.

## Opt-in SDK integration

- FR-006. Replay and the SDK share the same verified read projection.
- FR-007. Pydantic AI and LangChain/LangGraph adapters accept an explicit
  policy. The application supplies exact, verified read receipts in the current
  run and a token counter. With no policy, requests follow the existing path.
- FR-008. An enabled adapter projects only the model-bound messages. Native
  histories and tool-call/result identifiers stay available for recovery
  and audit. Unsupported results remain intact. A provider-boundary test
  must exhibit the change, and the saved tool results must still be exact.

# Formation Decision Contract V1

## Request

A request supplies a version, request ID, authorized-input digest, canonical
generation, one or more versioned typed questions and finite choices using
opaque IDs. Text is bounded by the active policy. It contains no credential,
authority grant, unrestricted store handle or instruction to write.

The serializer binds the pinned tokenizer and effective maximum length. It
reserves every mandatory question, choice and special token before admitting
whole source-range evidence units. Token overflow produces an explicit loss
receipt and escalation/review; runtime tokenizer truncation is forbidden.

## Response

A response supplies the matching IDs/version, selected choice IDs, raw bounded
scores, model/revision, question-schema digest and diagnostics. Unknown IDs,
nonfinite scores, cardinality violations, truncation or revision mismatch make
the response invalid.

## Authoritative processing

AtMem reloads the current generation, resolves every opaque ID, rechecks scope,
source support and admission policy, and records proposal and disposition. A
valid response may still be rejected, reviewed or superseded. Only the existing
Spec 040 service can mutate canonical state.

## Compatibility

Unknown major versions fail closed. Additive optional fields are ignored only
when their absence cannot widen authority. A profile binds the contract,
question schema, model and calibration digests as one activation unit.

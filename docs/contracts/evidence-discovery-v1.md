# Evidence discovery v1

Introduced as an opt-in SDK/host contract in AtMem 2.3.10b1.

## Authority and lifetime

The trusted application constructs `ContextRequestV3`, fixes subject/agent/workspace,
holds the encrypted `Memory` instance open, and supplies a live authorization
callback plus `NavigationBudget`. Authorization is checked before nomination and
again before delivery. A provider nominates IDs only; AtMem reloads canonical,
active, same-scope evidence. A similarity score cannot establish sufficiency.

## MCP requests

| Tool | Exact arguments | Effect |
| --- | --- | --- |
| `memory_search` | `{"query":"deployment channel"}` | Bounded lexical/optional semantic search |
| `memory_inspect` | `{"unit_id":"returned-unit-id"}` | Read one previously authorized source range |

No extra fields, scope selectors, writes, provider imports or lease creation are
model-callable. The host owns MCP process/session construction. Failures return
`isError: true` without credentials, source excerpts or internal paths in errors.

## Successful response

```json
{
  "format": "atmem-evidence-discovery-v1",
  "request_id": "host-request:discovery:1",
  "generation": 1,
  "status": "investigative_evidence",
  "sufficiency": "not_assessed",
  "channels": ["lexical"],
  "evidence": [],
  "omitted_count": 0,
  "operations_used": 1
}
```

When present, each evidence object contains `unit_id`, original `text`, and its
`source_range` identity/digest/offset fields. Empty results are not authorization
to broaden scope. `omitted_count` records packing omissions, not a claim that all
relevant facts were discovered. Optional source bundles/time frames/model-quoted
interpretations add explicitly named fields and retain their limited assurance.
The host persists an encrypted preparation receipt before returning evidence;
preparation alone does not establish model input delivery or an external action.

## Hermes host envelope

An administrator opens a lease for one active V3 binding and turn. Agent RPC
operations are `discovery-search` with exactly `lease_id, query`, and
`discovery-inspect` with exactly `lease_id, unit_id`. Each uses the binding's
scoped bearer credential, not an administrator/dashboard credential. The stdio
bridge accepts only a qualified loopback endpoint and a trusted host-created
connection/credential file; never place those files in a repository.

Reservations survive crashes and restarts. The host cannot silently retry an
uncertain operation or reset the model's lease. Disable/revoke, expiry or source
generation/revision change fails closed. Remote state assessment requires the
administrator's explicit lease egress permission in addition to a configured
application-owned assessor.

## Compatibility

The existing V3 context/sufficiency and ordinary MCP profiles are unchanged.
This investigative profile does not convert incomplete V3 context into a
sufficient V2 package. The source of authority remains AtMem, not an index or
AtBot. See the [setup guide](../evidence-discovery.md) for installed usage.

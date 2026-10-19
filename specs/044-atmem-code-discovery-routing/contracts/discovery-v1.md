# Repository navigation contract v1

The operator binds an authorized Code scope, repository root, current generation
and one backend before serving any model request. None is model-selectable.

## Model request

```json
{"format":"atmem-repository-discovery-request-v1","request_id":"req-01","turn_id":"turn-01","query":"automatic help option construction","limit":5,"budget":4096}
```

Exactly these keys: format, request_id, turn_id, query, limit, budget. IDs use
the existing opaque Code ID validator. Query is nonempty after stripping, at
most 4000 UTF-8 bytes and must pass secret screening before persistence/backend
use. Limit is integer 1–8; budget is integer 512–8192 bytes (booleans are not
integers). Unknown fields, including root, scope, operation, exact search,
credentials and backend, are refused. Invocation has navigation semantics only.

## Response

```json
{"format":"atmem-repository-discovery-response-v1","request_id":"req-01","turn_id":"turn-01","backend":"atmem","status":"ready","non_exhaustive":true,"items":[{"id":"code:opaque","title":"Command.get_help_option","location":{"path":"src/click/core.py","start_line":1130,"end_line":1185,"content_sha256":"<source-digest>"},"version":"<version-digest>","match":"identifier_or_path"}],"truncated":false,"freshness":"current_at_preparation","native_fallback":"available_to_host","assurance":"prepared_only"}
```

Example structure only, not a measured benchmark result. Item keys are an
allowlist; exact source anchors come from the authorized index, not generated
text. Title is a bounded source-derived identifier. No source body, summary,
observation, command, output, confidence, runtime proof or instruction field.
Items may be empty; non-exhaustive remains true. Complete serialized responses,
including metadata, must fit the requested budget. Emit a bounded withheld result
if metadata cannot fit or evidence is no longer authorized/current. The response
does not instruct a host to suppress native reads.

`ready` does not mean complete retrieval. Freshness is rechecked before actual
delivery and described at the observed boundary, not indefinitely. Provider or
stale-state failures produce withheld/fallback metadata, never an automatic
second provider lookup. Native fallback availability refers to the supported
host configuration; a transport with no known fallback must say `unknown`.

## Evidence and delivery

Preparation is retained in the existing encrypted `curation-exposure` document,
with its opaque receipt, complete request/response and source/generation binding.
Delivery must revalidate the original Curation selection and reproject through
the same allowlist. Stream writing and model-input observation have separate
receipts. The serving process may hold bounded pending preparation references;
these are not a memory authority or model-memory cache. Delete/clear must include
the original exposure plus attached navigation representation. No new document
kind bypasses existing governed cleanup/export.

No generic parser may rewrite arbitrary native shell commands into this request.
An SDK/CLI host adapter must map an explicitly supported navigation operation and
retain the original intent. Exact regex/literal search has a different contract.

# Python memory API

The embedded engine is useful without a hosted model. Run the complete
[isolated quickstart](getting-started.md) first.

## Main operations
| Call | Purpose |
| --- | --- |
| `Memory(path)` | Open canonical memory and its normal derived vector sidecar |
| `remember(subject_id, message, session_id=...)` | Admit a sourced memory through policy |
| `recall(subject_id, query, limit=...)` | Return matching eligible records |
| `verify(subject_id)` | Check retained integrity |
| `close()` | Flush/close owned resources |

## Procedure review authority (2.3.6)

An embedded application that can approve typed procedures must configure its
review principals when it opens `Memory`. A plain `actor` string is audit text,
not authority:

```python
from atmem import Memory
from atmem.extract import ReviewService

memory = Memory(
    "memories.db",
    review_authorities=(
        {
            "principal_id": "owner:alice",
            "subject_id": "alice",
            "agent_id": "assistant",
            "workspace_id": "personal",
            "scopes": ("procedure",),
            "assurance": "host_authenticated",
        },
    ),
)
authorization = memory.issue_review_authorization(
    "owner:alice", scopes=("procedure",)
)
ReviewService(memory).decide(
    proposal_id,
    "approve",
    actor="display-only",
    authorization=authorization,
)
```

The issued value is bound to that `Memory` instance, configured principal,
permission, subject, agent, and workspace. Caller-created values, widened
scopes, altered fields, and cross-instance reuse fail closed. The signed-in
local dashboard performs this mapping for an Administrator account.

`Memory.submit_proposal` also refuses secret-bearing or explicitly excluded
semantic payloads before creating active or quarantined records. Captured
source evidence remains subject to its separate evidence access and retention
policy.

A Python process using the embedded API owns its storage access. This is not the
same authentication boundary as a dashboard account or remote HTTP client.
Never turn user-supplied subject IDs into authorization without checking them.

## Retrieval versus injection
Calling `recall` does not prove that context was sent to a model.
Use a [host adapter](integrations.md) for preparation, exact delivery confirmation
and lifecycle evidence. Use [retrieval quality](../retrieval-quality.md) to
understand support checks and the opt-in fusion profile.

## HTTP client
`atmem.client.AtMemClient` accepts an endpoint and local credential. It is a
different interface from the embedded `Memory` class.
See [HTTP API](../http-api.md) before exposing any service beyond loopback.

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

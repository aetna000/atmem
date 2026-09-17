# Examples you can try

## No model or API key
Start with the [first-memory Python example](getting-started.md). It verifies both
a positive retrieval and separation between two subjects, then removes its temporary data.

## Connect a real runtime
These examples require the corresponding installed host and configured model.
They can incur model costs and are not run by this website.
- [OpenClaw onboarding](../examples/onboarding/openclaw.md)
- [Pydantic AI lifecycle](../framework-adapters.md#pydantic-ai)
- [LangGraph lifecycle](../framework-adapters.md#langgraph-and-langchain)
- [HTTP onboarding](../examples/onboarding/http.md)

## Read a synthetic API exchange
Illustrative fixture only — no request is sent by this page.

```http
GET /v1/health
Authorization: Bearer <local-credential>
```

The response describes the local service health. Without a valid credential the
request is rejected; a listening TCP port alone is not authenticated access.
Use the [HTTP reference](../http-api.md) for the actual response contract and
[troubleshooting](troubleshooting.md) for authentication failures.

## Verify what reached a model
After a supported host turn, inspect Sessions in the local dashboard. Follow the
request, context disposition, model input/output and tool timeline. Prepared context
is not confirmed delivery. See [Black Box interpretation](../agent-blackbox.md).

## Cleanup and side effects
The first-memory example deletes its temporary files automatically. Agent examples
create persistent memory/evidence and may call configured model services.
Return to shadow to stop future injection; this does not undo past tool actions.

# Code context routing v1

The coding host supplies a validated `atmem-code-context-request-v1` and opaque
request tags. The authenticated scope comes from its enrollment or dashboard
account. Tags select routes; they cannot add a subject, project, profile, agent,
endpoint or credential to the caller's authority.

Routes are stored in the encrypted canonical database and refer to existing
`DelegatedRegistration` records:

```json
{
  "route_id": "project-docs",
  "registration_id": "docs-provider:local",
  "tags": ["docs"],
  "profiles": ["shared"],
  "agents": ["claude", "codex"],
  "egress_enabled": false,
  "fallback": "withhold"
}
```

`atmem code route-set route.json`, `routes` and `route-delete ROUTE_ID` use
the same application methods as the dashboard. The route must name a registered
provider. Enabling the route's egress and the delegated registration are
separate, explicit configuration operations. Set `context_tags` in project
settings to supply default task tags; its default is the empty list.

No matching tag selects native AtMem recall. Multiple matching routes are
rejected as ambiguous. A match outside the route's exact profile/agent lists is
rejected before transport. Disabled egress and secret-bearing queries are also
rejected before transport. `fallback` is either `withhold` or `native` and applies
to a selected provider's operational/validation failure.

The provider receives the existing `atmem.delegated-context-request.v1`:
`workspace_id` is `PROJECT_ID:PROFILE_ID`, `user_id` is the authenticated Code
owner, and agent/session/turn/run IDs bind the request. The registration must
authorize those exact values. Transport uses the existing loopback-only,
redirect-refusing client with scoped HMAC request authentication and its
registered timeout and response-size limits.

The provider returns `atmem.delegated-context-provider.v1`. AtMem verifies the
provider/instance/key, Ed25519 signature, complete binding, issue/expiry times,
context byte count/digest, decision and receipt before using any content. It
screens returned text, enforces the Code context budget, and adds explicit
delegated-source attribution. A nonce and one-result-per-request reservation
protect retries; a cached signed result is reverified against current trust
and expiry before reuse. Provider text is never promoted to canonical memory.

The response includes a `CodeContextPackage`, authority (`atmem`,
`delegated-context`, or `atmem_fallback`), decision, provider attribution and
verified result/source references. The actual host submission remains a
separate context receipt. Failure results withhold or recompute native context
according to the configured policy; they never invent successful delivery.

Mem0 is served by the existing `atmem provider init NAME --kind mem0 --mode oss`
provider adapter. Local RAG services implement the same signed provider
contract. Provider initialization prints its separate trust-registration
command; configure its workspace as `PROJECT_ID:PROFILE_ID`, agents and owner
explicitly before enabling it. The Code layer does not reinterpret an unsigned
RAG response as a trusted provider envelope.

Local clear verifies local memory and derived cleanup. Provider-owned memory
has independent lifecycle authority: without a provider-confirmed deletion
receipt the result is partial and says `external_status: not_requested`.

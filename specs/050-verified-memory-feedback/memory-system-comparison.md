# Memory governance and tool admission: reviewed patterns

Reviewed 2026-11-09 in response to the owner's request. This is a review of
official documentation, not a comparative benchmark or a security audit of the
other implementations. “Not established here” does not mean a product lacks it.

| System | Verified documented mechanism | Implication for Spec 050 |
|---|---|---|
| Mem0 | Authenticated client, memory add/search/update/delete and user-scoped search filters. | Reuse scoped memory APIs. A stored memory or search result alone does not establish permission for an external action. The reviewed quickstart does not establish a final tool-dispatch veto. |
| LangMem | Memory tools accept runtime namespaces, typed schemas and `actions_permitted` to restrict create/update/delete. | Derive namespaces from trusted application identity; keep memory modification permissions distinct from downstream execution policy. A namespace supplied in configuration is not independent proof of authentication. |
| Letta | Agent-attached tools can require approval. Legacy client-tool flow returns a pending tool call for the application to execute and return a result. | Keep approval and execution explicit, bind decisions to the concrete pending call, and recognize the application as an enforcement boundary. Server pause does not prove a separately controlled client executed safely. |
| LangChain / LangGraph | HITL middleware interrupts before selected calls, checkpoints state, and resumes with approve/edit/reject/respond decisions. Batch decisions map to individual actions. | Preserve pending action identity and durable recovery; reject means no effect, while a synthetic response is a different result. Approval after editing must refer to the edited call. |

Sources, accessed on the date above:

- [Mem0 platform quickstart](https://docs.mem0.ai/platform/quickstart).
- [LangMem Memory Tools API](https://langchain-ai.github.io/langmem/reference/tools/).
- [Letta tool approval API](https://docs.letta.com/api/typescript/resources/agents/subresources/tools/methods/update_approval).
- [Letta legacy client tools](https://docs.letta.com/v1-sdk/tools/client-tools).
- [LangChain human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop).
- [LangChain HITL API reference, v1.4.0 as displayed when reviewed](https://reference.langchain.com/python/langchain/agents/middleware/human_in_the_loop/HumanInTheLoopMiddleware).

The Letta client-tools page redirected from the older `/guides/agents/` path to
its explicitly legacy V1 documentation. That flow is described here as legacy,
not assumed to define the current Agent SDK's behavior. The approval API page
independently documents the per-tool approval requirement.

## Decision adopted for AtMem and Hermes

Keep memory evidence, memory review, tool approval and dispatch admission as
distinct records. Models may propose; authenticated authority decides. Place an
idempotent read-only final-policy check after request/argument transformations,
immediately before the instrumented host callback or registry/connector dispatch.
An earlier transform hook can still rewrite or request human approval; it cannot
silently authorize a different final call. Any existing veto remains a veto.

Use detached JSON snapshots so a callback retaining its input cannot later change
the checked arguments. Invalid modifying final decisions, callback/dispatcher
failures and timeouts yield a blocked tool result, allowing a fresh attempt after
recovery. They do not authorize fallback execution or crash the conversation.

The generic host hook is only the boundary. Spec 050 still must implement server-
derived scope, current-source checks, independent outcome verification, qualified
rule lifecycle, and atomic single-use approval admission. The hook itself cannot
grant these properties, authenticate an `approved` argument, undo an admitted
write, or prevent direct execution outside the instrumented runtime.

No reviewed page establishes every protection above across arbitrary wrappers,
post-approval mutations, failures, replay and revocation. We therefore use the
documented patterns as design input and require our own conformance evidence;
we do not claim other systems already solve every case or that AtMem is superior.

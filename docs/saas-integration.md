# Using AtMem in a SaaS product

This guide explains how to use AtMem as the memory and evidence layer behind a
multi-user SaaS application. It covers the architecture AtMem supplies, the
security boundary your SaaS must supply, and a rollout path from memory-only
integration to auditable agent activity.

## Start with the correct integration model

Choose the path that matches your product:

### Your SaaS runs OpenClaw

Install AtMem beside each OpenClaw runtime:

```bash
python -m pip install --upgrade atmem
atmem openclaw install
atmem dashboard daemon start
```

The installer begins in **shadow mode**. It copies and continuously verifies
OpenClaw's native memory without changing the context sent to the model. After
the dashboard reports that the copy and restore path are healthy, activate it:

```bash
atmem control verify
atmem control activate
```

Use `atmem control restore` to return to the saved OpenClaw configuration.
OpenClaw is currently the only host with AtMem's complete automated migration,
Black Box lifecycle capture, activation, and restore adapter.

### Your SaaS has its own agent runtime

Use the embedded Python engine or run `atmem mcp` as a private child process.
Your host adapter must authenticate users, supply tenant/session/turn identity,
inject the returned memory into the actual model request, and record the model
and tool lifecycle it observes.

Do not describe a generic MCP connection as a complete Black Box integration.
The MCP server provides governed memory operations, but an MCP connection alone
cannot prove which context reached a model or what an external system did.

## Recommended SaaS architecture

```text
Authenticated request
        |
        v
Tenant and user resolver  ---> authorization and deletion policy
        |
        v
Agent runtime             ---> model and tool provider
        |
        +-- recall/capture ---> AtMem memory engine
        |                       one isolated database per tenant
        |
        +-- outcome ID ----> system-of-record verifier
                                email, payment, CRM, database, etc.
```

Treat AtMem as an internal service. Do not expose its MCP process, SQLite file,
or loopback dashboard directly to customers.

## Tenant isolation

AtMem scopes records and audit events by `subject_id`, but `subject_id` is a
logical data scope—not an authentication or authorization boundary.

For production SaaS deployments:

1. Derive tenant and user identity from your authenticated server session.
   Never trust a `subject_id` supplied by a browser or model.
2. Prefer one database per tenant. Within that database, use one opaque
   `subject_id` per user or account whose memories may be recalled together.
3. Keep the tenant-to-database mapping in your application control plane, not
   in model-visible prompts or tool arguments.
4. Use opaque internal identifiers. Avoid putting email addresses or customer
   names in database paths, subject IDs, session IDs, or logs.
5. Apply authorization before every remember, recall, inspect, export, promote,
   or forget operation.

A shared database with values such as `tenant-id:user-id` can be acceptable for
a prototype, but it increases the impact of an application authorization bug.
It should not be treated as hard tenant isolation.

## Minimal embedded integration

The following is application-layer pseudocode. `authenticated_user` must come
from your SaaS authentication middleware, never from the model:

```python
from pathlib import Path
from atmem import Memory


def run_agent_turn(authenticated_user, session_id, turn_id, user_text):
    tenant_db = (
        Path("/srv/atmem/tenants")
        / authenticated_user.tenant_db_name
        / "memories.db"
    )
    subject_id = authenticated_user.opaque_subject_id
    memory = Memory(tenant_db, retain_query_text=False)

    try:
        # Record trusted user input through AtMem's admission pipeline.
        memory.capture(
            subject_id,
            "user",
            user_text,
            session_id=session_id,
            turn_id=turn_id,
        )

        # Produce a bounded, audited block. Inject this exact block into the
        # model request; do not silently append different records afterward.
        context = memory.build_recall_block(
            subject_id,
            user_text,
            session_id=session_id,
            max_records=5,
            max_chars=2_000,
            min_score=0.3,
        )

        response_text = call_model(
            user_text=user_text,
            memory_context=context["block"],
            session_id=session_id,
            turn_id=turn_id,
        )

        # AtMem stores a response digest and bounded metadata, not the response
        # text, on this evidence path.
        memory.capture(
            subject_id,
            "assistant",
            response_text,
            session_id=session_id,
            turn_id=turn_id,
        )
        return response_text
    finally:
        memory.close()
```

Check the returned context object in your installed version before wiring it to
the prompt. The important invariant is that the **exact** block AtMem records as
injected is the block your host sends to the model.

For an MCP-based integration, run a private process with an application-chosen
default subject:

```bash
atmem mcp \
  --db /srv/atmem/tenants/TENANT_DB/memories.db \
  --subject OPAQUE_SUBJECT_ID
```

Use a separate MCP process or an authorization-enforcing broker for each tenant
boundary. Do not allow a model to choose another customer's `subject_id`.

## Capture the complete agent lifecycle

To obtain useful audit evidence, assign stable identifiers before the model
call and carry them through every hook:

| Identifier | Meaning |
| --- | --- |
| `tenant_id` | Authenticated customer boundary; keep it outside model control. |
| `subject_id` | The memory owner or shared account inside that tenant. |
| `session_id` | Conversation or workflow instance. |
| `turn_id` | One user-request/model-response cycle. |
| `run_id` | One agent execution or retry. |
| `tool_call_id` | One requested tool invocation and its completion. |
| `outcome_id` | Receipt from the independent system that proves the result. |

For a custom host adapter, observe at least:

1. the user request digest and accepted request time;
2. memory candidates, returned records, and the exact injected context block;
3. model provider, model name, start/end time, token usage, and response digest;
4. every tool request and exactly one matching completion or explicit timeout;
5. the final turn status: succeeded, failed, cancelled, or incomplete;
6. independently verified outcomes for consequential actions.

`Memory.capture()` can record user, assistant, tool-call, and tool-result
activity on the memory audit chain. A full custom Black Box adapter must also
implement the stronger lifecycle and correlation requirements described in
[the integration guide](integration-guide.md).

## Prove outcomes outside the model

A successful tool return is not proof that the real-world action happened.
Verify consequential outcomes against the owning system:

- email: provider message ID and delivery/bounce event;
- payment: processor transaction ID and final state;
- database: transaction or change ID read back from the database;
- CRM: object ID, version, and updated field read back through the CRM API;
- file/object storage: object version, digest, and storage receipt.

Store the full receipt in your protected evidence store. Bind only its opaque
ID, digest, status, and safe metadata to AtMem, for example:

```python
memory.log_action(
    subject_id,
    "outcome.verified",
    {
        "outcome_id": receipt.id,
        "receipt_sha256": receipt.sha256,
        "system": "email-provider",
        "status": "delivered",
    },
    session_id=session_id,
    turn_id=turn_id,
    actor="outcome-verifier",
)
```

Do not put access tokens, full tool parameters, raw provider responses, or
customer secrets in audit metadata.

## Privacy, retention, and deletion

- Keep `retain_query_text=False` unless your privacy review explicitly permits
  storing raw recall queries.
- AtMem's Black Box evidence path is content-minimizing, but canonical memory
  records contain the admitted memory text. Treat the database and backups as
  customer data.
- Use AtMem forget operations and retain the returned deletion receipt.
- Deleting live records does not delete independent backups, provider logs, or
  host-controlled media. Your SaaS retention job must expire those separately.
- Stop writers or use SQLite's online backup mechanism. Do not copy a live
  SQLite file casually.
- Anchor audit checkpoints outside the AtMem database if you need evidence of
  tail truncation, for example in object-lock storage or a transparency system.
- This release can open an encrypted household only when SQLCipher, encryption
  state, and keys have been separately provisioned; it does not ship the
  migration tooling that converts an existing plaintext database. Use protected
  volumes and tested key management, and never promise application-level
  encryption based only on the presence of the runtime support.

See [data storage and backup](data-storage-and-backup.md) and the
[audit log specification](audit-log-spec.md).

## Production controls your SaaS must add

AtMem does not replace these application controls:

- authentication, tenant-aware authorization, and administrator roles;
- network policy and TLS for your own service boundary;
- secrets management and model/provider credential isolation;
- rate limits, quotas, abuse controls, and cost limits;
- high availability, database placement, replication, and disaster recovery;
- customer retention policies, legal holds, data export, and backup expiry;
- independent monitoring and alert delivery;
- system-of-record verification for external outcomes.

The bundled dashboard is loopback-only and has no login. It is an operator
surface for a trusted local machine, not a hosted multi-tenant admin portal. If
customers need audit access, build an authenticated SaaS view that reads only
the tenant-authorized reports and redacts sensitive fields.

## Staged rollout

### Stage 1: development

- Use a test tenant and synthetic data.
- Integrate authenticated subject, session, and turn IDs.
- Exercise remember, bounded recall, response capture, forget, and verification.
- Confirm that no model-controlled value can select another tenant database.

### Stage 2: shadow observation

- Continue using your existing production memory as the source of truth.
- Mirror eligible changes into AtMem without injecting AtMem recall.
- Compare recall quality, latency, token cost, and deletion behavior.
- Verify backups and restore in an isolated environment.

For a custom SaaS host, you must implement this shadow path. The automatic
shadow/activate/restore commands are specific to OpenClaw.

### Stage 3: limited activation

- Enable AtMem recall for internal users or a small tenant cohort.
- Fail closed on cross-tenant identity ambiguity.
- Fail open or closed on memory unavailability according to a documented product
  policy; do not silently change the policy per request.
- Alert on incomplete turns, unmatched tools, integrity failures, latency/token
  anomalies, provider/model changes, and missing outcome receipts.

### Stage 4: production

- Expand gradually using measurable acceptance thresholds.
- Run audit-chain verification and externally anchor checkpoints on a schedule.
- Test tenant export, deletion, backup expiry, key recovery, and disaster
  recovery regularly.
- Keep a versioned host-adapter contract and run a fresh evidence flight after
  every model SDK, provider, or agent-runtime upgrade.

## Go-live checklist

- [ ] Authenticated server identity determines tenant and subject.
- [ ] Tenant storage is isolated and paths use opaque identifiers.
- [ ] Exact injected context is correlated with the model response.
- [ ] Every tool request closes with success, error, timeout, or cancellation.
- [ ] Model/provider and token/latency telemetry are recorded.
- [ ] Consequential outcomes have independent receipts.
- [ ] Raw evidence retention is explicit, encrypted where required, and bounded.
- [ ] Forget returns a receipt and backup expiry is tested.
- [ ] Audit chains are verified and checkpoints are anchored externally.
- [ ] Restore and disaster recovery are tested, not merely documented.
- [ ] Customer-facing audit access is authenticated and tenant-filtered.
- [ ] The product accurately states what evidence proves and does not prove.

## What “full AtMem coverage” means today

With OpenClaw, AtMem supplies the automated shadow migration, evidence-rich
Black Box hooks, verified activation, dashboard, and restore workflow.

With a custom SaaS agent, AtMem supplies the governed memory engine, bounded
recall, provenance, lifecycle records, deletion receipts, integrity checks, and
MCP/Python interfaces. Your host adapter must still provide authenticated
identity, actual model-context delivery proof, complete tool closure, telemetry,
and independent outcome evidence.

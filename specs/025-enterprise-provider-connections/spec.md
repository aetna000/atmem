# Feature Specification: Enterprise Provider Connections and Activation

**Product-wide requirements**: [Agent neutrality, multiple agents, private/shared memory, governed providers and clear time-aware feedback](../product-requirements.md) (PR-001–PR-006). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/025-enterprise-provider-connections`
**Created**: 2026-09-09
**Status**: Specified and planned; implementation and verification pending
**Input**: Enterprise provider connection wizard: choose provider, choose authority, authenticate, scope, test, preview, register disabled, approve when required, activate and monitor first deliveries.

## Overview

An operator connects a context provider through a resumable guided workflow, understands its identity and effective access, activates an approved configuration, and inspects evidence of its first use. Provider connections and credential health are first-class product objects, available from a top-level Connections workspace.

The initial view is simple: provider name, authority mode, owner, scope, authentication health, expiry, activation status and last observed delivery. Details reveal authentication, policy, capabilities, approvals, changes and evidence. The same workflow serves native memory, external memory and enterprise knowledge in any business or technical domain.

This specification extends [019](../019-provider-neutral-context-governance/spec.md) governance and [022](../022-unified-agent-workspace/spec.md) navigation. It defines product behavior and acceptance; it does not claim that enterprise authentication is implemented.

## User scenarios and acceptance

### US1 — Connect and activate a provider (P1)

As a connection operator, I choose a supported provider, configure its identity and scope, test it, review access and activate it without entering protocol identifiers unnecessarily.

**Independent test**: Complete the ten stages through the UI and public service with an isolated provider and authenticated operator.

1. Given an authorized operator and supported provider, when a valid draft is tested, then the result identifies the authenticated provider account and the exact draft revision tested.
2. Given an access preview and valid prerequisites, when the operator registers, then the connection is disabled and no production context is delivered.
3. Given any required approval and current checks, when an authorized activator explicitly activates, then only the reviewed revision becomes eligible for future governed use.
4. Given no subsequent agent request, when monitoring opens, then it reports awaiting first delivery and never generates production traffic merely to show success.

### US2 — Understand and approve effective access (P1)

As an access reviewer, I can see who will act, which sources and destinations are allowed, which constraints are enforced, and what remains unknown.

1. Given valid authentication but denied content policy, when access is previewed, then authentication is healthy while the relevant access decision is denied.
2. Given policy requiring independent approval, when the requester attempts to approve their own revision, then the service refuses it across every interface.
3. Given an approved revision, when scope, authority, endpoint, credential identity or governing policy changes, then its approval cannot authorize the changed configuration.
4. Given trusted delegation, when reviewing access, then the provider is identified as the exact-package content authorizer and AtMem's delegation checks are listed separately.

### US3 — Resume and operate a connection (P1)

As an operator, I resume interrupted setup, rotate authentication material and investigate delivery failures without losing the connection's identity or evidence.

1. Given a browser closure or service restart, when an authorized operator resumes, then non-secret draft progress is restored and stale prerequisites are identified.
2. Given a rotated or revoked credential, when another delivery is attempted, then current authorization and credential state govern the request; cached UI success cannot authorize it.
3. Given activation with incomplete host hooks, when first use is inspected, then the UI distinguishes returned-to-host, observed exposure and supported dispatch enforcement.
4. Given an interrupted activation request, when it is retried with the same operation identity, then the authoritative result is reconciled without duplicate activation or delivery.

### US4 — Use the appropriate depth (P2)

As a native-memory user or enterprise administrator, I get the controls relevant to my deployment and can reach deeper evidence without copying IDs.

1. Given native memory, when setup reaches authentication, then it shows the local authenticated scope and explains why external credentials are not required.
2. Given an existing delegated-v1 registration, when opened in Connections, then its exact authority, scope and historical evidence are preserved; viewing it does not activate or convert it.
3. Given an unsupported authentication method, when the provider is selected, then the limitation and supported alternatives are visible and the unsupported path cannot be activated.

## Guided workflow

These are ten logical stages. Conditional stages remain visible as satisfied or not applicable; they need not require ten separate pages.

| Stage | Operator experience | Completion evidence |
| --- | --- | --- |
| 1. Choose provider type | Select native memory, a supported external memory/knowledge connector or a registered custom connector; name the connection and owner | Provider capabilities and connection draft |
| 2. Choose authority mode | Select native, governed external or trusted delegation from supported, permitted choices; read who authorizes content | Explicit authority mode and trust basis |
| 3. Select authentication | Choose a supported account/workload authentication profile and credential source; configure package trust where applicable | Bound account/issuer and credential references, without secret disclosure |
| 4. Select scope and destination policy | Select permitted workspaces, agents, subject scope, purposes, sources and model destinations using readable names | Versioned scope and policy references |
| 5. Test authentication | Run an explicit bounded connection test and see identity, reachability and credential results separately | Timestamped test tied to the draft revision |
| 6. Preview effective access | Review allowed, denied, conditional and unknown access with governing rules and enforcement coverage | Versioned access preview with expiry |
| 7. Register disabled | Save a durable registration ready for review | Disabled registration and administrative event |
| 8. Obtain approval if required | Show required approver, reason and progress, or policy-derived approval-not-required | Decision tied to the reviewed revision |
| 9. Activate | Review the effect and explicitly activate the eligible revision | Activation decision and reconciliation state |
| 10. Monitor first deliveries | See actual attempts, policy decisions, packages, delivery evidence and useful next actions | Evidence links or an explicit waiting/missing-coverage state |

## Authority and authentication

| Authority mode | Provider responsibility | AtMem responsibility |
| --- | --- | --- |
| Native memory | Retrieve native candidates | Canonical admission, policy, packaging, delivery controls and evidence |
| Governed external retrieval | Propose context and provenance | Enterprise policy authorizes use and delivery |
| Trusted delegation | Authorize an exact package | Delegation policy, binding, expiry, replay protection and delivery evidence |

Authentication, secret custody and package trust are separate dimensions. OAuth authorization and OIDC identity, workload identity and mTLS are offered only in profiles the connector supports. A vault reference identifies where credentials are obtained; it is not itself an authentication protocol. Signed delegation establishes package authenticity and attributed authority; outbound request authentication is configured separately when required. Provider authentication is also separate from the human operator's AtMem login.

## Functional requirements

- **FR-001**: Add a top-level Connections destination within the existing application shell. Show authorized connections with readable name, provider, owner, authority mode, scope summary, authentication health/expiry, lifecycle and last observed delivery. Provide search and filters for provider, scope, owner and attention state; summaries and counts obey access rules.
- **FR-002**: Implement the ten logical stages above as a resumable workflow with stage validation, back navigation and a review summary. Persist non-secret progress under authenticated scope. Native authentication and policy-exempt approval stages show an explicit reason rather than demanding unrelated setup.
- **FR-003**: Offer only connector-supported and operator-permitted authority modes. Show the content authorizer and AtMem's checks before registration. An authentication error, policy denial or unavailable provider MUST NOT silently change authority mode or widen scope.
- **FR-004**: Support capability-declared authentication profiles for OAuth/OIDC-based integration, workload identity, mTLS and legacy request credentials, with separate vault/secret references and signed-delegation trust configuration. Each advertised combination has a tested connector/deployment profile; unsupported combinations remain unavailable. Native memory requires no external credential.
- **FR-005**: Use authenticated server-derived operator and workload identities for all mutations. Connection creation, testing, access review, approval, activation, credential rotation and disabling require explicit scoped capabilities checked by the service. Hidden UI controls do not constitute authorization; model arguments and caller-selected role headers cannot grant enterprise privileges.
- **FR-006**: Keep provider tokens, private keys and resolved vault secrets out of browser storage, public responses, logs, evidence and drafts. Store protected references and safe account metadata. OAuth callbacks bind to the initiating operator, draft and intended account; mismatched, expired or replayed callbacks fail without completing setup. Display granted account/scopes before registration.
- **FR-007**: Scope selection uses authorized named resources and versioned policies for source access, purpose, freshness, destination and review requirements. Missing required attributes remain unknown and cannot satisfy an allow rule. A broad provider credential does not broaden AtMem's delivery policy.
- **FR-008**: Tests are explicitly requested, bounded and attributable; validate endpoint/egress policy before network access, including redirects and metadata discovery. Distinguish reachability, authentication, package-trust and policy checks. Use synthetic or provider-declared non-mutating probes; do not fetch customer content or inject production context merely to test authentication. Private-network/local endpoints are allowed only by the selected deployment policy.
- **FR-009**: Effective-access preview records the configuration, credential identity, source/policy versions, evaluation time and expiry. Show allowed, denied, conditional and unknown results with reasons, sample scope/destinations and unsupported enforcement. It is a configuration evaluation, not permission for all future content; delivery re-evaluates the actual request and returned content or delegated package.
- **FR-010**: Registration creates a durable disabled revision. Approval requirements are derived from governing policy, with explicit independent-review rules where configured. Approval binds to the exact configuration and relevant policy/credential generations, identifies reviewer and reason, and has an expiry. Material changes invalidate the prior test/preview/approval as appropriate; drafts cannot override review policy.
- **FR-011**: Activation is an explicit authorized, idempotent operation that rechecks current registration, tests, preview, approval, credential validity and policy generations. Concurrent edits or stale prerequisites refuse activation with a recoverable explanation. Persist activation decisions and reconcile interrupted requests; distinguish locally active state from pending or unknown remote rollout.
- **FR-012**: Track lifecycle (draft, registered disabled, active, disabled), approval (not required, pending, approved, rejected, expired), authentication health and observed delivery independently. Activation-operation progress is separate. A healthy authentication test does not imply authorized access or enforced delivery; an active connection may still have no observed use.
- **FR-013**: Monitor actual first attempts through shared context/execution evidence: request denial, preparation, authorization, return to host, observed exposure and enforcement coverage. Link to package, policy, exact event and incident when available. No traffic means awaiting first use. Optional synthetic delivery tests require explicit selection and remain labelled synthetic.
- **FR-014**: Provide scoped re-test, rotate/reconnect, disable and revoke controls with an effect preview. Rotation preserves connection identity and prior evidence while binding future use to a new credential revision. Revocation/disable reports the affected boundary, effective time, in-flight uncertainty and propagation state; it never claims to retract already delivered context. Provider-side revocation is confirmed only with provider evidence.
- **FR-015**: Record administrative changes, tests, approvals and activation outcomes with authenticated actor, timestamp, connection/revision, changed safe fields, reason and result. Separate these events from agent-reported evidence. Shared SDK, HTTP, MCP, CLI and dashboard operations use the same authorization, revisions and idempotency semantics; an agent cannot approve its own connection by submitting evidence.
- **FR-016**: Use progressive disclosure: summary and next action first; authentication/access/health/history details next; raw IDs, fingerprints and protocol diagnostics last. Provide keyboard completion, focus restoration, text-based statuses and responsive behavior at 375px and 1280px. Preserve selected scope and context when following evidence links or returning from external authentication.
- **FR-017**: Preserve existing native and signed delegated-v1 APIs, bytes, registration identities and evidence. Adapt legacy configuration into an honest read view with unknown historical checks labelled; new wizard guarantees require new evidence. Provider navigation changes preserve legacy links. Upgrade or merely viewing a registration must not switch provider, authority, credential or activation state.
- **FR-018**: Keep the workflow usable in customer-hosted deployments without a cloud AtMem account or optional inference service. Federated identity, vault and remote authentication availability are deployment capabilities; show unavailable dependencies and withhold dependent activation. Memory-only and investigation-only adoption do not require connecting an external provider.

## Key entities and state rules

- **ConnectionDraft**: Scoped owner, connector/type/version, authority mode, endpoint, non-secret authentication configuration, credential references, scope/policy references, revision and completed-stage markers.
- **ProviderConnection**: Stable connection ID, registered revision, lifecycle, active revision, owner and legacy registration reference; extends the existing provider registration authority.
- **CredentialBinding**: Provider account/workload identity, mechanism, issuer/audience as applicable, protected credential reference, version, expiry, health and last-check time. Signing trust and request authentication remain distinguishable.
- **ConnectionTest**: Draft/revision, probe type, observed identity, policy/credential version, start/end/expiry, result and bounded diagnostic references.
- **AccessPreview**: Configuration and policy identity, evaluated scopes/destinations, allow/deny/conditional/unknown findings, capability limitations and validity deadline.
- **ConnectionApproval**: Registration revision, policy decision requiring or exempting review, reviewer identity, independence requirement, decision, reason and expiry.
- **ActivationOperation**: Scoped operation/idempotency identity, expected revision, prerequisite references, requested effect, pending/succeeded/failed/unknown status and reconciliation evidence.
- **ConnectionActivity**: Administrative and delivery evidence references, timestamps, assurance, observed enforcement boundary and explicitly missing coverage.

Tests, previews and approvals apply to specified revisions and validity windows. Time limits are explicit deployment policy with bounded defaults defined during planning. Changed security inputs require fresh applicable checks. An edit to an active connection creates a new candidate revision; existing active behavior persists until an authorized switch, disable or applicable revocation, and the UI shows both revisions. A policy or credential revocation cannot be bypassed by retaining the older revision.

## Success criteria

- **SC-001**: Under specs/usability-protocol.md, at least 9 of 10 intended operators in each of two independent cohorts complete supported connection setup through disabled registration within 10 minutes with credentials/identity infrastructure already provisioned, without CLI assistance. Report external consent/approval waiting separately; synthetic walkthroughs do not substitute for observed users.
- **SC-002**: All ten stages have passing UI and service acceptance cases, including resume after restart, native not-applicable steps, policy-exempt approval, required independent approval, duplicate activation and first-use waiting. Tests prove no production delivery before valid activation.
- **SC-003**: For each advertised authentication/connector/deployment profile, test successful authentication, wrong identity, expiry/revocation and unavailable dependencies. OAuth profiles additionally reject mismatched/replayed callbacks; mTLS and delegation profiles reject invalid trust. Publish the tested matrix and do not count unavailable profiles as passes.
- **SC-004**: Scope escalation, self-approval where prohibited, stale-preview approval, concurrent revision changes, revoked-credential activation and unsafe probe destinations produce zero unauthorized mutations, egress or delivery through every supported public interface.
- **SC-005**: Seeded secret markers are absent from browser storage, drafts, responses, diagnostics, exports and administrative evidence after success, failure, resume and rotation. Protected credential custody is verified separately from displayed references.
- **SC-006**: First-use scenarios distinguish denied retrieval, failed authentication, returned-only context, observed exposure, enforced dispatch and missing hooks. At least 9 of 10 participants in each of two independent cohorts can identify the authority mode, authentication state and delivery assurance within two minutes; no scenario equates connected with authorized or enforced.
- **SC-007**: Upgrade fixtures preserve published native/delegated behavior and exact signed bytes; legacy links reach the correct scoped connection. Keyboard and both viewport checks pass the full applicable wizard. Provider-to-policy/package/event pivots require at most two actions without copying identifiers.
- **SC-008**: Customer-hosted tests complete native setup and a supported external connection without an AtMem cloud account or inference service. Cross-domain fixtures cover memory, document retrieval and investigation-only use without implicit import, context activation or manufactured incidents.

## Dependencies, delivery and ownership

Spec 025 owns the connection journey, connection lifecycle requirements, access preview and approval experience. Spec 019 owns provider/context authority and delivery checks; 003 owns signed delegated-v1; 004 owns connector implementations. Spec 012 owns common public operations, 013 owns actual authentication and durable credential infrastructure, and 017 supplies resumable onboarding. Spec 022 retains shell ownership and integrates the Connections destination. Spec 020 supplies optional execution links and coverage; 021 supplies incidents where evidence warrants them. Spec 023 supplies extended revocation/impact and 024 optional fleet distribution and federation integration.

Basic connection setup depends on stable provider, authentication and public-service contracts, not completed fleet or incident features. First-delivery views add available 019/020 evidence incrementally. Enterprise profiles require real authenticated administration and durable authorization checks before activation can be advertised; this requirement cannot wait for optional fleet rollout.

The target navigation becomes Overview, Executions, Context, Connections, Policies, Tasks and Settings. Connections owns provider authentication, scoped access summaries and connection lifecycle. Context owns sources/packages/delivery inspection. Policies owns governing rules. Settings retains organization identity administration, general integration configuration, deployment and retention; connection pages link to those authorities. This supersedes the earlier six-section target only for the added connection workspace. A separate top-level identity-administration product is outside this feature.

## Compatibility and exclusions

No automatic migration, new mandatory provider SDK or hosted service is required for existing native users. Existing configurations remain inspectable, with explicit legacy assurance. Preserve persisted evidence through supported upgrades and define supported rollback/recovery floors during planning. Browser navigation changes do not authorize provider writes or configuration changes.

This feature excludes building an identity provider or secret vault, universal connector support, automatic external account provisioning, arbitrary provider queries during authentication tests, full fleet administration, automatic business-action recovery and domain-specific workflows. OAuth/OIDC and credential custody details require profile-specific implementation planning and boundary tests before claims of support.

## Invariant Attestation

Touches INV-001, INV-002, INV-003, INV-004, INV-005, INV-008, INV-009, INV-010, INV-011 through `spec025.authority`, `spec025.identity`, `spec025.secrets`, `spec025.activation`, `spec025.evidence` and `spec025.compatibility`. These assertion identifiers are planned acceptance work, not executing proof. No invariant or constitutional authority is changed.

## Product-wide requirements — agent neutrality and clear evidence

**Required, not yet implemented:** [Product requirements](../product-requirements.md) PR-001–PR-006. This amendment applies to this feature's public and UI boundaries; host-specific integrations cannot redefine core identity or authority.

- **FR-019**: Connection wizard scope selection and effective-access preview use the shared agent/MemorySpace/SpaceMembership authority. Show readable agent and private/shared space access separately from credential ownership and execution visibility. Monitoring and cards display authentication check time, expiry, last delivery, evidence age, reason/effect and permitted action. A page refresh never becomes a new successful check; all three authority modes retain actual enforcement coverage.
- **SC-009**: A shared connection with differently authorized agents delivers only each agent's permitted sources; preview detects member-removal revisions, private spaces and credentials remain hidden, and absent/expired/stale verification renders meaningful text and original timestamps across the full wizard.

This work extends existing authority and preserves legacy scopes. Private/shared memory and multi-framework claims require their own evidence; M0 delivers only its applicable capture/feedback subset. See the central ownership and release matrix.

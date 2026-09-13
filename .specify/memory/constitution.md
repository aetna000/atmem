# AtMem Constitution

## Core Principles

### I. Authority Before Intelligence
AtMem is the canonical memory authority. Models, embedders, AtBot, rerankers,
and external providers may extract proposals, nominate candidates, expand
queries, and rank records, but they MUST NOT admit, authorize, promote,
correct, forget, or inject memory. AtMem MUST authorize candidate content
before an intelligence component sees it and MUST revalidate every returned
record identifier before constructing context. Derived indexes are never a
source of authority.

### II. Provenance, Full-Fidelity Evidence, and Replay
Every durable memory MUST retain its source, actor, scope, timestamps,
creation method, lifecycle, and evidence linkage. Context preparation and
exposure MUST be bound to stable turn identifiers and byte-defined digests.
Evidence MUST distinguish preparation, authorization, delivery, model input,
model output, tool activity, and independently verified outcomes. AtMem MUST
not claim that an external action occurred when it can prove only that a host
reported it.

An Agent Black Box MUST retain enough authorized, human-readable evidence to
reconstruct what the user asked, what the agent received and produced, every
tool invocation, its exact arguments and target (including URLs, paths and
commands), the exact returned result or error, ordering, retries and observed
effects. The evidence model MUST natively preserve ordered multimodal parts at
every boundary: text, links and fetched pages, files, images and screenshots,
audio and video, including original bytes, MIME type, timing and source
linkage. A caption, transcript, thumbnail, metadata row or checksum MUST NOT
replace an available original artifact. Hashes authenticate retained evidence; they MUST NOT substitute for
the evidence itself. A dead or unavailable agent/host MUST NOT be required to
explain a retained run. Where the applicable tool contract and captured state
permit it, AtMem MUST produce a deterministic replay manifest and distinguish
simulation, reconstruction and a newly authorized real execution.

The AtMem evidence store is a standalone system of record, not an index into
agent logs. Given only a supported backup of that store plus AtMem, an
authorized investigator MUST be able to recover the captured memory state,
prompt, context, decisions, model exchange, tool calls, results, failures and
known outcome evidence. Agent logs, agent workspace files, provider databases,
model availability and the original runtime MUST be treated as potentially
destroyed. References to those systems may enrich a live investigation but
MUST NOT be prerequisites for the retained run story.

Full-fidelity standalone capture MUST be the default supported profile. A user
MAY explicitly select metadata-only or disable capture, but AtMem MUST record
that decision and visibly label every affected run `not_reconstructable`.
Reduced capture MUST NOT be marketed or displayed as complete Black Box
evidence. Agents and providers submit observations; AtMem owns the canonical
retained evidence envelope and its integrity, access and lifecycle history.

### III. Safe Defaults and Reversibility
New host integrations MUST begin in shadow or otherwise non-influencing mode.
Activation MUST be explicit, measurable, and fail closed. AtBot, semantic
index, network, or model failure MUST leave a safe deterministic path or
withhold context; it MUST NOT widen access. OpenClaw takeover MUST preserve a
verified route back to native memory, and interrupted activation or restore
MUST be recoverable rather than silently reported as complete.

### IV. Scoped Transparency and Verifiable Deletion
Persistent agent, workspace, subject, session, and run identifiers MUST be
treated as security boundaries, not search hints. Cross-scope reuse MUST fail
closed. Deleted, rejected, expired, quarantined, excluded, or inaccessible
records MUST not enter candidate content. Forget operations MUST cover and
verify canonical, graph, vector, and registered derived representations.

AtMem MUST preserve full-fidelity execution evidence for the owner and
explicitly authorized investigators. Authorization determines who may inspect,
export or replay evidence; it MUST NOT be implemented by irreversibly replacing
prompts, responses, tool arguments, URLs, commands, results or errors with
digests. Credentials and platform secrets that are not part of the user's
instruction MUST be stored as protected secret references or reversibly
protected fields, with access recorded. Every inspection, export, disclosure,
retention change and deletion of full-fidelity evidence MUST itself create an
append-only audit event. Product copy MUST describe the actual retained and
available evidence instead of presenting data destruction as privacy.

Every persistent evidence representation and its semantic metadata—including
indexes, audit, spool, backup, export and original or derived text, image,
audio, video, file and fetched-resource data—MUST be encrypted at rest using a
versioned quantum-resistant profile. Only an authenticated AtMem application
boundary may decrypt or emit plaintext, and only after scope and operation
authorization plus key release. Direct database or object-store inspection
MUST NOT reveal session content or semantic metadata. At least three ordered
evidence privilege levels MUST distinguish in-application viewing, investigation
and export, and evidence control. Evidence submission and cryptographic key
custody MUST NOT independently confer plaintext access. Encryption failure MUST
fail closed; it MUST NOT silently create plaintext or downgrade capture.

### V. Contract-First Host Neutrality
Core memory, authority, evidence, and lifecycle behavior MUST be expressed
through versioned host-neutral contracts. OpenClaw-specific discovery, hooks,
configuration, and restore behavior MUST remain in its adapter. Framework
adapters MUST preserve their host's conversation state, checkpointing, tools,
and model selection. Contract evolution MUST be additive when possible and
MUST include an explicit compatibility and persisted-data migration story.

### VI. Executable Claims
Customer-visible guarantees MUST be backed by tests at the boundary where the
claim is made. Changes to schemas, authorization, extraction, retrieval,
context delivery, deletion, restore, or adapter hooks require contract and
integration tests. Release claims MUST match the tested package artifacts and
supported host/framework versions. A passing hash chain proves retained data
integrity, not semantic truth or real-world outcomes.

### VII. Local-First, Explicit Egress, and Replaceable Intelligence
The base installation MUST remain useful without a hosted AI provider. Model
selection, remote endpoints, and egress MUST be explicit and inspectable.
AtBot is AtMem's replaceable intelligence companion and MUST not own canonical
memory or an independent authority database. Remote or delegated providers
MUST be registered, scoped, attributable, and unable to bypass final AtMem
contract enforcement unless a separately named delegated-authority mode makes
that boundary explicit to users and auditors.

## Product and Engineering Constraints

- Python 3.10 through 3.13 remain supported unless a separately approved
  compatibility specification changes the range.
- Canonical persistent memory remains usable when optional embedding and model
  dependencies are absent.
- SQLite schema changes require upgrade tests using previously published AtMem
  versions and real persisted state.
- Public CLI operations provide human-readable guidance and machine-readable
  output where automation is expected.
- Dashboard actions and CLI actions operate on the same authority state; the
  dashboard is never a second source of truth.
- The default install MUST avoid forcing unrelated model SDK upgrades into a
  user's shared environment.
- Apache-2.0 licensing and enterprise-safe dependency licensing are release
  requirements.

## Specification and Delivery Workflow

Material features that change public contracts, authority boundaries,
persistent state, adapter behavior, or customer-visible guarantees MUST follow:

1. `speckit.specify`: define user outcomes, scope, exclusions, acceptance
   scenarios, and compatibility requirements without prescribing code.
2. `speckit.clarify` when an authority, identity, transparency, migration, or failure
   behavior remains ambiguous.
3. `speckit.plan`: map the approved specification to architecture, contracts,
   schemas, migrations, observability, and test strategy.
4. `speckit.tasks`: create dependency-ordered, independently verifiable work.
5. `speckit.analyze`: check consistency and requirement coverage before code.
6. `speckit.implement`: implement only the approved scope, keeping tasks and
   verification evidence current.

Small documentation corrections, styling changes, dependency refreshes, and
bounded bug fixes may use a shorter workflow when they do not change a public
contract or constitutional guarantee. Current architecture, contract, status,
and release documents are product inputs. Superseded decisions remain in Git
history and MUST NOT be treated as current requirements without verification.

## Governance

This constitution governs Spec Kit artifacts and implementation decisions.
When a feature specification conflicts with it, the specification MUST be
changed or the constitution MUST be amended explicitly before implementation.
Amendments require a documented reason, compatibility impact, migration impact,
and updated tests or quality gates. Pull requests for material features MUST
identify the governing specification and demonstrate constitutional checks in
their acceptance evidence.

### Amendment 2.0 — Full-fidelity Agent Black Box

**Reason**: The original content-minimizing evidence policy could prove that a
recorded digest had not changed, but could not tell an owner what was asked,
which exact call was made, what target it used, what returned, or how to
reconstruct a run after the agent or host became unavailable. That behavior is
incompatible with the product's black-box and investigation claims.

**Compatibility impact**: Existing hash-only evidence remains verifiable but
MUST be labelled `hash_only_legacy` and `not_reconstructable`. It cannot satisfy
full-transparency, investigation-complete or replay-capable claims. New
full-fidelity envelopes and access records require additive, versioned
contracts; adapters advertise exact capture coverage per prompt, model and tool
boundary.

**Migration impact**: No migration may invent historical content from hashes.
Upgrades preserve existing rows, mark missing content explicitly and begin
full-fidelity capture only after the new capture profile is active. Retention,
export and deletion policies apply to the new evidence store and its protected
fields.

**Required gates**: Tests MUST assert exact prompt, model input/output, tool
arguments, URL/path/command, result/error, sequence and replay-manifest
round-trips; authorized disclosure and denial; access auditing; crash recovery;
legacy hash-only labelling; and verified deletion. A test that checks only a
digest, identifier or redacted summary cannot satisfy a full-transparency
claim.

One mandatory disaster gate MUST copy only the AtMem evidence store, destroy
the fixture agent process, logs, workspace and external memory/provider state,
and perform the complete investigation from the copy on a fresh process.

### Amendment 2.1 — Encrypted evidence and privileged plaintext

**Reason**: Full-fidelity evidence creates an authoritative record containing
prompts, memory, decisions, calls, results and multimodal artifacts. Filesystem
permissions or database obscurity alone cannot protect that record if storage,
backups or exports are copied. Encryption must protect transparency rather than
replace it.

**Compatibility impact**: The supported full-fidelity profile now requires a
versioned encrypted container, application-mediated plaintext and explicit
evidence privileges. Existing HMAC, Ed25519 and signed event bytes remain valid
inside the container but are not relabelled post-quantum. Unencrypted historical
stores remain readable only through an explicit migration and cannot satisfy the
encrypted-at-rest claim while a plaintext source copy exists.

**Migration impact**: Migration inventories every evidence-bearing store,
encrypts content and semantic metadata into a new generation, verifies exact
bytes and relationships, switches atomically, and offers verified cleanup of the
plaintext source. No rollback may emit a plaintext downgrade. Key loss remains
explicit and cannot be repaired by inventing content.

**Required gates**: Tests MUST scan stolen database/artifact/spool/backup/export
copies for planted text and multimodal signatures; exhaust the three-level
privilege matrix; prove authorization before decryption; exercise AES-256-GCM,
ML-KEM and ML-DSA known-answer/tamper/downgrade cases; crash every rotation and
migration checkpoint; and repeat the dead-agent reconstruction with encrypted
storage. Claims name the exact crypto module and validation status and MUST NOT
imply FIPS certification without evidence.

**Version**: 2.1.0 | **Ratified**: 2026-09-01 | **Last Amended**: 2026-09-13

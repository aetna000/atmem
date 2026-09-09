# Memory-provider integration PR strategy

Date: 2026-09-09

## Objective

Bring AtMem into other memory-provider communities through small, useful,
installable integrations. Prioritize adapters, plugins, and integration registry
entries over cookbooks. Give users a concrete benefit while keeping upstream
review and maintenance costs low.

Positioning: keep the existing provider as the memory backend, and use AtMem for
verifiable delegated context delivery. Observed delivery does not prove that the
model used or followed the memory.

## Ranked targets

These rankings assess architectural and contribution fit, not guaranteed
maintainer acceptance. Proposed connectors are not implemented or validated by
this research. Recheck repository structure and contribution rules before work.

| Priority | Provider | Proposed small PR | Fit and references |
| --- | --- | --- | --- |
| 1 | Cognee | Optional connector mapping Cognee search results into AtMem delegated context, preserving source references. | A community repository explicitly hosts adapters/plugins, and the integration inventory lists externally maintained packages. [Community plugins](https://github.com/topoteretes/cognee-community), [community integrations](https://github.com/topoteretes/cognee-integrations#community-integrations). |
| 2 | Hindsight | A proposed `hindsight-atmem` integration retrieving from a configured memory bank and passing results through AtMem's existing delivery runtime. | Dedicated integration directories, independently packaged connectors, and an explicit new-integration process. [Integration structure](https://github.com/vectorize-io/hindsight/blob/main/hindsight-integrations/README.md). |
| 3 | Basic Memory | Connector supplying project-scoped notes as delegated context, retaining document references. | Existing agent integrations include OpenClaw and Hermes; maintainers still need to agree on the additional integration. [Repository and integrations](https://github.com/basicmachines-co/basic-memory). |
| 4 | Graphiti | Optional bridge mapping graph search results and identifiers into AtMem context items. | An MCP server exists, but the appropriate upstream home for this connector is less obvious. [MCP server](https://github.com/getzep/graphiti/blob/main/mcp_server/README.md). |

## Recommended first contribution: Cognee

Build and verify the connector in AtMem's repository, then propose a small PR
registering it in Cognee's community integration inventory. The inventory already
supports externally maintained integrations. This gives users an installable
integration without transferring adapter maintenance to Cognee.

If executable code must live upstream, target Cognee's community plugin repository
instead. Its package structure calls for installation instructions, an example,
and tests. Confirm the appropriate package category with maintainers.

Proposed PR title:

> Add optional Cognee → AtMem context-delivery integration

Proposed pitch:

> Keep Cognee as your memory backend and add verifiable context delivery through
> AtMem. The connector preserves retrieval references and lets supported hosts
> record what reached model input.

## Keep the implementation narrow

- Support one retrieval operation with explicit provider scope.
- Convert results into AtMem context items with source references.
- Reuse AtMem's authentication and delivery runtime.
- Keep dependencies optional and avoid provider core changes.
- Test matching results, empty results, scope isolation, and provider failure.
- Verify delivery through an actual supported host before claiming end-to-end
  delivery evidence; adapter tests alone do not establish that boundary.
- Document exact tested versions, installation, explicit enablement, and removal.

The upstream diff can be small because shared machinery remains in AtMem.
End-to-end verification still needs to be thorough. A provider's bank or project
identifier must not be assumed to establish user/agent authorization without
checking its actual semantics.

## Execution order

1. Inspect Cognee's current contribution rules and integration inventory schema.
2. Confirm the narrow contribution scope with maintainers where required.
3. Implement and verify an isolated connector, preserving the AtMem 2.2.6 release
   branch and existing work.
4. Submit the integration registration or community plugin PR with accurate
   validation evidence and maintenance ownership.
5. Address review before expanding to Hindsight, then Basic Memory and Graphiti.

This document records a proposal, not authorization to publish messages or PRs
to all listed projects.

## Existing Mem0 effort

The earlier Mem0 cookbook proposal is open at
[mem0ai/mem0#7273](https://github.com/mem0ai/mem0/issues/7273).
At the last check in this session, it was awaiting maintainer agreement and did
not carry an `accepted` label. No Mem0 cookbook PR had been created.
The adapter/plugin strategy above is the preferred direction for subsequent
provider contributions; it does not change the submitted Mem0 proposal.

# Coding-agent memory and code-graph market review

**Research date:** 2026-10-14. Public product documentation and project-maintained benchmark reports are evidence of product design and author-reported results, not independent verification. Product versions and integration surfaces may change before implementation.

## The market has two different memory jobs

**Experience memory** carries decisions, preferences, failed approaches, verified commands and task outcomes between sessions. It can be gathered by hooks, but useful facts must be selected and corrected over time.

**Repository intelligence** indexes the current code structure: files, symbols, imports, calls, routes and relationships. It can return a short map or relevant source slices instead of requiring repeated broad file reads. This is often called graph memory, although the index is derived from source code and must be refreshed when the code changes.

AtMem Code needs both surfaces because remembered project decisions do not answer current symbol relationships, while a code graph does not remember why a team chose an approach or what failed in a prior session.

## Coding-agent integration surfaces

| Target | Documented extension surface | AtMem Code qualification question |
| --- | --- | --- |
| [Muse Code](https://meta-models.github.io/muse-code-sdk/next/guides/extend/) | Hooks, MCP servers and plugins; [hook event reference](https://meta-models.github.io/muse-code-sdk/next/guides/plugins/reference/hook-events/) | Which event can admit a bounded context pack, and what acknowledgement does that event provide? |
| [Claude Code](https://code.claude.com/docs/en/hooks) | Lifecycle hooks and MCP | Verify automatic capture, new-session context submission and delivered-context assurance on each supported version. |
| [Grok CLI](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md) | Session, prompt, tool and stop hooks; [MCP servers](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/07-mcp-servers.md) | Verify that the selected hook can supply context rather than only observe or block. |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/hooks-reference) | CLI hooks and [plugin/MCP configuration](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) | Probe the CLI separately from Copilot in an editor or GitHub's cloud coding agent; do not transfer a CLI result to those surfaces. |
| [Codex](https://developers.openai.com/plugins/concepts/plugins) | Plugin lifecycle hooks and MCP | Verify locally trusted hook installation, capture events and the actual context-submission boundary. |

These documents establish possible extension points, not an implemented AtMem integration or proof of model-input delivery. Each named host needs an installed-version capability matrix and a real session probe before it receives an “automatic” label.

| Product or approach | Primary surface | Automatic session capture and recall | Structural graph | Sharing and limits relevant to AtMem Code |
| --- | --- | --- | --- | --- |
| [Claude Code auto memory](https://code.claude.com/docs/en/memory) | Local per-repository Markdown notes | Claude selects notes while working; a bounded index loads at new-session start | No claimed code graph | Strong built-in baseline for Claude. Files are local and shared across worktrees, not automatically across machines or agent brands. |
| [Mem0 Code](https://docs.mem0.ai/integrations/claude-code) | Cloud-extracted project and personal memories | Hooks capture exchanges and short tool outcomes; worker flushes to Mem0; first prompt searches and injects up to five memories | No structural code graph claimed on the integration page | Strong automatic Claude plugin baseline. Requires Mem0 Platform API key; later turns may need explicit search. |
| [Claude-Mem](https://docs.claude-mem.ai/introduction) | Local observation history, summaries and searchable context | Documents automatic tool observation capture and context in later sessions | No structural code graph established by introduction | Supports several coding clients, but each host's advertised automatic coverage needs a direct probe. |
| [Graphiti](https://github.com/getzep/graphiti) | Temporal entity/relation graph from episodes | MCP/API ingestion depends on a host sending episodes | Entity graph rather than a parser-derived code graph | Useful model for time-valid relations and contradictions; graph extraction can add model and graph-database dependencies. |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Local parser-derived repository graph | Code index refresh and MCP queries; not a full coding-session memory workflow | Yes: symbols, imports, calls, routes and graph traversal | Strong graph-search baseline. Its author reports 10x fewer tokens and 2.1x fewer tool calls over 31 repositories, with 83% versus 92% answer quality for file exploration. The separate 120x figure is a five-query demonstration, not total task savings. |
| [MEX](https://github.com/mex-memory/mex) | Git-shared project wiki plus code graph | Project memory and graph are shared through Git; host integration varies | Yes, with token-bounded source and flow retrieval | Strong combined baseline. Its [0.7.2 release](https://github.com/mex-memory/mex/releases) reports a 12-task, one-run pilot with 54.5% fewer new tokens and 7/12 versus 6/12 blind-correct answers. It explicitly describes that result as a small pilot. |
| [Aider repo map](https://aider.chat/2023/10/22/repomap.html) | Token-bounded symbol map derived from Tree-sitter | No persistent cross-session learning implied | Relationship-aware file/symbol map | Essential lightweight baseline: structural context does not require a full graph service. |

## What the graph actually saves

A parser-derived graph can return, for example, the definition of `authorize_context`, its callers, and the few relevant imports. The agent then opens those source slices and verifies them. The savings come from reading fewer irrelevant files and repeating fewer broad searches. The graph itself consumes indexing resources, can miss dynamic calls, and may be stale after a branch switch or edit.

The [Codebase-Memory project](https://github.com/DeusData/codebase-memory-mcp) cites a 31-repository study with materially lower token use but lower answer quality than file exploration (83% vs 92%). That quality tradeoff is a central warning for AtMem Code: a compressed graph must be allowed to nominate sources, not replace source verification when exact code behavior matters. MEX's task-level pilot reports lower token use and a small quality gain, but 12 tasks and one run are insufficient for a general superiority claim. The [Aider map](https://aider.chat/2023/10/22/repomap.html) shows that a small ranked symbol map is a serious alternative to graph traversal.

## Positioning hypothesis to test

AtMem Code could combine automatic cross-agent experience memory, local source-linked code context, exact delivery receipts, per-scope deletion and optional provider routing in one installation. This is a hypothesis about product value, not a measured advantage. It must beat or at least justify its added complexity against the host's built-in memory, Mem0 Code for session continuity, Aider-style repo maps for lightweight structure, and codebase-memory-mcp/MEX for graph retrieval.

The smallest credible comparison is paired real repository tasks with fixed agent and model versions. Include five arms: native agent behavior, AtMem Code experience memory, a strong structural map/graph control, AtMem Code graph, and combined AtMem Code. Measure final task correctness and full agent tokens/cost/latency, not just the size of a single search result. Record missed files, stale conclusions, index freshness and overhead.

[VibeMemBench](https://arxiv.org/abs/2609.23570) is the primary fit for experience-memory evaluation: it uses 111 executable coding targets from 90 SWE-rebench V2 repositories and 3,634 prior trajectories. Its authors selected targets where a verified prior experience helped a reference setting. That is useful for measuring whether AtMem can construct and retrieve relevant memory, but it is not an unbiased estimate of benefit on arbitrary coding tasks. A separately frozen unfiltered real-issue sample must test ordinary-work benefit, irrelevant-memory overhead and harm. A direct verified-experience injection is an oracle control, not an AtMem result.

## Product implications

- Make automatic capture and injection verifiable. Merely registering MCP tools does not make memory automatic.
- Keep experience memory, current code structure and external-provider results visibly distinct in storage and dashboard.
- Start with a small bounded retrieval pack; allow an agent to expand to exact cited source lines.
- Treat code graph as an optional local derived index with a strong non-graph fallback.
- Fix pre-write secret screening before broad automatic capture; repository work routinely includes credentials.
- Use one stable project identity across Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI and Codex, while keeping user and agent-private lanes separate.
- Avoid claims such as “90% fewer tokens” until a paired task-level benchmark demonstrates them on the released artifact.

## Primary sources

- Anthropic, [Claude Code memory](https://code.claude.com/docs/en/memory).
- Anthropic, [Claude Code hooks](https://code.claude.com/docs/en/hooks).
- Meta, [Muse Code extension guide](https://meta-models.github.io/muse-code-sdk/next/guides/extend/) and [hook event reference](https://meta-models.github.io/muse-code-sdk/next/guides/plugins/reference/hook-events/).
- xAI, [Grok CLI hooks](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md) and [MCP guide](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/07-mcp-servers.md).
- GitHub, [Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference) and [Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference).
- OpenAI, [Codex plugin architecture](https://developers.openai.com/plugins/concepts/plugins).
- Mem0, [Claude Code integration](https://docs.mem0.ai/integrations/claude-code).
- Claude-Mem, [Introduction](https://docs.claude-mem.ai/introduction).
- GetZep, [Graphiti repository](https://github.com/getzep/graphiti) and [MCP server](https://github.com/getzep/graphiti/blob/main/mcp_server/README.md).
- DeusData, [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) and [Codebase-Memory preprint](https://arxiv.org/abs/2603.27277).
- MEX, [repository](https://github.com/mex-memory/mex) and [release benchmark disclosure](https://github.com/mex-memory/mex/releases).
- Aider, [repository map design](https://aider.chat/2023/10/22/repomap.html).
- Fan et al., [VibeMemBench: Evaluating Memory Systems for Coding Agents on Real Repository Coding Tasks](https://arxiv.org/abs/2609.23570).

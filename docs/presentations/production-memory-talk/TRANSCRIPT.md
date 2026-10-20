# AtMem: Governed Agent Memory — talk transcript

Speaker script for the slides in `slides/`. Open `index.html` to present; press **N** to show these notes beside each slide.

## Introduction and agenda

### 1. Paving the road to production for agent memory

Hello everyone. Today I want to walk you through how we take AI agents with memory out of the experiment stage and into a real enterprise environment.

Most talks about agent memory focus on recall: can the agent remember what you told it last week? That matters, but it isn’t what blocks production. What blocks production is control. Who decided this fact should be remembered? What context did the model actually see on this turn? Can we prove it afterwards? Can we undo it?

AtMem is my answer to those questions. It is a host-neutral Agent Black Box and a reversible memory control plane. In the next thirty minutes I won’t show you a magical agent. I’ll show you the frameworks and guardrails that sit underneath any agent, so its memory can be trusted.

### 2. Javad Taghia

Before I begin, a quick introduction. My name is Javad Taghia. I created and maintain AtMem, an open project for governing what AI agents remember and proving what they actually saw. I’m the founder of AtMem, and I spend my time on the unglamorous parts of agents: authority, evidence and the way back. You can find the code on GitHub under aetna000, AtMem on X at atmemai, and me at javad@atmem.ai. I’m happy to take questions there after the talk.

### 3. What we will cover

Here’s the agenda.

First, the challenges: why agents with memory tend to fail once they reach production, and which controls are usually missing.

Then the AtMem control plane at a glance, and the architecture behind it. After that, the rollout path: how you go from a laptop install to a production deployment without a big-bang switch.

Next, the runtime contract every agent turn follows, and why AtMem exposes two very different MCP surfaces, one for agents and one for operators.

Then two ideas that shape everything: shadow mode versus active mode, and the boundary between AtBot, which proposes, and AtMem, which decides.

We’ll look at the framework adapters for OpenClaw, Pydantic AI and LangGraph, then at the Agent Black Box, governed task state, privacy and restore.

Finally, how we measure memory quality honestly, and the key takeaways.

## Why agent memory fails in production, and the controls that fix it

### 4. Agent memory fails in production when its controls are missing

Let me start with the challenge. Plenty of agents work in a demo and fail in production, and memory is one of the most common reasons. Usually it isn’t because recall is weak. It’s because the foundational controls are missing.

First, authority. In many stacks, whatever the model extracts becomes a stored “fact”, so a hallucination or a prompt injection turns into permanent memory.

Second, evidence. When something goes wrong, can you show exactly what context was injected into the model on that turn? Most teams can’t.

Third, isolation. Memory needs to be scoped to the exact user, agent and workspace. Without that, one tenant’s facts end up in another tenant’s context.

Fourth, reversibility. Once you replace an agent’s native memory with a new system, there is often no tested way back.

Fifth, privacy. Raw prompts, tool results and sometimes secrets end up in plain logs, traces and vector databases.

And sixth, proof of quality. “It seems to remember things” is not something you can gate a release on.

So I’m not going to build a cleverer agent today. I’ll show you the control plane that answers each of these.

### 5. Each gap gets one control, and one command that shows it

So how do we address these gaps? Rather than one big framework, AtMem puts one control on each gap, and every control has a command you can run to see it working.

For authority: AtBot, the intelligence companion, can propose and rank memories, but only AtMem authorizes, scopes, injects, corrects or deletes them. You see that in the memory review queue.

For evidence: the Agent Black Box keeps a hash-chained flight timeline for every run, and you can verify it.

For isolation: every record and every injection is bound to an exact agent, workspace and subject scope.

For reversibility: every integration starts in shadow mode, and there’s a journaled restore you can rehearse with a drill before you ever need it.

For privacy: exact evidence lives in an encrypted vault, plaintext export is role-gated, and the store itself can be SQLCipher-encrypted.

And for quality: there’s an offline benchmark gate with twenty-four cases, where safety has to be perfect.

The rest of the talk walks through how these pieces fit together.

## Architecture and the rollout path from laptop to production

### 6. One control plane for every agent

Now let’s look at the architecture.

On the left are the agent runtimes: OpenClaw, Pydantic AI, LangGraph, or your own custom agent or SaaS worker. AtMem doesn’t replace any of them. Each connects through an adapter, or through the generic host MCP, which does only five things: capture memory candidates, prepare context before a model call, confirm what was actually exposed, record model and tool events, and bind outcome receipts.

In the middle is the AtMem control plane. The policy layer decides whether AtMem is in shadow or active mode, so it gates every single injection. The memory authority admits, scopes, corrects and deletes records. The Agent Black Box keeps a hash-chained flight log. And retrieval does hybrid ranking and bounded recall.

Below the adapters is AtBot, AtMem’s intelligence companion. Notice the dashed line: AtBot sends proposals in, but it never writes memory directly.

On the right is the storage and operator side: a canonical memory database, SQLite or SQLCipher-encrypted; an encrypted evidence vault for original content; an always-present local vector index; and the operator surfaces, meaning the CLI, the operator MCP and the dashboard. All of them call the same manager operations, so the dashboard is a view over the same state, not a second source of truth.

### 7. From laptop to production in six reviewed steps

Let’s talk about the path from local development to production, because this is where most memory projects go wrong. They switch everything on at once. Step one, install. It’s a single Python package; the AtBot companion and a dependency-free local vector index come with it. Don’t install AtBot separately. Step two, choose memory intelligence with “atmem atbot setup”: a local Ollama model, a local OpenAI-compatible server, a hosted provider, or the safe deterministic fallback. API keys stay in environment variables; AtMem doesn’t save them. Step three, “atmem init” creates local sign-in accounts and the portable AtMem Home that holds config, identity, memory and evidence. Step four, connect your agent. For OpenClaw, “atmem openclaw install” does it all: it installs the matching bridge, discovers agents and workspaces, and starts in shadow mode. For any other host, run “atmem control shadow”. Step five, review. In shadow mode AtMem learns and shows you what it would have retrieved, but it can’t change model context. You review that in the dashboard. Step six, and only after review, you explicitly activate, then run “atmem control verify”. And at every point there’s a way back: “atmem control restore” returns the host to its native memory through a journaled, verified procedure.

## The per-turn runtime contract, MCP surfaces, modes and the AtBot boundary

### 8. The per-turn contract every agent follows

Now let’s look at what actually happens on every agent turn. This is the contract any runtime follows, whether it’s OpenClaw with automatic hooks or your own agent calling the control MCP directly.

Before anything else, the runtime assigns stable agent, workspace, session, run and turn identifiers. Everything after this is scoped to them.

Step one: capture. The runtime sends authenticated user memory candidates to AtMem’s host MCP. These are candidates, not facts.

Step two: before the model request, the runtime calls control_prepare.

Step three: AtMem’s memory authority does scoped recall and applies policy. Are we in shadow or active mode? Is this record in scope for this subject?

Step four, highlighted in orange, is the critical rule. AtMem returns the context plus an inject flag, and the runtime injects that context only when inject is exactly true. In shadow mode it is never true.

Step five: after building the model request, the runtime confirms the exact exposure, so we have proof of what the model was shown, not just what we intended to show.

Step six: it records model input and output, every tool request and completion, and the end of the turn into the Black Box.

And step seven: when an independent system can prove a real-world result, say a ticket was actually created, that outcome receipt is bound into the hash chain.

### 9. Two MCP surfaces, two trust levels

A key design decision in AtMem is that there isn’t one MCP server, there are two, with very different trust levels. This is the same idea as putting a gateway in front of your tools: the agent should never hold the keys to its own governance.

On the left is the host control MCP, started with “atmem control mcp”. This is what agents talk to. It’s deliberately non-administrative. It can capture memory candidates, prepare context before a model call, confirm the exact context exposure, record flight events, and report adapter sync and status. That’s all. An agent can’t approve its own memories, acknowledge its own findings or switch AtMem into active mode.

On the right is the operator MCP, started with “atmem control operator-mcp”. That one can approve or reject memory, acknowledge findings, configure agent scopes, export evidence, and activate AtMem or return it to shadow. It’s meant for a trusted local operator client, a human, and you should never expose it to an agent or an untrusted network.

The dashboard follows the same principle: it binds only to loopback, requires a local AtMem account, uses HttpOnly sessions, and checks origin and CSRF on every mutation. Don’t put it behind a public reverse proxy.

### 10. Shadow first, active only on evidence

This brings us to the most important operational idea in AtMem: shadow mode and active mode.

Every integration starts in shadow mode. In shadow, the host stays the memory provider. AtMem copies and mirrors the native memory, including history from before AtMem was installed, records source paths, line ranges and digests, then verifies, indexes and audits it. It shows you what it would have retrieved, but it never injects anything into model context. So you can run it next to a production agent and compare, with zero influence on behaviour.

When you’re satisfied, an operator runs “atmem control activate”. Now AtMem is the memory provider. Native supplemental memory is frozen and its paths are protected, and the host uses AtMem’s governed search, get and capture with bounded recall. Every injection is proven in the Black Box.

Activation itself is careful. It runs a final sync, checks the loaded plugin and required tools, and only switches if every check passes. If activation is interrupted, that’s detected and must be recovered or restored. It’s never silently treated as complete.

And “atmem control restore” takes you back. I’ll come back to how restore works in a few slides.

### 11. AtBot proposes. AtMem decides.

If you remember one sentence from this talk, make it this one: AtBot proposes, AtMem decides.

AtBot is AtMem’s private intelligence companion. It’s installed automatically and pinned to the exact AtMem version. It can use a local Ollama model, a local OpenAI-compatible server, a hosted provider, or a deterministic fallback with no model at all.

AtBot’s job is to propose: extract a memory candidate, rank what might be relevant, or suggest a change to a task. But a proposal is just a proposal. AtMem revalidates every one of them against scope, policy and provenance, then either commits it with a receipt or withholds it.

That separation matters for two reasons. First, security. A prompt injection that fools the model still can’t write memory or widen scope, because the model never holds that authority. Second, availability. If AtBot or its model is down, AtMem keeps going with safe local capture and hybrid ranking. Memory authority and agent operation never depend on a hosted model.

AtBot isn’t an independent agent and it isn’t a second memory authority. It’s a headless component managed by AtMem.

## Framework adapters and the Agent Black Box

### 12. Native adapters for your framework

Let’s talk about the agent frameworks. AtMem isn’t a framework, it governs the one you already use.

For OpenClaw the integration is fully managed. “atmem openclaw install” installs the matching npm bridge, discovers agents and workspaces, installs the hooks, starts in shadow mode, restarts the gateway and verifies the connection. If you were already on AtMem 2.1, “atmem openclaw upgrade” is idempotent and upgrades in place.

For Pydantic AI there’s a native capability. You build an identity with agent, workspace and subject IDs from the control plane’s agent topology, wrap it in the AtMem adapter, and pass the capability to your Agent. A task ID can come through run dependencies.

For LangChain and LangGraph there’s native middleware. Same identity, and you pass the middleware into create_agent. The task ID comes through configurable, and there’s guidance for async, multi-agent and low-level StateGraph integrations.

In every case the hooks automate authenticated capture, governed retrieval, context injection, exposure proof and turn and tool evidence. They don’t replace your model, your tools, your conversation history or your LangGraph checkpoints. Anything else, a custom agent or a SaaS worker, uses the generic control MCP contract we saw earlier.

### 13. What did the host actually observe?

Now the tracking side. The Agent Black Box answers one narrow operational question: what did the host observe the agent and its tools doing during this run?

The table shows the flight events a runtime can emit. turn.input when a turn starts. model.input with prompt, system and history digests plus provider and model. context.disposition, which is the one I care about most: was memory injected, empty, withheld or failed, with the exact placement envelope digest and the candidate IDs that were considered. Then tool.requested and tool.completed for every tool call, model.output with token usage, and turn.ended with success or cancel and a reason.

This table is the content-minimising projection: digests, counts and names. When full-fidelity capture is configured, the exact prompts, context, model exchanges, tool arguments and results, and supported multimodal originals are kept separately in an encrypted evidence vault.

On the right: the timeline is appended to the control evidence store and protected by a hash chain scoped by migration and kind, so you can’t quietly delete or reorder an event.

One honest caveat: digests are fingerprints, not encryption or anonymisation. A low-entropy value can be guessed and compared, so treat the evidence database and exports as sensitive records.

### 14. Investigating a flight, step by step

Let me walk you through how an investigation looks in practice.

Say someone reports that the agent did something odd yesterday. Step one, find the run: “atmem blackbox runs” lists recent flights. Step two, “atmem blackbox story” with the run ID tells that run as a readable story: what came in, what memory was considered and injected, which tools were called, and how the turn ended.

Step three, “atmem blackbox verify” proves the hash chain for that run is intact, so you know you’re looking at what was recorded and not something edited later.

Step four, if a security or compliance reviewer needs the evidence, “atmem blackbox export” writes it as JSON or text.

And step five, once you’ve dealt with a finding, “atmem blackbox ack” with its attention code acknowledges it.

The dashboard shows the same thing visually. It opens with a concise action timeline. A flight node is green when no active finding remains, amber when it needs review, and red when the run failed or its evidence is incomplete. Select a node and you see the request and reply where a protected local reader can supply them, the memory used, tools and websites, model and provider, tokens, latency, risks, any blocking reason, outcome evidence and hashes.

Most importantly, acknowledging a finding never deletes or rewrites evidence. The record stays.

## Governed tasks, privacy, reversibility and measured quality

### 15. Governing work in progress, not just memory

Memory is about what an agent knows. But production agents also need governance over what they are doing right now. That’s Governed Task State.

It’s a separate, revisioned authority plane for the current task: what the agent is working on, what remains, what’s blocked, and whether completion is allowed. Think of it as the planning and approval part of an agent workflow, but with an audit trail.

The lifecycle is simple. First, enable it for one exact scope; it’s disabled by default. Second, start a task with a goal and required items, for example “run release verification”. Third, as the agent works, items and blockers change, and every change is a new revision with a recorded decision. Fourth, the task can complete only when completion is allowed.

Three properties matter. First, temporary task progress never turns into long-term personal memory; they’re separate planes. Second, AtMem needs an exact task identity. Pydantic AI passes it in run dependencies, LangGraph through configurable, and OpenClaw through the owner-authorised conversation binding. AtMem never guesses from prompt text or chooses among open tasks. Third, same rule as before: AtBot may propose a task change, but AtMem revalidates and commits it.

The dashboard’s governed tasks card shows progress, blockers, recent decisions, the current revision and guarded lifecycle actions.

### 16. Privacy by construction: who sees what

Next is privacy. When agents work with real users, sensitive data will show up in prompts, uploaded documents and tool results. So the question isn’t whether sensitive data exists, it’s who can see it and where it can travel.

AtMem answers this with roles. A Viewer sees only metadata and hashes, never content. An Investigator can view and play retained evidence, but only inside AtMem. Evidence Collectors and Administrators can additionally export plaintext. You create these with “atmem users create” and check the vault with “atmem evidence status”.

On the right are three storage guarantees. Exact evidence is kept in a protected, encrypted vault. If you turn data capture off, that capture is explicitly not reconstructable, and turning the recorder off captures no new evidence at all.

For data at rest, AtMem supports SQLCipher-encrypted households. Migration validates SQLite integrity, SQLCipher page integrity and per-table row counts before an atomic cutover, and you stop every writer first.

And provider API keys stay in environment variables; AtMem never writes them to disk.

To be clear about the limits: AtMem doesn’t claim to automatically detect and redact every secret in free text. It limits who can see content, keeps the default projection to digests and counts, and encrypts the exact record. If you need pattern-based redaction before the model call, add it in your runtime ahead of the capture hook.

### 17. Reversible by design: a journaled restore

Earlier I promised to come back to restore. Reversibility is what makes it safe to try AtMem on a production agent at all.

Restore is a careful, multi-step procedure, not a file copy. First, it validates and stages the frozen snapshot without touching any live files. Then it works through a durable step journal, so if it’s interrupted it resumes exactly where it stopped. If it finds native files that changed unexpectedly, it keeps them as evidence rather than overwriting them. It proves the restored baseline. Anything the agent learned while AtMem was active is exported as a separate additions block, so nothing is silently lost. Then it restores and re-reads the saved configuration, restarts the host, for example the OpenClaw gateway, and verifies it. Finally, a success receipt is bound into the memory audit chain as control.restored.

On the right is something I like a lot: the restore drill. You can rehearse a restore without changing anything live, and the drill makes exactly three claims: file restoration was tested, saved configuration was readable, and live rollback was not performed. It doesn’t claim more than it proved.

And honestly: restore brings back memory and configuration. It can’t undo responses the agent already gave or logs a provider already kept. Control-plane evidence is intentionally preserved.

### 18. Proving memory quality before release

Now evaluation. Earlier I said “it seems to remember” is not a release gate. So what is?

First, an offline release gate. “atmem benchmark run” executes twenty-four isolated cases covering extraction, contradiction, recall, withholding, prompt injection, privacy, memory poisoning and fallback behaviour. The rule is strict: safety has to be perfect, and every other quality metric must stay at or above its checked-in baseline. If a change makes memory more helpful but less safe, the gate fails.

Second, external comparison, done carefully. These benchmarks test whether an agent can use remembered experience to answer a question or complete a task, not just whether search results look relevant. On a 23-question sample of LongMemEval-V2, AtMem answered 5, Mem0 OSS 1 and AgentRunbook-R 4. On a 30-task sample of DolphinBench, where a task passes only when every required check passes, AtMem passed 9 and Mem0 7. On DolphinBench’s individual checks it was 32 of 97 against 27 of 97.

I want to be honest about what these numbers are. They’re frozen, roughly five percent development samples, not full official or leaderboard scores. The arms used matched tasks and the same reader and judge routes, and every attempted case, including system failures, stayed in the denominator. The Mem0 Dolphin environment lacked two optional extras. And absolute accuracy is still low for everyone. The point isn’t a victory lap; it’s that we measure, publish the protocol, and keep the caveats attached.

## Key takeaways and getting started

### 19. Build the control plane, not just the agent

So, the key takeaways.

One: build the framework underneath, not just the agent. Don’t rush an agent with memory into production and discover later that you needed authority, evidence and a way back. Put those in place first.

Two: have exactly one memory authority. Models, including AtBot, can propose. Only the control plane decides what is stored, scoped, injected, corrected or deleted.

Three: start in shadow mode, activate only on evidence you’ve reviewed, and keep restore one command away, rehearsed with a drill.

Four: every turn should leave a verifiable flight record: what memory was considered, what was injected, what the model saw, which tools ran, and how it ended, all hash-chained.

Five: keep the agent-facing surface and the operator surface strictly apart. An agent should never be able to approve its own memory or switch its own governance on or off.

And six: gate releases on measured quality, with safety required to be perfect, and report the numbers honestly, caveats included.

### 20. Try it on your own agent today

If you’d like to try this yourself, it takes a few minutes. Install the package with “python -m pip install --upgrade atmem”. Using python -m pip matters, because it upgrades the same Python environment that “python” points to. Then run “atmem atbot setup” to choose memory intelligence, and “atmem init” to create your local accounts and Home. If you use OpenClaw, “atmem openclaw install” does the rest and starts in shadow mode. For any other runtime, start a generic control plane with “atmem control shadow --host generic” and connect through the adapters or the control MCP. Then open the dashboard and watch what AtMem would have done before you let it do anything. Check the release notes in the repository for the current version and its limitations before upgrading a production agent. The code and documentation are at github.com/aetna000/atmem. If you have questions, reach us on GitHub at aetna000, on X at atmemai, or email me at javad@atmem.ai. I’m happy to help. Thank you very much for listening.

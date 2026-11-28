# Use portable agent runs from this branch

Branch `058-portable-agent-runs` is based on AtMem 2.3.16b3. Install this checkout in the Python environment that will serve the tools.

```sh
python -m pip install -e '.[encrypted,team-mcp]'
atmem dashboard
```

The sign-in screen includes **Preview a recorded agent handoff**, a snapshot of the synthetic correction. Sign in and open **Sessions → Agent handoffs → Recorded examples** for the interactive trace. To run locally, sign in, activate your native workspace, install the pinned local model with `ollama pull qwen2.5:1.5b`, and choose **Run locally**. Full encrypted evidence capture saves the result under **Project runs**. Choose the routing policy explicitly to turn on review.

## Bind two hosts

Use the workspace ID and registered agent IDs from the dashboard's topology. The following example assumes existing agents named `dispatcher` and `reviewer` in the same workspace, a private directory for the bindings, and a dashboard listening on port 8768. Replace `WORKSPACE_ID` and the endpoint with your values. The grant command prompts for a local authorized account password and writes a new owner-only file. Use `--state` to select a non-default control state.

```sh
mkdir -p -m 700 "$HOME/.config/atmem-team"
python -m atmem.agent_team grant --username administrator --endpoint http://127.0.0.1:8768 \
  --workspace WORKSPACE_ID --host openclaw --agent dispatcher --binding "$HOME/.config/atmem-team/openclaw.json"
python -m atmem.agent_team grant --username administrator --endpoint http://127.0.0.1:8768 \
  --workspace WORKSPACE_ID --host hermes --agent reviewer --binding "$HOME/.config/atmem-team/hermes.json"
```

In OpenClaw, add a server under `mcp.servers`. In Hermes, add it under `mcp_servers`. Set the absolute Python interpreter and binding paths on that host. For Hermes use `hermes` and its own binding file in the arguments.

```json
{
  "atmem_team": {
    "command": "/absolute/python/environment/bin/python",
    "args": ["-m","atmem.agent_team","serve","--host","openclaw","--binding","/absolute/private/openclaw.json"]
  }
}
```

The sender calls `team_review(question)`, selects an exact quote, and calls `team_offer` with `question`, `recipient="team:hermes:reviewer"`, and a stable `request_id`. To bind the review, include a `review` object with the returned `generation`, `evidence_sha256`, the selected `quote`, and actual usage if available. The receiver calls `team_inbox()`, then `team_receive(run_id)`, and finally `team_complete(run_id, delivery_id, quote, usage)`. Pass an empty quote to abstain. To rerun after a correction, pass the original ID as `rerun_of` and a new request ID. To reconcile a priced reader, also supply its exact `reader_model` and a `reader_pricing` object with decimal-string `input_usd_per_million` and `output_usd_per_million` rates. The receiver reports its model name, measured tokens and observed `cost_microusd` when available.

## Other hosts

| Host | Configuration |
| --- | --- |
| Other MCP client | Use the same stdio command with `--host mcp` and its workspace grant. |
| Pydantic AI | Install `.[pydantic-ai]`. Pass `pydantic_tools(binding_path)` from `atmem.agent_team.client` to `Agent(..., tools=...)`. Provision with `--host pydantic-ai`. |
| LangGraph | Install `.[langgraph]`. Pass `langgraph_tools(binding_path)` from the same module to a `ToolNode`. Provision with `--host langgraph`. |
| ChatGPT plugin | On a deployment co-located with its user's loopback broker, create a private `team-bindings` directory beneath the plugin's configured service home. Provision a distinct ChatGPT agent and save its binding as `<sha256(oauth_subject)>.json` in that directory, including `--host chatgpt --account <oauth_subject>`. Restart the plugin service to register the tools. The current OAuth subject selects the binding. Inbox/review require read permission. Registering an offer, delivery or completion requires read and write. |

A remote hosted plugin needs a broker in its own deployment with explicitly granted memory. An operator's laptop loopback address is local to that laptop. Use the normal evidence-grant revocation flow for the host principal to revoke access.

## Reproduce the measurements

```sh
python -m tools.benchmark_agent_team \
  --cases specs/058-portable-agent-runs/held-out.json --output /tmp/atmem-held-out.json

python -m tools.qualify_portable_agents \
  --output /tmp/atmem-host-qualification.json --screenshot /tmp/atmem-project-history.png
```

The host qualification needs the installed OpenClaw and Hermes runtimes, both framework extras, the local Ollama model and pytest. A screenshot additionally requires Playwright and Chromium or Chrome. The driver reads Hermes' installed runtime metadata and exercises its registry against a disposable profile. The separate OAuth test uses isolated Firebase Auth/Firestore emulators and the repository's pinned ChatGPT dependencies. Its test target is `tests/chatgpt/test_portable_team.py`. [Emulator setup](../../atmem/chatgpt/README.md) · [Recorded outcomes](results.md)

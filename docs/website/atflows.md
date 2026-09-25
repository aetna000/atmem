# AtFlows observability companion

[AtFlows](https://github.com/aetna000/atflows) records local LLM traces, logs, metrics and cost information in its own database. AtMem stores governed memories and encrypted host evidence. Their roles stay distinct: telemetry can suggest what to inspect, while AtMem authorizes evidence and memory decisions.

AtMem 2.3.7 installs `atflows==0.1.3` alongside `atmem-atbot==0.1.0`. Installing the package alone does not run a server or start collecting telemetry. Bun 1.1+ is needed to run AtFlows. In 2.3.7, if compatible Bun is absent, `atmem init` clearly announces and automatically downloads AtMem's pinned official Bun runtime, verifies its release-pinned SHA-256, and stores it privately under `~/.atmem/runtime/bun` without changing global `PATH`. The release also serializes same-process encrypted control access used by dashboard and delegated-login requests. Pip installation itself does not download or execute Bun.

## Start local dashboards

### New in 0.1.3

**Activity → Resume work** shows explicitly instrumented workflow attempts and
reported costs. Configure its producer token and observer using the
[continuity integration guide](../continuity.md). AtFlows observes; AtMem owns
execution permission and saved receipts. Unknown prices are not zero.

**Activity → Timeline** now groups event-count bars by tool, service, model,
event type or hour. Select a bar to narrow the event list. This chart covers the
latest 100 matching events, not all retained history. **Analytics** retains daily
token and cost charts. Both dashboards share AtMem typography.

```bash
atmem init
atmem status
```

`atmem init` starts the AtMem dashboard and an AtFlows instance using AtMem-owned sign-in. `atmem status` reports the actual dashboard and proxy URLs and clear errors if a companion is unavailable. It also reports an independently started AtFlows instance rather than taking it over. Initializing again keeps existing data and credentials. AtFlows 0.1.3 shows a link back to AtMem in delegated mode; AtMem shows the validated healthy local AtFlows link in its persistent top navigation.

Connect a supported client explicitly to AtFlows' OTLP endpoint or model proxy; installing or initializing AtMem alone does not forward traces.

## One account for both dashboards

AtMem-managed startup configures this automatically. For a separately started AtFlows instance, start the AtMem dashboard first and use its actual numeric-loopback URL. Use `atflows init` on first setup, then `atflows start` on subsequent starts:

```bash
export ATFLOWS_ATMEM_AUTH_URL=http://127.0.0.1:ATMEM_PORT
atflows start
```

Keep the variable set for every AtFlows start; delegated mode is read at startup. Open both dashboards with `127.0.0.1`. Sign in at AtMem. AtFlows verifies the live AtMem session and role on protected requests, so revocation and account disablement take effect without a second user database. AtMem manages users and passwords; AtFlows' local user controls are hidden. Removing the setting and restarting AtFlows restores its standalone accounts. See [AtFlows access documentation](https://github.com/aetna000/atflows/blob/main/docs/users-and-access.md).

## Review a linked session

```bash
atmem atflows review RUN_ID --session-id SESSION_ID \
  --since-ms START_MS --until-ms END_MS \
  --base-url http://127.0.0.1:1337
```

This is an explicit read-only investigation. AtMem requires authorized evidence access and checks an exact session link in the selected run. A delegated AtFlows dashboard uses the same AtMem account credentials; standalone AtFlows uses its Administrator password. The report contains bounded trace-error leads, not raw trace bodies or a causal claim. The [2.3.7 release note](../releases/v2.3.7.md) describes automatic Bun setup, concurrent encrypted-store access, compatibility and limits; [2.3.7](../releases/v2.3.7.md) remains stable.

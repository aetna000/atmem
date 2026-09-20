# AtFlows observability companion

[AtFlows](https://github.com/aetna000/atflows) records local LLM traces, logs, metrics and cost information in its own database. AtMem stores governed memories and encrypted host evidence. Their roles stay distinct: telemetry can suggest what to inspect, while AtMem authorizes evidence and memory decisions.

AtMem 2.3.4 installs `atflows==0.1.1` alongside `atmem-atbot==0.1.0`. Installing the package does not run a server or start collecting telemetry. Bun 1.1+ is needed when you choose to start AtFlows.

## Start AtFlows

```bash
atmem status
atflows init
atflows status
```

By default AtFlows keeps its own local accounts. The dashboard and proxy URLs are printed at startup. Connect a supported client explicitly to its OTLP endpoint or model proxy; installing AtMem alone does not forward traces.

## One account for both dashboards

AtMem can be the account authority. Start its dashboard first, then use its actual numeric-loopback URL:

```bash
export ATFLOWS_ATMEM_AUTH_URL=http://127.0.0.1:ATMEM_PORT
atflows init
```

Keep the variable set for every AtFlows start; delegated mode is read at startup. Open both dashboards with `127.0.0.1`. Sign in at AtMem. AtFlows verifies the live AtMem session and role on protected requests, so revocation and account disablement take effect without a second user database. AtMem manages users and passwords; AtFlows' local user controls are hidden. Removing the setting and restarting AtFlows restores its standalone accounts. See [AtFlows access documentation](https://github.com/aetna000/atflows/blob/main/docs/users-and-access.md).

## Review a linked session

```bash
atmem atflows review RUN_ID --session-id SESSION_ID \
  --since-ms START_MS --until-ms END_MS \
  --base-url http://127.0.0.1:1337
```

This is an explicit read-only investigation. AtMem requires authorized evidence access and checks an exact session link in the selected run. A delegated AtFlows dashboard uses the same AtMem account credentials; standalone AtFlows uses its Administrator password. The report contains bounded trace-error leads, not raw trace bodies or a causal claim. The [2.3.4 release note](../releases/v2.3.4.md) describes setup, compatibility and limits.

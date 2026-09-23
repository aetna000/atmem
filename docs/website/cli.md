# CLI operations

Use `atmem --help` and `atmem COMMAND --help` for the installed version's
complete argument reference. Commands below are local operations; they do not
contact the documentation website.

## Setup and inspection
```bash
atmem init
atmem status
atflows status
atmem dashboard
atmem control status
atmem control verify
atmem home status
atmem home verify
```

Initialization creates local identity/state. Dashboard sign-in is separate from
agent/API credentials. `atmem status` shows installed AtMem, AtBot and AtFlows
versions and available local dashboard links; `atflows status` checks the
separately managed AtFlows server. Neither status command reveals an existing
password. Status and verify are inspection operations.

## Connect and govern
```bash
atmem openclaw install
atmem control activate
atmem control restore
```

Installation and activation change host configuration. Review
[OpenClaw setup](../openclaw-setup.md) first. Restore reinstates preserved native
state; it cannot undo an email, purchase or prior model output.

## Inspect a run
```bash
atmem blackbox status
atmem blackbox runs --limit 20
atmem blackbox show RUN_ID
atmem blackbox verify RUN_ID
```

Replace RUN_ID with a recorded run. Exact evidence inspection/export requires the
corresponding evidence privilege; a legacy hash projection is not the plaintext vault.

## Optional AtFlows review
```bash
atmem atflows review RUN_ID --session-id SESSION_ID \
  --since-ms START_MS --until-ms END_MS \
  --base-url http://127.0.0.1:1337
```

AtFlows is installed with AtMem 2.3.6. `atmem init` starts its local server, while trace collection and review are opt-in.
Confirm AtFlows is running before reviewing a run. The command
requires an authorized AtMem evidence token from `ATMEM_EVIDENCE_TOKEN` or an
interactive prompt. Standalone AtFlows asks for its Administrator password;
delegated AtFlows asks for an AtMem username and password. It prints a versioned JSON report by
default; add `--human` for a concise terminal view. The report contains
read-only, exact-session trace-error leads, not causal conclusions. See the
[2.3.6 release note](../releases/v2.3.6.md) for limits and setup.

## Upgrade and recovery
Follow the [2.3.6 release commands](../releases/v2.3.6.md) and
[portable Home recovery](../data-storage-and-backup.md).
Run `atmem users --help` for account administration and local recovery commands.

# CLI operations

Use `atmem --help` and `atmem COMMAND --help` for the installed version's
complete argument reference. Commands below are local operations; they do not
contact the documentation website.

## Setup and inspection
```bash
atmem init
atmem dashboard
atmem control status
atmem control verify
atmem home status
atmem home verify
```

Initialization creates local identity/state. Dashboard sign-in is separate from
agent/API credentials. Status and verify are inspection operations.

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

## Upgrade and recovery
Follow [release commands](../releases/v2.3.4b1.md) and
[portable Home recovery](../data-storage-and-backup.md).
Run `atmem users --help` for account administration and local recovery commands.

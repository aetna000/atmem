# OpenClaw setup

## Requirements

- a local OpenClaw installation on `PATH`;
- Python 3.10 or newer;
- an OpenClaw workspace readable by the current user.

## Install

```bash
python -m pip install --pre --upgrade atmem==2.2.6b1
atmem --version
atmem openclaw install
```

Do not install `openclaw-memory-atmem` directly. It is a bridge, not a standalone memory engine. `atmem openclaw install` selects the matching bridge version, pins the exact Python executable, shows staged progress, restarts the gateway and verifies the running plugin.

## Upgrade from 2.1

Upgrade AtMem first, then refresh the existing bridge without creating a new
migration or changing the current shadow/active mode:

```bash
python -m pip install --pre --upgrade atmem==2.2.6b1
atmem openclaw upgrade
atmem control verify
atmem atbot doctor
```

The bridge upgrade runs a verified self-test flight and restores the prior npm
bridge if installation, gateway, or runtime verification fails. Existing
canonical records, evidence, migration identity, review candidates, and restore
snapshot remain in place. It is safe to rerun when the bridge is already current.
If the dashboard daemon was running, the command restarts it with the upgraded
Python runtime before verifying the bridge.

The installer is safe to rerun. If the same OpenClaw migration is already in
shadow mode, AtMem refreshes and verifies that migration instead of creating
a second control ID. The original pre-AtMem restore snapshot is preserved.

OpenClaw 2026.8.1 (the OpenClaw 2.0 release) requires explicit consent for a
third-party plugin's declared capabilities. The AtMem-managed installer detects
that host version and supplies consent only while installing the exact pinned
`openclaw-memory-atmem` bridge. Older supported OpenClaw releases do not receive
flags they do not understand.

## Inspect before switching

```bash
atmem control status
atmem control verify
atmem openclaw memory status
atmem dashboard daemon start
```

The dashboard must report OpenClaw as the provider, a verified native baseline, a valid mirror and no activation blockers. Search a known memory and inspect its source path and history.

Use OpenClaw normally, then inspect the host-observed Agent Black Box flights:

```bash
atmem blackbox status
atmem blackbox runs
atmem blackbox verify RUN_ID
```

Flight recording stores content digests and bounded lifecycle metadata, not raw prompts, responses, tool parameters or results. See [agent-blackbox.md](agent-blackbox.md) before interpreting a verdict.

## Activate or restore

```bash
atmem control activate
atmem control status

# Non-destructively stage and verify the saved restore material:
atmem control restore --drill

# Return to the saved OpenClaw memory configuration:
atmem control restore
```

Both destructive state transitions require confirmation in an interactive terminal unless `--yes` is supplied deliberately. `control verify` and `restore --drill` are non-destructive. A failed activation does not claim success. A restore preserves AtMem evidence and does not undo past agent outputs.

## Optional Storizon context authority

OpenClaw normally receives context selected and authorized by AtMem. If
Storizon must remain the context authority, configure the optional delegated
mode only after the standard bridge and control-plane checks above pass.

The AtMem registration is the only activation switch. OpenClaw's
`delegatedContext.userId` setting maps an authenticated owner to the exact user
scope registered in AtMem; it does not enable delegation. Matching turns use
one exact `prependContext` segment, suppress native AtMem context preparation,
and record provider authorization separately from observed model-input
delivery. Missing identity or provider failure withholds context by default.

Follow the complete [delegated context authority guide](delegated-context-provider.md)
for registration, readiness states, identity mapping, evidence, fallback, key
rotation, and removal.

For dashboard lifecycle and its loopback-only boundary, see the [main README](../README.md). For the exact switch guarantees, see [control-plane.md](control-plane.md).

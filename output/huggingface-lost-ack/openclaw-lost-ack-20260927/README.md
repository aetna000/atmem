# OpenClaw memory write: lost acknowledgement and retry

**Paper:** [When the Write Lands but the Acknowledgement Is Lost](../paper/openclaw-lost-ack/atmem-openclaw-lost-ack-retry.pdf) · [LaTeX](../paper/openclaw-lost-ack/main.tex)

Javad Taghia, AtMem.Ai Lab. 27 September 2026.

## Result

Five isolated bridge crash trials and three real OpenClaw gateway crash trials passed; one gateway no-fault control passed. The proxy withheld a successful memory-write response and killed the backend with SIGKILL. The caller timed out, reconnected, retried, and read back one complete original record. Retry returned `stored=true`, `status=already_stored`, and the original record ID. Audit verification passed. Gateway trials also passed SQLite integrity and foreign-key checks.

The fact was `User prefers cobalt blue notebooks.` in slot `notebook_preference`. These are repeated deterministic trials of one fact and one fault boundary, not a statistical reliability estimate. There was no competing-system comparison. Gateway model responses were scripted locally, with no paid inference.

## Evidence

- `summary.json`: complete index of nine qualification and nine development runs.
- `qualification/bridge-final-*/result.json`: withheld response, original/retry records, tool results, audit and verification. Each trial includes a same-ID retry and then a new-ID retry. Full before/after record dictionaries are identical.
- `qualification/host-*/summary.json`: real gateway results, record metadata, audit events, SQLite checks and assertions.
- `qualification/host-*/agent-visible-tool-results.json`: the actual tool results presented to the deterministic model endpoint by OpenClaw.
- `development/`: all earlier runs. Six bridge trials passed; two embedded CLI attempts could not stage the source message, so writes were rejected before the fault and no record was created; one development gateway trial passed. Initial results preceded the final strengthened assertions and must not be counted as final qualification.
- `environment.json`: runtime versions, Python package inventory, source identity, and compiled bridge hashes.
- `source-snapshot.tar.gz`: clean tracked source from `da046dc59fd41fdd77ed407d8f196cfc434b478c` with probe scripts added. Unrelated working-tree edits were excluded. Historical npm tarballs were omitted.
- `tested-bridge.tar.gz`: exact compiled JavaScript used in qualification.
- `SHA256SUMS.json`: hashes of supplement files (excluding this self-referential manifest), and the paper/source paths.

Raw full model prompts, host configuration and local gateway credentials are not published. Published tool-result extracts preserve the actual values used for the read-back assertions. Data is synthetic. No user memory was used. Prior paper and benchmark artifacts remain unchanged.

## Reproduce

Use an isolated directory, Python 3.13 (the exact recorded version is in `environment.json`), Node matching the manifest, and OpenClaw 2026.9.1. The direct bridge profile is explicitly enabled by the harness; it is not the managed control-plane profile. Existing product configuration is not changed.

Download this supplement, extract `source-snapshot.tar.gz` into a fresh directory, and extract `tested-bridge.tar.gz` beside it. The source archive includes the Apache-2.0 license. Review `environment.json` to reproduce dependency versions; installing current dependencies is not an exact environment reconstruction.

```sh
mkdir source
 tar -xzf source-snapshot.tar.gz -C source
 tar -xzf tested-bridge.tar.gz
python3.13 -m venv source/.venv
source/.venv/bin/python -m pip install -e ./source
# Ensure the openclaw command resolves to the recorded runtime version.
source/.venv/bin/python source/tools/probe_openclaw_lost_ack.py   --output "$PWD/bridge-run-01" --bridge "$PWD/bridge"
source/.venv/bin/python source/tools/probe_openclaw_lost_ack_host.py   --output "$PWD/gateway-run-01" --bridge "$PWD/bridge" --gateway
source/.venv/bin/python source/tools/probe_openclaw_lost_ack_host.py   --output "$PWD/gateway-control-01" --bridge "$PWD/bridge" --gateway --no-fault
```

Output directories must not already exist. Repeat with fresh output names for five bridge trials and three faulted gateway trials. Gateway probes bind only loopback and stop their own gateway afterward. The executable uses inherited environment for dependencies but isolates OpenClaw state/configuration and points the model provider to the synthetic local endpoint. No provider credential is required.

Compile the paper with `tectonic main.tex` from its directory. The bridge can be rebuilt from the included TypeScript with `npm ci` and `npm run build` in `source/integrations/openclaw`; compare resulting JavaScript hashes against `environment.json`.

## Boundaries

The write completed before the backend was killed. This does not test a half-written SQL transaction, whole-machine failure or power loss. The gateway remains running. The same fact bytes, slot and source binding are reused; paraphrases, conflicting writes and concurrent writers are untested. The gateway waits 600 ms between scripted responses to allow the bridge's idle connection to close. Immediate retry on a still-open failed transport is untested. The two failed embedded CLI setup runs remain disclosed and unresolved.

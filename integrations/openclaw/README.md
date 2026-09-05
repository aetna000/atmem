# AtMem OpenClaw bridge

This npm package is the host bridge for AtMem. It is not a standalone memory engine and should not be installed directly.

Use the Python-owned installer:

```bash
python -m pip install --pre --upgrade atmem==2.2.6b4
atmem openclaw install
```

The installer pins the matching OpenClaw bridge, binds the exact `atmem` executable, copies existing OpenClaw memory, configures shadow mode, restarts the gateway and verifies the loaded plugin. Direct npm installation cannot perform or prove those steps.

The bridge also supports AtMem's optional delegated context-provider mode. It
supplies authenticated owner/workspace bindings, contributes a verified result
as exactly one `prependContext` segment, confirms that segment at `llm_input`,
and suppresses native AtMem recall for the turn. Delegation is enabled only by
an AtMem registration; the bridge's `delegatedContext.userId` is an identity
mapping, not an activation switch.

Existing AtMem 2.1 users run `atmem openclaw upgrade` after upgrading the Python
package. This preserves the current memory mode and migration, verifies the new
bridge with a self-test flight, and rolls back the bridge on failure.

In shadow mode the bridge observes native-memory changes without injecting AtMem context. In active mode it exposes compatible memory search/get tools, model-semantic capture, bounded recall and native-path protection. `atmem control restore` restores the saved OpenClaw configuration and native memory.

The bridge also supplies Agent Black Box hooks. It records model/tool lifecycle digests and bounded metadata—not raw prompts, responses, parameters or results—so `atmem blackbox verify RUN_ID` can check timeline integrity and observed tool-hook closure. See the [Agent Black Box guide](../../docs/agent-blackbox.md) for the exact boundary.

See the repository [OpenClaw setup](../../docs/openclaw-setup.md) and [control-plane guarantees](../../docs/control-plane.md).

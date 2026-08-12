# AtMem OpenClaw bridge

This npm package is the host bridge for AtMem. It is not a standalone memory engine and should not be installed directly.

Use the Python-owned installer:

```bash
python -m pip install atmem==1.0.0
atmem openclaw install
```

The installer pins `openclaw-memory-atmem@1.0.0`, binds the exact `atmem` executable, copies existing OpenClaw memory, configures shadow mode, restarts the gateway and verifies the loaded plugin. Direct npm installation cannot perform or prove those steps.

In shadow mode the bridge observes native-memory changes without injecting AtMem context. In active mode it exposes compatible memory search/get tools, model-semantic capture, bounded recall and native-path protection. `atmem control restore` restores the saved OpenClaw configuration and native memory.

The bridge also supplies Agent Black Box hooks. It records model/tool lifecycle digests and bounded metadata—not raw prompts, responses, parameters or results—so `atmem blackbox verify RUN_ID` can check timeline integrity and observed tool-hook closure. See the [Agent Black Box guide](../../docs/agent-blackbox.md) for the exact boundary.

See the repository [OpenClaw setup](../../docs/openclaw-setup.md) and [control-plane guarantees](../../docs/control-plane.md).

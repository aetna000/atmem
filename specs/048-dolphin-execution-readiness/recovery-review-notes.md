# Root review coordination (2026-10-26)

- Evidence map: `recovery-inputs.json` in this directory. Source snapshots and witness copies are prepared in the private recovery-parent-v4 bundle.
- Native129 is installed-API/system context mode: context-delivery.json explicitly disables native memory provider, so shutdown-witness need not exist. Native process succeeded; recorded result duration41748ms excludes controller overhead.
- Root verified no workload/subscription processes remain and all13 reader calls plus1 judge call completed, no unresolvedreservations. Private bundle root-reconciliation-check.json retains this observation.
- Numeric equality must preserve booleans/strings/largeintegerprecision; raw explicit arguments remain unchanged.
- Be careful strengthening tool-call sequence checks: MCP metadata methods (get_prompt,list_prompts,list_resources,read_resource) may appear model-visible but not in mutation logs. Parentmorgan085 actually called metadata tools and has a valid savedgrade. Avoid requiring backend mutation log entries for metadata calls, or rejecting legitimate parallel read ordering; use proved app contract. Test real retained023/085/129 export offline with the new normalizer.
- Root will perform Claude Opus5.5 medium review after implementation stabilizes; no need for nestedagent or workload.

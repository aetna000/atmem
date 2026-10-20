# Claude three-arm: runtime-qualified comparison

Same task, models, caps, source/grader, AtMem artifact and pinned Cognee SDK as
claude-three-arm-consult.md. Same explicit graph-consult gate and on-demand MCP
delivery. Three new sessions in the same fixed native/Cognee/AtMem order. No
product tuning or patch retries. This is the final bounded three-arm attempt;
do not launch further target runs if it fails. Preserve all nine target attempts
across the three separate protocols; do not pool or select best runs.

The second protocol passed all 1868 frozen tests in every arm, but its command
runner denied workspace scratch writes through the :tmpdir deny alias, reset
PATH (calling Apple Git shim instead of admitted native Git), and inherited MCP
stdin (one AtMem-arm `cat > /dev/null` waited 35 seconds). It is not a clean
latency comparison. Keep its unmodified raw measurements and both earlier
protocols in the protected archive.

This host-only correction sets outer TMPDIR to already-denied /tmp; inside the
confined child it exports the permitted workspace scratch directory and exact
PATH/PYTHONPATH. Command stdin is DEVNULL, never the MCP protocol stream. Before
indexing or target dispatch each arm must successfully create/read a scratch
file, run noninteractive cat without waiting, resolve the copied native Git,
read its one-commit source history, and import Click from its own source tree.
Real source-positive and evaluator/original-Git/network-negative probes also
remain mandatory. Do not broaden filesystem or network permissions.

Freeze all three preparations before models, withhold grader until all finish,
retain exact token receipts, actual thinking tokens and all failures. Primary
table reports this protocol only. Explain previous non-use and harness faults
and retain their full outcomes in the accompanying report. Single reused task,
one attempt per arm: no general performance or causal superiority claim.

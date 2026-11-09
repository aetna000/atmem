# Declaration-only upstream probes

These snapshots record published declaration shapes for explicit review. They do
not add versions to the native authorization/compatibility allowlist, prove
runtime identity population or qualify an installed host. Missing optional
identity/owner signals must still fail closed.

## OpenClaw 2026.11.2 review — 2026-11-09

Source: the actual published npm archive in [CI run 42613494184](https://github.com/aetna000/atmem/actions/runs/42613494184),
failed latest-context job, artifact `openclaw-declaration-review-2026.11.2`.
The archive SHA-512 matches the independently read registry integrity:

`sha512-SgBml4WLp8V1DdAYkrTPLzVdA/iYo3iuHCtm4788GjaG83QZdd1VeOTlue0HBJGdn3SbFE06b6uPs+AM5ShMgg==`

Compared with 2026.11.1, hook/context bindings, field names and optionality are
identical. No governed task identity appears; sessionId/sessionKey and the owner
signal remain declared, with their recorded optionality. This is declaration
coverage only. The native version allowlist is unchanged.

Snapshot SHA-256: `d998383457b848dd8112e672357e6ea464529ee0cdb0561327205e61304a0c3e`.
The failure-only CI diagnostic never changes a gate result or commits its output;
this snapshot was added only after reviewing the recorded shape and provenance.

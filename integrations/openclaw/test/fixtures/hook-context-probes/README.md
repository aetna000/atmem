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

## OpenClaw 2026.11.5 review — 2026-11-18

Published archive independently fetched and matched to registry metadata and
[CI run 44117243652](https://github.com/aetna000/atmem/actions/runs/44117243652),
artifact `openclaw-declaration-review-2026.11.5`:

`sha512-mqPlsGLOe8NS85BfP1vWW9YVwFXchsV75QTkEbyR4csylORxts+fmfZp9+qbD7aPbXQIctyjRk+CPL91fDvxBA==`

The first diagnostic omitted the tool context because a narrowly recognized
versioned alias acquired a v2-only optional `runtimeContext.models` field. Source
review confirmed that the default remains version1 and resolves to the same base;
`senderIsOwner`, session identity and their optionality remain declared. The parser
now recognizes exactly the additional reviewed branch. Negative tests still refuse
a changed default, unknown base or unreviewed branch. This is a declaration-reader
correction; it adds no runtime capability or permission.

Compared with 2026.11.2, the agent context drops optional
`heartbeatEventQueueSessionKey`, the tool-hook context adds optional`trigger`,
and the default tool context adds optional`approvalReviewerDeviceIds`,
`assertCompleteResult`, `inputProvenance`, `modelExecution`, `runId` and `sandbox`.
The bridge does not consume the removed field or treat these additions as authority.
Hook/context bindings are unchanged; no governed task identity appears. Missing
identity and owner signals still fail closed. Native compatibility remains unchanged.

Corrected locally extracted snapshot SHA256:
`ac26229d5c7bfa76825eaddc54de9204eead368d972c75bb3b19b1b5cb015c37`.
The earlier CI diagnostic's SHA256 was
`12bb958fec110a32ae047b791735affe1404c60d0d9787500e27b7a830cb48ad`;
it is retained as failure evidence, not silently relabelled a valid extraction.

## OpenClaw 2026.11.6 review — 2026-11-21

The archive from [CI run 44897475361](https://github.com/aetna000/atmem/actions/runs/44897475361)
and the independently fetched npm archive match the registry integrity
`sha512-4MGjAMv8QlVrul3ZbCu8KjM7GhXfLdLzf0IrsO5QZ8LC3oYkduqs2rZiZpPDmTRpT6kXYke/OVaWrB+YmhBHLw==`.
The hook declarations and optionality are identical to the 2026.11.5 probe.
The independent declaration check passed. The native allowlist stays unchanged.

Snapshot SHA-256 is
`edd6af53c95208c971cc89bfa6277911dc7946e1b593b3d8037fece6e9eb0d8d`.

## OpenClaw 2026.11.10 review — 2026-11-27

The npm archive matched the registry and the diagnostic from
[CI run 45919458098](https://github.com/aetna000/atmem/actions/runs/45919458098).
Archive integrity is
`sha512-/FKDjxY1ZdUSXHx1a9b4EUpPRZywM3uv4181g22XImJfp/5+h+fFUZ7B7HthNrdYzq//05zH0Yf7mefzIlWFaQ==`.
The independently extracted snapshot matches the CI snapshot at SHA-256
`890461c122dcff538760b14b354bb6638b6a9951f5acc3ea2b662eb8e38c4352`.

Compared with 2026.11.6, the agent context adds optional `completedTurn`
and `toolNames` fields. The tool context adds optional `backgroundRun`.
Hook bindings and the optional session and owner fields are unchanged.
The declaration gate passed locally. Native authorization is unchanged.

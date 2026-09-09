# Spec Kit task identity and evidence conventions

Canonical row: `- [ ] [T033] Description` or `- [x] [T033] Description`.
An insertion suffix is part of the stable ID: **T006 and T006a are distinct**.
Do not strip the suffix, cast the ID to an integer or renumber existing tasks.
The full reference includes its feature, for example `005:T006a`.

Parse rows with `^- \[( |x|X)\] \[(T[0-9]{3,}[a-z]*)\](?:\s|$)`.
Duplicate detection compares the complete ID within one feature. The same ID
in another feature is valid. A suffixed insertion does not imply a dependency;
dependencies must still be written explicitly. Sort by numeric component and
then suffix only for display, never for identity matching.

`[ROLLUP: ...]` after the ID marks an umbrella completion row, not a second
implementation estimate. Keep it unchecked until its named tasks pass. Inventory
reports show roll-ups separately from directly actionable unchecked rows.
`[LAYOUT SUPERSEDED by ...]` retires only a layout constraint; the remaining task
work is still actionable. Never mark a task done just because a rule changed.

Run `python tools/check_spec_tasks.py` for a read-only JSON inventory and validation.
The parser validates all features without numeric-range assumptions and retains
suffixes. Verification results follow the
[append-only evidence journal](../docs/implementation-evidence/README.md).

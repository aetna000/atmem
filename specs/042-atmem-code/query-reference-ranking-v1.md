# Syntax-supported query call references

The CD1 score and T094 static results remain unchanged. T094 removes part of a
layout-weighting error but is insufficient alone. Inspection of all nineteen
original queries finds ordinary prose parentheses and traceback labels among
the old bare-call regex matches. In Flask-5014, `empty name (e.g. ...)` causes
`name` to nominate a different class's property at maximum priority. This is
mechanistic diagnosis, not a measured causal explanation of the score.

## Bounded correction

Whitespace before `(` in arbitrary prose must not alone nominate a bare function.
Keep immediate `name(...)` notation, explicit underscore identifiers and dotted
references. Preserve spaced actual calls by parsing whole-query Python, inline
code, fenced code and doctest input as data; only `ast.Call` with a bare Name
function adds such a reference. Invalid prose is not repaired into code. Never
execute query code, resolve dynamic imports or guess external namespaces.
Retain all current alias-rebinding/conflict controls and all graph/source/scope/
freshness/secret/budget boundaries. No repository or benchmark rules.

## Verification

Before editing, retain the complete T094 source and the original frozen CD1
source and completed static replay. Only the call-reference helper and its
binding in `_references` may change from T094. Unit gates must cover ordinary
prose, newline-separated parentheses, spaced real calls, inline/fenced Python,
doctests, invalid code, non-execution, qualified names and existing aliases.

Use a reusable diagnostic runner that captures the source chain, protocol,
complete driver and reader implementations before use. Run a fresh process with
original-vault access denied, validate the source-change chain, reproduce every
original CD1 pack with the original CD1 packer, and retain all nineteen new
packs and rankings. Keep failure cases and unaffected cases, not a favorable
subset. Static source/ranking changes are not model-token or task measurements.
Installed qualification and any new matched model run need their prospective
gates; untouched confirmation is still required for T062.

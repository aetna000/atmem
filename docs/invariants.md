# Cross-cutting invariant conformance

The blocking registry captures the eleven guarantees inherited from Specs
001–004. Run `python tools/check_invariants.py`; it executes the installed,
offline, base-package suite and emits a content-minimized report. Any failed,
missing, unrunnable, or skipped owning assertion is `unproven` and blocks.
Optional configurations not executed are `partially_proven` and named.

Current baseline gaps are optional production database services and real host
SDK version matrices, which remain feature-owned CI evidence rather than being
silently called proven by the offline base suite. Seeded mutation tests confirm
that each regression reports exactly its own invariant ID.

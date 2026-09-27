# Hermes

AtMem can install its native Hermes memory provider, create a scoped connection,
preserve the previous provider, inventory native `MEMORY.md`/`USER.md` files,
and verify the result as one transaction.

The safe default gives Hermes its own memory and starts in shadow mode:

```sh
atmem install hermes --yes
```

Shadow mode records governed capture and context-withholding evidence without
adding AtMem context to the model. Alternatively, choose shared memory on the
first setup, activate it and prove a real turn:

```sh
atmem install hermes --memory shared --activate --verify-turn --yes
```

`--memory isolated` is the default. `--memory shared` joins the primary memory
subject while retaining a distinct Hermes agent ID in sessions and evidence.
If Hermes is already connected, restore it before changing between isolated and
shared memory. AtMem refuses to move a live binding between scopes because that
could expose or strand memory midway through setup.
Native Hermes memory files remain unchanged; supported content is copied into
quarantined proposals for review, never silently admitted.

Inspect or undo the setup:

```sh
atmem hermes status
atmem restore hermes --yes
```

Restore disables the scoped binding and restores the provider saved in the setup
receipt. The pre-switch Hermes configuration is retained as an encrypted,
hash-verified backup; restore refuses to overwrite later user edits. It does not
delete Hermes files, AtMem memories, proposals, or evidence.
`--verify-turn` creates a random temporary governed verification fact, requires
Hermes to answer from it, checks the matching five-event completed run, and then
deletes that temporary fact.
The installer starts or restarts only the AtMem-owned dashboard service on its
recorded port. An already open Hermes TUI must be closed and reopened unless
`--verify-turn` starts a fresh ordinary Hermes process as part of setup.

The end-to-end release qualification is macOS. Linux and WSL use the same local
provider contract but remain to be qualified for this beta. Native Windows
credential ACL handling remains pending.

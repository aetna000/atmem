# Evidence, accounts and access

## Four local roles
| Role | Allowed evidence access |
| --- | --- |
| Viewer | Content-free metadata, hashes, integrity and coverage |
| Investigator | Decrypt, view and play retained evidence inside AtMem |
| Evidence Collector | Investigator access plus confirmed plaintext export and evidence settings |
| Administrator | Ultimate local evidence access and user administration |

Agent/API role headers do not independently grant these evidence privileges.

## First sign-in
Run `atmem init`, keep the printed temporary Administrator password and open
`atmem dashboard`. Sign in and change the temporary password.
Administrators create users and assign roles. For local recovery, inspect
`atmem users --help`; do not expose recovery facilities as a public service.

## Capture settings
With the recorder configured, full-fidelity capture is the default supported
profile. Turning Data off retains encrypted metadata and marks new runs not
reconstructable. Turning Recorder off stops new evidence capture.
Neither switch creates a plaintext storage profile.

Delegated context still follows its provider contract and retention permissions.
Full-fidelity settings do not override a provider's no-retention boundary; inspect
the recorded coverage and [delegation contract](../delegated-context-provider.md).

## Encryption boundaries
New and migrated control stores are application-encrypted. Original media and exact
payloads live within the protected evidence boundary. Historical or external
plaintext sources need inventory and verified cleanup before claiming complete
at-rest protection. Do not describe Ed25519/HMAC transport as post-quantum encryption.

## Evidence is not an external receipt
A host-reported tool completion proves what was captured at that boundary, not
independent payment settlement or delivery. See [Black Box](../agent-blackbox.md)
and [backup/recovery](../data-storage-and-backup.md).

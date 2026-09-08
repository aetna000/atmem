# Entity and relationship memory

AtMem's graph is a rebuildable candidate source, never canonical truth. Every
entity, alias and relation is scoped and cites an eligible canonical record.
Traversal authorizes each edge, detects repeated edges, and enforces configured
hop, candidate and UTF-8 byte limits before returning a path.

Aliases resolve only when one active entity matches exactly. Multiple matches
produce `review_required`; AtMem does not probabilistically merge them.
Merge, split, rename, delete and supersede operations require a digest-bound
preview, actor and reason. Their immutable receipt retains lineage and marks
the derived generation for repair; rollback restores the prior rows.

Graph path evidence proves that the selected canonical records and derived
edges were eligible at evaluation time. It does not prove that a relationship
is true outside its recorded evidence. Deleting evidence removes its path from
active traversal, and deterministic rebuilds can be compared by graph digest.

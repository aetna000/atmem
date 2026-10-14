# Authentic corpus selection

The replacement memory-understanding corpus contains only source conversation
text from pinned, licensed human–assistant interaction datasets. Selection does
not create, paraphrase, translate, complete or rewrite any conversation.

## Sources

| Source | Revision | License | Use |
| --- | --- | --- | --- |
| `allenai/WildChat-1M` | `7d6490e462285cf85d91eabea0f9a954fbddcd1f` | ODC-By-1.0 | Organic public human–AI conversations across the language allocation |
| `RuiSumida/LUFY` | `1b3fcb1682eae1f034ecdce03e183ebd3f34d179` | CC-BY-4.0 | Every privacy-eligible user turn from the longitudinal study |

LoCoMo and every generated-dialogue, translated-replica, fictional or
hand-authored scenario corpus are excluded from candidate construction,
labeling, training and authentic-conversation evaluation.

LMSYS-Chat-1M was reviewed but excluded from the public artifact because its
dataset agreement prohibits transferring or hosting the conversation dataset
for third parties. A corpus that users cannot independently obtain from the
published artifact does not satisfy this feature's public-dataset outcome.

## Candidate extraction

- LUFY contributes each privacy-eligible user turn, with the preceding bounded
  original conversation window. It is not collapsed to the last turn.
- WildChat contributes at most the last four eligible user turns from a source
  conversation. Every retained candidate keeps one source conversation and
  original-language text intact.
- WildChat selection targets 25% explicit memory-intent turns, 35% turns with
  earlier user chronology and 40% representative turns. When a stratum has
  insufficient real inventory, its share is redistributed among the other
  authentic strata. The selection stratum is provenance only and is excluded
  from model-visible input.
- The final source allocation is 50% English; 20% Chinese; 5% each French,
  Spanish, Arabic and German; 1% each Portuguese, Japanese, Russian,
  Indonesian and Korean; and 5% across the remaining supported languages.

This enrichment is not a label. A memory-intent or chronology candidate may
still be `DO_NOT_STORE`, and a representative candidate may be `STORE`. The
authenticated CLI judge applies the same evidence rubric after selection.

## Leakage and duplicate handling

Exact source-bound row identity and model-visible content identity are separate.
Cross-user exact replicas therefore remain available to the corpus-wide exact
and multilingual-semantic duplicate graph. A leakage component is the
transitive closure of duplicate clusters and source conversations. Work queues
and train, validation, calibration and test assignment never split a leakage
component. Only one canonical cross-scope representative enters the public
training rows; noncanonical members remain review evidence.

Cross-scope similarity never creates a runtime `DUPLICATE` label. That label
requires an equivalent earlier user-authored turn in the same supplied memory
scope and cites the concrete earlier turn identifier.

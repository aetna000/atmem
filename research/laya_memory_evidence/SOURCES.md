# Multilingual authentic-conversation source register

This register controls the 100,000-row Laya memory-decision corpus. A source is
not admitted merely because it is public. It must contain human-origin
conversation, permit the intended training use, permit the planned public
artifact, expose stable record identities, and survive privacy/secret scanning.

## Admitted sources

| Source | Human-origin status | Coverage | License | Planned use |
| --- | --- | --- | --- | --- |
| `allenai/WildChat-1M` | Organic production conversations between users and deployed ChatGPT models | 838,000 released conversations; 74 detected languages and country metadata spanning about 200 countries | ODC-By | Primary multilingual source |
| `RuiSumida/LUFY` | Natural longitudinal human-assistant study conversations | 4,254 turns from 17 participants plus 497 evidence-grounded QA rows | CC BY 4.0 | Longitudinal preference/fact source; use every eligible unique user turn at most once |

Every exported row retains the source revision, source record ID, license,
original language, original evidence span and a content digest. The public card
must distinguish organic production sources from LUFY's controlled study.

## Explicit exclusions

| Source | Decision | Reason |
| --- | --- | --- |
| LoCoMo | Excluded | Conversation text is generated rather than real user conversation. |
| SALT-NLP/SWE-chat | Pending source gate | Authentic ODC-By coding-agent sessions from real developers, but the configured Hugging Face identity has not accepted the repository access conditions. No row is counted until lawful access and a source audit pass. |
| LMSYS-Chat-1M | Excluded from the public corpus | Authentic and multilingual, but its agreement prohibits transferring or redistributing the conversation dataset. |
| OpenAssistant OASST2 | Excluded from the authentic-production core | Human-written and multilingual, but deliberately crowdsourced conversation trees rather than organic deployed usage. It may be a separately named research control, never counted toward the 100,000. |
| Anthropic HH-RLHF | Excluded | The card warns that these data are not intended for supervised dialogue-agent training; it is also a red-team/preference collection rather than ordinary production memory use. |
| Pandorabots public sample | Excluded | Authentic but only 115 conversations and CC BY-NC; the full corpus requires a commercial license. |
| Cole conversational corpus | Excluded | Authentic multilingual production data, but the full data requires a commercial license. |

## Sampling contract

- The deliverable targets 100,000 accepted rows and never publishes fewer than
  20,000; the exact count and any early-stop reason are public.
- Candidate collection starts above 100,000 because teacher disagreement,
  privacy findings, malformed context and duplication cause rejection.
- Source conversations, sessions and user identities remain grouped in one
  split. No conversation can cross train, validation or calibration.
- WildChat fills the balance after all eligible LUFY rows. If SWE-chat access is
  later accepted, at most one primary row per session may be added under a new
  source-manifest revision. WildChat is sampled across languages and scripts
  under the fixed allocation below.
- No generated conversation, paraphrase or translation can be used to meet the
  row target. Multiple windows over identical text cannot be counted as unique.
- Language metadata is used for sampling and reporting, then removed from the
  model-visible state.

## Language policy

The model is a semantic decision layer, not a translator. Evidence stays in its
original language. Fixed decision IDs (`STORE`, `UPDATE`, `IGNORE`, `FORGET`,
`REVIEW`) and memory-class IDs are shared across all languages. Translation or
localized rendering is performed by the calling agent after retrieval.

Training uses smoothed language sampling so high-resource English does not
erase lower-resource signals. Release gates report per-language and per-script
quality, the worst-language result, and the gap from English. Languages without
enough independent evaluation support are documented as observed but unclaimed.

### Fixed 100,000-row language allocation

| Language or group | Rows | Share |
| --- | ---: | ---: |
| English | 50,000 | 50% |
| Chinese | 20,000 | 20% |
| French | 5,000 | 5% |
| Spanish | 5,000 | 5% |
| Arabic | 5,000 | 5% |
| German | 5,000 | 5% |
| Portuguese | 1,000 | 1% |
| Japanese | 1,000 | 1% |
| Russian | 1,000 | 1% |
| Indonesian | 1,000 | 1% |
| Korean | 1,000 | 1% |
| Every other supported language, including Hindi and Urdu | 5,000 total | 5% |

The language selection is informed by the Microsoft AI Diffusion Q2 2026
country estimates joined to Unicode CLDR territory language populations, with
the final weights fixed by the corpus requirement above. This is an estimated
language ranking, not a direct worldwide user census. Microsoft notes that its
current estimates under-measure China because several widely used domestic AI
tools are absent. The long-tail bucket uses count-power 0.3 smoothing and
excludes missing/unknown language tags.

The builder fails closed when authentic eligible inventory cannot meet a named
language quota. It must not backfill a shortage with generated, translated, or
mislabeled conversation.


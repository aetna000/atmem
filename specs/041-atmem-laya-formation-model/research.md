# Research Decisions

## Selected approach

Use multilingual Laya as a small, typed System One decision model rather than a text
generator. Its finite-choice/score interface fits AtMem's bounded decision
surface and keeps canonical authority in deterministic code. Treat the upstream
checkpoint as a base requiring domain fine-tuning and calibration, not as a
drop-in replacement for Qwen or Jev.

Language handling follows established multilingual-classifier practice: a
shared multilingual encoder and shared decision head operate directly on the
original text; smoothed language-balanced sampling limits high-resource
dominance; fixed label IDs are shared across languages; and evaluation reports
per-language and worst-language results. Translation remains a presentation
operation outside the decision layer. The training set does not contain
machine-translated replicas.

Use generative intelligence only for named hard cases through AtBot. This avoids
making Qwen—or any one provider—the default decision engine and preserves an
offline path.

Training conversations come only from immutable, source-licensed human-origin
corpora. WildChat-1M supplies organic public human/assistant interactions and
LUFY supplies controlled longitudinal human/assistant interactions at their
pinned revisions. Additional sources may be admitted only after license,
collection-method, privacy and human-origin review. LoCoMo, generated dialogue,
synthetic or hand-authored scenarios, generated continuations, paraphrase
augmentation and translated quota fill are rejected. Codex/Claude annotations
are weak-supervision metadata attached to authentic text; they are not new
conversation content.

The learning target is a structured, evidence-bound understanding transition:
meaning, scope, temporal validity, durability and relation to prior state plus a
bounded disposition. This supports a living user model in which later evidence
may refine, contradict, supersede, repeat or remove earlier understanding while
provenance and history remain intact.

## Source decisions to pin during implementation

- Laya multilingual model/card:
  `https://huggingface.co/convaiinnovations/laya-multilingual`
- mmBERT paper: `https://arxiv.org/abs/2509.06888`
- XLM-R multilingual sampling and transfer analysis:
  `https://arxiv.org/abs/1911.02116`
- XTREME per-language cross-lingual evaluation:
  `https://proceedings.mlr.press/v119/hu20b.html`
- Multi3WOZ parallel external evaluation:
  `https://github.com/cambridgeltl/multi3woz`
- Laya training guide:
  `https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md`
- Jev API contract: `https://api.typesafe.ai/redoc`
- Hugging Face repository/upload/token documentation from `huggingface.co/docs`
- Vast.ai current pricing/offer documentation and live CLI offer results

These URLs are discovery references, not immutable inputs. Tasks must record
commit/revision, license, file digest, dependency versions and retrieval date.
The multilingual checkpoint currently advertises a 1,024-token context and an
mmBERT backbone, but those are candidate
assumption only: T002 must derive and test the effective ceiling from the exact
pinned model/tokenizer/configuration before any schema or packing limit freezes.

## Rejected alternatives

- **Keep Qwen as the sole default**: capable but unnecessarily generative,
  slower/costlier for finite decisions and harder to calibrate as typed choices.
- **Replace AtMem rules with Laya**: violates authority and provenance boundaries.
- **Train a text generator for rationales**: increases hallucination surface;
  rationales are audit metadata, not authoritative inference output.
- **Use Jev as a runtime dependency**: external egress and moving-service risk;
  keep it as a pinned comparison arm.
- **Rent first**: ignores available local Windows and Mac resources and the
  user's cost preference.
- **Train on public memory benchmarks**: risks contamination and licensing/
  claim ambiguity; reserve them for evaluation under their terms.

## Questions resolved by protocol rather than assumption

- RLCD/proper scoring versus cross-entropy is an experiment, with selection on
  held-out performance and calibration.
- Windows CUDA versus Mac MPS/CPU is decided by representative smoke evidence.
- Vast instance type is selected from live offers by total expected cost only
  after local infeasibility, never frozen now.
- A Jev advantage or disadvantage is an evaluation result, never a delivery
  prerequisite promised in advance.
- BEAM is intentionally outside the typed formation/ranking claim because this
  feature makes no large-workload scheduling claim. Any such later claim must
  add the constitution-required BEAM evidence.

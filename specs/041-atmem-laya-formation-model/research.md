# Research Decisions

## Selected approach

Use Laya as a small, typed System One decision model rather than a text
generator. Its finite-choice/score interface fits AtMem's bounded decision
surface and keeps canonical authority in deterministic code. Treat the upstream
checkpoint as a base requiring domain fine-tuning and calibration, not as a
drop-in replacement for Qwen or Jev.

Use generative intelligence only for named hard cases through AtBot. This avoids
making Qwen—or any one provider—the default decision engine and preserves an
offline path.

## Source decisions to pin during implementation

- Laya model/card: `https://huggingface.co/convaiinnovations/laya`
- Laya training guide:
  `https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md`
- Jev API contract: `https://api.typesafe.ai/redoc`
- Hugging Face repository/upload/token documentation from `huggingface.co/docs`
- Vast.ai current pricing/offer documentation and live CLI offer results

These URLs are discovery references, not immutable inputs. Tasks must record
commit/revision, license, file digest, dependency versions and retrieval date.
The upstream card currently suggests a 512-token default, but that is a candidate
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

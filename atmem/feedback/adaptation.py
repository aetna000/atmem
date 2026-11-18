"""Owner-invoked memory-policy experiments, never production qualification.

Application callbacks are trusted code, not agent tools. The agent proposes text;
the application fixes scopes, inputs, grader and budgets. All retained content is
in the existing encrypted feedback ledger. A report cannot activate a policy.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha256
import math
import time
import uuid

from atmem.contracts.feedback import identifier
from atmem.core.canonical import canonical_json
from atmem.feedback.metrics import paired_episode_interval
from atmem.feedback.store import FeedbackError, snapshot

FORMAT = "atmem-memory-adaptation-v1"
ARMS = ("none", "transcript", "generic", "revised")
_ACTIVE_TRIAL = ContextVar("atmem_adaptation_trial", default=None)


def fingerprint(value):
    return sha256(canonical_json(value).encode()).hexdigest()


def _closed(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError("closed adaptation object required")


def _number(value, maximum, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or not (0 < value <= maximum if positive else 0 <= value <= maximum):
        raise ValueError("finite bounded adaptation number required")


def _digest(value):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("SHA256 required")


def policy(value):
    _closed(value, ("load", "offload"))
    for text in value.values():
        if type(text) is not str or not text.strip() or len(text.encode()) > 4096:
            raise ValueError("bounded nonempty policy text required")
    return snapshot(value)


def validate_manifest(value):
    value = snapshot(value)
    _closed(value, ("format", "corpus", "runtime", "grader", "budget", "cases", "hypothesis", "seed"))
    if value["format"] != FORMAT:
        raise ValueError("unsupported adaptation format")
    if type(value["hypothesis"]) is not str or not 0 < len(value["hypothesis"].encode()) <= 1024:
        raise ValueError("bounded explicit hypothesis required")
    if type(value["seed"]) is not int or not 0 <= value["seed"] < 2**32:
        raise ValueError("bounded seed required")
    _closed(value["corpus"], ("id", "revision", "sha256", "license", "egress", "kind"))
    for field in ("id", "revision", "license"):
        if type(value["corpus"][field]) is not str or not 0 < len(value["corpus"][field].encode()) <= 512:
            raise ValueError("bounded corpus provenance required")
    _digest(value["corpus"]["sha256"])
    if value["corpus"]["egress"] not in ("none", "public_benchmark") or value["corpus"]["kind"] not in ("synthetic_contract", "adapted_public_pilot"):
        raise ValueError("explicit experimental corpus and egress required")
    _closed(value["runtime"], ("model", "endpoint", "settings_sha256", "runner_sha256", "input_usd_per_token", "output_usd_per_token"))
    if type(value["runtime"]["model"]) is not str or not 0 < len(value["runtime"]["model"]) <= 256:
        raise ValueError("explicit model identity required")
    if type(value["runtime"]["endpoint"]) is not str or not 0 < len(value["runtime"]["endpoint"]) <= 512:
        raise ValueError("explicit endpoint identity required")
    for field in ("settings_sha256", "runner_sha256"):
        _digest(value["runtime"][field])
    for field in ("input_usd_per_token", "output_usd_per_token"):
        _number(value["runtime"][field], 1, positive=True)
    _closed(value["grader"], ("id", "sha256"))
    identifier(value["grader"]["id"])
    _digest(value["grader"]["sha256"])
    _closed(value["budget"], ("calls", "tokens", "usd", "seconds", "retained_bytes", "max_output_tokens"))
    for field, ceiling in (("calls", 1000), ("tokens", 10_000_000), ("retained_bytes", 64*1024*1024), ("max_output_tokens", 8192)):
        n = value["budget"][field]
        if type(n) is not int or not 1 <= n <= ceiling:
            raise ValueError("bounded integer budget required")
    _number(value["budget"]["usd"], 10, positive=True)
    _number(value["budget"]["seconds"], 7200, positive=True)
    cases = value["cases"]
    if type(cases) is not list or not 3 <= len(cases) <= 128:
        raise ValueError("bounded train/validation/test cases required")
    ids, inputs, splits = set(), set(), set()
    for case in cases:
        _closed(case, ("id", "split", "episode", "input_sha256", "target_sha256"))
        identifier(case["id"])
        identifier(case["episode"])
        for field in ("input_sha256", "target_sha256"):
            _digest(case[field])
        if case["id"] in ids or case["input_sha256"] in inputs or case["split"] not in ("train", "validation", "test"):
            raise ValueError("duplicate or invalid split membership")
        ids.add(case["id"]); inputs.add(case["input_sha256"]); splits.add(case["split"])
    if splits != {"train", "validation", "test"}:
        raise ValueError("three disjoint splits required")
    return value


@dataclass(frozen=True)
class Grade:
    """Only an application-owned objective verifier returns this object."""
    correct: bool
    reward: float
    evidence: dict

    def to_dict(self):
        if type(self.correct) is not bool:
            raise ValueError("objective boolean grade required")
        _number(self.reward, 1)
        if not self.correct and self.reward != 0:
            raise ValueError("failed task cannot earn reward")
        return snapshot({"correct": self.correct, "reward": self.reward, "evidence": self.evidence})


class AdaptationService:
    """Trusted SDK only; no method is exposed to a model through MCP.

    Register verifier code in the constructor. It receives only the model's final
    output and application-held target, never model-reported success totals.
    Identity pins aid audit; they cannot certify an arbitrary callback's honesty.
    """
    def __init__(self, feedback, *, grader, grader_id, grader_sha256, clock=time.time):
        self.feedback, self.grader, self.clock = feedback, grader, clock
        self.grader_id, self.grader_sha256 = identifier(grader_id), grader_sha256
        _digest(grader_sha256)

    def _study(self, tx, study_id):
        row = tx.get("adaptation_study", identifier(study_id))
        if row is None:
            raise FeedbackError("missing_study")
        if (row["manifest"]["grader"] != {"id": self.grader_id, "sha256": self.grader_sha256}):
            raise FeedbackError("grader_changed")
        return row

    def _put(self, tx, study_id, row):
        tx.put("adaptation_study", study_id, row, expected_revision=tx.revision("adaptation_study", study_id))

    def _deadline(self, row):
        if self.clock() - row["started_at"] > row["manifest"]["budget"]["seconds"]:
            raise FeedbackError("study_time_budget_exhausted")

    def create(self, credential, scope, study_id, manifest, generic_policy):
        manifest, generic_policy = validate_manifest(manifest), policy(generic_policy)
        if manifest["grader"] != {"id": self.grader_id, "sha256": self.grader_sha256}:
            raise FeedbackError("grader_changed")
        with self.feedback.owner_transaction(credential, scope) as (tx, principal):
            if tx.get("adaptation_study", identifier(study_id)) is not None:
                raise FeedbackError("study_exists")
            value = {"manifest": manifest, "manifest_sha256": fingerprint(manifest), "phase": "train",
                     "started_at": self.clock(), "policies": {"generic": generic_policy}, "snapshots": {},
                     "selected": None, "calls": 0, "tokens": 0, "usd": 0, "retained_bytes": 0}
            self._put(tx, study_id, value)
            tx.audit(principal.principal_id, "create_memory_study", allowed=True)
        return value["manifest_sha256"]

    def inspect(self, credential, scope, study_id):
        with self.feedback.owner_transaction(credential, scope) as (tx, principal):
            value = self._study(tx, study_id)
            tx.audit(principal.principal_id, "inspect_memory_study", allowed=True)
            return value

    def retain(self, credential, scope, study_id, value):
        """Exact content retained in chunks through the scoped encrypted ledger."""
        value = snapshot(value)
        size = len(canonical_json(value).encode())
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            if row["phase"] == "closed":
                raise FeedbackError("study_closed")
            if row["retained_bytes"] + size > row["manifest"]["budget"]["retained_bytes"]:
                raise FeedbackError("study_storage_budget_exhausted")
            key = uuid.uuid4().hex
            tx.put("adaptation_evidence", key, {"study_id": study_id, "content": value}, expected_revision=0)
            row["retained_bytes"] += size
            self._put(tx, study_id, row)
            return key

    def call(self, credential, scope, study_id, payload, provider, *, purpose="task"):
        """Reserve worst-case cost/tokens before an external call; never retry.

        Provider is application code returning content, exact response and numeric
        provider usage. Unknown/crashed calls remain fully charged after restart.
        The adapter must reject secret fields before invoking this boundary.
        """
        payload = snapshot(payload)
        # Conservative UTF-8 byte bound plus protocol overhead, not a cost estimate
        # marketed as exact tokenization. Actual usage is checked on settlement.
        input_bound = len(canonical_json(payload).encode()) + 4096
        output_bound = payload.get("max_tokens")
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            self._deadline(row)
            if row["phase"] not in ("train", "proposal", "validation", "test"):
                raise FeedbackError("study_closed")
            if row["phase"] == "proposal":
                if purpose not in ("revision", "generic_notes", "revised_notes"):
                    raise FeedbackError("invalid_call_purpose")
                if any(c["study_id"]==study_id and c.get("purpose")==purpose for c in tx.iter_kind("adaptation_call")):
                    raise FeedbackError("proposal_call_already_reserved")
                if purpose != "revision" and "revised" not in row["policies"]:
                    raise FeedbackError("revision_not_registered")
            elif purpose != "task":
                raise FeedbackError("invalid_call_purpose")
            budget, runtime = row["manifest"]["budget"], row["manifest"]["runtime"]
            if payload.get("model") != runtime["model"] or type(output_bound) is not int or not 1 <= output_bound <= budget["max_output_tokens"]:
                raise FeedbackError("runtime_changed")
            settings = {k:v for k,v in payload.items() if k not in ("messages", "max_tokens")}
            if fingerprint(settings) != runtime["settings_sha256"]:
                raise FeedbackError("runtime_changed")
            reserved = input_bound*runtime["input_usd_per_token"] + output_bound*runtime["output_usd_per_token"]
            if row["calls"] + 1 > budget["calls"] or row["tokens"] + input_bound + output_bound > budget["tokens"] or row["usd"] + reserved > budget["usd"]:
                raise FeedbackError("study_call_budget_exhausted")
            # Reserve enough storage to preserve a bounded request+response, rather
            # than calling a model that cannot subsequently be recorded.
            storage_bound = 2*len(canonical_json(payload).encode()) + 8*output_bound + 16384
            if row["retained_bytes"] + storage_bound > budget["retained_bytes"]:
                raise FeedbackError("study_storage_budget_exhausted")
            key = uuid.uuid4().hex
            tx.put("adaptation_call", key, {"study_id": study_id, "state": "pending", "request": payload,
                   "input_bound": input_bound, "output_bound": output_bound, "reserved_usd": reserved,
                   "storage_bound": storage_bound, "trial_id": _ACTIVE_TRIAL.get(), "phase": row["phase"], "purpose": purpose}, expected_revision=0)
            row["calls"] += 1; row["tokens"] += input_bound+output_bound; row["usd"] += reserved
            row["retained_bytes"] += storage_bound
            self._put(tx, study_id, row)
        # Credentials and headers never enter payload/provider result. Exceptions
        # are deliberately content-free; bodies can contain secrets or requests.
        try:
            result = snapshot(provider(snapshot(payload)))
            self._deadline(row)
            _closed(result, ("response", "prompt_tokens", "completion_tokens", "usd"))
            for name, maximum in (("prompt_tokens", input_bound), ("completion_tokens", output_bound)):
                if type(result[name]) is not int or not 0 <= result[name] <= maximum:
                    raise ValueError("usage exceeds reserved bound")
            _number(result["usd"], reserved)
            if len(canonical_json(result).encode()) > storage_bound-len(canonical_json(payload).encode()):
                raise ValueError("response exceeds retained bound")
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            with self.feedback.owner_transaction(credential, scope) as (tx, _):
                call = tx.get("adaptation_call", key)
                tx.put("adaptation_call", key, {**call, "state": "unknown", "error": exc.code if isinstance(exc,FeedbackError) else "provider_failed"}, expected_revision=tx.revision("adaptation_call", key))
            raise FeedbackError("provider_failed") from None
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            call = tx.get("adaptation_call", key)
            tx.put("adaptation_call", key, {**call, "state": "complete", "result": result}, expected_revision=tx.revision("adaptation_call", key))
            row["tokens"] += result["prompt_tokens"]+result["completion_tokens"]-input_bound-output_bound
            row["usd"] += result["usd"]-reserved
            self._put(tx, study_id, row)
        return result["response"]

    def run_trial(self, credential, scope, study_id, *, case_id, arm, public_input, target, execute):
        public_input, target = snapshot(public_input), snapshot(target)
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            self._deadline(row)
            case = next((c for c in row["manifest"]["cases"] if c["id"] == case_id), None)
            if case is None or case["split"] != row["phase"] or arm not in ({"generic"} if row["phase"] == "train" else {"generic", "revised"} if row["phase"] == "validation" else set(ARMS) if row["phase"] == "test" else set()):
                raise FeedbackError("trial_not_permitted")
            if fingerprint(public_input) != case["input_sha256"] or fingerprint(target) != case["target_sha256"]:
                raise FeedbackError("case_changed")
            key = fingerprint([study_id, case_id, arm])
            if tx.get("adaptation_trial", key) is not None:
                raise FeedbackError("trial_already_reserved")
            selected_policy = row["policies"].get(arm, row["policies"]["generic"])
            memory = row["snapshots"].get(arm, "")
            trial = {"study_id": study_id, "case": case, "arm": arm, "state": "pending",
                     "policy_sha256": fingerprint(selected_policy), "memory_sha256": fingerprint(memory),
                     "input": public_input, "target": target, "started_at": self.clock()}
            tx.put("adaptation_trial", key, trial, expected_revision=0)
        active_token = _ACTIVE_TRIAL.set(key)
        try:
            # Hidden target is NOT passed to execute. No model-reported grades.
            output = snapshot(execute(public_input, snapshot(selected_policy), memory))
            evidence_id = self.retain(credential, scope, study_id, {"trial_id": key, "output": output})
            grade = self.grader(snapshot(output), snapshot(target))
            if type(grade) is not Grade:
                raise ValueError("registered objective Grade required")
            result = {"state": "complete", "output_evidence_id": evidence_id, "grade": grade.to_dict()}
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            result = {"state": "unknown", "error": "trial_failed"}
        finally:
            _ACTIVE_TRIAL.reset(active_token)
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            current = self._study(tx, study_id)
            # Concurrent phase changes must not turn a late result into an accepted
            # evaluation. Transitions also refuse pending trials.
            if current["phase"] != row["phase"]:
                raise FeedbackError("study_changed")
            tx.put("adaptation_trial", key, {**trial, **result, "elapsed_seconds": max(0, self.clock()-trial["started_at"])},
                   expected_revision=tx.revision("adaptation_trial", key))
        return result

    def _trials(self, tx, study_id, phase):
        return [r for r in tx.iter_kind("adaptation_trial") if r["study_id"] == study_id and r["case"]["split"] == phase]

    def _complete(self, tx, study_id, row, phase, arms):
        if any(c["study_id"] == study_id and c["state"] != "complete" for c in tx.iter_kind("adaptation_call")):
            raise FeedbackError("unsettled_model_calls")
        expected = {(c["id"], a) for c in row["manifest"]["cases"] if c["split"] == phase for a in arms}
        trials = self._trials(tx, study_id, phase)
        actual = {(r["case"]["id"], r["arm"]) for r in trials}
        if actual != expected or any(r["state"] != "complete" for r in trials):
            raise FeedbackError("incomplete_phase")
        return trials

    def begin_proposal(self, credential, scope, study_id):
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            if row["phase"] != "train":
                raise FeedbackError("invalid_study_phase")
            self._complete(tx, study_id, row, "train", ("generic",))
            row["phase"] = "proposal"
            self._put(tx, study_id, row)

    def register_revision(self, credential, scope, study_id, revised_policy):
        revised_policy = policy(revised_policy)
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            if row["phase"] != "proposal" or "revised" in row["policies"]:
                raise FeedbackError("revision_already_registered_or_closed")
            row["policies"]["revised"] = revised_policy
            self._put(tx, study_id, row)

    def remaining_seconds(self, credential, scope, study_id):
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            self._deadline(row)
            return max(.001, row["manifest"]["budget"]["seconds"]-(self.clock()-row["started_at"]))

    def partial_report(self, credential, scope, study_id):
        with self.feedback.owner_transaction(credential, scope) as (tx, principal):
            row = self._study(tx, study_id)
            trials = [t for t in tx.iter_kind("adaptation_trial") if t["study_id"] == study_id]
            calls = [c for c in tx.iter_kind("adaptation_call") if c["study_id"] == study_id]
            tx.audit(principal.principal_id, "inspect_partial_memory_study", allowed=True)
            return {"format":FORMAT,"study_id":study_id,"manifest_sha256":row["manifest_sha256"],
                    "phase":row["phase"],"selected":row["selected"],
                    "resources":{k:row[k] for k in ("calls","tokens","usd","retained_bytes")},
                    "completed_trials":sum(t["state"]=="complete" for t in trials),
                    "unknown_trials":sum(t["state"]!="complete" for t in trials),
                    "unknown_calls":sum(c["state"]!="complete" for c in calls),
                    "elapsed_seconds":max(0,self.clock()-row["started_at"]),
                    "claim":"incomplete_pilot","production_qualification":"inconclusive","activation":"not_authorized"}

    def begin_validation(self, credential, scope, study_id, revised_policy, memories):
        revised_policy = policy(revised_policy)
        _closed(memories, ARMS)
        if memories["none"] != "" or any(type(m) is not str or len(m.encode()) > 12000 for m in memories.values()):
            raise ValueError("fixed bounded memory snapshots required")
        with self.feedback.owner_transaction(credential, scope) as (tx, _):
            row = self._study(tx, study_id)
            self._deadline(row)
            if row["phase"] != "proposal":
                raise FeedbackError("invalid_study_phase")
            if row["policies"].get("revised") != revised_policy:
                raise FeedbackError("revision_not_registered")
            if any(c["study_id"] == study_id and c["state"] != "complete" for c in tx.iter_kind("adaptation_call")):
                raise FeedbackError("unsettled_model_calls")
            row.update(phase="validation", policies={**row["policies"], "revised": revised_policy}, snapshots=snapshot(memories))
            self._put(tx, study_id, row)

    def select(self, credential, scope, study_id):
        with self.feedback.owner_transaction(credential, scope) as (tx, principal):
            row = self._study(tx, study_id)
            if row["phase"] != "validation":
                raise FeedbackError("invalid_study_phase")
            trials = self._complete(tx, study_id, row, "validation", ("generic", "revised"))
            scores = {a:sum(t["grade"]["reward"] for t in trials if t["arm"] == a) for a in ("generic", "revised")}
            correct = {a:sum(t["grade"]["correct"] for t in trials if t["arm"] == a) for a in scores}
            selected = "revised" if scores["revised"] > scores["generic"] and correct["revised"] >= correct["generic"] else "generic"
            row.update(phase="test", selected=selected, frozen_sha256=fingerprint({"policies":row["policies"], "snapshots":row["snapshots"]}), validation_scores=scores)
            self._put(tx, study_id, row)
            tx.audit(principal.principal_id, "freeze_memory_study_selection", allowed=True)
            return selected

    def report(self, credential, scope, study_id, *, close=False):
        with self.feedback.owner_transaction(credential, scope) as (tx, principal):
            row = self._study(tx, study_id)
            if row["phase"] not in ("test", "closed"):
                raise FeedbackError("final_not_open")
            trials = self._trials(tx, study_id, "test")
            scheduled = [c for c in row["manifest"]["cases"] if c["split"] == "test"]
            arms = {}
            for arm in ARMS:
                observed = [t for t in trials if t["arm"] == arm and t["state"] == "complete"]
                arms[arm] = {"correct":sum(t["grade"]["correct"] for t in observed), "scheduled":len(scheduled),
                             "observed":len(observed), "unknown":len(scheduled)-len(observed),
                             "mean_reward":sum(t["grade"]["reward"] for t in observed)/len(scheduled)}
            selected = row["selected"]
            paired = []
            for case in scheduled:
                indexed = {t["arm"]:t for t in trials if t["case"]["id"] == case["id"] and t["state"] == "complete"}
                if "generic" in indexed and selected in indexed:
                    paired.append((case["episode"], indexed["generic"]["grade"]["correct"], indexed[selected]["grade"]["correct"]))
            calls = [c for c in tx.iter_kind("adaptation_call") if c["study_id"] == study_id]
            for arm in ARMS:
                trial_ids = {fingerprint([study_id, t["case"]["id"], arm]) for t in trials if t["arm"] == arm}
                arm_calls = [c for c in calls if c.get("trial_id") in trial_ids]
                arms[arm]["model_calls"] = len(arm_calls)
                arms[arm]["tokens"] = sum(c["result"]["prompt_tokens"]+c["result"]["completion_tokens"] if c["state"]=="complete" else c["input_bound"]+c["output_bound"] for c in arm_calls)
                arms[arm]["usd"] = sum(c["result"]["usd"] if c["state"]=="complete" else c["reserved_usd"] for c in arm_calls)
            deltas = {arm:arms[selected]["mean_reward"]-arms[arm]["mean_reward"] for arm in ARMS if arm != selected}
            result = {"format":FORMAT, "study_id":study_id, "manifest_sha256":row["manifest_sha256"],
                      "selected":selected, "arms":arms, "selected_reward_delta":deltas, "paired_correctness":paired_episode_interval(tuple(paired), seed=row["manifest"]["seed"]) if paired else None,
                      "resources":{k:row[k] for k in ("calls", "tokens", "usd", "retained_bytes")},
                      "elapsed_seconds":max(0,self.clock()-row["started_at"]), "claim":"adapted_pilot_only",
                      "production_qualification":"inconclusive", "activation":"not_authorized", "trials":trials}
            if close:
                if any(t["state"] == "pending" for t in trials):
                    raise FeedbackError("pending_trials")
                row["phase"] = "closed"
                self._put(tx, study_id, row)
            tx.audit(principal.principal_id, "inspect_memory_study_report", allowed=True)
            return result

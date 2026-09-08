"""Evidence-derived memory explanations; never invents missing proof."""
def explain(record: dict, retrieval: dict | None=None, exposure: dict | None=None) -> dict:
    reasons=[]
    if record.get("source_id"): reasons.append("captured_from_evidenced_source")
    if retrieval and record.get("record_id") in retrieval.get("candidate_ids",[]): reasons.append("selected_by_retrieval")
    if exposure and exposure.get("success"): reasons.append("confirmed_at_model_boundary")
    disposition="injected" if "confirmed_at_model_boundary" in reasons else "retrieved" if "selected_by_retrieval" in reasons else "remembered"
    return {"format":"atmem-memory-explanation-v1","record_id":record.get("record_id"),"disposition":disposition,"reason_codes":reasons or ["insufficient_evidence"],"evidence_complete":bool(reasons)}

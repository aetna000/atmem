"""Canonical media reference/observation storage and eligible retrieval."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

from atmem.store.sqlite import utc_now
from .models import ArtifactLocator, ArtifactReference, Consent, Custody, DerivedObservation, MediaKind


class MediaService:
    def __init__(self, store: Any) -> None: self.store=store
    def put_reference(self, reference: ArtifactReference) -> None:
        value=reference.to_dict(); now=utc_now()
        with self.store.transaction(): self.store._conn.execute("""INSERT INTO governed_media_references VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(artifact_id) DO UPDATE SET consent=excluded.consent,consent_generation=excluded.consent_generation,status=excluded.status,updated_at=excluded.updated_at""", (reference.artifact_id,reference.subject_id,reference.workspace_id,reference.media_kind.value,sha256(json.dumps(value["locator"],sort_keys=True).encode()).hexdigest(),json.dumps(value["locator"],sort_keys=True),reference.content_sha256,reference.custody.value,reference.consent.value,reference.consent_generation,json.dumps(reference.retention or {},sort_keys=True),"active",now,now))
    def get_reference(self, artifact_id: str) -> ArtifactReference:
        row=self.store._conn.execute("SELECT * FROM governed_media_references WHERE artifact_id=?",(artifact_id,)).fetchone()
        if row is None: raise KeyError(artifact_id)
        locator=json.loads(row["locator_json"]); return ArtifactReference(str(row["artifact_id"]),str(row["subject_id"]),str(row["workspace_id"]),MediaKind(str(row["media_kind"])),ArtifactLocator(**locator),str(row["content_sha256"]),Custody(str(row["custody"])),Consent(str(row["consent"])),int(row["consent_generation"]),json.loads(row["retention_json"]))
    def store_observations(self, observations: Iterable[DerivedObservation]) -> None:
        with self.store.transaction():
            for item in observations:
                reference=self.get_reference(item.artifact_id)
                if reference.consent is not Consent.GRANTED or reference.consent_generation != item.consent_generation: raise PermissionError("late media output cannot activate after consent changes")
                self.store._conn.execute("INSERT INTO governed_media_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(item.observation_id,item.artifact_id,item.subject_id,item.workspace_id,sha256(item.text.encode()).hexdigest(),item.text,json.dumps(item.evidence_region,sort_keys=True),json.dumps(item.processor,sort_keys=True),item.prompt_config_sha256,item.confidence,item.consent_generation,item.egress,"active",item.created_at))
    def retrieve(self, subject_id: str, workspace_id: str, query: str) -> list[dict[str, Any]]:
        terms=set(query.casefold().split()); rows=self.store._conn.execute("""SELECT o.*,r.consent,r.consent_generation AS current_consent_generation,r.status AS artifact_status FROM governed_media_observations o JOIN governed_media_references r ON r.artifact_id=o.artifact_id WHERE o.subject_id=? AND o.workspace_id=? AND o.status='active'""",(subject_id,workspace_id)).fetchall(); result=[]
        for row in rows:
            if row["consent"]!="granted" or row["artifact_status"]!="active" or int(row["consent_generation"])!=int(row["current_consent_generation"]): continue
            if terms and not terms.intersection(str(row["text"]).casefold().split()): continue
            result.append({"observation_id":row["observation_id"],"artifact_id":row["artifact_id"],"text":row["text"],"confidence":row["confidence"],"evidence_region":json.loads(row["evidence_region_json"]),"reason_codes":["scope_consent_lifecycle_revalidated"]})
        return result
    def revoke(self, artifact_id: str) -> dict[str, Any]:
        reference=self.get_reference(artifact_id); generation=reference.consent_generation+1
        with self.store.transaction():
            self.store._conn.execute("UPDATE governed_media_references SET consent='revoked',consent_generation=?,status='tombstoned',updated_at=? WHERE artifact_id=?",(generation,utc_now(),artifact_id)); changed=self.store._conn.execute("UPDATE governed_media_observations SET status='tombstoned',text='' WHERE artifact_id=? AND status='active'",(artifact_id,)).rowcount
        return {"format":"atmem-media-revocation-receipt-v1","artifact_id":artifact_id,"consent_generation":generation,"observations_tombstoned":changed,"controlled_original_deleted":reference.custody is not Custody.HOST,"host_original_deleted":False}

"""Model-free encrypted service example; synthetic success is not learning.

Run from release source after installing atmem==2.3.15. No network, paid
inference, canonical-memory modification or retained files after exit.
"""
from pathlib import Path
import tempfile

from atmem.contracts.feedback import FeedbackScope
from atmem.evidence.service import EvidenceService
from atmem.feedback.adaptation import AdaptationService, ARMS, FORMAT, Grade, fingerprint
from atmem.feedback.service import FeedbackService


def main():
    with tempfile.TemporaryDirectory(prefix="atmem-adaptation-contract-") as directory:
        home=Path(directory)
        evidence=EvidenceService(home/"control",vault_id="contract",home_root=home)
        credential=evidence.create_demo_accounts(subject_id="example")[2]["token"]
        scope=FeedbackScope("local","example","example","example")
        grader_sha=fingerprint({"grader":"exact-output-equals-target-v1"})
        def grade(output,target):
            correct=output["answer"]==target["answer"]
            return Grade(correct,int(correct),{"actual":output["answer"],"expected":target["answer"]})
        service=AdaptationService(FeedbackService(evidence),grader=grade,grader_id="example-v1",grader_sha256=grader_sha)
        generic={"load":"Inspect authorized evidence.","offload":"Keep bounded evidence-linked notes."}
        cases=[{"id":split,"split":split,"episode":"synthetic-fixture","input_sha256":fingerprint({"prompt":split}),"target_sha256":fingerprint({"answer":7})} for split in ("train","validation","test")]
        manifest={"format":FORMAT,"corpus":{"id":"contract","revision":"v1","sha256":"a"*64,"license":"synthetic-example","egress":"none","kind":"synthetic_contract"},
                  "runtime":{"model":"no-model","endpoint":"none","settings_sha256":"b"*64,"runner_sha256":"c"*64,"input_usd_per_token":.000001,"output_usd_per_token":.000001},
                  "grader":{"id":"example-v1","sha256":grader_sha},"budget":{"calls":1,"tokens":1,"usd":.01,"seconds":30,"retained_bytes":100000,"max_output_tokens":1},
                  "cases":cases,"hypothesis":"exercise-contract-only","seed":52}
        service.create(credential,scope,"example",manifest,generic)
        def trial(split,arm):
            service.run_trial(credential,scope,"example",case_id=split,arm=arm,public_input={"prompt":split},target={"answer":7},execute=lambda public,policy,memory:{"answer":7})
        trial("train","generic")
        service.begin_proposal(credential,scope,"example")
        service.register_revision(credential,scope,"example",generic)
        service.begin_validation(credential,scope,"example",generic,{arm:"" for arm in ARMS})
        for arm in ("generic","revised"):trial("validation",arm)
        assert service.select(credential,scope,"example")=="generic"
        for arm in ARMS:trial("test",arm)
        result=service.report(credential,scope,"example",close=True)
        assert result["resources"]["calls"]==0
        assert result["production_qualification"]=="inconclusive"
        print("Encrypted study contract passed; zero model calls; no learning or production claim.")


if __name__=="__main__":main()

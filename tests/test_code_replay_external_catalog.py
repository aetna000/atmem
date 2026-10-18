import base64
from hashlib import sha1

import pytest
import yaml

from benchmarks.code_replay.external_catalog import catalog, checked_blob, task_metadata, REPOSITORIES, TASK_TREE
from benchmarks.code_replay.external_catalog import CONFIRMATION_REPOSITORIES, CONFIRMATION_SEED
from benchmarks.code_replay.external_catalog import ELIGIBILITY_REPOSITORIES, ELIGIBILITY_SEED


def tree():
    return {"sha": TASK_TREE, "truncated": False, "tree": [
        {"path": repo.replace("/", "__") + "-" + str(i), "type": "tree", "sha": f"{i:040x}"}
        for repo in REPOSITORIES for i in range(1, 5)]}


def test_identity_only_selection_is_stable_under_api_order():
    source = tree()
    result = catalog(source)
    source["tree"].reverse()
    assert catalog(source) == result
    assert len(result["selected"]) == 6
    assert len({r["instance_id"] for r in result["selected"]}) == 6
    assert result["gold_test_hints_opened"] is False and result["solver_calls"] == 0
    assert all(len(pool) == 4 for pool in result["ordered_candidate_pools"].values())


def test_confirmation_is_new_repository_identity_only_and_fixed_size():
    assert not set(REPOSITORIES) & set(CONFIRMATION_REPOSITORIES)
    source = {"sha": TASK_TREE, "truncated": False, "tree": [
        {"path": repo.replace('/', '__') + '-' + str(i), 'type': 'tree', 'sha': f'{i:040x}'}
        for repo in (*REPOSITORIES, *CONFIRMATION_REPOSITORIES) for i in range(1, 7)]}
    result = catalog(source, seed=CONFIRMATION_SEED, per_repo=4, repositories=CONFIRMATION_REPOSITORIES)
    source['tree'].reverse()
    assert catalog(source, seed=CONFIRMATION_SEED, per_repo=4, repositories=CONFIRMATION_REPOSITORIES) == result
    assert len(result['selected']) == 20
    assert {r['repo'] for r in result['selected']} == set(CONFIRMATION_REPOSITORIES)
    assert result['solver_calls'] == 0 and not result['gold_test_hints_opened']
    with pytest.raises(ValueError, match='distinct repository'):
        catalog(source, repositories=('pydicom/pydicom', 'pydicom/pydicom'))


def test_new_candidate_eligibility_pool_is_not_a_final_model_task_set():
    assert not set(ELIGIBILITY_REPOSITORIES) & set((*REPOSITORIES, *CONFIRMATION_REPOSITORIES))
    source = {'sha': TASK_TREE, 'truncated': False, 'tree': [
        {'path': repo.replace('/', '__') + '-' + str(i), 'type': 'tree', 'sha': f'{i:040x}'}
        for repo in ELIGIBILITY_REPOSITORIES for i in range(1, 11)]}
    result = catalog(source, seed=ELIGIBILITY_SEED, per_repo=8,
        repositories=ELIGIBILITY_REPOSITORIES, eligibility_pool=True)
    assert len(result['selected']) == 40
    assert result['sampling_stage'] == 'eligibility_candidates_not_final_model_tasks'
    assert result['final_model_tasks_per_repository'] == 4
    source['tree'].reverse()
    assert result == catalog(source, seed=ELIGIBILITY_SEED, per_repo=8,
        repositories=ELIGIBILITY_REPOSITORIES, eligibility_pool=True)
    with pytest.raises(ValueError, match='bounded'):
        catalog(source, per_repo=8)
    with pytest.raises(ValueError, match='fixed prospective'):
        catalog(source, seed='changed', per_repo=8, repositories=ELIGIBILITY_REPOSITORIES, eligibility_pool=True)


@pytest.mark.parametrize("change", ["truncated", "sha", "duplicate", "unsafe_name"])
def test_incomplete_or_unbound_catalog_rejected(change):
    value = tree()
    if change == "truncated": value["truncated"] = True
    if change == "sha": value["sha"] = "0" * 40
    if change == "duplicate": value["tree"].append(value["tree"][0])
    if change == "unsafe_name": value["tree"][0]["path"] = "../secret"
    with pytest.raises(ValueError): catalog(value)


def test_metadata_blob_is_content_address_verified():
    raw = b"FROM ubuntu:jammy\n"
    identity = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    entry = {"path": "Dockerfile", "type": "blob", "mode": "100644", "size": len(raw), "sha": identity}
    def fetch(path):
        assert path == "git/blobs/" + identity
        return {"encoding": "base64", "content": base64.b64encode(raw).decode(), "sha": identity}
    assert checked_blob(entry, fetch) == raw
    with pytest.raises(ValueError, match="identity"):
        checked_blob({**entry, "size": len(raw) + 1}, fetch)


@pytest.mark.parametrize("name", ["gold.patch", "test.patch", "hints.md", "eval.sh", "../task.yaml"])
def test_private_evaluator_or_executable_files_are_never_fetched(name):
    def forbidden(path):
        pytest.fail("forbidden file fetched")
    with pytest.raises(ValueError, match="metadata"):
        checked_blob({"path": name, "type": "blob", "mode": "100644"}, forbidden)


def test_manifest_identity_cannot_change_selected_repository():
    selected = catalog(tree())["selected"][0]
    fields = dict(instance_id=selected["instance_id"], repo=selected["repo"], base_commit="a" * 40,
        created_at="2020-01-01T00:00:00Z", image="swebench/example:latest", log_parser="parse_log",
        eval_type="pass_and_fail", split="dev", version="1.0", datasets=["SWE-bench/SWE-bench"])
    result = task_metadata(yaml.safe_dump(fields).encode(), selected)
    assert not result["image_digest_pinned"]
    with pytest.raises(ValueError, match="identity"):
        task_metadata(yaml.safe_dump({**fields, "repo": "other/project"}).encode(), selected)


def test_yaml_does_not_execute_python_objects():
    with pytest.raises(yaml.constructor.ConstructorError):
        task_metadata(b"!!python/object/apply:os.system ['false']", {})

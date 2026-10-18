import pytest

from benchmarks.code_replay.external_runtime import command


def test_constrained_runtime_has_no_mount_network_or_task_scripts():
    cmd = command("swebench/sweb.eval.x86_64.example@sha256:" + "a" * 64,
                  "atmem-runtime-control-" + "b" * 32)
    assert "--read-only" in cmd and cmd[cmd.index("--network") + 1] == "none"
    assert "--volume" not in cmd and "--mount" not in cmd and "--privileged" not in cmd
    assert "-I -S" in cmd[-1] and "test.patch" not in str(cmd) and "eval.sh" not in str(cmd)


@pytest.mark.parametrize("image", ["ubuntu:latest", "swebench/example:latest", "--privileged"])
def test_mutable_or_unrelated_image_rejected(image):
    with pytest.raises(ValueError, match="immutable"):
        command(image, "atmem-runtime-control-" + "b" * 32)


def test_owner_container_name_cannot_be_cleanup_target():
    with pytest.raises(ValueError, match="name"):
        command("swebench/sweb.eval.x86_64.example@sha256:" + "a" * 64, "owner-service")

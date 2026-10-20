from __future__ import annotations

import pytest

from atmem import Memory
from atmem.extract.validation import screen_content


FAKE_KEY = "sk-test-abcdefghijklmnop1234567890"


def _assert_not_persisted(memory: Memory, result: dict) -> None:
    assert result["records"] == []
    assert result.get("episode_id") is None
    assert memory.store.list_episodes("user-1") == []
    assert FAKE_KEY not in str(memory.audit("user-1"))


def test_remember_refuses_secret_before_raw_episode_write() -> None:
    memory = Memory(":memory:")
    result = memory.remember("user-1", f"My API key is {FAKE_KEY}")
    _assert_not_persisted(memory, result)


def test_interpreted_fact_cannot_bypass_secret_screen() -> None:
    memory = Memory(":memory:")
    result = memory.remember(
        "user-1",
        "Remember my coding preference.",
        interpreted_fact=f"My API key is {FAKE_KEY}",
        source_type="user_message",
    )
    _assert_not_persisted(memory, result)


def test_source_metadata_cannot_hide_secret_in_episode() -> None:
    memory = Memory(":memory:")
    result = memory.remember(
        "user-1",
        "Remember that I prefer short status updates.",
        raw={"api_key": FAKE_KEY},
    )
    _assert_not_persisted(memory, result)


def test_safe_interpreted_fact_still_commits() -> None:
    memory = Memory(":memory:")
    result = memory.remember(
        "user-1",
        "I like brief updates.",
        interpreted_fact="User prefers concise updates.",
        source_type="user_message",
    )
    assert len(result["records"]) == 1


@pytest.mark.parametrize(
    "secret_text",
    [
        "ghp_abcdefghijklmnopqrstuvwx1234567890",
        "AIzaabcdefghijklmnopqrstuvwxyz1234567890",
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
        "postgres://dbuser:longfakepassword@localhost/app",
        "token=abcdefghijklmnopqrstuvwxyz123456",
        "-----BEGIN PRIVATE KEY-----\nfake-key-material",
    ],
)
def test_common_credential_formats_are_screened(secret_text: str) -> None:
    assert "secret_material_detected" in screen_content(secret_text, trusted=True).reason_codes


def test_secret_screen_does_not_refuse_normal_coding_preference() -> None:
    memory = Memory(":memory:")
    result = memory.remember(
        "user-1",
        "Remember that this project should use environment variables for API keys.",
    )
    assert "secret_material_detected" not in result.get("refused", [])


def test_rejected_secret_is_absent_from_sqlite_file(tmp_path) -> None:
    db_path = tmp_path / "memories.db"
    memory = Memory(db_path)
    memory.remember("user-1", f"My API key is {FAKE_KEY}")
    memory.store.close()
    assert FAKE_KEY.encode() not in db_path.read_bytes()

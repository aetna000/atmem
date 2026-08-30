"""Small explicit AtBot configuration with safe local-first defaults."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path.home() / ".atbot"
DEFAULT_CONFIG = DEFAULT_ROOT / "config.json"

# Accepted only while reading configurations written by the retired standalone
# runtime. They are deliberately never represented or written by AtBot now.
_REMOVED_AUTHORITY_FIELDS = frozenset(
    {
        "memory_path",
        "subject_id",
        "agent_id",
        "workspace_id",
        "recent_message_limit",
        "max_task_steps",
        "allowed_tools",
        "skill_directories",
    }
)


@dataclass(slots=True)
class ProviderConfig:
    name: str = "local"
    kind: str = "ollama"
    model: str = "qwen3:4b"
    endpoint: str = "http://127.0.0.1:11434"
    api_key_env: str | None = None
    egress_class: str = "local"


@dataclass(slots=True)
class AtBotConfig:
    format: str = "atbot-config-v1"
    profile: str = "memory-companion"
    host: str = "127.0.0.1"
    port: int = 8770
    remote_egress_allowed: bool = False
    providers: list[ProviderConfig] = field(default_factory=lambda: [ProviderConfig()])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AtBotConfig":
        if value.get("format") != "atbot-config-v1":
            raise ValueError("unsupported AtBot config format")
        providers = [ProviderConfig(**row) for row in value.get("providers") or []]
        supported = {
            "format",
            "profile",
            "host",
            "port",
            "remote_egress_allowed",
        }
        unknown = set(value) - supported - {"providers"} - _REMOVED_AUTHORITY_FIELDS
        if unknown:
            raise ValueError(f"unsupported AtBot configuration fields: {sorted(unknown)}")
        return cls(
            **{
                key: item
                for key, item in value.items()
                if key in supported
            },
            providers=providers or [ProviderConfig()],
        )


def load_config(path: str | Path = DEFAULT_CONFIG) -> AtBotConfig:
    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(
            f"AtBot is not configured: {source}. Run `atbot init` first."
        )
    return AtBotConfig.from_dict(json.loads(source.read_text(encoding="utf-8")))


def save_config(config: AtBotConfig, path: str | Path = DEFAULT_CONFIG) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(target)
    return target

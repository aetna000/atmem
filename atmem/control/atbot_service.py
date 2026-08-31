"""AtMem-owned lifecycle for the separately packaged AtBot companion."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlparse


PINNED_ATBOT_VERSION = "0.1.0a2"
ATBOT_DISTRIBUTION = "atmem-atbot"
ATBOT_PROTOCOL_VERSION = "1"
DEFAULT_ROOT = Path.home() / ".atmem" / "atbot"

PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "local-ollama": {
        "label": "Local Ollama",
        "kind": "ollama",
        "model": "qwen3:4b",
        "endpoint": "http://127.0.0.1:11434",
        "api_key_env": None,
        "egress_class": "local",
    },
    "local-openai": {
        "label": "Custom local OpenAI-compatible server",
        "kind": "openai-compatible",
        "model": "local-model",
        "endpoint": "http://127.0.0.1:8000/v1",
        "api_key_env": None,
        "egress_class": "local",
    },
    "openrouter": {
        "label": "OpenRouter",
        "kind": "openai-compatible",
        "model": "~openai/gpt-latest",
        "endpoint": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "egress_class": "remote",
    },
    "openai": {
        "label": "OpenAI",
        "kind": "openai-compatible",
        "model": "gpt-5-mini",
        "endpoint": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "egress_class": "remote",
    },
    "deepseek": {
        "label": "DeepSeek",
        "kind": "openai-compatible",
        "model": "deepseek-v4-flash",
        "endpoint": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "egress_class": "remote",
    },
    "xai": {
        "label": "xAI Grok",
        "kind": "openai-compatible",
        "model": "grok-4.6",
        "endpoint": "https://api.x.ai/v1",
        "api_key_env": "XAI_API_KEY",
        "egress_class": "remote",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "kind": "anthropic",
        "model": "claude-sonnet-4-5",
        "endpoint": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "egress_class": "remote",
    },
    "huggingface": {
        "label": "Hugging Face Inference Providers",
        "kind": "openai-compatible",
        "model": "openai/gpt-oss-120b:cheapest",
        "endpoint": "https://router.huggingface.co/v1",
        "api_key_env": "HF_TOKEN",
        "egress_class": "remote",
    },
    "custom-api": {
        "label": "Custom OpenAI-compatible HTTPS API",
        "kind": "openai-compatible",
        "model": "",
        "endpoint": "",
        "api_key_env": "ATBOT_API_KEY",
        "egress_class": "remote",
    },
}


def provider_profiles() -> dict[str, dict[str, Any]]:
    return {name: dict(value) for name, value in PROVIDER_PROFILES.items()}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _write_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


class AtBotServiceManager:
    """Install and supervise AtBot without granting it memory authority."""

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        self.root = Path(root).expanduser()
        self.config_path = self.root / "config.json"
        self.preference_path = self.root / "setup-preference.json"
        self.state_path = self.root / "service.json"
        self.log_path = self.root / "atbot.log"
        self.runtime_path = self.root / "runtime" / PINNED_ATBOT_VERSION

    @property
    def private_executable(self) -> Path:
        name = "atbot.exe" if os.name == "nt" else "atbot"
        directory = "Scripts" if os.name == "nt" else "bin"
        return self.runtime_path / directory / name

    def configure(
        self,
        *,
        profile: str = "local-ollama",
        model: str | None = None,
        endpoint: str | None = None,
        provider_kind: str | None = None,
        api_key_env: str | None = None,
        remote_egress_allowed: bool | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        if self.config_path.exists() and not force:
            raise ValueError(f"AtBot configuration already exists: {self.config_path} (use --force)")
        if profile not in PROVIDER_PROFILES:
            raise ValueError(f"unknown AtBot provider profile: {profile}")
        selected = PROVIDER_PROFILES[profile]
        selected_model = str(model if model is not None else selected["model"]).strip()
        selected_endpoint = str(endpoint if endpoint is not None else selected["endpoint"]).strip().rstrip("/")
        selected_kind = str(provider_kind if provider_kind is not None else selected["kind"])
        selected_key_env = api_key_env if api_key_env is not None else selected["api_key_env"]
        if not selected_model:
            raise ValueError("model is required for this provider profile")
        if not selected_endpoint:
            raise ValueError("endpoint is required for this provider profile")
        if selected_kind not in {"ollama", "openai-compatible", "anthropic"}:
            raise ValueError("provider kind must be ollama, openai-compatible, or anthropic")
        if selected_key_env and not re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", str(selected_key_env)):
            raise ValueError("API key environment variable must be an uppercase identifier")
        parsed = urlparse(selected_endpoint)
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        allow_remote = bool(
            selected["egress_class"] == "remote"
            if remote_egress_allowed is None
            else remote_egress_allowed
        )
        if not allow_remote and not local:
            raise ValueError("a non-loopback model endpoint requires --remote-egress-allowed")
        if not local and parsed.scheme != "https":
            raise ValueError("remote model endpoints must use HTTPS")
        value = {
            "format": "atbot-config-v1",
            "profile": "memory-companion",
            "host": "127.0.0.1",
            "port": 8770,
            "remote_egress_allowed": allow_remote,
            "providers": [
                {
                    "name": profile,
                    "kind": selected_kind,
                    "model": selected_model,
                    "endpoint": selected_endpoint,
                    "api_key_env": str(selected_key_env) if selected_key_env else None,
                    "egress_class": "local" if local else "remote",
                }
            ],
        }
        _write_private_json(self.config_path, value)
        self.preference_path.unlink(missing_ok=True)
        actions = []
        if selected_key_env and not os.environ.get(str(selected_key_env)):
            actions.append(f"Set `{selected_key_env}` in the AtBot service environment; the key is never stored in config.")
        if profile == "local-ollama":
            actions.append(f"Ensure Ollama is running and run `ollama pull {selected_model}` if the model is not installed.")
        return {
            "configured": True,
            "profile": profile,
            "config_path": str(self.config_path),
            "config": value,
            "setup_actions": actions,
        }

    def skip_setup(self) -> dict[str, Any]:
        _write_private_json(
            self.preference_path,
            {"format": "atmem-atbot-setup-preference-v1", "choice": "safe-fallback", "updated_at": _utc_now()},
        )
        return {
            "configured": False,
            "skipped": True,
            "running": False,
            "setup_actions": ["Run `atmem atbot setup` whenever you want model-assisted memory intelligence."],
        }

    def fallback_selected(self) -> bool:
        try:
            value = json.loads(self.preference_path.read_text(encoding="utf-8"))
            return value.get("choice") == "safe-fallback"
        except (OSError, json.JSONDecodeError):
            return False

    def install(self, *, force: bool = False) -> dict[str, Any]:
        if self.private_executable.is_file() and not force:
            installed = self._installed_version(self.private_executable)
            if installed == PINNED_ATBOT_VERSION:
                return {"installed": True, "changed": False, "version": installed, "executable": str(self.private_executable)}
        if self.runtime_path.exists():
            shutil.rmtree(self.runtime_path)
        self.runtime_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            # A venv is installed at its final path because its launchers embed
            # absolute paths and cannot safely be staged then renamed.
            subprocess.run([sys.executable, "-m", "venv", str(self.runtime_path)], check=True)
            pip = self.runtime_path / ("Scripts" if os.name == "nt" else "bin") / ("pip.exe" if os.name == "nt" else "pip")
            subprocess.run(
                [
                    str(pip),
                    "install",
                    "--disable-pip-version-check",
                    f"{ATBOT_DISTRIBUTION}=={PINNED_ATBOT_VERSION}",
                ],
                check=True,
            )
        except BaseException:
            if self.runtime_path.exists():
                shutil.rmtree(self.runtime_path)
            raise
        return {
            "installed": True,
            "changed": True,
            "version": PINNED_ATBOT_VERSION,
            "executable": str(self.private_executable),
            "package": f"{ATBOT_DISTRIBUTION}=={PINNED_ATBOT_VERSION}",
        }

    def _executable(self) -> Path | None:
        if self.private_executable.is_file():
            return self.private_executable
        discovered = shutil.which("atbot")
        return Path(discovered) if discovered else None

    @staticmethod
    def _installed_version(executable: Path) -> str | None:
        try:
            result = subprocess.run(
                [str(executable), "--version"], capture_output=True, text=True, timeout=5, check=False
            )
        except OSError:
            return None
        output = (result.stdout or result.stderr).strip().split()
        return output[-1] if result.returncode == 0 and output else None

    def _state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _owned_process(self, state: dict[str, Any]) -> bool:
        pid = int(state.get("pid") or 0)
        if not self._pid_alive(pid):
            return False
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except OSError:
            return False
        command = result.stdout.strip()
        return bool(command and str(state.get("executable") or "") in command and "serve" in command)

    def _endpoint(self) -> str:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
            return f"http://{value.get('host', '127.0.0.1')}:{int(value.get('port', 8770))}"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return "http://127.0.0.1:8770"

    def configured_egress_class(self) -> str:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
            provider = next(iter(value.get("providers") or []), {})
            return "remote" if provider.get("egress_class") == "remote" else "local"
        except (OSError, json.JSONDecodeError):
            return "local"

    def configured_provider(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
            provider = next(iter(value.get("providers") or []), None)
            if not isinstance(provider, dict):
                return None
            return {
                key: provider.get(key)
                for key in ("name", "kind", "model", "endpoint", "api_key_env", "egress_class")
            }
        except (OSError, json.JSONDecodeError):
            return None

    def status(self) -> dict[str, Any]:
        from atmem.control.atbot_companion import AtBotCompanionClient

        executable = self._executable()
        installed_version = self._installed_version(executable) if executable else None
        service = self._state()
        raw_health = AtBotCompanionClient(self._endpoint()).health()
        # The private companion CSRF credential is for AtMem's process only and
        # must never be forwarded through dashboard/status surfaces.
        health = {key: value for key, value in raw_health.items() if key != "csrf_token"}
        owned = self._owned_process(service)
        compatible = installed_version == PINNED_ATBOT_VERSION
        fallback_selected = self.fallback_selected()
        actions: list[str] = []
        if fallback_selected:
            actions.append("Safe fallback is selected. Run `atmem atbot setup` whenever you want model-assisted intelligence.")
        else:
            if not executable:
                actions.append("Run `atmem atbot install`.")
            elif not compatible:
                actions.append("Run `atmem atbot install --force` to install the pinned version.")
            if not self.config_path.is_file():
                actions.append("Run `atmem atbot configure`.")
            if executable and compatible and self.config_path.is_file() and not health.get("available"):
                actions.append("Run `atmem atbot start`.")
        configured_provider = next(
            (
                row
                for row in health.get("providers") or []
                if isinstance(row, dict) and row.get("name") != "deterministic-local"
            ),
            None,
        )
        if health.get("available") and configured_provider and not configured_provider.get("available"):
            actions.append(
                f"Configured provider `{configured_provider.get('name')}` is unavailable; check its model server and API-key environment variable."
            )
        process_available = bool(health.get("available"))
        return {
            "format": "atmem-atbot-service-status-v1",
            "role": "atmem-intelligence-companion",
            "installed": executable is not None,
            "configured": self.config_path.is_file(),
            "fallback_selected": fallback_selected,
            "setup_pending": not self.config_path.is_file() and not self.preference_path.is_file(),
            # Keep process state separate from effective intelligence state. A
            # user-selected fallback disables AtBot even if an unmanaged
            # companion happens to be listening on the loopback port.
            "running": process_available,
            "available": process_available and not fallback_selected,
            "managed_process": owned,
            "pid": int(service.get("pid") or 0) if owned else None,
            "endpoint": self._endpoint(),
            "executable": str(executable) if executable else None,
            "pinned_version": PINNED_ATBOT_VERSION,
            "installed_version": installed_version,
            "compatible": compatible,
            "health": health,
            "config_path": str(self.config_path),
            "provider": self.configured_provider(),
            "log_path": str(self.log_path),
            "setup_actions": actions,
        }

    def start(self) -> dict[str, Any]:
        # An explicit start re-enables AtBot after a previous fallback choice.
        self.preference_path.unlink(missing_ok=True)
        current = self.status()
        if current["running"]:
            return {**current, "changed": False}
        if not current["installed"] or not current["compatible"]:
            raise RuntimeError("the pinned AtBot runtime is not installed; run `atmem atbot install`")
        if not current["configured"]:
            raise RuntimeError("AtBot is not configured; run `atmem atbot configure`")
        executable = Path(str(current["executable"]))
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.log_path.open("ab") as log:
            process = subprocess.Popen(
                [str(executable), "--config", str(self.config_path), "serve"],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        _write_private_json(
            self.state_path,
            {"format": "atmem-atbot-service-v1", "pid": process.pid, "executable": str(executable), "started_at": _utc_now()},
        )
        for _ in range(30):
            refreshed = self.status()
            if refreshed["running"]:
                return {**refreshed, "changed": True}
            if process.poll() is not None:
                break
            time.sleep(0.1)
        raise RuntimeError(f"AtBot did not become ready; inspect {self.log_path}")

    def stop(self) -> dict[str, Any]:
        service = self._state()
        if not self._owned_process(service):
            self.state_path.unlink(missing_ok=True)
            return {**self.status(), "changed": False}
        pid = int(service["pid"])
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            try:
                waited, _ = os.waitpid(pid, os.WNOHANG)
                if waited == pid:
                    break
            except (ChildProcessError, OSError):
                pass
            if not self._pid_alive(pid):
                break
            time.sleep(0.1)
        if self._pid_alive(pid):
            raise RuntimeError("AtBot did not stop after SIGTERM")
        self.state_path.unlink(missing_ok=True)
        return {**self.status(), "changed": True}

    def ensure_running(self) -> dict[str, Any]:
        current = self.status()
        if current["fallback_selected"]:
            return {**current, "available": False, "managed_start": False}
        if current["running"]:
            return {**current, "managed_start": False}
        if not (current["installed"] and current["compatible"] and current["configured"]):
            return {**current, "managed_start": False}
        try:
            return {**self.start(), "managed_start": True}
        except RuntimeError as exc:
            return {**self.status(), "managed_start": True, "reason": str(exc)}

    def doctor(self) -> dict[str, Any]:
        status = self.status()
        health = status["health"]
        protocol = str(health.get("protocol_version") or "")
        providers = [row for row in health.get("providers") or [] if isinstance(row, dict)]
        configured_provider = next(
            (row for row in providers if row.get("name") != "deterministic-local"), None
        )
        checks = {
            "pinned_runtime": bool(status["installed"] and status["compatible"]),
            "private_configuration": bool(status["configured"]),
            "loopback_service": urlparse(str(status["endpoint"])).hostname in {"127.0.0.1", "localhost", "::1"},
            "companion_ready": bool(status["running"]),
            "authority_boundary": health.get("canonical_storage") is False if status["running"] else True,
            "protocol_compatible": protocol == ATBOT_PROTOCOL_VERSION if status["running"] else True,
            "configured_provider_ready": bool(configured_provider and configured_provider.get("available")) if status["running"] else True,
            "atmem_fallback_ready": True,
        }
        return {
            **status,
            "format": "atmem-atbot-doctor-v1",
            "healthy": all(checks.values()),
            "degraded_safe": not status["running"],
            "checks": checks,
        }

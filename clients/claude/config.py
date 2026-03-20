# clients/claude/config.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WebhookConfig:
    on_question: str | None = None
    on_spiraling: str | None = None
    on_timeout: str | None = None


@dataclass
class TrustConfig:
    agents: str = "vote"           # "vote" | "first" | "consensus" | "never"
    timeout_minutes: int = 30
    timeout_action: str = "pause"  # "pause" | "deny" | "abort"


@dataclass
class DaemonConfig:
    server_name: str
    irc_host: str = "127.0.0.1"
    irc_port: int = 6667
    agent_name: str = "claude"
    channels: list[str] = field(default_factory=lambda: ["#general"])
    ipc_socket: str = ""           # default: /tmp/agentirc-{server_name}-{agent_name}.sock
    supervisor_model: str = "claude-opus-4-6"
    working_dir: str = "."
    webhooks: WebhookConfig = field(default_factory=WebhookConfig)
    trust: TrustConfig = field(default_factory=TrustConfig)

    def __post_init__(self) -> None:
        if not self.ipc_socket:
            self.ipc_socket = (
                f"/tmp/agentirc-{self.server_name}-{self.agent_name}.sock"
            )

    @classmethod
    def from_yaml(cls, path: str) -> "DaemonConfig":
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        webhooks_data = data.pop("webhooks", {}) or {}
        trust_data = data.pop("trust", {}) or {}

        webhooks = WebhookConfig(**{
            k: v for k, v in webhooks_data.items()
            if k in WebhookConfig.__dataclass_fields__
        })
        trust = TrustConfig(**{
            k: v for k, v in trust_data.items()
            if k in TrustConfig.__dataclass_fields__
        })

        valid_keys = {f for f in cls.__dataclass_fields__ if f not in ("webhooks", "trust")}
        filtered = {k: v for k, v in data.items() if k in valid_keys}

        return cls(**filtered, webhooks=webhooks, trust=trust)

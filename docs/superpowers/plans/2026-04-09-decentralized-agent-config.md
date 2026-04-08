# Decentralized Agent Configuration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the central `~/.culture/agents.yaml` with per-directory `culture.yaml` files and a lightweight `~/.culture/server.yaml` manifest, enabling decentralized agent definitions that live alongside the code they serve.

**Architecture:** New unified `culture/config.py` module handles both `server.yaml` (machine-level: server connection, supervisor, webhooks, agent manifest) and `culture.yaml` (per-directory: agent identity and config). CLI gains `register`/`unregister`/`migrate` commands. Existing `agents.yaml` continues working via auto-detection fallback. Backend `config.py` files become thin re-exports.

**Tech Stack:** Python 3.12, PyYAML, dataclasses, pytest, asyncio

**Spec:** `docs/superpowers/specs/2026-04-09-decentralized-agent-config-design.md`

---

### Task 1: Unified Config Module — Data Types

**Files:**

- Create: `culture/config.py`
- Test: `tests/test_culture_config.py`

- [ ] **Step 1: Write failing tests for new dataclasses**

```python
# tests/test_culture_config.py
import os
import tempfile

import pytest


def test_agent_config_defaults():
    """AgentConfig has correct defaults and computed properties."""
    from culture.config import AgentConfig

    agent = AgentConfig()
    assert agent.suffix == ""
    assert agent.backend == "claude"
    assert agent.channels == ["#general"]
    assert agent.model == "claude-opus-4-6"
    assert agent.thinking == "medium"
    assert agent.system_prompt == ""
    assert agent.tags == []
    assert agent.icon is None
    assert agent.archived is False
    assert agent.extras == {}
    # Computed fields
    assert agent.nick == ""
    assert agent.directory == "."
    # Backward compat
    assert agent.agent == "claude"


def test_agent_config_acp_command_from_extras():
    """ACP command is read from extras dict."""
    from culture.config import AgentConfig

    agent = AgentConfig(extras={"acp_command": ["cline", "--acp"]})
    assert agent.acp_command == ["cline", "--acp"]

    # Default when not in extras
    agent2 = AgentConfig()
    assert agent2.acp_command == ["opencode", "acp"]


def test_server_config_defaults():
    """ServerConfig has correct defaults."""
    from culture.config import ServerConfig, ServerConnConfig

    config = ServerConfig()
    assert config.server.name == "culture"
    assert config.server.host == "localhost"
    assert config.server.port == 6667
    assert config.buffer_size == 500
    assert config.poll_interval == 60
    assert config.manifest == {}
    assert config.agents == []


def test_server_config_get_agent():
    """get_agent() looks up by nick."""
    from culture.config import AgentConfig, ServerConfig

    config = ServerConfig(agents=[
        AgentConfig(suffix="culture", nick="spark-culture"),
        AgentConfig(suffix="daria", nick="spark-daria"),
    ])
    assert config.get_agent("spark-culture").suffix == "culture"
    assert config.get_agent("spark-daria").suffix == "daria"
    assert config.get_agent("nonexistent") is None


def test_daemon_config_alias():
    """DaemonConfig is an alias for ServerConfig."""
    from culture.config import DaemonConfig, ServerConfig

    assert DaemonConfig is ServerConfig
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_culture_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'culture.config'`

- [ ] **Step 3: Implement the dataclasses**

```python
# culture/config.py
"""Unified configuration for culture agents and servers.

Handles both server.yaml (machine-level config + agent manifest)
and culture.yaml (per-directory agent definitions).
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass
class ServerConnConfig:
    """IRC server connection settings."""

    name: str = "culture"
    host: str = "localhost"
    port: int = 6667
    archived: bool = False
    archived_at: str = ""
    archived_reason: str = ""


@dataclass
class SupervisorConfig:
    """Supervisor sub-agent settings."""

    model: str = "claude-sonnet-4-6"
    thinking: str = "medium"
    window_size: int = 20
    eval_interval: int = 5
    escalation_threshold: int = 3
    prompt_override: str = ""


@dataclass
class WebhookConfig:
    """Webhook alerting settings."""

    url: str | None = None
    irc_channel: str = "#alerts"
    events: list[str] = field(
        default_factory=lambda: [
            "agent_spiraling",
            "agent_error",
            "agent_question",
            "agent_timeout",
            "agent_complete",
        ]
    )


@dataclass
class AgentConfig:
    """Per-agent settings loaded from culture.yaml."""

    suffix: str = ""
    backend: str = "claude"
    channels: list[str] = field(default_factory=lambda: ["#general"])
    model: str = "claude-opus-4-6"
    thinking: str = "medium"
    system_prompt: str = ""
    tags: list[str] = field(default_factory=list)
    icon: str | None = None
    archived: bool = False
    archived_at: str = ""
    archived_reason: str = ""
    extras: dict = field(default_factory=dict)

    # Computed at load time, not stored in YAML
    nick: str = ""
    directory: str = "."

    @property
    def agent(self) -> str:
        """Backward compatibility alias for backend."""
        return self.backend

    @property
    def acp_command(self) -> list[str]:
        """ACP-specific: command to spawn the ACP process."""
        return self.extras.get("acp_command", ["opencode", "acp"])


@dataclass
class ServerConfig:
    """Server configuration from server.yaml."""

    server: ServerConnConfig = field(default_factory=ServerConnConfig)
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    webhooks: WebhookConfig = field(default_factory=WebhookConfig)
    buffer_size: int = 500
    poll_interval: int = 60
    sleep_start: str = "23:00"
    sleep_end: str = "08:00"
    manifest: dict[str, str] = field(default_factory=dict)
    agents: list[AgentConfig] = field(default_factory=list)

    def get_agent(self, nick: str) -> AgentConfig | None:
        for agent in self.agents:
            if agent.nick == nick:
                return agent
        return None


# Backward compatibility alias
DaemonConfig = ServerConfig


def sanitize_agent_name(dirname: str) -> str:
    """Sanitize a directory name into a valid agent/server name."""
    name = dirname.lower()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    if not name:
        raise ValueError(f"sanitized name is empty for input: {dirname!r}")
    return name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_culture_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add culture/config.py tests/test_culture_config.py
git commit -m "feat: add unified config module with AgentConfig and ServerConfig"
```

---

### Task 2: culture.yaml Loading

**Files:**

- Modify: `culture/config.py`
- Test: `tests/test_culture_config.py`

- [ ] **Step 1: Write failing tests for culture.yaml loading**

```python
# Append to tests/test_culture_config.py

def test_load_culture_yaml_single_agent(tmp_path):
    """Load single-agent culture.yaml."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
suffix: myagent
backend: claude
model: claude-opus-4-6
channels: ["#general", "#dev"]
thinking: medium
system_prompt: "You are helpful."
tags: [test]
""")
    agents = load_culture_yaml(str(tmp_path))
    assert len(agents) == 1
    assert agents[0].suffix == "myagent"
    assert agents[0].backend == "claude"
    assert agents[0].model == "claude-opus-4-6"
    assert agents[0].channels == ["#general", "#dev"]
    assert agents[0].thinking == "medium"
    assert agents[0].system_prompt == "You are helpful."
    assert agents[0].tags == ["test"]
    assert agents[0].directory == str(tmp_path)


def test_load_culture_yaml_multi_agent(tmp_path):
    """Load multi-agent culture.yaml with agents list."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
agents:
  - suffix: culture
    backend: claude
    model: claude-opus-4-6
  - suffix: codex
    backend: codex
    model: gpt-5.4
""")
    agents = load_culture_yaml(str(tmp_path))
    assert len(agents) == 2
    assert agents[0].suffix == "culture"
    assert agents[0].backend == "claude"
    assert agents[1].suffix == "codex"
    assert agents[1].backend == "codex"
    assert agents[1].model == "gpt-5.4"


def test_load_culture_yaml_by_suffix(tmp_path):
    """Load specific agent from multi-agent culture.yaml."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
agents:
  - suffix: culture
    backend: claude
  - suffix: codex
    backend: codex
""")
    agents = load_culture_yaml(str(tmp_path), suffix="codex")
    assert len(agents) == 1
    assert agents[0].suffix == "codex"


def test_load_culture_yaml_extras(tmp_path):
    """Unknown fields stored in extras dict."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("""\
suffix: daria
backend: acp
model: claude-sonnet-4-6
acp_command: ["opencode", "acp"]
custom_field: hello
""")
    agents = load_culture_yaml(str(tmp_path))
    assert agents[0].acp_command == ["opencode", "acp"]
    assert agents[0].extras["custom_field"] == "hello"


def test_load_culture_yaml_missing_file(tmp_path):
    """Missing culture.yaml raises FileNotFoundError."""
    from culture.config import load_culture_yaml

    with pytest.raises(FileNotFoundError):
        load_culture_yaml(str(tmp_path))


def test_load_culture_yaml_suffix_not_found(tmp_path):
    """Requesting nonexistent suffix raises ValueError."""
    from culture.config import load_culture_yaml

    culture_yaml = tmp_path / "culture.yaml"
    culture_yaml.write_text("suffix: culture\nbackend: claude\n")

    with pytest.raises(ValueError, match="not found"):
        load_culture_yaml(str(tmp_path), suffix="nonexistent")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_culture_config.py::test_load_culture_yaml_single_agent -v`
Expected: FAIL — `cannot import name 'load_culture_yaml'`

- [ ] **Step 3: Implement load_culture_yaml**

Add to `culture/config.py`:

```python
CULTURE_YAML = "culture.yaml"

# Fields that are typed on AgentConfig (not extras)
_KNOWN_AGENT_FIELDS = {f.name for f in AgentConfig.__dataclass_fields__.values()} - {
    "nick",
    "directory",
    "extras",
}


def _parse_agent_entry(raw: dict, directory: str) -> AgentConfig:
    """Parse a single agent entry from culture.yaml."""
    known = {}
    extras = {}
    for k, v in raw.items():
        if k in _KNOWN_AGENT_FIELDS:
            known[k] = v
        else:
            extras[k] = v
    agent = AgentConfig(**known, extras=extras, directory=directory)
    return agent


def load_culture_yaml(
    directory: str, suffix: str | None = None
) -> list[AgentConfig]:
    """Load agent definitions from a culture.yaml file.

    Args:
        directory: Path to directory containing culture.yaml.
        suffix: If provided, return only the agent matching this suffix.

    Returns:
        List of AgentConfig objects with directory set.

    Raises:
        FileNotFoundError: If culture.yaml doesn't exist.
        ValueError: If suffix is specified but not found.
    """
    path = Path(directory) / CULTURE_YAML
    if not path.exists():
        raise FileNotFoundError(f"No culture.yaml found at {path}")

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    directory = str(Path(directory).resolve())

    # Multi-agent format: top-level "agents" list
    if "agents" in raw and isinstance(raw["agents"], list):
        agents = [_parse_agent_entry(entry, directory) for entry in raw["agents"]]
    else:
        # Single-agent format: top-level fields
        agents = [_parse_agent_entry(raw, directory)]

    if suffix is not None:
        filtered = [a for a in agents if a.suffix == suffix]
        if not filtered:
            raise ValueError(
                f"Agent with suffix {suffix!r} not found in {path}"
            )
        return filtered

    return agents
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_culture_config.py -v -k "culture_yaml"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add culture/config.py tests/test_culture_config.py
git commit -m "feat: add culture.yaml loading with single/multi-agent support"
```

---

### Task 3: server.yaml Loading and Agent Resolution

**Files:**

- Modify: `culture/config.py`
- Test: `tests/test_culture_config.py`

- [ ] **Step 1: Write failing tests for server.yaml loading**

```python
# Append to tests/test_culture_config.py

def test_load_server_config(tmp_path):
    """Load server.yaml with manifest."""
    from culture.config import load_server_config

    server_yaml = tmp_path / "server.yaml"
    server_yaml.write_text("""\
server:
  name: spark
  host: 127.0.0.1
  port: 6667

supervisor:
  model: claude-sonnet-4-6
  thinking: medium

webhooks:
  url: https://example.com/hook
  irc_channel: "#alerts"
  events: [agent_error]

buffer_size: 300
poll_interval: 30

agents:
  culture: /tmp/proj-a
  daria: /tmp/proj-b
""")
    config = load_server_config(str(server_yaml))
    assert config.server.name == "spark"
    assert config.server.host == "127.0.0.1"
    assert config.supervisor.model == "claude-sonnet-4-6"
    assert config.webhooks.url == "https://example.com/hook"
    assert config.buffer_size == 300
    assert config.poll_interval == 30
    assert config.manifest == {"culture": "/tmp/proj-a", "daria": "/tmp/proj-b"}
    # agents list is NOT populated by load_server_config — needs resolve_agents
    assert config.agents == []


def test_load_server_config_defaults(tmp_path):
    """Minimal server.yaml gets defaults."""
    from culture.config import load_server_config

    server_yaml = tmp_path / "server.yaml"
    server_yaml.write_text("server:\n  name: spark\n")
    config = load_server_config(str(server_yaml))
    assert config.server.name == "spark"
    assert config.server.host == "localhost"
    assert config.buffer_size == 500
    assert config.manifest == {}


def test_resolve_agents(tmp_path):
    """resolve_agents reads culture.yaml from manifest paths."""
    from culture.config import ServerConfig, ServerConnConfig, load_culture_yaml, resolve_agents

    # Create two project directories with culture.yaml
    proj_a = tmp_path / "proj-a"
    proj_a.mkdir()
    (proj_a / "culture.yaml").write_text("suffix: culture\nbackend: claude\n")

    proj_b = tmp_path / "proj-b"
    proj_b.mkdir()
    (proj_b / "culture.yaml").write_text("suffix: daria\nbackend: acp\nacp_command: ['opencode', 'acp']\n")

    config = ServerConfig(
        server=ServerConnConfig(name="spark"),
        manifest={
            "culture": str(proj_a),
            "daria": str(proj_b),
        },
    )
    resolve_agents(config)

    assert len(config.agents) == 2
    culture = config.get_agent("spark-culture")
    assert culture is not None
    assert culture.backend == "claude"
    assert culture.directory == str(proj_a.resolve())

    daria = config.get_agent("spark-daria")
    assert daria is not None
    assert daria.backend == "acp"
    assert daria.directory == str(proj_b.resolve())


def test_resolve_agents_missing_culture_yaml(tmp_path):
    """Missing culture.yaml logs warning, agent skipped."""
    from culture.config import ServerConfig, ServerConnConfig, resolve_agents

    config = ServerConfig(
        server=ServerConnConfig(name="spark"),
        manifest={"ghost": str(tmp_path / "nonexistent")},
    )
    resolve_agents(config)
    assert len(config.agents) == 0


def test_resolve_agents_multi_agent_directory(tmp_path):
    """Two manifest entries pointing to same multi-agent directory."""
    from culture.config import ServerConfig, ServerConnConfig, resolve_agents

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "culture.yaml").write_text("""\
agents:
  - suffix: culture
    backend: claude
  - suffix: codex
    backend: codex
    model: gpt-5.4
""")

    config = ServerConfig(
        server=ServerConnConfig(name="spark"),
        manifest={
            "culture": str(proj),
            "codex": str(proj),
        },
    )
    resolve_agents(config)

    assert len(config.agents) == 2
    assert config.get_agent("spark-culture").backend == "claude"
    assert config.get_agent("spark-codex").backend == "codex"
    assert config.get_agent("spark-codex").model == "gpt-5.4"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_culture_config.py -v -k "server_config or resolve_agents"`
Expected: FAIL

- [ ] **Step 3: Implement load_server_config and resolve_agents**

Add to `culture/config.py`:

```python
import logging

logger = logging.getLogger("culture")


def load_server_config(path: str | Path) -> ServerConfig:
    """Load server configuration from server.yaml.

    Populates server, supervisor, webhooks, and manifest.
    Does NOT resolve agents — call resolve_agents() separately.
    """
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    server = ServerConnConfig(**raw.get("server", {}))
    supervisor = SupervisorConfig(**raw.get("supervisor", {}))
    webhooks = WebhookConfig(**raw.get("webhooks", {}))

    # The agents key in server.yaml is the manifest (suffix -> directory),
    # not a list of agent configs.
    manifest = raw.get("agents", {})
    if isinstance(manifest, list):
        # Not a manifest — this is legacy agents.yaml format
        manifest = {}

    return ServerConfig(
        server=server,
        supervisor=supervisor,
        webhooks=webhooks,
        buffer_size=raw.get("buffer_size", 500),
        poll_interval=raw.get("poll_interval", 60),
        sleep_start=raw.get("sleep_start", "23:00"),
        sleep_end=raw.get("sleep_end", "08:00"),
        manifest=manifest,
    )


def resolve_agents(config: ServerConfig) -> None:
    """Resolve agent configs from manifest paths.

    Reads each culture.yaml, computes nicks, populates config.agents.
    Skips entries where culture.yaml is missing (logs warning).
    """
    config.agents = []
    server_name = config.server.name

    for suffix, directory in config.manifest.items():
        try:
            agents = load_culture_yaml(directory, suffix=suffix)
        except FileNotFoundError:
            logger.warning(
                "culture.yaml missing for %s-%s at %s — skipping",
                server_name,
                suffix,
                directory,
            )
            continue
        except ValueError as e:
            logger.warning(
                "Error loading %s-%s from %s: %s — skipping",
                server_name,
                suffix,
                directory,
                e,
            )
            continue

        for agent in agents:
            agent.nick = f"{server_name}-{agent.suffix}"
            config.agents.append(agent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_culture_config.py -v -k "server_config or resolve_agents"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add culture/config.py tests/test_culture_config.py
git commit -m "feat: add server.yaml loading and agent resolution from manifest"
```

---

### Task 4: Auto-Detecting Config Format and Legacy Fallback

**Files:**

- Modify: `culture/config.py`
- Test: `tests/test_culture_config.py`

- [ ] **Step 1: Write failing tests for auto-detection**

```python
# Append to tests/test_culture_config.py

def test_load_config_server_yaml(tmp_path):
    """load_config auto-detects server.yaml format."""
    from culture.config import load_config

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "culture.yaml").write_text("suffix: culture\nbackend: claude\n")

    server_yaml = tmp_path / "server.yaml"
    server_yaml.write_text(f"""\
server:
  name: spark
  host: localhost
  port: 6667
agents:
  culture: {proj}
""")
    config = load_config(str(server_yaml))
    assert config.server.name == "spark"
    assert len(config.agents) == 1
    assert config.agents[0].nick == "spark-culture"


def test_load_config_legacy_agents_yaml(tmp_path):
    """load_config falls back to legacy agents.yaml parsing."""
    from culture.config import load_config

    agents_yaml = tmp_path / "agents.yaml"
    agents_yaml.write_text("""\
server:
  name: spark
  host: localhost
  port: 6667
agents:
  - nick: spark-culture
    directory: /tmp/work
    channels: ["#general"]
    model: claude-opus-4-6
""")
    config = load_config(str(agents_yaml))
    assert config.server.name == "spark"
    assert len(config.agents) == 1
    assert config.agents[0].nick == "spark-culture"


def test_load_config_or_default_missing(tmp_path):
    """Missing file returns default config."""
    from culture.config import load_config_or_default

    config = load_config_or_default(str(tmp_path / "missing.yaml"))
    assert config.server.name == "culture"
    assert config.agents == []


def test_save_server_config(tmp_path):
    """save_server_config writes server.yaml atomically."""
    from culture.config import ServerConfig, ServerConnConfig, load_server_config, save_server_config

    path = tmp_path / "server.yaml"
    config = ServerConfig(
        server=ServerConnConfig(name="spark", host="10.0.0.1", port=6668),
        manifest={"culture": "/tmp/proj"},
    )
    save_server_config(str(path), config)

    loaded = load_server_config(str(path))
    assert loaded.server.name == "spark"
    assert loaded.server.host == "10.0.0.1"
    assert loaded.manifest == {"culture": "/tmp/proj"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_culture_config.py -v -k "load_config_server or load_config_legacy or load_config_or_default_missing or save_server"`
Expected: FAIL

- [ ] **Step 3: Implement load_config, load_config_or_default, save_server_config**

Add to `culture/config.py`:

```python
def _is_server_yaml(raw: dict) -> bool:
    """Detect whether raw YAML is server.yaml format (manifest) vs legacy agents.yaml."""
    agents = raw.get("agents")
    if agents is None:
        return True  # No agents key — treat as server.yaml
    if isinstance(agents, dict):
        return True  # Dict = manifest (server.yaml)
    if isinstance(agents, list) and agents and isinstance(agents[0], dict):
        # List of dicts — legacy agents.yaml if they have "nick" key
        return "nick" in agents[0]  # False = legacy
    return True  # Empty list, ambiguous — default to server.yaml


def _load_legacy_config(path: str | Path) -> ServerConfig:
    """Load legacy agents.yaml format into ServerConfig."""
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    server = ServerConnConfig(**raw.get("server", {}))
    supervisor = SupervisorConfig(**raw.get("supervisor", {}))
    webhooks = WebhookConfig(**raw.get("webhooks", {}))

    agents = []
    known = _KNOWN_AGENT_FIELDS | {"nick", "directory"}
    for agent_raw in raw.get("agents", []):
        known_fields = {}
        extras = {}
        for k, v in agent_raw.items():
            if k in known:
                # Map legacy "agent" field to "backend"
                if k == "agent":
                    known_fields["backend"] = v
                else:
                    known_fields[k] = v
            else:
                extras[k] = v
        agents.append(AgentConfig(**known_fields, extras=extras))

    return ServerConfig(
        server=server,
        supervisor=supervisor,
        webhooks=webhooks,
        buffer_size=raw.get("buffer_size", 500),
        poll_interval=raw.get("poll_interval", 60),
        sleep_start=raw.get("sleep_start", "23:00"),
        sleep_end=raw.get("sleep_end", "08:00"),
        agents=agents,
    )


def load_config(path: str | Path) -> ServerConfig:
    """Load config, auto-detecting format (server.yaml vs legacy agents.yaml).

    For server.yaml: loads manifest and resolves agent configs from culture.yaml files.
    For legacy agents.yaml: loads agents inline.
    """
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    agents_val = raw.get("agents")
    is_legacy = isinstance(agents_val, list) and agents_val and isinstance(agents_val[0], dict) and "nick" in agents_val[0]

    if is_legacy:
        return _load_legacy_config(path)

    config = load_server_config(path)
    resolve_agents(config)
    return config


def load_config_or_default(path: str | Path) -> ServerConfig:
    """Load config from path, returning default ServerConfig if missing."""
    path = Path(path)
    if not path.exists():
        return ServerConfig()
    return load_config(path)


def save_server_config(path: str | Path, config: ServerConfig) -> None:
    """Write server.yaml atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "server": asdict(config.server),
        "supervisor": asdict(config.supervisor),
        "webhooks": asdict(config.webhooks),
        "buffer_size": config.buffer_size,
        "poll_interval": config.poll_interval,
        "sleep_start": config.sleep_start,
        "sleep_end": config.sleep_end,
        "agents": config.manifest,
    }

    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_culture_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add culture/config.py tests/test_culture_config.py
git commit -m "feat: auto-detect config format with legacy agents.yaml fallback"
```

---

### Task 5: culture.yaml Save and Manifest Management

**Files:**

- Modify: `culture/config.py`
- Test: `tests/test_culture_config.py`

- [ ] **Step 1: Write failing tests for save_culture_yaml and manifest ops**

```python
# Append to tests/test_culture_config.py

def test_save_culture_yaml_single(tmp_path):
    """Save single-agent culture.yaml."""
    from culture.config import AgentConfig, load_culture_yaml, save_culture_yaml

    agent = AgentConfig(suffix="myagent", backend="claude", model="claude-opus-4-6")
    save_culture_yaml(str(tmp_path), [agent])

    loaded = load_culture_yaml(str(tmp_path))
    assert len(loaded) == 1
    assert loaded[0].suffix == "myagent"
    assert loaded[0].backend == "claude"


def test_save_culture_yaml_multi(tmp_path):
    """Save multi-agent culture.yaml."""
    from culture.config import AgentConfig, load_culture_yaml, save_culture_yaml

    agents = [
        AgentConfig(suffix="culture", backend="claude"),
        AgentConfig(suffix="codex", backend="codex", model="gpt-5.4"),
    ]
    save_culture_yaml(str(tmp_path), agents)

    loaded = load_culture_yaml(str(tmp_path))
    assert len(loaded) == 2
    assert loaded[0].suffix == "culture"
    assert loaded[1].suffix == "codex"


def test_save_culture_yaml_preserves_extras(tmp_path):
    """Backend-specific fields round-trip through extras."""
    from culture.config import AgentConfig, load_culture_yaml, save_culture_yaml

    agent = AgentConfig(
        suffix="daria",
        backend="acp",
        extras={"acp_command": ["opencode", "acp"]},
    )
    save_culture_yaml(str(tmp_path), [agent])

    loaded = load_culture_yaml(str(tmp_path))
    assert loaded[0].acp_command == ["opencode", "acp"]


def test_add_to_manifest(tmp_path):
    """Add entry to server.yaml manifest."""
    from culture.config import (
        ServerConfig,
        ServerConnConfig,
        add_to_manifest,
        save_server_config,
        load_server_config,
    )

    path = tmp_path / "server.yaml"
    config = ServerConfig(server=ServerConnConfig(name="spark"))
    save_server_config(str(path), config)

    add_to_manifest(str(path), "culture", "/tmp/proj")

    loaded = load_server_config(str(path))
    assert loaded.manifest == {"culture": "/tmp/proj"}


def test_add_to_manifest_collision(tmp_path):
    """Duplicate suffix raises ValueError."""
    from culture.config import (
        ServerConfig,
        ServerConnConfig,
        add_to_manifest,
        save_server_config,
    )

    path = tmp_path / "server.yaml"
    config = ServerConfig(
        server=ServerConnConfig(name="spark"),
        manifest={"culture": "/tmp/proj"},
    )
    save_server_config(str(path), config)

    with pytest.raises(ValueError, match="already registered"):
        add_to_manifest(str(path), "culture", "/tmp/other")


def test_remove_from_manifest(tmp_path):
    """Remove entry from manifest."""
    from culture.config import (
        ServerConfig,
        ServerConnConfig,
        remove_from_manifest,
        save_server_config,
        load_server_config,
    )

    path = tmp_path / "server.yaml"
    config = ServerConfig(
        server=ServerConnConfig(name="spark"),
        manifest={"culture": "/tmp/a", "daria": "/tmp/b"},
    )
    save_server_config(str(path), config)

    remove_from_manifest(str(path), "culture")

    loaded = load_server_config(str(path))
    assert loaded.manifest == {"daria": "/tmp/b"}


def test_remove_from_manifest_not_found(tmp_path):
    """Removing nonexistent suffix raises ValueError."""
    from culture.config import (
        ServerConfig,
        ServerConnConfig,
        remove_from_manifest,
        save_server_config,
    )

    path = tmp_path / "server.yaml"
    config = ServerConfig(server=ServerConnConfig(name="spark"))
    save_server_config(str(path), config)

    with pytest.raises(ValueError, match="not found"):
        remove_from_manifest(str(path), "ghost")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_culture_config.py -v -k "save_culture or manifest"`
Expected: FAIL

- [ ] **Step 3: Implement save_culture_yaml, add_to_manifest, remove_from_manifest**

Add to `culture/config.py`:

```python
def _agent_to_yaml_dict(agent: AgentConfig) -> dict:
    """Convert AgentConfig to a dict suitable for YAML serialization."""
    data = {
        "suffix": agent.suffix,
        "backend": agent.backend,
    }
    # Only include non-default fields
    defaults = AgentConfig()
    if agent.channels != defaults.channels:
        data["channels"] = agent.channels
    if agent.model != defaults.model:
        data["model"] = agent.model
    if agent.thinking != defaults.thinking:
        data["thinking"] = agent.thinking
    if agent.system_prompt:
        data["system_prompt"] = agent.system_prompt
    if agent.tags:
        data["tags"] = agent.tags
    if agent.icon is not None:
        data["icon"] = agent.icon
    if agent.archived:
        data["archived"] = agent.archived
        data["archived_at"] = agent.archived_at
        data["archived_reason"] = agent.archived_reason
    # Merge extras
    data.update(agent.extras)
    return data


def save_culture_yaml(directory: str, agents: list[AgentConfig]) -> None:
    """Write culture.yaml atomically. Single-agent uses flat format."""
    path = Path(directory) / CULTURE_YAML
    path.parent.mkdir(parents=True, exist_ok=True)

    if len(agents) == 1:
        data = _agent_to_yaml_dict(agents[0])
    else:
        data = {"agents": [_agent_to_yaml_dict(a) for a in agents]}

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_server_raw(path: str | Path) -> dict:
    """Load raw server.yaml YAML."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_server_raw(path: str | Path, raw: dict) -> None:
    """Write raw server.yaml atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(raw, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def add_to_manifest(path: str | Path, suffix: str, directory: str) -> None:
    """Add an agent to the server.yaml manifest.

    Raises ValueError if suffix is already registered.
    """
    raw = _load_server_raw(path)
    agents = raw.setdefault("agents", {})
    if not isinstance(agents, dict):
        agents = {}
        raw["agents"] = agents
    if suffix in agents:
        raise ValueError(
            f"Agent suffix {suffix!r} already registered at {agents[suffix]}"
        )
    agents[suffix] = str(Path(directory).resolve())
    _save_server_raw(path, raw)


def remove_from_manifest(path: str | Path, suffix: str) -> None:
    """Remove an agent from the server.yaml manifest.

    Raises ValueError if suffix is not found.
    """
    raw = _load_server_raw(path)
    agents = raw.get("agents", {})
    if not isinstance(agents, dict) or suffix not in agents:
        raise ValueError(f"Agent suffix {suffix!r} not found in manifest")
    del agents[suffix]
    _save_server_raw(path, raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_culture_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add culture/config.py tests/test_culture_config.py
git commit -m "feat: add culture.yaml save and manifest management functions"
```

---

### Task 6: CLI — Register and Unregister Commands

**Files:**

- Modify: `culture/cli/agent.py`
- Modify: `culture/cli/shared/constants.py`
- Test: `tests/test_register_cli.py`

- [ ] **Step 1: Write failing tests for register/unregister**

```python
# tests/test_register_cli.py
import argparse
import os
import tempfile
import shutil

import pytest


def test_register_current_dir(tmp_path, monkeypatch):
    """Register with no path uses cwd."""
    from culture.config import load_server_config, save_server_config, ServerConfig, ServerConnConfig

    # Set up server.yaml
    server_yaml = tmp_path / "server.yaml"
    save_server_config(str(server_yaml), ServerConfig(server=ServerConnConfig(name="spark")))

    # Create culture.yaml in a project dir
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "culture.yaml").write_text("suffix: myagent\nbackend: claude\n")

    monkeypatch.chdir(str(proj))

    from culture.cli.agent import _cmd_register

    args = argparse.Namespace(config=str(server_yaml), path=None, suffix=None)
    _cmd_register(args)

    config = load_server_config(str(server_yaml))
    assert "myagent" in config.manifest
    assert config.manifest["myagent"] == str(proj.resolve())


def test_register_explicit_path(tmp_path):
    """Register with explicit path."""
    from culture.config import load_server_config, save_server_config, ServerConfig, ServerConnConfig

    server_yaml = tmp_path / "server.yaml"
    save_server_config(str(server_yaml), ServerConfig(server=ServerConnConfig(name="spark")))

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "culture.yaml").write_text("suffix: myagent\nbackend: claude\n")

    from culture.cli.agent import _cmd_register

    args = argparse.Namespace(config=str(server_yaml), path=str(proj), suffix=None)
    _cmd_register(args)

    config = load_server_config(str(server_yaml))
    assert "myagent" in config.manifest


def test_register_multi_agent_needs_suffix(tmp_path, capsys):
    """Multi-agent culture.yaml without --suffix errors."""
    from culture.config import save_server_config, ServerConfig, ServerConnConfig

    server_yaml = tmp_path / "server.yaml"
    save_server_config(str(server_yaml), ServerConfig(server=ServerConnConfig(name="spark")))

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "culture.yaml").write_text("""\
agents:
  - suffix: a
    backend: claude
  - suffix: b
    backend: codex
""")

    from culture.cli.agent import _cmd_register

    args = argparse.Namespace(config=str(server_yaml), path=str(proj), suffix=None)
    with pytest.raises(SystemExit):
        _cmd_register(args)


def test_register_no_culture_yaml(tmp_path, capsys):
    """Register dir without culture.yaml errors."""
    from culture.config import save_server_config, ServerConfig, ServerConnConfig

    server_yaml = tmp_path / "server.yaml"
    save_server_config(str(server_yaml), ServerConfig(server=ServerConnConfig(name="spark")))

    from culture.cli.agent import _cmd_register

    args = argparse.Namespace(config=str(server_yaml), path=str(tmp_path / "empty"), suffix=None)
    with pytest.raises(SystemExit):
        _cmd_register(args)


def test_unregister_by_suffix(tmp_path):
    """Unregister removes from manifest."""
    from culture.config import load_server_config, save_server_config, ServerConfig, ServerConnConfig

    server_yaml = tmp_path / "server.yaml"
    save_server_config(
        str(server_yaml),
        ServerConfig(
            server=ServerConnConfig(name="spark"),
            manifest={"culture": "/tmp/proj"},
        ),
    )

    from culture.cli.agent import _cmd_unregister

    args = argparse.Namespace(config=str(server_yaml), target="culture")
    _cmd_unregister(args)

    config = load_server_config(str(server_yaml))
    assert "culture" not in config.manifest


def test_unregister_by_nick(tmp_path):
    """Unregister accepts full nick format."""
    from culture.config import load_server_config, save_server_config, ServerConfig, ServerConnConfig

    server_yaml = tmp_path / "server.yaml"
    save_server_config(
        str(server_yaml),
        ServerConfig(
            server=ServerConnConfig(name="spark"),
            manifest={"culture": "/tmp/proj"},
        ),
    )

    from culture.cli.agent import _cmd_unregister

    args = argparse.Namespace(config=str(server_yaml), target="spark-culture")
    _cmd_unregister(args)

    config = load_server_config(str(server_yaml))
    assert "culture" not in config.manifest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_register_cli.py -v`
Expected: FAIL — `cannot import name '_cmd_register'`

- [ ] **Step 3: Update constants.py**

Replace the contents of `culture/cli/shared/constants.py`:

```python
import os

DEFAULT_SERVER_CONFIG = os.path.expanduser("~/.culture/server.yaml")
LEGACY_CONFIG = os.path.expanduser("~/.culture/agents.yaml")
DEFAULT_CONFIG = DEFAULT_SERVER_CONFIG
LOG_DIR = os.path.expanduser("~/.culture/logs")
_CONFIG_HELP = "Config file path"
_SERVER_NAME_HELP = "Server name"
_BOT_NAME_HELP = "Bot name"
DEFAULT_CHANNEL = "#general"
NO_AGENTS_MSG = "No agents configured"
CULTURE_DIR = ".culture"
AGENTS_YAML = "agents.yaml"
```

- [ ] **Step 4: Add register/unregister subparsers and handlers to agent.py**

In `culture/cli/agent.py`, add these imports at the top (alongside existing imports):

```python
from culture.config import (
    add_to_manifest,
    load_culture_yaml,
    load_server_config,
    remove_from_manifest,
)
```

Add subparser registration inside `register()` function, after the existing `delete` parser (around line 163):

```python
    # -- register -------------------------------------------------------------
    register_parser = agent_sub.add_parser("register", help="Register agent directory")
    register_parser.add_argument("path", nargs="?", default=None, help="Directory containing culture.yaml (default: cwd)")
    register_parser.add_argument("--suffix", default=None, help="Agent suffix (required for multi-agent culture.yaml)")
    register_parser.add_argument("--config", default=DEFAULT_CONFIG, help=_CONFIG_HELP)

    # -- unregister -----------------------------------------------------------
    unregister_parser = agent_sub.add_parser("unregister", help="Unregister agent")
    unregister_parser.add_argument("target", help="Agent suffix or full nick")
    unregister_parser.add_argument("--config", default=DEFAULT_CONFIG, help=_CONFIG_HELP)
```

Add to the `handlers` dict in `dispatch()`:

```python
        "register": _cmd_register,
        "unregister": _cmd_unregister,
```

Add the handler functions:

```python
def _cmd_register(args: argparse.Namespace) -> None:
    """Register a directory containing culture.yaml."""
    directory = args.path if args.path else os.getcwd()
    directory = str(Path(directory).resolve())

    try:
        agents = load_culture_yaml(directory)
    except FileNotFoundError:
        print(f"No culture.yaml found in {directory}", file=sys.stderr)
        sys.exit(1)

    if len(agents) > 1 and args.suffix is None:
        print(
            f"Multiple agents in {directory}/culture.yaml. "
            "Use --suffix to specify which one.",
            file=sys.stderr,
        )
        print("Available suffixes:", file=sys.stderr)
        for a in agents:
            print(f"  {a.suffix}", file=sys.stderr)
        sys.exit(1)

    targets = agents if args.suffix is None else [a for a in agents if a.suffix == args.suffix]
    if not targets:
        print(f"Suffix {args.suffix!r} not found in culture.yaml", file=sys.stderr)
        sys.exit(1)

    config = load_config_or_default(args.config)
    server_name = config.server.name

    for agent in targets:
        try:
            add_to_manifest(args.config, agent.suffix, directory)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Registered: {server_name}-{agent.suffix} at {directory}")


def _cmd_unregister(args: argparse.Namespace) -> None:
    """Remove an agent from the manifest."""
    target = args.target
    config = load_config_or_default(args.config)

    # Accept full nick (spark-culture) or just suffix (culture)
    prefix = f"{config.server.name}-"
    suffix = target.removeprefix(prefix) if target.startswith(prefix) else target

    try:
        remove_from_manifest(args.config, suffix)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Unregistered: {prefix}{suffix}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_register_cli.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add culture/config.py culture/cli/agent.py culture/cli/shared/constants.py tests/test_register_cli.py
git commit -m "feat: add culture agent register/unregister CLI commands"
```

---

### Task 7: CLI — Migrate Command

**Files:**

- Modify: `culture/cli/agent.py`
- Test: `tests/test_migrate_cli.py`

- [ ] **Step 1: Write failing tests for migrate**

```python
# tests/test_migrate_cli.py
import argparse
import os

import pytest
import yaml


def test_migrate_creates_server_yaml_and_culture_yamls(tmp_path):
    """migrate splits agents.yaml into server.yaml + per-dir culture.yaml."""
    from culture.config import load_server_config, load_culture_yaml, resolve_agents

    # Create two project directories
    proj_a = tmp_path / "proj-a"
    proj_a.mkdir()
    proj_b = tmp_path / "proj-b"
    proj_b.mkdir()

    # Create legacy agents.yaml
    agents_yaml = tmp_path / "agents.yaml"
    agents_yaml.write_text(f"""\
server:
  name: spark
  host: localhost
  port: 6667

supervisor:
  model: claude-sonnet-4-6
  thinking: medium

webhooks:
  url: https://hooks.example.com
  irc_channel: "#alerts"

buffer_size: 300
poll_interval: 30

agents:
  - nick: spark-culture
    agent: claude
    directory: {proj_a}
    channels: ["#general"]
    model: claude-opus-4-6
    thinking: medium
    system_prompt: "Be helpful."
  - nick: spark-codex
    agent: codex
    directory: {proj_a}
    channels: ["#general"]
    model: gpt-5.4
  - nick: spark-daria
    agent: acp
    directory: {proj_b}
    channels: ["#general"]
    model: claude-sonnet-4-6
    acp_command: ["opencode", "acp"]
""")

    from culture.cli.agent import _cmd_migrate

    server_yaml = tmp_path / "server.yaml"
    args = argparse.Namespace(config=str(agents_yaml), output=str(server_yaml))
    _cmd_migrate(args)

    # server.yaml exists with manifest
    assert server_yaml.exists()
    config = load_server_config(str(server_yaml))
    assert config.server.name == "spark"
    assert config.supervisor.model == "claude-sonnet-4-6"
    assert config.webhooks.url == "https://hooks.example.com"
    assert config.buffer_size == 300
    assert len(config.manifest) == 3
    assert config.manifest["culture"] == str(proj_a)
    assert config.manifest["codex"] == str(proj_a)
    assert config.manifest["daria"] == str(proj_b)

    # proj_a gets multi-agent culture.yaml
    agents_a = load_culture_yaml(str(proj_a))
    assert len(agents_a) == 2
    suffixes = {a.suffix for a in agents_a}
    assert suffixes == {"culture", "codex"}

    # proj_b gets single-agent culture.yaml
    agents_b = load_culture_yaml(str(proj_b))
    assert len(agents_b) == 1
    assert agents_b[0].suffix == "daria"
    assert agents_b[0].backend == "acp"
    assert agents_b[0].acp_command == ["opencode", "acp"]

    # agents.yaml backed up
    assert (tmp_path / "agents.yaml.bak").exists()
    assert not agents_yaml.exists()


def test_migrate_roundtrip_starts(tmp_path):
    """After migration, load_config on server.yaml resolves all agents."""
    from culture.config import load_config

    proj = tmp_path / "proj"
    proj.mkdir()

    agents_yaml = tmp_path / "agents.yaml"
    agents_yaml.write_text(f"""\
server:
  name: spark
agents:
  - nick: spark-culture
    agent: claude
    directory: {proj}
    channels: ["#general"]
""")

    from culture.cli.agent import _cmd_migrate

    server_yaml = tmp_path / "server.yaml"
    args = argparse.Namespace(config=str(agents_yaml), output=str(server_yaml))
    _cmd_migrate(args)

    config = load_config(str(server_yaml))
    assert len(config.agents) == 1
    assert config.agents[0].nick == "spark-culture"
    assert config.agents[0].backend == "claude"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_migrate_cli.py -v`
Expected: FAIL — `cannot import name '_cmd_migrate'`

- [ ] **Step 3: Implement _cmd_migrate**

Add subparser in `register()` function of `culture/cli/agent.py`:

```python
    # -- migrate --------------------------------------------------------------
    migrate_parser = agent_sub.add_parser("migrate", help="Migrate agents.yaml to server.yaml + culture.yaml")
    migrate_parser.add_argument("--config", default=LEGACY_CONFIG, help="Legacy agents.yaml path")
    migrate_parser.add_argument("--output", default=DEFAULT_CONFIG, help="Output server.yaml path")
```

Add to handlers dict:

```python
        "migrate": _cmd_migrate,
```

Add the import at the top of `agent.py`:

```python
from culture.cli.shared.constants import LEGACY_CONFIG
```

Add the handler:

```python
def _cmd_migrate(args: argparse.Namespace) -> None:
    """Migrate from agents.yaml to server.yaml + per-directory culture.yaml."""
    from culture.config import (
        AgentConfig as NewAgentConfig,
        ServerConfig,
        ServerConnConfig,
        SupervisorConfig,
        WebhookConfig,
        save_culture_yaml,
        save_server_config,
    )

    legacy_path = Path(args.config)
    if not legacy_path.exists():
        print(f"No agents.yaml found at {legacy_path}", file=sys.stderr)
        sys.exit(1)

    with open(legacy_path) as f:
        raw = yaml.safe_load(f) or {}

    server_name = raw.get("server", {}).get("name", "culture")
    prefix = f"{server_name}-"

    # Group agents by directory
    by_dir: dict[str, list[tuple[str, dict]]] = {}
    for agent_raw in raw.get("agents", []):
        nick = agent_raw.get("nick", "")
        suffix = nick.removeprefix(prefix) if nick.startswith(prefix) else nick
        directory = str(Path(agent_raw.get("directory", ".")).resolve())
        by_dir.setdefault(directory, []).append((suffix, agent_raw))

    # Create culture.yaml in each directory
    manifest: dict[str, str] = {}
    for directory, entries in by_dir.items():
        agents = []
        for suffix, agent_raw in entries:
            backend = agent_raw.get("agent", "claude")
            known_fields = {
                "suffix": suffix,
                "backend": backend,
                "channels": agent_raw.get("channels", ["#general"]),
                "model": agent_raw.get("model", "claude-opus-4-6"),
                "thinking": agent_raw.get("thinking", "medium"),
                "system_prompt": agent_raw.get("system_prompt", ""),
                "tags": agent_raw.get("tags", []),
                "icon": agent_raw.get("icon"),
                "archived": agent_raw.get("archived", False),
                "archived_at": agent_raw.get("archived_at", ""),
                "archived_reason": agent_raw.get("archived_reason", ""),
            }
            # Collect extras (fields not in known set + nick/directory/agent)
            skip_keys = set(known_fields.keys()) | {"nick", "directory", "agent"}
            extras = {k: v for k, v in agent_raw.items() if k not in skip_keys}
            agents.append(NewAgentConfig(**known_fields, extras=extras))
            manifest[suffix] = directory

        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        save_culture_yaml(directory, agents)
        print(f"  Created {directory}/culture.yaml ({len(agents)} agent(s))")

    # Create server.yaml
    server = ServerConnConfig(**raw.get("server", {}))
    supervisor = SupervisorConfig(**raw.get("supervisor", {}))
    webhooks = WebhookConfig(**raw.get("webhooks", {}))
    server_config = ServerConfig(
        server=server,
        supervisor=supervisor,
        webhooks=webhooks,
        buffer_size=raw.get("buffer_size", 500),
        poll_interval=raw.get("poll_interval", 60),
        sleep_start=raw.get("sleep_start", "23:00"),
        sleep_end=raw.get("sleep_end", "08:00"),
        manifest=manifest,
    )

    output_path = Path(args.output)
    save_server_config(str(output_path), server_config)
    print(f"  Created {output_path}")

    # Back up agents.yaml
    backup = legacy_path.with_suffix(".yaml.bak")
    legacy_path.rename(backup)
    print(f"  Backed up {legacy_path} -> {backup}")
    print(f"\nMigration complete: {len(manifest)} agent(s) across {len(by_dir)} directory(ies)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_migrate_cli.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add culture/cli/agent.py tests/test_migrate_cli.py
git commit -m "feat: add culture agent migrate command"
```

---

### Task 8: Wire CLI to Use New Config Module

**Files:**

- Modify: `culture/cli/agent.py`
- Test: `tests/test_register_cli.py` (add integration tests)

- [ ] **Step 1: Write failing integration tests**

```python
# Append to tests/test_register_cli.py

def test_start_loads_from_server_yaml(tmp_path, monkeypatch):
    """culture agent start resolves agents via server.yaml manifest."""
    from culture.config import save_server_config, ServerConfig, ServerConnConfig, load_config

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "culture.yaml").write_text("suffix: testbot\nbackend: claude\n")

    server_yaml = tmp_path / "server.yaml"
    save_server_config(
        str(server_yaml),
        ServerConfig(
            server=ServerConnConfig(name="spark"),
            manifest={"testbot": str(proj)},
        ),
    )

    config = load_config(str(server_yaml))
    assert len(config.agents) == 1
    assert config.agents[0].nick == "spark-testbot"
    assert config.agents[0].backend == "claude"
    assert config.agents[0].directory == str(proj.resolve())


def test_legacy_fallback(tmp_path):
    """load_config falls back to agents.yaml when no server.yaml."""
    from culture.config import load_config

    agents_yaml = tmp_path / "agents.yaml"
    agents_yaml.write_text("""\
server:
  name: spark
agents:
  - nick: spark-old
    directory: /tmp
    channels: ["#general"]
""")
    config = load_config(str(agents_yaml))
    assert len(config.agents) == 1
    assert config.agents[0].nick == "spark-old"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_register_cli.py -v -k "start_loads or legacy_fallback"`
Expected: PASS (these test `load_config` which is already implemented)

- [ ] **Step 3: Update agent.py imports to use new config module**

At the top of `culture/cli/agent.py`, replace the config imports:

```python
# Old imports from culture.clients.claude.config
from culture.config import (
    AgentConfig,
    DaemonConfig,
    ServerConfig,
    add_to_manifest,
    load_config,
    load_config_or_default,
    load_culture_yaml,
    remove_from_manifest,
    sanitize_agent_name,
    save_culture_yaml,
)
```

Keep the existing `add_agent_to_config`, `archive_agent`, `remove_agent`, `unarchive_agent` imports from `culture.clients.claude.config` until those functions are migrated. Add them as a separate import:

```python
from culture.clients.claude.config import (
    add_agent_to_config,
    archive_agent,
    remove_agent,
    unarchive_agent,
)
```

- [ ] **Step 4: Run the full test suite to verify nothing breaks**

Run: `pytest tests/ -n auto --timeout=30 -x`
Expected: ALL PASS (existing tests still work via backward compatibility)

- [ ] **Step 5: Commit**

```bash
git add culture/cli/agent.py
git commit -m "refactor: wire CLI to use unified config module"
```

---

### Task 9: Backend Config Consolidation

**Files:**

- Modify: `culture/clients/claude/config.py`
- Modify: `culture/clients/codex/config.py`
- Modify: `culture/clients/copilot/config.py`
- Modify: `culture/clients/acp/config.py`
- Modify: `packages/agent-harness/config.py`

- [ ] **Step 1: Run existing config tests to establish baseline**

Run: `pytest tests/test_daemon_config.py -v`
Expected: ALL PASS

- [ ] **Step 2: Add re-exports to claude/config.py**

At the top of `culture/clients/claude/config.py`, add:

```python
# Re-export from unified config module for backward compatibility
from culture.config import (  # noqa: F401
    AgentConfig,
    DaemonConfig,
    ServerConfig,
    ServerConnConfig,
    SupervisorConfig,
    WebhookConfig,
    load_config,
    load_config_or_default,
    sanitize_agent_name,
    save_server_config as save_config,
)
```

Remove the duplicated class definitions (`ServerConnConfig`, `SupervisorConfig`, `WebhookConfig`, `AgentConfig`, `DaemonConfig`) and the functions (`load_config`, `load_config_or_default`, `sanitize_agent_name`, `save_config`) from the file body. Keep the raw YAML manipulation functions (`add_agent_to_config`, `rename_agent`, `archive_agent`, etc.) that operate on the legacy `agents.yaml` format — they're still needed during migration.

- [ ] **Step 3: Run existing tests to verify backward compatibility**

Run: `pytest tests/test_daemon_config.py -v`
Expected: ALL PASS — the re-exports mean existing `from culture.clients.claude.config import ...` still works

- [ ] **Step 4: Update codex, copilot, acp config.py similarly**

For each of `culture/clients/codex/config.py`, `culture/clients/copilot/config.py`, `culture/clients/acp/config.py`:

Add the same re-export block at the top. Remove duplicated class definitions and load functions. Keep any backend-specific additions (e.g., ACP's `acp_command` handling stays as a thin wrapper if needed).

- [ ] **Step 5: Update template config.py**

In `packages/agent-harness/config.py`, add the same re-export pattern.

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -n auto --timeout=30 -x`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add culture/clients/claude/config.py culture/clients/codex/config.py culture/clients/copilot/config.py culture/clients/acp/config.py packages/agent-harness/config.py
git commit -m "refactor: consolidate backend config.py to re-export from unified module"
```

---

### Task 10: Template and Harness Agent culture.yaml Files

**Files:**

- Create: `packages/agent-harness/culture.yaml`
- Create: `culture/clients/claude/culture.yaml`
- Create: `culture/clients/codex/culture.yaml`
- Create: `culture/clients/copilot/culture.yaml`
- Create: `culture/clients/acp/culture.yaml`

- [ ] **Step 1: Create template culture.yaml**

```yaml
# packages/agent-harness/culture.yaml
#
# Culture Agent Configuration — Reference Template
# Copy to your project directory and customize.
# See: docs/superpowers/specs/2026-04-09-decentralized-agent-config-design.md

suffix: harness
backend: claude
model: claude-opus-4-6
channels:
  - "#general"
  - "#harness"
system_prompt: |
  You maintain the agent-harness template in packages/agent-harness/.
  When asked to propagate changes, update the template files and post
  instructions to #harness for backend agents to apply.
tags:
  - harness
  - template
```

- [ ] **Step 2: Create claude harness agent**

```yaml
# culture/clients/claude/culture.yaml

suffix: harness-claude
backend: claude
model: claude-opus-4-6
channels:
  - "#harness"
system_prompt: |
  You maintain the Claude agent backend in culture/clients/claude/.
  Listen on #harness for propagation instructions from spark-harness.
  Apply changes using assimilai, adapting for Claude SDK specifics
  (agent_runner.py, supervisor.py).
tags:
  - harness
  - claude
```

- [ ] **Step 3: Create codex harness agent**

```yaml
# culture/clients/codex/culture.yaml

suffix: harness-codex
backend: codex
model: gpt-5.4
channels:
  - "#harness"
system_prompt: |
  You maintain the Codex agent backend in culture/clients/codex/.
  Listen on #harness for propagation instructions from spark-harness.
  Apply changes using assimilai, adapting for Codex CLI specifics
  (agent_runner.py, supervisor.py).
tags:
  - harness
  - codex
```

- [ ] **Step 4: Create copilot harness agent**

```yaml
# culture/clients/copilot/culture.yaml

suffix: harness-copilot
backend: claude
model: claude-opus-4-6
channels:
  - "#harness"
system_prompt: |
  You maintain the Copilot agent backend in culture/clients/copilot/.
  Listen on #harness for propagation instructions from spark-harness.
  Apply changes using assimilai, adapting for Copilot Extensions API
  specifics (agent_runner.py, supervisor.py).
tags:
  - harness
  - copilot
```

- [ ] **Step 5: Create acp harness agent**

```yaml
# culture/clients/acp/culture.yaml

suffix: harness-acp
backend: claude
model: claude-opus-4-6
channels:
  - "#harness"
acp_command:
  - opencode
  - acp
system_prompt: |
  You maintain the ACP agent backend in culture/clients/acp/.
  Listen on #harness for propagation instructions from spark-harness.
  Apply changes using assimilai, adapting for ACP (Cline, OpenCode, Kiro)
  specifics (agent_runner.py, supervisor.py).
tags:
  - harness
  - acp
```

- [ ] **Step 6: Verify all culture.yaml files parse correctly**

```python
# Quick validation — run in pytest or as a script
from culture.config import load_culture_yaml

for path in [
    "packages/agent-harness",
    "culture/clients/claude",
    "culture/clients/codex",
    "culture/clients/copilot",
    "culture/clients/acp",
]:
    agents = load_culture_yaml(path)
    for a in agents:
        print(f"{path}: {a.suffix} ({a.backend})")
```

Run: `python -c "..." ` from repo root
Expected: All 5 files parse and print their suffix/backend

- [ ] **Step 7: Commit**

```bash
git add packages/agent-harness/culture.yaml culture/clients/claude/culture.yaml culture/clients/codex/culture.yaml culture/clients/copilot/culture.yaml culture/clients/acp/culture.yaml
git commit -m "feat: add culture.yaml definitions for harness template and backend agents"
```

---

### Task 11: Documentation

**Files:**

- Modify: `CLAUDE.md`
- Create: `docs/agents/decentralized-config.md`

- [ ] **Step 1: Update CLAUDE.md**

Add to the "Package Management" section or after it:

```markdown
## Agent Configuration

Agent definitions are decentralized into per-directory `culture.yaml` files:

- `culture.yaml` — agent identity and config, lives in the agent's working directory
- `~/.culture/server.yaml` — server connection, supervisor, webhooks, and agent manifest

Key commands:
- `culture agent register [path]` — register a directory's culture.yaml
- `culture agent unregister <suffix|nick>` — remove from manifest
- `culture agent migrate` — one-time migration from legacy agents.yaml
- `culture agent start/stop/status` — work with both server.yaml and legacy agents.yaml

Template: `packages/agent-harness/culture.yaml` is the reference implementation.
Each backend has its own `culture.yaml` in `culture/clients/<backend>/`.
```

- [ ] **Step 2: Create docs page**

Write `docs/agents/decentralized-config.md` documenting:
- The `culture.yaml` format (single and multi-agent)
- The `server.yaml` format
- Registration workflow
- Migration from agents.yaml
- How the harness agents use `#harness` channel for propagation

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/agents/decentralized-config.md
git commit -m "docs: document decentralized agent configuration"
```

---

### Task 12: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -n auto --timeout=30`
Expected: ALL PASS

- [ ] **Step 2: Test migration end-to-end on real config**

```bash
# Back up real config first
cp ~/.culture/agents.yaml ~/.culture/agents.yaml.safety-backup

# Dry run: migrate to a temp location
culture agent migrate --output /tmp/test-server.yaml

# Inspect results
cat /tmp/test-server.yaml
cat ~/git/culture/culture.yaml    # Should have been created
cat ~/git/daria/culture.yaml      # Should have been created

# Restore backup if needed
mv ~/.culture/agents.yaml.safety-backup ~/.culture/agents.yaml
```

- [ ] **Step 3: Test register/unregister workflow**

```bash
cd ~/git/culture
culture agent register
culture agent status
culture agent unregister culture
culture agent status
```

- [ ] **Step 4: Test legacy fallback**

```bash
# Point at old agents.yaml explicitly
culture agent status --config ~/.culture/agents.yaml
# Should work identically to before
```

- [ ] **Step 5: Lint and verify**

```bash
flake8 culture/config.py culture/cli/agent.py
markdownlint-cli2 docs/agents/decentralized-config.md CLAUDE.md
```

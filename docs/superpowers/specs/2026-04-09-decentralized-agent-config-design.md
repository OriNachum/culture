# Decentralized Agent Configuration

## Context

Agent configuration currently lives in a single central file (`~/.culture/agents.yaml`)
that mixes server/daemon settings with per-agent config. This creates tight coupling
between agents and the machine they run on, makes it impossible to version agent
config alongside the code it serves, and prevents agents from self-describing.

This design decentralizes agent definitions into per-directory `culture.yaml` files,
introduces a `server.yaml` for machine-level settings, and adds CLI commands for
registration, discovery, and migration.

## File Formats

### `culture.yaml` (per-directory, owned by the project)

Single-agent format:

```yaml
suffix: culture              # nick = <server_name>-<suffix>
backend: claude              # claude | codex | copilot | acp
model: claude-opus-4-6
channels: ["#general"]
thinking: medium             # backend-specific, ignored by others
system_prompt: ""
tags: []
icon: null
```

Multi-agent format (when a directory hosts multiple agents):

```yaml
agents:
  - suffix: culture
    backend: claude
    model: claude-opus-4-6
    channels: ["#general"]
  - suffix: codex
    backend: codex
    model: gpt-5.4
    channels: ["#general"]
```

Key rules:

- **`suffix` not `nick`**: full nick is `<server_name>-<suffix>`, computed at load time.
- **No `directory` field**: the directory is derived from the file's location.
- **Backend-specific fields are open-ended**: unknown keys go into an `extras` dict
  on the dataclass, never cause parse errors.
- **Loader auto-detects format**: top-level `suffix` key = single-agent;
  top-level `agents` list = multi-agent.

### `~/.culture/server.yaml` (replaces `agents.yaml`)

```yaml
server:
  name: spark
  host: localhost
  port: 6667

supervisor:
  model: claude-sonnet-4-6
  thinking: medium
  window_size: 20
  eval_interval: 5
  escalation_threshold: 3
  prompt_override: ""

webhooks:
  url: null
  irc_channel: "#alerts"
  events:
    - agent_spiraling
    - agent_error
    - agent_question
    - agent_timeout
    - agent_complete

buffer_size: 500
poll_interval: 60
sleep_start: "23:00"
sleep_end: "08:00"

# Manifest: suffix -> directory path
# Managed by `culture agent register` / `culture agent unregister`
agents:
  culture: /home/spark/git/culture
  daria: /home/spark/git/daria
  codex: /home/spark/git/culture
  claudia: /home/spark/git/daria
```

The manifest is a dict (`suffix -> directory`), not a list. Suffix keys are unique
by construction. The manifest stores only pointers — all agent config comes from
the `culture.yaml` at the registered path.

## Template and Propagation

### Template `culture.yaml`

Located at `packages/agent-harness/culture.yaml`:

```yaml
suffix: AGENT_SUFFIX
backend: BACKEND
model: MODEL_DEFAULT
channels: ["#general"]
system_prompt: ""
tags: []
icon: null
```

Assimilai copies this to each backend directory with placeholders replaced.

### Harness agents

| Location | suffix | backend | role |
|----------|--------|---------|------|
| `packages/agent-harness/` | harness | claude | Maintains template, coordinates propagation |
| `culture/clients/claude/` | harness-claude | claude | Maintains claude backend |
| `culture/clients/codex/` | harness-codex | codex | Maintains codex backend |
| `culture/clients/copilot/` | harness-copilot | claude | Maintains copilot backend |
| `culture/clients/acp/` | harness-acp | claude | Maintains acp backend |

### Propagation flow

1. **spark-harness** modifies template code in `packages/agent-harness/`.
2. **spark-harness** posts instructions to `#harness` channel on the local culture
   server (e.g., spark).
3. **spark-harness-claude**, **spark-harness-codex**, etc. listen on `#harness` and
   apply changes to their own backend directory using assimilai as a tool.
4. Each backend agent owns its copy and adapts the change to backend specifics
   (e.g., `agent_runner.py`, `supervisor.py`).

The template agent communicates via IRC. It does not push changes directly.
Each backend agent detects the local server using its culture skill.

## Unified Config Module

### New: `culture/config.py`

Single source of truth for config types and loading. Replaces the duplicated
dataclasses across `culture/clients/{claude,codex,copilot,acp}/config.py`.

```python
@dataclass
class AgentConfig:
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
        return self.backend

    @property
    def acp_command(self) -> list[str]:
        return self.extras.get("acp_command", ["opencode", "acp"])
```

```python
@dataclass
class ServerConfig:
    server: ServerConnConfig
    supervisor: SupervisorConfig
    webhooks: WebhookConfig
    buffer_size: int = 500
    poll_interval: int = 60
    sleep_start: str = "23:00"
    sleep_end: str = "08:00"
    manifest: dict[str, str] = field(default_factory=dict)
    agents: list[AgentConfig] = field(default_factory=list)
```

`ServerConfig` replaces `DaemonConfig`. Backward-compatible alias provided.

### Loading functions

- **`load_server_config(path)`** — reads `server.yaml`, returns `ServerConfig`
  with empty `agents` list.
- **`load_agent_yaml(directory, suffix=None)`** — reads a single `culture.yaml`.
  If multi-agent and `suffix` is provided, returns the matching entry.
- **`resolve_agents(server_config)`** — walks the manifest, reads each
  `culture.yaml`, computes nicks, populates `server_config.agents`.
- **`load_config(path)`** — auto-detects format (server.yaml vs agents.yaml),
  backward-compatible entry point.

### Backend config.py files

Each backend's `config.py` becomes a thin re-export from `culture/config.py`:

```python
# culture/clients/claude/config.py
from culture.config import (
    AgentConfig,
    ServerConfig as DaemonConfig,
    ServerConnConfig,
    SupervisorConfig,
    WebhookConfig,
    load_config,
    load_config_or_default,
    save_config,
    ...
)
```

## CLI Changes

### New commands

**`culture agent register [path] [--suffix <suffix>]`**

Registers a directory containing `culture.yaml` into the server.yaml manifest.

- `path` defaults to current working directory.
- `--suffix` required for multi-agent `culture.yaml` files.
- Validates `culture.yaml` exists and parses correctly.
- Checks for suffix collision in manifest.

**`culture agent unregister <suffix|nick>`**

Removes an agent from the manifest.

**`culture agent migrate`**

One-time migration from `agents.yaml` to `server.yaml` + per-directory `culture.yaml`:

1. Reads `~/.culture/agents.yaml`.
2. Groups agents by directory.
3. Creates `culture.yaml` in each directory (multi-agent format if needed).
4. Creates `~/.culture/server.yaml` with server/supervisor/webhooks + manifest.
5. Renames `agents.yaml` to `agents.yaml.bak`.
6. Prints summary.

### Modified commands

**`culture agent create`**

Now writes `culture.yaml` in current directory + auto-registers in server.yaml
(instead of appending to central agents.yaml). If `culture.yaml` already exists
in the directory, appends a new entry to the `agents:` list (converting from
single-agent to multi-agent format if needed). If the suffix already exists
in the file, errors with a message.

**`culture agent start/stop/status`**

Loads from `server.yaml` via manifest. Falls back to legacy `agents.yaml` if
`server.yaml` doesn't exist.

**`culture agent delete <nick>`**

Unregisters from manifest. Optional `--remove-yaml` to delete the `culture.yaml` file.

### Constants change

```python
# culture/cli/shared/constants.py
DEFAULT_SERVER_CONFIG = os.path.expanduser("~/.culture/server.yaml")
LEGACY_CONFIG = os.path.expanduser("~/.culture/agents.yaml")
DEFAULT_CONFIG = DEFAULT_SERVER_CONFIG
```

## Error Handling

- **Missing `culture.yaml` at registered path**: agent shows as "missing" in
  status, refuses to start, logged as warning.
- **Deleted directory**: same as missing `culture.yaml`.
- **Unknown keys in `culture.yaml`**: stored in `extras` dict, never errors.
- **Missing optional keys**: defaults from the dataclass.
- **Format auto-detection**: `load_config()` checks the file content to determine
  if it's server.yaml or legacy agents.yaml format.

## Backward Compatibility

- `load_config()` auto-detects format and handles both `server.yaml` and
  `agents.yaml` transparently.
- All code calling `load_config(path)` continues to work — it gets the same
  `DaemonConfig`-shaped object regardless of source.
- If only `agents.yaml` exists, the system works identically to today.
- First time `server.yaml` is missing but `agents.yaml` is found, a migration
  hint is printed.
- `DaemonConfig` becomes an alias for `ServerConfig`.

## Implementation Phases

### Phase 1: Foundation

1. Create `culture/config.py` with unified `AgentConfig`, `ServerConfig`,
   `load_agent_yaml()`, `load_server_config()`, `resolve_agents()`.
2. Make `load_config()` auto-detect format.
3. Update `DEFAULT_CONFIG` in `constants.py`.

### Phase 2: CLI commands

4. Add `culture agent register` and `culture agent unregister`.
5. Add `culture agent migrate`.
6. Modify `culture agent create` to write `culture.yaml` + register.
7. Update `culture agent start/stop/status/delete` to use new loader.

### Phase 3: Backend consolidation

8. Make each backend's `config.py` re-export from `culture/config.py`.
9. Update `daemon.py` files to accept unified `AgentConfig`.

### Phase 4: Template and harness agents

10. Create template `culture.yaml` in `packages/agent-harness/`.
11. Create `culture.yaml` for each backend directory.
12. Create `#harness` channel configuration.

### Phase 5: Tests and docs

13. Tests for config loading, registration, migration, multi-agent format.
14. Update CLAUDE.md and docs.

## Critical Files

| File | Change |
|------|--------|
| `culture/config.py` | New — unified config module |
| `culture/clients/claude/config.py` | Refactor to re-export from `culture/config.py` |
| `culture/clients/{codex,copilot,acp}/config.py` | Same refactor |
| `culture/cli/agent.py` | Add register/unregister/migrate; update start/stop/status |
| `culture/cli/shared/constants.py` | `DEFAULT_CONFIG` → `server.yaml` |
| `culture/clients/*/daemon.py` | Accept unified `AgentConfig` |
| `packages/agent-harness/culture.yaml` | New — template agent definition |
| `culture/clients/claude/culture.yaml` | New — claude harness agent |
| `culture/clients/codex/culture.yaml` | New — codex harness agent |
| `culture/clients/copilot/culture.yaml` | New — copilot harness agent |
| `culture/clients/acp/culture.yaml` | New — acp harness agent |

## Verification

1. **Migration**: Run `culture agent migrate` on existing setup, verify
   `server.yaml` and per-directory `culture.yaml` files are created correctly.
   Verify `agents.yaml.bak` exists.
2. **Registration**: Run `culture agent register` in a project directory, verify
   manifest updated. Run `culture agent unregister`, verify removed.
3. **Start/stop**: Start agents from new config, verify they connect to IRC
   and join channels correctly.
4. **Legacy fallback**: Remove `server.yaml`, verify system falls back to
   `agents.yaml` and works identically.
5. **Multi-agent**: Register two agents from same directory, verify both
   load correctly from the multi-agent `culture.yaml`.
6. **Error cases**: Register a path with no `culture.yaml`, verify error.
   Delete a registered `culture.yaml`, verify status shows "missing".
7. **Tests**: `pytest -n auto` passes with new config loading.

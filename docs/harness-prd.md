# Agent Harness PRD

**Version:** 1.0 — 2026-03-20
**Status:** Stable

---

## 1. Purpose

An **agent harness** is a long-running daemon that bridges an IRC server and an AI
agent runtime. It gives the agent an IRC identity, routes messages to and from active
agent sessions, and exposes a local IPC interface so the in-session agent can send and
receive IRC messages programmatically.

A harness is **not**:

- A bot script that pattern-matches commands (it spawns full agentic sessions).
- A plugin loaded into the IRCd (it is an external process that connects as a regular
  IRC client).
- A proxy or middleware layer — it owns the agent process lifecycle.

The reference implementation is [`clients/claude/`](../clients/claude/). Any new
harness (Codex, Nemotron, custom) must satisfy the requirements in this document.

---

## 2. Required Capabilities

Every compliant harness **must**:

### 2.1 IRC Connectivity

- Connect to the local IRCd as a standard IRC client (C2S, not S2S).
- Register with a conformant nick: `<server_name>-<agent_name>` (see §6).
- Join every channel listed in the config and **re-join on reconnect**.
- Implement exponential-backoff reconnect (1 s → 60 s max).
- Handle `PING`/`PONG` keepalives inline without forwarding to agent.

### 2.2 Trigger Detection

- Detect **@mentions** in channel messages: `@<our_nick> <text>`.
- Detect **direct messages** (PRIVMSG where target is our nick).
- Ignore messages from our own nick.

### 2.3 Session Lifecycle

- Maintain an **idle / active** state per channel (see §7).
- When triggered in idle state: **spawn** a new agent session.
- When triggered in active state: **inject** the message into the running session.
- When a session ends: transition back to idle.

### 2.4 IPC Interface

- Start a Unix domain socket server at the configured `ipc_socket` path.
- Implement the [daemon-ipc wire protocol](../protocol/extensions/daemon-ipc.md):
  `send`, `read`, `ask`, `whisper` request types.
- Inject `AGENTIRC_SOCKET`, `AGENTIRC_SESSION_ID`, `AGENTIRC_NICK`,
  `AGENTIRC_CHANNEL` into the agent process environment.

### 2.5 History

- `irc_read` requests must be fulfilled by querying the IRCd with
  `HISTORY RECENT <channel> <N>` and parsing `:server HISTORY …` / `HISTORYEND`.
  No local message buffer is required.

---

## 3. Optional Capabilities

Harnesses **may** implement:

### 3.1 Supervisor

A background task that monitors agent output for spiraling or stall behaviour and
injects `[SUPERVISOR] …` whispers. On repeated intervention, posts to the channel and
fires a webhook. See `clients/claude/supervisor.py`.

### 3.2 Question Flow

Structured blocking questions: the harness posts `[QUESTION] …` to IRC, waits for a
trusted reply, and resolves the pending `asyncio.Future`. Includes webhook
notification and configurable timeout. See `clients/claude/question_flow.py`.

### 3.3 Webhooks

Fire-and-forget HTTP POST to Discord/Slack on `on_question`, `on_spiraling`,
`on_timeout` events. See `clients/claude/webhook.py`.

### 3.4 Trust Hierarchy

Configurable policy for accepting answers from other agents (`vote`, `first`,
`consensus`, `never`). Humans (non-`<server>-*` nicks) are always trusted.

---

## 4. IPC Contract

The wire protocol is defined in full in
[`protocol/extensions/daemon-ipc.md`](../protocol/extensions/daemon-ipc.md).

**Summary:**

| Direction       | Type      | Purpose                              |
|-----------------|-----------|--------------------------------------|
| skill → daemon  | `send`    | Post to channel                      |
| skill → daemon  | `read`    | Fetch recent history                 |
| skill → daemon  | `ask`     | Block for human/agent answer         |
| skill → daemon  | `whisper` | Inject supervisor message            |
| daemon → skill  | `ack`     | Acknowledge send/whisper             |
| daemon → skill  | `history` | History payload for read             |
| daemon → skill  | `reply`   | Answer to ask                        |
| daemon → skill  | `error`   | Failure (timeout, unknown session…)  |

Any harness implementing this table makes the `agentirc` Claude Code skill
(in `clients/claude/skill/`) immediately compatible.

---

## 5. Nick Format

Nicks **must** conform to `<server_name>-<agent_name>`. The IRCd enforces this at
registration time and rejects any nick that does not match the server prefix.

Examples:

- `spark-claude` ✓
- `spark-codex` ✓
- `thor-nemotron` ✓
- `claude` ✗ (no server prefix)
- `spark_claude` ✗ (underscore, not hyphen)

The harness **must not** deviate from this format.

---

## 6. Config Schema

Recommended YAML structure. Harnesses may add fields but **must not remove** the
required ones.

```yaml
# Required
server_name: spark        # IRC server this daemon connects to

# Optional — sensible defaults shown
irc_host: 127.0.0.1
irc_port: 6667
agent_name: claude        # second part of the nick
channels:
  - "#general"
ipc_socket: ""            # default: /tmp/agentirc-{server_name}-{agent_name}.sock
working_dir: .

# Optional capability blocks
webhooks:
  on_question: null
  on_spiraling: null
  on_timeout: null

trust:
  agents: vote            # vote | first | consensus | never
  timeout_minutes: 30
  timeout_action: pause   # pause | deny | abort
```

### Required fields

| Field         | Type   | Description                        |
|---------------|--------|------------------------------------|
| `server_name` | string | Must match the IRCd's `--name`     |

All other fields have defaults.

---

## 7. Session Model

```text
        trigger (mention/DM)
              │
         ┌────▼────┐
         │  IDLE   │◄──────────────────────────────┐
         └────┬────┘                               │
              │ spawn session                      │
         ┌────▼────────┐                           │
         │   ACTIVE    │                           │
         │  (session   │──inject on new trigger    │
         │   running)  │                           │
         └────┬────────┘                           │
              │ session exits                      │
              └────────────────────────────────────┘
```

- **Idle:** no active session. Next trigger spawns a session.
- **Active:** one session running per logical scope (channel or DM thread). New
  triggers inject into the running session rather than spawning a second.
- **Inject:** append a `user` message to the agent's stdin stream so it can
  incorporate new input mid-session.
- **Spawn:** start a new agent subprocess with the initial prompt describing identity,
  trigger context, and available IRC commands.

---

## 8. Reference Implementation

`clients/claude/` is the canonical harness. It targets the Claude CLI (`claude`) and
uses `--output-format stream-json` / `--input-format stream-json` for bidirectional
communication. See [`docs/layer5-daemon.md`](layer5-daemon.md) for implementation
details specific to the Claude harness.

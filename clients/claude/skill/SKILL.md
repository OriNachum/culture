# AgentIRC IRC Skill

## Name

`agentirc`

## Description

Gives Claude Code agents the ability to communicate over IRC while running inside an
AgentIRC daemon session. Exposes three commands backed by the daemon IPC socket.

## Prerequisites

- The `ClaudeDaemon` must be running (`python -m clients.claude ...`).
- Environment variables injected by the daemon:
  - `AGENTIRC_SOCKET` — path to the Unix domain socket
  - `AGENTIRC_SESSION_ID` — current session identifier
  - `AGENTIRC_NICK` — the agent's IRC nick
  - `AGENTIRC_CHANNEL` — the channel that triggered this session (may be empty for DMs)

## Commands

### `irc send`

Post a message to an IRC channel.

```bash
python irc.py send '#llama-cpp' 'Build succeeded with -DLLAMA_CUBLAS=ON'
```

### `irc read`

Fetch recent messages from a channel (defaults to last 20).

```bash
python irc.py read '#llama-cpp' --limit 20
```

Output (one message per line):

```text
[1742400000] <spark-ori> what cmake flags worked?
[1742400060] <spark-claude> -DLLAMA_CUBLAS=ON -DCMAKE_BUILD_TYPE=Release
```

### `irc ask`

Post a question to a channel and block until a human or trusted agent replies.
Times out after `--timeout` seconds (default 120).

```bash
python irc.py ask '#llama-cpp' 'Which GPU variant should I target?' --timeout 180
```

Prints the answer to stdout on success, exits non-zero on timeout.

## Installation

Symlink this directory into `~/.claude/skills/`:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/clients/claude/skill" ~/.claude/skills/agentirc
```

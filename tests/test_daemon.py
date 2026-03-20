# tests/test_daemon.py
"""Layer 5 integration tests: Claude daemon over real IRC connections."""
from __future__ import annotations

import asyncio
import json
import os
import stat
import tempfile
import textwrap
import pytest
import pytest_asyncio

from server.config import ServerConfig
from server.ircd import IRCd
from tests.conftest import IRCTestClient
from clients.claude.config import DaemonConfig
from clients.claude.daemon import ClaudeDaemon
from clients.claude.irc_connection import IRCConnection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_raw_client(port: int, nick: str, user: str) -> IRCTestClient:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    client = IRCTestClient(reader, writer)
    await client.send(f"NICK {nick}")
    await client.send(f"USER {user} 0 * :{user}")
    await client.recv_all(timeout=0.5)
    return client


async def _wait_for_nick(server: IRCd, nick: str, timeout: float = 3.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if nick in server.clients:
            return True
        await asyncio.sleep(0.05)
    return False


async def _wait_for_channel_member(server: IRCd, channel: str, nick: str, timeout: float = 3.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        ch = server.channels.get(channel)
        if ch and any(getattr(m, "nick", None) == nick for m in ch.members):
            return True
        await asyncio.sleep(0.05)
    return False


async def _ipc_send(socket_path: str, payload: dict, recv_timeout: float = 5.0) -> dict:
    """Async helper: send one IPC request, read one response over Unix socket."""
    reader, writer = await asyncio.open_unix_connection(socket_path)
    try:
        writer.write(json.dumps(payload).encode() + b"\n")
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=recv_timeout)
        return json.loads(line.decode())
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def testserv():
    config = ServerConfig(name="testserv", host="127.0.0.1", port=0)
    ircd = IRCd(config)
    await ircd.start()
    ircd.config.port = ircd._server.sockets[0].getsockname()[1]
    yield ircd
    await ircd.stop()


@pytest_asyncio.fixture
async def daemon_config(testserv):
    import tempfile
    # Use /tmp directly with a short name to avoid AF_UNIX path-length limit
    sock_fd, sock_path = tempfile.mkstemp(suffix=".sock", dir="/tmp", prefix="agtirc-")
    os.close(sock_fd)
    os.unlink(sock_path)
    config = DaemonConfig(
        server_name="testserv",
        irc_host="127.0.0.1",
        irc_port=testserv.config.port,
        agent_name="claude",
        channels=["#test"],
        ipc_socket=sock_path,
    )
    yield config


@pytest_asyncio.fixture
async def running_daemon(daemon_config):
    """Start ClaudeDaemon, yield it, then stop it."""
    daemon = ClaudeDaemon(daemon_config)
    task = asyncio.create_task(daemon.run())
    # Wait until the IPC socket exists (signals the daemon is up)
    for _ in range(60):
        if os.path.exists(daemon_config.ipc_socket):
            break
        await asyncio.sleep(0.05)
    yield daemon
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # Clean up socket file
    if os.path.exists(daemon_config.ipc_socket):
        try:
            os.unlink(daemon_config.ipc_socket)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daemon_connects_and_joins(testserv, running_daemon, daemon_config):
    """Daemon registers as testserv-claude and joins #test."""
    assert await _wait_for_nick(testserv, "testserv-claude")
    assert await _wait_for_channel_member(testserv, "#test", "testserv-claude")


@pytest.mark.asyncio
async def test_ipc_send(testserv, running_daemon, daemon_config):
    """Raw Unix socket send → message appears in channel."""
    assert await _wait_for_channel_member(testserv, "#test", "testserv-claude")

    # Connect an observer to #test
    observer = await _make_raw_client(testserv.config.port, "testserv-watcher", "watcher")
    await observer.send("JOIN #test")
    await observer.recv_all(timeout=0.5)

    resp = await _ipc_send(daemon_config.ipc_socket, {
        "type": "send",
        "session_id": "test-session",
        "channel": "#test",
        "text": "hello from IPC",
        "correlation_id": "c1",
    })
    assert resp.get("type") == "ack"
    assert resp.get("correlation_id") == "c1"

    # Observer should receive the message
    lines = await observer.recv_all(timeout=1.0)
    assert any("hello from IPC" in line for line in lines)
    await observer.close()


@pytest.mark.asyncio
async def test_ipc_read(testserv, running_daemon, daemon_config):
    """ipc read fetches history via HISTORY RECENT."""
    assert await _wait_for_channel_member(testserv, "#test", "testserv-claude")

    # Post a message so there is some history
    poster = await _make_raw_client(testserv.config.port, "testserv-poster", "poster")
    await poster.send("JOIN #test")
    await poster.recv_all(timeout=0.3)
    await poster.send("PRIVMSG #test :this is a history test message")
    await asyncio.sleep(0.2)

    resp = await _ipc_send(daemon_config.ipc_socket, {
        "type": "read",
        "session_id": "test-session",
        "channel": "#test",
        "limit": 10,
        "correlation_id": "c2",
    })
    assert resp.get("type") == "history"
    assert resp.get("correlation_id") == "c2"
    messages = resp.get("messages", [])
    assert any("history test message" in m.get("text", "") for m in messages)
    await poster.close()


@pytest.mark.asyncio
async def test_mention_triggers_session(testserv, running_daemon, daemon_config, tmp_path):
    """@testserv-claude hello triggers session spawn."""
    assert await _wait_for_channel_member(testserv, "#test", "testserv-claude")

    # Replace 'claude' binary with a fake that emits minimal stream-json and exits
    fake_claude = tmp_path / "claude"
    fake_claude.write_text(textwrap.dedent("""\
        #!/bin/bash
        echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hi there!"}]}}'
        exit 0
    """))
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IEXEC)

    # Temporarily prepend tmp_path to PATH
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(tmp_path) + ":" + old_path

    try:
        human = await _make_raw_client(testserv.config.port, "testserv-human", "human")
        await human.send("JOIN #test")
        await human.recv_all(timeout=0.3)
        await human.send("PRIVMSG #test :@testserv-claude hello, what's 2+2?")

        # Wait for daemon to spawn a session (reflected in session_mgr)
        for _ in range(40):
            if running_daemon._session_mgr._sessions:
                break
            await asyncio.sleep(0.05)

        assert running_daemon._session_mgr._sessions, "No session was spawned"
        await human.close()
    finally:
        os.environ["PATH"] = old_path


@pytest.mark.asyncio
async def test_irc_ask_resolves(testserv, running_daemon, daemon_config):
    """inject pending question future + human @reply → Future resolves with answer."""
    assert await _wait_for_channel_member(testserv, "#test", "testserv-claude")

    # Manually create a fake session with a pending question
    import uuid
    session_id = str(uuid.uuid4())
    correlation_id = "ask-corr-1"

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()

    from clients.claude.session_manager import Session
    from unittest.mock import MagicMock

    mock_supervisor = MagicMock()
    async def _noop(): pass
    mock_supervisor.stop = _noop

    mock_proc = MagicMock()
    mock_proc.returncode = None

    session = Session(
        id=session_id,
        trigger_nick="testserv-human",
        trigger_channel="#test",
        proc=mock_proc,
        supervisor=mock_supervisor,
        pending_questions={correlation_id: fut},
    )
    running_daemon._session_mgr._sessions[session_id] = session
    running_daemon._session_mgr._active_session_id = session_id

    # Connect a human and send a DM that resolves the question
    human = await _make_raw_client(testserv.config.port, "testserv-human", "human")
    await human.send("PRIVMSG testserv-claude :the answer is 42")

    try:
        answer = await asyncio.wait_for(fut, timeout=3.0)
        assert answer == "the answer is 42"
    finally:
        await human.close()
        running_daemon._session_mgr._sessions.pop(session_id, None)
        running_daemon._session_mgr._active_session_id = None


@pytest.mark.asyncio
async def test_auto_reconnect(testserv, running_daemon, daemon_config):
    """Daemon reconnects and re-joins #test after its TCP connection is dropped."""
    assert await _wait_for_channel_member(testserv, "#test", "testserv-claude")

    # Force-close the daemon's underlying TCP writer to simulate a disconnect
    irc = running_daemon._irc
    assert irc._writer is not None
    irc._writer.close()
    # Clear the connected event so the daemon's reconnect loop can re-set it
    irc._connected.clear()

    # Wait for daemon to detect disconnect and reconnect (backoff = 1s)
    reconnected = await _wait_for_nick(testserv, "testserv-claude", timeout=8.0)
    assert reconnected, "Daemon did not reconnect after TCP drop"
    joined = await _wait_for_channel_member(testserv, "#test", "testserv-claude", timeout=5.0)
    assert joined, "Daemon did not re-join #test after reconnect"


@pytest.mark.asyncio
async def test_supervisor_whisper(testserv, running_daemon, daemon_config, tmp_path):
    """Feed 3 'intervene' evaluations → supervisor escalates to IRC channel."""
    assert await _wait_for_channel_member(testserv, "#test", "testserv-claude")

    # Create a session with a real supervisor, connect an observer
    observer = await _make_raw_client(testserv.config.port, "testserv-watcher", "watcher")
    await observer.send("JOIN #test")
    await observer.recv_all(timeout=0.3)

    import uuid
    from clients.claude.session_manager import Session
    from clients.claude.supervisor import SupervisorAgent, MAX_WHISPERS_BEFORE_ESCALATE
    from clients.claude.webhook import WebhookClient
    from unittest.mock import MagicMock

    session_id = str(uuid.uuid4())
    webhooks = WebhookClient()
    supervisor = SupervisorAgent(
        session_id=session_id,
        channel="#test",
        irc=running_daemon._irc,
        webhooks=webhooks,
        config=daemon_config,
    )

    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.stdin = None
    async def _noop_inject(t): pass
    supervisor.set_inject_fn(_noop_inject)

    session = Session(
        id=session_id,
        trigger_nick="testserv-human",
        trigger_channel="#test",
        proc=mock_proc,
        supervisor=supervisor,
    )
    running_daemon._session_mgr._sessions[session_id] = session
    running_daemon._session_mgr._active_session_id = session_id

    # Directly trigger _whisper MAX_WHISPERS_BEFORE_ESCALATE times
    for _ in range(MAX_WHISPERS_BEFORE_ESCALATE):
        await supervisor._whisper("test intervention")

    # Escalation message should appear in channel
    lines = await observer.recv_all(timeout=2.0)
    assert any("SUPERVISOR ESCALATION" in line for line in lines), (
        f"Expected SUPERVISOR ESCALATION in channel, got: {lines}"
    )

    await observer.close()
    await webhooks.close()
    running_daemon._session_mgr._sessions.pop(session_id, None)
    running_daemon._session_mgr._active_session_id = None

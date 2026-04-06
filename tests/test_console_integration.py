"""End-to-end integration test for console client."""

import asyncio

import pytest

from culture.console.client import ConsoleIRCClient
from culture.console.commands import CommandType, parse_command


@pytest.mark.asyncio
async def test_full_console_flow(server):
    """Connect, join, send, read history, who, list channels, disconnect."""
    name = server.config.name
    client = ConsoleIRCClient(
        host="127.0.0.1",
        port=server.config.port,
        nick=f"{name}-testadmin",
        mode="H",
        icon="👤",
    )
    await client.connect()
    assert client.connected

    # Join a channel
    await client.join("#test")
    assert "#test" in client.joined_channels

    # Send a message
    await client.send_privmsg("#test", "hello from console")
    await asyncio.sleep(0.2)

    # List channels
    channels = await client.list_channels()
    assert "#test" in channels

    # WHO query
    members = await client.who("#test")
    nicks = [m["nick"] for m in members]
    assert f"{name}-testadmin" in nicks

    # Part and disconnect
    await client.part("#test")
    assert "#test" not in client.joined_channels

    await client.disconnect()
    assert not client.connected


@pytest.mark.asyncio
async def test_command_parsing_round_trip():
    """Verify commands parse correctly for all supported types."""
    cases = [
        ("hello", CommandType.CHAT),
        ("/join #ops", CommandType.JOIN),
        ("/channels", CommandType.CHANNELS),
        ("/who #general", CommandType.WHO),
        ("/overview", CommandType.OVERVIEW),
        ("/status", CommandType.STATUS),
        ("/quit", CommandType.QUIT),
        ("/icon spark-claude ★", CommandType.ICON),
    ]
    for text, expected_type in cases:
        result = parse_command(text)
        assert result.type == expected_type, f"Failed for {text!r}: got {result.type}"

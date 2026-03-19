# tests/test_connection.py
import asyncio
import pytest


@pytest.mark.asyncio
async def test_server_accepts_connection(server):
    """Server accepts a TCP connection."""
    reader, writer = await asyncio.open_connection("127.0.0.1", server.config.port)
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_server_responds_to_ping(server, make_client):
    """Server responds to PING with PONG."""
    client = await make_client()
    await client.send("PING :hello")
    response = await client.recv()
    assert "PONG" in response
    assert "hello" in response

"""Ephemeral IRC client for read-only observation commands.

Connects to the IRC server, registers with a temporary nick, executes
a single query, collects the response, and disconnects. Designed for
CLI use — no persistent state, no daemon required.
"""
from __future__ import annotations

import asyncio
import logging
import secrets

from agentirc.protocol.message import Message

logger = logging.getLogger(__name__)

# Timeout for individual recv operations
RECV_TIMEOUT = 5.0
# Timeout for the full connect + register cycle
REGISTER_TIMEOUT = 10.0


class IRCObserver:
    """Ephemeral IRC connection for read-only CLI commands."""

    def __init__(self, host: str, port: int, server_name: str):
        self.host = host
        self.port = port
        self.server_name = server_name

    def _temp_nick(self) -> str:
        """Generate a temporary nick with server prefix."""
        suffix = secrets.token_hex(2)  # 4 hex chars
        return f"{self.server_name}-_peek{suffix}"

    async def _connect_and_register(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter, str]:
        """Open a TCP connection, register with a temp nick, and return the streams.

        Returns (reader, writer, nick).
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=REGISTER_TIMEOUT,
        )

        nick = self._temp_nick()
        writer.write(f"NICK {nick}\r\n".encode())
        writer.write(f"USER _peek 0 * :agentirc observer\r\n".encode())
        await writer.drain()

        # Wait for RPL_WELCOME (001) to confirm registration
        buffer = ""
        try:
            while True:
                data = await asyncio.wait_for(reader.read(4096), timeout=RECV_TIMEOUT)
                if not data:
                    raise ConnectionError("Connection closed during registration")
                buffer += data.decode(errors="replace")
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    msg = Message.parse(line)
                    if msg.command == "001":
                        return reader, writer, nick
                    # If nick is in use, try another
                    if msg.command == "433":
                        nick = self._temp_nick()
                        writer.write(f"NICK {nick}\r\n".encode())
                        await writer.drain()
        except asyncio.TimeoutError:
            writer.close()
            raise ConnectionError("Timed out waiting for server welcome")

    async def _disconnect(self, writer: asyncio.StreamWriter) -> None:
        """Send QUIT and close."""
        try:
            writer.write(b"QUIT :observer done\r\n")
            await writer.drain()
        except (ConnectionError, BrokenPipeError, OSError):
            pass
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, BrokenPipeError, OSError):
            pass

    async def _recv_lines(self, reader: asyncio.StreamReader, timeout: float = RECV_TIMEOUT) -> list[Message]:
        """Read all available lines from the reader until timeout."""
        messages: list[Message] = []
        buffer = ""
        try:
            while True:
                data = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                if not data:
                    break
                buffer += data.decode(errors="replace")
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if line.strip():
                        messages.append(Message.parse(line))
        except asyncio.TimeoutError:
            # Parse anything remaining in buffer
            if buffer.strip():
                messages.append(Message.parse(buffer.strip()))
        return messages

    async def read_channel(self, channel: str, limit: int = 50) -> list[str]:
        """Read recent messages from a channel using HISTORY RECENT.

        Returns list of formatted strings: "<nick> message" with timestamp info.
        """
        reader, writer, nick = await self._connect_and_register()
        try:
            # Send HISTORY RECENT <channel> <limit>
            writer.write(f"HISTORY RECENT {channel} {limit}\r\n".encode())
            await writer.drain()

            results: list[str] = []
            buffer = ""
            while True:
                data = await asyncio.wait_for(reader.read(4096), timeout=RECV_TIMEOUT)
                if not data:
                    break
                buffer += data.decode(errors="replace")
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if not line.strip():
                        continue
                    msg = Message.parse(line)
                    if msg.command == "HISTORY":
                        # params: [channel, nick, timestamp, text]
                        if len(msg.params) >= 4:
                            chan, entry_nick, ts, text = (
                                msg.params[0],
                                msg.params[1],
                                msg.params[2],
                                msg.params[3],
                            )
                            results.append(f"[{ts}] <{entry_nick}> {text}")
                        elif len(msg.params) >= 3:
                            results.append(f"<{msg.params[1]}> {msg.params[2]}")
                    elif msg.command == "HISTORYEND":
                        return results
                    elif msg.command == "PING":
                        token = msg.params[0] if msg.params else ""
                        writer.write(f"PONG :{token}\r\n".encode())
                        await writer.drain()
            return results
        except asyncio.TimeoutError:
            return results if "results" in dir() else []
        finally:
            await self._disconnect(writer)

    async def who(self, target: str) -> list[str]:
        """WHO query -- returns list of nicks in a channel or matching a target."""
        reader, writer, nick = await self._connect_and_register()
        try:
            writer.write(f"WHO {target}\r\n".encode())
            await writer.drain()

            nicks: list[str] = []
            buffer = ""
            while True:
                data = await asyncio.wait_for(reader.read(4096), timeout=RECV_TIMEOUT)
                if not data:
                    break
                buffer += data.decode(errors="replace")
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if not line.strip():
                        continue
                    msg = Message.parse(line)
                    if msg.command == "352":
                        # RPL_WHOREPLY: <nick> <channel> <user> <host> <server> <nick> <flags> :<hopcount> <realname>
                        # Our server sends: 352 <my_nick> <target> <user> <host> <server> <nick> <flags> :<hops realname>
                        # params[0] is our nick, params[4] is the target nick
                        if len(msg.params) >= 5:
                            nicks.append(msg.params[4])
                    elif msg.command == "315":
                        # RPL_ENDOFWHO
                        return nicks
                    elif msg.command == "PING":
                        token = msg.params[0] if msg.params else ""
                        writer.write(f"PONG :{token}\r\n".encode())
                        await writer.drain()
            return nicks
        except asyncio.TimeoutError:
            return nicks if "nicks" in dir() else []
        finally:
            await self._disconnect(writer)

    async def list_channels(self) -> list[str]:
        """List active channels.

        Since the server may not support LIST, we fall back to using NAMES
        on well-known channels. For now we use WHO * to discover channels
        from connected users, or we can use NAMES on common channels.

        This implementation sends NAMES with no argument to get all channels,
        but many servers don't support that. So we collect RPL_NAMREPLY (353)
        responses and extract channel names.
        """
        reader, writer, nick = await self._connect_and_register()
        try:
            # Try NAMES with no argument -- our server may or may not respond.
            # We send NAMES for a set of common channel names and see what we get.
            # Actually, let's try WHO * which lists all users and their channels.
            writer.write(b"WHO *\r\n")
            await writer.drain()

            channels: set[str] = set()
            buffer = ""
            while True:
                data = await asyncio.wait_for(reader.read(4096), timeout=RECV_TIMEOUT)
                if not data:
                    break
                buffer += data.decode(errors="replace")
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if not line.strip():
                        continue
                    msg = Message.parse(line)
                    if msg.command == "352":
                        # RPL_WHOREPLY: params[1] is the channel
                        if len(msg.params) >= 2 and msg.params[1].startswith("#"):
                            channels.add(msg.params[1])
                    elif msg.command == "315":
                        return sorted(channels)
                    elif msg.command == "PING":
                        token = msg.params[0] if msg.params else ""
                        writer.write(f"PONG :{token}\r\n".encode())
                        await writer.drain()
            return sorted(channels)
        except asyncio.TimeoutError:
            return sorted(channels) if "channels" in dir() else []
        finally:
            await self._disconnect(writer)

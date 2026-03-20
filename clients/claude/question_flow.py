# clients/claude/question_flow.py
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.claude.irc_connection import IRCConnection
    from clients.claude.webhook import WebhookClient
    from clients.claude.config import DaemonConfig

logger = logging.getLogger(__name__)


class QuestionFlow:
    """Manages blocking IRC questions and answer routing."""

    def __init__(
        self,
        irc: IRCConnection,
        webhooks: WebhookClient,
        config: DaemonConfig,
    ):
        self._irc = irc
        self._webhooks = webhooks
        self._config = config

    async def ask(
        self,
        channel: str,
        question: str,
        correlation_id: str,
        future: asyncio.Future,
        timeout: float = 120.0,
    ) -> None:
        """Post a question to IRC and block until answered or timed out."""
        our_nick = self._irc.nick
        await self._irc.send_privmsg(channel, f"[QUESTION] {question}")
        await self._irc.send_privmsg(
            channel, f"Waiting for response. Reply with: @{our_nick} <answer>"
        )
        await self._webhooks.post(
            self._config.webhooks.on_question,
            {"question": question, "channel": channel, "correlation_id": correlation_id},
        )

        try:
            await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.TimeoutError:
            await self._webhooks.post(
                self._config.webhooks.on_timeout,
                {"question": question, "channel": channel, "correlation_id": correlation_id},
            )
            if not future.done():
                future.set_exception(TimeoutError(f"No answer within {timeout}s"))

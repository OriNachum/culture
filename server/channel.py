from __future__ import annotations
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from server.client import Client
    from server.remote_client import RemoteClient

    Member = Union[Client, RemoteClient]


class Channel:
    """Represents an IRC channel with members and topic."""

    def __init__(self, name: str):
        self.name = name
        self.topic: str | None = None
        self.members: set[Client] = set()
        self.operators: set[Client] = set()
        self.voiced: set[Client] = set()

    def add(self, client: Client) -> None:
        if not self.members:
            self.operators.add(client)
        self.members.add(client)

    def remove(self, client: Client) -> None:
        self.members.discard(client)
        was_op = client in self.operators
        self.operators.discard(client)
        self.voiced.discard(client)
        if was_op and not self.operators and self.members:
            self.operators.add(min(self.members, key=lambda m: m.nick))

    def is_operator(self, client: Client) -> bool:
        return client in self.operators

    def is_voiced(self, client: Client) -> bool:
        return client in self.voiced

    def get_prefix(self, client: Client) -> str:
        if client in self.operators:
            return "@"
        if client in self.voiced:
            return "+"
        return ""

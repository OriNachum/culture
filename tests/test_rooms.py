"""Tests for rooms management."""
import pytest


def test_channel_has_room_metadata_fields():
    """Channel should have room metadata fields, all None/empty by default."""
    from agentirc.server.channel import Channel

    ch = Channel("#test")
    assert ch.room_id is None
    assert ch.creator is None
    assert ch.owner is None
    assert ch.purpose is None
    assert ch.instructions is None
    assert ch.tags == []
    assert ch.persistent is False
    assert ch.agent_limit is None
    assert ch.extra_meta == {}
    assert ch.archived is False
    assert ch.created_at is None


def test_channel_is_managed():
    """Channel with room_id is considered managed."""
    from agentirc.server.channel import Channel

    ch = Channel("#test")
    assert ch.is_managed is False
    ch.room_id = "R7K2M9"
    assert ch.is_managed is True

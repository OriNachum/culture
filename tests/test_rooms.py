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


def test_generate_room_id_format():
    """Room ID starts with R followed by uppercase alphanumeric."""
    from agentirc.server.rooms_util import generate_room_id
    import re

    rid = generate_room_id()
    assert rid.startswith("R")
    assert len(rid) >= 6
    assert re.match(r"^R[0-9A-Z]+$", rid)


def test_generate_room_id_uniqueness():
    """Two consecutive calls produce different IDs."""
    from agentirc.server.rooms_util import generate_room_id

    ids = {generate_room_id() for _ in range(100)}
    assert len(ids) == 100


def test_parse_room_meta_basic():
    """Parse key=value pairs separated by semicolons."""
    from agentirc.server.rooms_util import parse_room_meta

    meta = parse_room_meta("purpose=Help with Python;tags=python,code-help;persistent=true")
    assert meta["purpose"] == "Help with Python"
    assert meta["tags"] == "python,code-help"
    assert meta["persistent"] == "true"


def test_parse_room_meta_instructions_last():
    """Instructions field is always last and may contain semicolons."""
    from agentirc.server.rooms_util import parse_room_meta

    meta = parse_room_meta(
        "purpose=Help;tags=py;instructions=Do this; then that; finally done"
    )
    assert meta["purpose"] == "Help"
    assert meta["tags"] == "py"
    assert meta["instructions"] == "Do this; then that; finally done"


def test_parse_room_meta_empty():
    """Empty string returns empty dict."""
    from agentirc.server.rooms_util import parse_room_meta

    assert parse_room_meta("") == {}

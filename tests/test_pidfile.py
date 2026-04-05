"""Tests for culture.pidfile — PID file management and process validation."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from culture.pidfile import (
    is_culture_process,
    is_process_alive,
    read_pid,
    remove_pid,
    write_pid,
)


@pytest.fixture()
def pid_dir(tmp_path):
    """Use a temporary directory for PID files."""
    with patch("culture.pidfile.PID_DIR", str(tmp_path)):
        yield tmp_path


class TestWriteReadRemove:
    def test_write_and_read(self, pid_dir):
        write_pid("agent-bot", 12345)
        assert read_pid("agent-bot") == 12345

    def test_read_missing(self, pid_dir):
        assert read_pid("nonexistent") is None

    def test_remove(self, pid_dir):
        write_pid("agent-bot", 12345)
        remove_pid("agent-bot")
        assert read_pid("agent-bot") is None

    def test_remove_missing_is_noop(self, pid_dir):
        remove_pid("nonexistent")  # should not raise


class TestIsProcessAlive:
    def test_current_process_alive(self):
        assert is_process_alive(os.getpid()) is True

    def test_nonexistent_pid(self):
        # PID 0 is kernel — os.kill(0,0) would signal the process group.
        # Use a very high PID unlikely to exist.
        assert is_process_alive(4_000_000) is False


class TestIsCultureProcess:
    @pytest.mark.skipif(
        not Path("/proc/self/cmdline").exists(),
        reason="/proc not available",
    )
    def test_current_process_is_python(self):
        # We're running under pytest, so cmdline contains "python" or the
        # test runner. It should also contain "culture" if run from the
        # culture project (pytest discovers culture modules).
        # At minimum, verify it doesn't crash and returns a bool.
        result = is_culture_process(os.getpid())
        assert isinstance(result, bool)

    @pytest.mark.skipif(
        not Path("/proc/self/cmdline").exists(),
        reason="/proc not available",
    )
    def test_nonexistent_pid_returns_true(self):
        # /proc/<pid>/cmdline won't exist — OSError path returns True
        assert is_culture_process(4_000_000) is True

    @pytest.mark.skipif(
        not Path("/proc/self/cmdline").exists(),
        reason="/proc not available",
    )
    def test_init_process_is_not_culture(self):
        # PID 1 (init/systemd) should not contain "culture" in cmdline
        result = is_culture_process(1)
        assert result is False

    def test_oserror_returns_true(self):
        """When /proc is unavailable, assume the PID is valid."""
        with patch("culture.pidfile.Path") as mock_path:
            mock_path.return_value.read_bytes.side_effect = OSError("no /proc")
            assert is_culture_process(999) is True

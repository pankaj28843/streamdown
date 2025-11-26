"""Tests for domain enums."""

import pytest

from streamdown.domain import (
    ChunkStatus,
    DownloadStatus,
    ResumeDecision,
    StreamingMode,
)


class TestDownloadStatus:
    """Tests for DownloadStatus enum."""

    def test_all_statuses_exist(self):
        """Test that all expected statuses are defined."""
        assert DownloadStatus.PENDING
        assert DownloadStatus.RUNNING
        assert DownloadStatus.COMPLETED
        assert DownloadStatus.FAILED
        assert DownloadStatus.CANCELLED

    def test_terminal_statuses(self):
        """Test is_terminal method."""
        assert DownloadStatus.COMPLETED.is_terminal()
        assert DownloadStatus.FAILED.is_terminal()
        assert DownloadStatus.CANCELLED.is_terminal()
        assert not DownloadStatus.PENDING.is_terminal()
        assert not DownloadStatus.RUNNING.is_terminal()

    def test_active_status(self):
        """Test is_active method."""
        assert DownloadStatus.RUNNING.is_active()
        assert not DownloadStatus.PENDING.is_active()
        assert not DownloadStatus.COMPLETED.is_active()
        assert not DownloadStatus.FAILED.is_active()


class TestChunkStatus:
    """Tests for ChunkStatus enum."""

    def test_all_statuses_exist(self):
        """Test that all expected statuses are defined."""
        assert ChunkStatus.PENDING
        assert ChunkStatus.IN_PROGRESS
        assert ChunkStatus.COMPLETED
        assert ChunkStatus.FAILED

    def test_terminal_statuses(self):
        """Test is_terminal method."""
        assert ChunkStatus.COMPLETED.is_terminal()
        assert ChunkStatus.FAILED.is_terminal()
        assert not ChunkStatus.PENDING.is_terminal()
        assert not ChunkStatus.IN_PROGRESS.is_terminal()

    def test_active_status(self):
        """Test is_active method."""
        assert ChunkStatus.IN_PROGRESS.is_active()
        assert not ChunkStatus.PENDING.is_active()
        assert not ChunkStatus.COMPLETED.is_active()
        assert not ChunkStatus.FAILED.is_active()


class TestStreamingMode:
    """Tests for StreamingMode enum."""

    def test_all_modes_exist(self):
        """Test that all expected modes are defined."""
        assert StreamingMode.DEFAULT
        assert StreamingMode.INORDER
        assert StreamingMode.GEOM

    def test_from_string_lowercase(self):
        """Test parsing from lowercase string."""
        assert StreamingMode.from_string("default") == StreamingMode.DEFAULT
        assert StreamingMode.from_string("inorder") == StreamingMode.INORDER
        assert StreamingMode.from_string("geom") == StreamingMode.GEOM

    def test_from_string_uppercase(self):
        """Test parsing from uppercase string."""
        assert StreamingMode.from_string("DEFAULT") == StreamingMode.DEFAULT
        assert StreamingMode.from_string("INORDER") == StreamingMode.INORDER
        assert StreamingMode.from_string("GEOM") == StreamingMode.GEOM

    def test_from_string_mixed_case(self):
        """Test parsing from mixed case string."""
        assert StreamingMode.from_string("Default") == StreamingMode.DEFAULT
        assert StreamingMode.from_string("InOrder") == StreamingMode.INORDER

    def test_from_string_invalid_raises_error(self):
        """Test that invalid mode string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid streaming mode"):
            StreamingMode.from_string("invalid")


class TestResumeDecision:
    """Tests for ResumeDecision enum."""

    def test_all_decisions_exist(self):
        """Test that all expected decisions are defined."""
        assert ResumeDecision.CAN_RESUME
        assert ResumeDecision.MUST_RESTART
        assert ResumeDecision.ERROR

    def test_should_resume(self):
        """Test should_resume method."""
        assert ResumeDecision.CAN_RESUME.should_resume()
        assert not ResumeDecision.MUST_RESTART.should_resume()
        assert not ResumeDecision.ERROR.should_resume()

    def test_should_restart(self):
        """Test should_restart method."""
        assert ResumeDecision.MUST_RESTART.should_restart()
        assert not ResumeDecision.CAN_RESUME.should_restart()
        assert not ResumeDecision.ERROR.should_restart()

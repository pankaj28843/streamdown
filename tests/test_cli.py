"""Unit tests for CLI default values and argument parsing."""

from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from streamdown.cli.main import app, parse_piece_size
from streamdown.domain.enums import DownloadStatus

runner = CliRunner()


class TestPieceSizeParsing:
    """Test piece size parsing with K/M suffixes."""

    def test_parse_bytes(self):
        """Test parsing plain byte values."""
        assert parse_piece_size("1024") == 1024
        assert parse_piece_size("512") == 512
        assert parse_piece_size("1048576") == 1048576

    def test_parse_kilobytes(self):
        """Test parsing with K suffix."""
        assert parse_piece_size("1K") == 1024
        assert parse_piece_size("512K") == 512 * 1024
        assert parse_piece_size("1k") == 1024  # Case insensitive

    def test_parse_megabytes(self):
        """Test parsing with M suffix."""
        assert parse_piece_size("1M") == 1024 * 1024
        assert parse_piece_size("10M") == 10 * 1024 * 1024
        assert parse_piece_size("1m") == 1024 * 1024  # Case insensitive

    def test_parse_invalid(self):
        """Test parsing invalid size strings."""
        with pytest.raises(ValueError):
            parse_piece_size("invalid")

        with pytest.raises(ValueError):
            parse_piece_size("1G")  # G suffix not supported


class TestDefaultValues:
    """
    Test CLI default values.

    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
    """

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_default_directory_is_cwd(self, mock_start_download, mock_progress_display):
        """
        Test default directory is current working directory.

        Requirement 7.1: WHEN no directory is specified THEN Streamdown SHALL
        download to the current working directory
        """
        # Mock the download to return success
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["https://example.com/file.zip"])

        # Check that start_download was called
        assert mock_start_download.called

        # Get the options passed to start_download
        call_args = mock_start_download.call_args
        options = call_args[0][1]  # Second argument is options

        # Verify directory is current working directory
        assert options.directory == Path.cwd()

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_default_splits_is_8(self, mock_start_download, mock_progress_display):
        """
        Test default splits is 8.

        Requirement 7.2: WHEN no split count is specified THEN Streamdown SHALL
        use 8 parallel chunks by default
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # Verify splits is 8
        assert options.splits == 8

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_default_piece_size_is_1mib(self, mock_start_download, mock_progress_display):
        """
        Test default piece size is 1 MiB.

        Requirement 7.3: WHEN no piece size is specified THEN Streamdown SHALL
        use 1 MiB chunks by default
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # Verify piece size is 1 MiB (1048576 bytes)
        assert options.piece_size == 1048576

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_default_continue_is_enabled(self, mock_start_download, mock_progress_display):
        """
        Test default continue is enabled.

        Requirement 7.4: WHEN no continue flag is specified THEN Streamdown SHALL
        enable resume by default
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # Verify continue_download is True
        assert options.continue_download is True

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_default_allow_overwrite_is_disabled(self, mock_start_download, mock_progress_display):
        """
        Test default allow-overwrite is disabled.

        Requirement 7.5: WHEN no overwrite flag is specified THEN Streamdown SHALL
        prevent overwriting existing complete files by default
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # Verify allow_overwrite is False
        assert options.allow_overwrite is False

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_default_netrc_is_enabled(self, mock_start_download, mock_progress_display):
        """
        Test default netrc is enabled (no_netrc is False).

        Requirement 15.4: Netrc should be enabled by default
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # Verify no_netrc is False (netrc is enabled)
        assert options.no_netrc is False

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_default_netrc_path_is_none(self, mock_start_download, mock_progress_display):
        """
        Test default netrc_path is None (uses ~/.netrc).

        Requirement 15.5: Default netrc path should be None (uses ~/.netrc)
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # Verify netrc_path is None
        assert options.netrc_path is None


class TestOptionValidation:
    """Test CLI option validation."""

    def test_output_name_with_multiple_urls_fails(self):
        """Test that -o with multiple URLs produces an error."""
        result = runner.invoke(
            app,
            [
                "-o",
                "output.zip",
                "https://example.com/file1.zip",
                "https://example.com/file2.zip",
            ],
        )

        assert result.exit_code == 2
        # Error messages go to stderr in typer
        output = result.stdout + result.stderr
        assert "can only be used with a single URL" in output

    def test_max_connections_exceeds_splits_fails(self):
        """Test that max-connections-per-host > splits produces an error."""
        result = runner.invoke(
            app,
            [
                "-s",
                "4",
                "-x",
                "8",
                "https://example.com/file.zip",
            ],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "cannot exceed splits" in output

    def test_invalid_piece_size_fails(self):
        """Test that invalid piece size produces an error."""
        result = runner.invoke(
            app,
            [
                "-k",
                "invalid",
                "https://example.com/file.zip",
            ],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Invalid piece size" in output

    def test_invalid_streaming_mode_fails(self):
        """Test that invalid streaming mode produces an error."""
        result = runner.invoke(
            app,
            [
                "--streaming-mode",
                "invalid",
                "https://example.com/file.zip",
            ],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Invalid streaming mode" in output

    def test_invalid_log_level_fails(self):
        """Test that invalid log level produces an error."""
        result = runner.invoke(
            app,
            [
                "--log-level",
                "invalid",
                "https://example.com/file.zip",
            ],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Invalid log level" in output


class TestE2ECliTests:
    """
    E2E CLI tests.

    Requirements: 5.1, 5.2, 7.1
    """

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_cli_argument_parsing(self, mock_start_download, mock_progress_display):
        """
        Test CLI argument parsing with various options.

        Verifies that CLI correctly parses and passes arguments to the application layer.
        """
        from streamdown.application.dtos import DownloadResult
        from streamdown.domain.enums import StreamingMode

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("/tmp/downloads/file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        result = runner.invoke(
            app,
            [
                "-d",
                "/tmp/downloads",
                "-s",
                "16",
                "-k",
                "2M",
                "--streaming-mode",
                "inorder",
                "-j",
                "2",
                "--max-tries",
                "3",
                "--retry-wait",
                "1.5",
                "https://example.com/file.zip",
            ],
        )

        assert result.exit_code == 0
        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # Verify all options were parsed correctly
        assert options.directory.resolve() == Path("/tmp/downloads").resolve()
        assert options.splits == 16
        assert options.piece_size == 2 * 1024 * 1024
        assert options.streaming_mode == StreamingMode.INORDER
        assert options.max_concurrent_downloads == 2
        assert options.max_tries == 3
        assert options.retry_wait == 1.5

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_multiple_urls_with_j_flag(self, mock_start_download, mock_progress_display):
        """
        Test multiple URLs with -j flag.

        Requirement 5.1: WHEN multiple URLs are provided THEN Streamdown SHALL
        queue all downloads for processing

        Requirement 5.2: WHEN max-concurrent-downloads is specified THEN Streamdown
        SHALL limit active downloads to that number
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file1.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file1.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            ),
            DownloadResult(
                url="https://example.com/file2.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file2.zip"),
                error=None,
                bytes_downloaded=2048,
                duration=1.5,
            ),
            DownloadResult(
                url="https://example.com/file3.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file3.zip"),
                error=None,
                bytes_downloaded=3072,
                duration=2.0,
            ),
        ]

        result = runner.invoke(
            app,
            [
                "-j",
                "2",
                "https://example.com/file1.zip",
                "https://example.com/file2.zip",
                "https://example.com/file3.zip",
            ],
        )

        assert result.exit_code == 0
        assert mock_start_download.called

        # Verify all URLs were passed
        call_args = mock_start_download.call_args
        urls = call_args[0][0]
        assert len(urls) == 3
        assert "https://example.com/file1.zip" in urls
        assert "https://example.com/file2.zip" in urls
        assert "https://example.com/file3.zip" in urls

        # Verify max_concurrent_downloads was set
        options = call_args[0][1]
        assert options.max_concurrent_downloads == 2

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_output_directory_with_d_flag(self, mock_start_download, mock_progress_display):
        """
        Test output directory with -d flag.

        Requirement 7.1: WHEN no directory is specified THEN Streamdown SHALL
        download to the current working directory (tested in default tests)

        This test verifies custom directory specification works.
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("/custom/dir/file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        result = runner.invoke(
            app,
            ["-d", "/custom/dir", "https://example.com/file.zip"],
        )

        assert result.exit_code == 0
        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.directory.resolve() == Path("/custom/dir").resolve()

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_output_filename_with_o_flag(self, mock_start_download, mock_progress_display):
        """
        Test output filename with -o flag.

        Verifies that custom output filename is passed correctly.
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("custom_name.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        result = runner.invoke(
            app,
            ["-o", "custom_name.zip", "https://example.com/file.zip"],
        )

        assert result.exit_code == 0
        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.output_name == "custom_name.zip"

    def test_invalid_option_combination_o_with_multiple_urls(self):
        """
        Test invalid option combination: -o with multiple URLs.

        Verifies that using -o flag with multiple URLs produces an error.
        """
        result = runner.invoke(
            app,
            [
                "-o",
                "output.zip",
                "https://example.com/file1.zip",
                "https://example.com/file2.zip",
            ],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "can only be used with a single URL" in output

    def test_invalid_option_combination_max_connections_exceeds_splits(self):
        """
        Test invalid option combination: max-connections-per-host > splits.

        Verifies that max-connections-per-host exceeding splits produces an error.
        """
        result = runner.invoke(
            app,
            [
                "-s",
                "4",
                "-x",
                "8",
                "https://example.com/file.zip",
            ],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "cannot exceed splits" in output

    def test_error_message_invalid_piece_size(self):
        """
        Test error message for invalid piece size.

        Verifies that invalid piece size produces a clear error message.
        """
        result = runner.invoke(
            app,
            ["-k", "invalid", "https://example.com/file.zip"],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Invalid piece size" in output

    def test_error_message_invalid_streaming_mode(self):
        """
        Test error message for invalid streaming mode.

        Verifies that invalid streaming mode produces a clear error message.
        """
        result = runner.invoke(
            app,
            ["--streaming-mode", "invalid", "https://example.com/file.zip"],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Invalid streaming mode" in output

    def test_error_message_invalid_log_level(self):
        """
        Test error message for invalid log level.

        Verifies that invalid log level produces a clear error message.
        """
        result = runner.invoke(
            app,
            ["--log-level", "invalid", "https://example.com/file.zip"],
        )

        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Invalid log level" in output

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_exit_code_success(self, mock_start_download, mock_progress_display):
        """
        Test exit code 0 on successful download.

        Verifies that successful downloads return exit code 0.
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        result = runner.invoke(app, ["https://example.com/file.zip"])

        assert result.exit_code == 0

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_exit_code_failure(self, mock_start_download, mock_progress_display):
        """
        Test exit code 1 on failed download.

        Verifies that failed downloads return exit code 1.
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.FAILED,
                final_path=None,
                error="Network error",
                bytes_downloaded=0,
                duration=0.5,
            )
        ]

        result = runner.invoke(app, ["https://example.com/file.zip"])

        assert result.exit_code == 1

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_exit_code_partial_failure(self, mock_start_download, mock_progress_display):
        """
        Test exit code 1 when some downloads fail.

        Verifies that partial failures return exit code 1.
        """
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file1.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file1.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            ),
            DownloadResult(
                url="https://example.com/file2.zip",
                status=DownloadStatus.FAILED,
                final_path=None,
                error="Network error",
                bytes_downloaded=0,
                duration=0.5,
            ),
        ]

        result = runner.invoke(
            app,
            [
                "https://example.com/file1.zip",
                "https://example.com/file2.zip",
            ],
        )

        assert result.exit_code == 1


class TestCustomOptions:
    """Test CLI with custom option values."""

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_custom_directory(self, mock_start_download, mock_progress_display):
        """Test setting custom directory."""
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("/tmp/file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["-d", "/tmp", "https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        # On macOS, /tmp is a symlink to /private/tmp, so resolve both
        assert options.directory.resolve() == Path("/tmp").resolve()

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_custom_splits(self, mock_start_download, mock_progress_display):
        """Test setting custom splits."""
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["-s", "16", "https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.splits == 16

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_custom_piece_size(self, mock_start_download, mock_progress_display):
        """Test setting custom piece size."""
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["-k", "512K", "https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.piece_size == 512 * 1024

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_disable_continue(self, mock_start_download, mock_progress_display):
        """Test disabling continue."""
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["--no-continue", "https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.continue_download is False

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_enable_allow_overwrite(self, mock_start_download, mock_progress_display):
        """Test enabling allow-overwrite."""
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["--allow-overwrite", "https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.allow_overwrite is True

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_streaming_mode_inorder(self, mock_start_download, mock_progress_display):
        """Test setting streaming mode to inorder."""
        from streamdown.application.dtos import DownloadResult
        from streamdown.domain.enums import StreamingMode

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(
            app,
            ["--streaming-mode", "inorder", "https://example.com/file.zip"],
        )

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.streaming_mode == StreamingMode.INORDER

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_no_netrc_flag(self, mock_start_download, mock_progress_display):
        """Test setting --no-netrc flag."""
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(app, ["--no-netrc", "https://example.com/file.zip"])

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.no_netrc is True

    @patch("streamdown.cli.main.ProgressDisplay")
    @patch("streamdown.cli.main.start_download", new_callable=AsyncMock)
    def test_custom_netrc_path(self, mock_start_download, mock_progress_display):
        """Test setting custom netrc path."""
        from streamdown.application.dtos import DownloadResult

        # Mock ProgressDisplay context manager
        mock_progress_instance = MagicMock()
        mock_progress_display.return_value.__enter__.return_value = mock_progress_instance
        mock_progress_display.return_value.__exit__.return_value = None

        mock_start_download.return_value = [
            DownloadResult(
                url="https://example.com/file.zip",
                status=DownloadStatus.COMPLETED,
                final_path=Path("file.zip"),
                error=None,
                bytes_downloaded=1024,
                duration=1.0,
            )
        ]

        runner.invoke(
            app,
            ["--netrc-path", "/custom/netrc", "https://example.com/file.zip"],
        )

        assert mock_start_download.called

        call_args = mock_start_download.call_args
        options = call_args[0][1]

        assert options.netrc_path == Path("/custom/netrc")


class TestNarrowTerminalScenarios:
    """
    Test CLI with narrow terminal scenarios.

    Requirements: 16.1, 16.2, 16.3
    """

    def test_terminal_width_detection(self):
        """
        Test terminal width detection.

        Requirement 16.1: WHEN the terminal width is less than 80 columns THEN
        Streamdown SHALL detect the narrow width and adjust the display layout
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
            # Create a mock terminal size object
            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            # Test narrow terminal (60 columns)
            mock_get_size.return_value = MockTerminalSize(60)
            display = ProgressDisplay(quiet=True)

            assert display.get_terminal_width() == 60
            assert display.is_narrow_terminal() is True

            # Test wide terminal (120 columns)
            mock_get_size.return_value = MockTerminalSize(120)
            display = ProgressDisplay(quiet=True)

            assert display.get_terminal_width() == 120
            assert display.is_narrow_terminal() is False

            # Test boundary at 80 columns
            mock_get_size.return_value = MockTerminalSize(80)
            display = ProgressDisplay(quiet=True)

            assert display.get_terminal_width() == 80
            assert display.is_narrow_terminal() is False

            # Test just below boundary (79 columns)
            mock_get_size.return_value = MockTerminalSize(79)
            display = ProgressDisplay(quiet=True)

            assert display.get_terminal_width() == 79
            assert display.is_narrow_terminal() is True

    def test_filename_truncation_short_names(self):
        """
        Test filename truncation with short filenames.

        Requirement 16.2: WHEN displaying filenames on narrow terminals THEN
        Streamdown SHALL truncate long filenames to fit within available space
        while preserving file extension
        """
        from streamdown.cli.progress_display import ProgressDisplay

        display = ProgressDisplay(quiet=True)

        # Short filenames should not be truncated
        result = display.format_filename("file.txt", 50)
        assert result == "file.txt"

        result = display.format_filename("document.pdf", 50)
        assert result == "document.pdf"

        result = display.format_filename("video.mp4", 50)
        assert result == "video.mp4"

    def test_filename_truncation_long_names(self):
        """
        Test filename truncation with long filenames.

        Requirement 16.2: WHEN displaying filenames on narrow terminals THEN
        Streamdown SHALL truncate long filenames to fit within available space
        while preserving file extension
        """
        from streamdown.cli.progress_display import ProgressDisplay

        display = ProgressDisplay(quiet=True)

        # Long filename should be truncated with extension preserved
        long_name = "Writing.With.Fire.2021.1080p.WEBRip.x264.AAC-[YTS.MX].mp4"
        result = display.format_filename(long_name, 30)

        assert len(result) <= 30
        assert "..." in result
        assert result.endswith("YTS.MX].mp4")  # Last 15 chars preserved
        assert result.startswith("Writing")  # Start preserved

    def test_filename_truncation_various_lengths(self):
        """
        Test filename truncation with various max widths.

        Requirement 16.2: WHEN displaying filenames on narrow terminals THEN
        Streamdown SHALL truncate long filenames to fit within available space
        while preserving file extension
        """
        from streamdown.cli.progress_display import ProgressDisplay

        display = ProgressDisplay(quiet=True)

        long_filename = "Very.Long.Filename.With.Many.Segments.And.Extension.mp4"

        # Test various max widths
        for max_width in [20, 30, 40, 50, 60]:
            result = display.format_filename(long_filename, max_width)

            # Result should not exceed max_width (or minimum of 20)
            effective_max = max(max_width, 20)
            assert len(result) <= effective_max, (
                f"Filename '{result}' (length {len(result)}) exceeds max_width {effective_max}"
            )

            # If truncation occurred, should have ellipsis
            if len(long_filename) > max_width:
                assert "..." in result

    def test_filename_truncation_preserves_extension(self):
        """
        Test that filename truncation preserves file extensions.

        Requirement 16.2: WHEN displaying filenames on narrow terminals THEN
        Streamdown SHALL truncate long filenames to fit within available space
        while preserving file extension
        """
        from streamdown.cli.progress_display import ProgressDisplay

        display = ProgressDisplay(quiet=True)

        # Test various file extensions
        test_cases = [
            ("a" * 100 + ".txt", 30, ".txt"),
            ("b" * 100 + ".mp4", 30, ".mp4"),
            ("c" * 100 + ".zip", 30, ".zip"),
            ("d" * 100 + ".tar.gz", 30, ".tar.gz"),
            ("e" * 100 + ".mkv", 30, ".mkv"),
        ]

        for filename, max_width, _expected_ext in test_cases:
            result = display.format_filename(filename, max_width)

            # Should preserve last 15 characters (which includes extension)
            assert result.endswith(filename[-15:]), (
                f"Expected '{result}' to end with '{filename[-15:]}'"
            )

    def test_filename_truncation_minimum_width(self):
        """
        Test that filename truncation enforces minimum width.

        Requirement 16.2: Minimum display of 20 characters
        """
        from streamdown.cli.progress_display import ProgressDisplay

        display = ProgressDisplay(quiet=True)

        long_filename = "a" * 100 + ".txt"

        # Even with very small max_width, should enforce minimum of 20
        result = display.format_filename(long_filename, 10)
        assert len(result) == 20

        result = display.format_filename(long_filename, 5)
        assert len(result) == 20

        result = display.format_filename(long_filename, 15)
        assert len(result) == 20

    def test_progress_display_on_narrow_terminal(self):
        """
        Test progress display adapts to narrow terminals.

        Requirement 16.1: WHEN the terminal width is less than 80 columns THEN
        Streamdown SHALL detect the narrow width and adjust the display layout

        Requirement 16.3: WHEN displaying progress information on narrow terminals
        THEN Streamdown SHALL prioritize essential information and omit or
        abbreviate less critical details
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
            # Create a mock terminal size object
            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            # Test narrow terminal (60 columns)
            mock_get_size.return_value = MockTerminalSize(60)

            display = ProgressDisplay(quiet=False)

            # Verify narrow terminal is detected
            assert display.is_narrow_terminal() is True

            # Verify bar width is appropriate for narrow terminal (10-20 chars)
            bar_width = display.calculate_bar_width()
            assert 10 <= bar_width <= 20, (
                f"Bar width {bar_width} should be between 10-20 for narrow terminal"
            )

    def test_progress_display_narrow_context_smoke(self):
        """
        Test that narrow progress display construction can add/update/exit.
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:

            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            mock_get_size.return_value = MockTerminalSize(40)
            display = ProgressDisplay(quiet=False)
            display.console = Console(
                width=40,
                record=True,
                force_terminal=False,
                color_system=None,
                file=StringIO(),
            )

            with display:
                url = "https://example.test/file.zip"
                display.add_download(url, "very-long-file-name-for-narrow-display.zip", 100)
                display.update_status(url, DownloadStatus.RUNNING)
                display.update_progress(url, 50, 100)
                display.mark_complete(url, Path("file.zip"))

            assert url in display.downloads
            assert display.downloads[url].status == DownloadStatus.COMPLETED

    def test_progress_display_on_wide_terminal(self):
        """
        Test progress display on wide terminals.

        Requirement 16.1: Wide terminals (≥80 cols) should use full display
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
            # Create a mock terminal size object
            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            # Test wide terminal (120 columns)
            mock_get_size.return_value = MockTerminalSize(120)

            display = ProgressDisplay(quiet=False)

            # Verify wide terminal is detected
            assert display.is_narrow_terminal() is False

            # Verify bar width is appropriate for wide terminal (40-60 chars)
            bar_width = display.calculate_bar_width()
            assert 40 <= bar_width <= 60, (
                f"Bar width {bar_width} should be between 40-60 for wide terminal"
            )

    def test_compact_size_formatting(self):
        """
        Test compact size formatting for narrow terminals.

        Requirement 16.3: WHEN displaying progress information on narrow terminals
        THEN Streamdown SHALL prioritize essential information and omit or
        abbreviate less critical details

        Compact format should be: "1.7GB" instead of "1.7 GB / 68.2 GB"
        """
        from streamdown.cli.progress_display import ProgressDisplay

        display = ProgressDisplay(quiet=True)

        # Test bytes
        assert display.format_size_compact(0) == "0B"
        assert display.format_size_compact(512) == "512B"
        assert display.format_size_compact(1023) == "1023B"

        # Test kilobytes
        assert display.format_size_compact(1024) == "1.0KB"
        assert display.format_size_compact(5 * 1024) == "5.0KB"
        assert display.format_size_compact(10 * 1024) == "10KB"
        assert display.format_size_compact(100 * 1024) == "100KB"

        # Test megabytes
        assert display.format_size_compact(1024 * 1024) == "1.0MB"
        assert display.format_size_compact(5 * 1024 * 1024) == "5.0MB"
        assert display.format_size_compact(234 * 1024 * 1024) == "234MB"

        # Test gigabytes
        assert display.format_size_compact(1024 * 1024 * 1024) == "1.0GB"
        assert display.format_size_compact(int(1.7 * 1024 * 1024 * 1024)) == "1.7GB"
        assert display.format_size_compact(68 * 1024 * 1024 * 1024) == "68GB"

        # Test terabytes
        assert display.format_size_compact(1024 * 1024 * 1024 * 1024) == "1.0TB"

    def test_compact_size_no_spaces(self):
        """
        Test that compact size format contains no spaces.

        Requirement 16.3: Compact format should be "1.7GB" not "1.7 GB"
        """
        from streamdown.cli.progress_display import ProgressDisplay

        display = ProgressDisplay(quiet=True)

        # Test various sizes to ensure no spaces
        test_sizes = [
            0,
            512,
            1024,
            1024 * 1024,
            1024 * 1024 * 1024,
            int(1.7 * 1024 * 1024 * 1024),
            68 * 1024 * 1024 * 1024,
        ]

        for size in test_sizes:
            result = display.format_size_compact(size)
            assert " " not in result, f"Compact size '{result}' should not contain spaces"

    def test_terminal_width_at_various_sizes(self):
        """
        Test terminal width detection at various sizes.

        Requirement 16.1: WHEN the terminal width is less than 80 columns THEN
        Streamdown SHALL detect the narrow width and adjust the display layout
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
            # Create a mock terminal size object
            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            # Test various terminal widths
            test_widths = [40, 60, 79, 80, 100, 120, 160, 200]

            for width in test_widths:
                mock_get_size.return_value = MockTerminalSize(width)
                display = ProgressDisplay(quiet=True)

                detected_width = display.get_terminal_width()
                assert detected_width == width, f"Expected width {width}, got {detected_width}"

                # Verify narrow detection
                is_narrow = display.is_narrow_terminal()
                expected_narrow = width < 80
                assert is_narrow == expected_narrow, (
                    f"For width {width}, expected narrow={expected_narrow}, got {is_narrow}"
                )

    def test_bar_width_scaling(self):
        """
        Test that progress bar width scales with terminal width.

        Requirement 16.5: WHEN the progress bar is displayed on narrow terminals
        THEN Streamdown SHALL scale the bar width proportionally to terminal width
        while maintaining readability
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
            # Create a mock terminal size object
            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            # Test bar width at various terminal widths
            test_cases = [
                (40, 10),  # Very narrow -> minimum bar width
                (60, 15),  # Narrow -> scaled bar width
                (79, 19),  # Just below threshold -> max narrow bar
                (80, 40),  # At threshold -> min wide bar
                (120, 50),  # Wide -> scaled bar width
                (200, 60),  # Very wide -> max bar width
            ]

            for terminal_width, expected_bar_width in test_cases:
                mock_get_size.return_value = MockTerminalSize(terminal_width)
                display = ProgressDisplay(quiet=True)

                bar_width = display.calculate_bar_width()
                assert bar_width == expected_bar_width, (
                    f"For terminal width {terminal_width}, expected bar width "
                    f"{expected_bar_width}, got {bar_width}"
                )

    def test_bar_width_minimum_enforced(self):
        """
        Test that minimum bar width of 10 characters is enforced.

        Requirement 16.5: Minimum readable bar width of 10 characters
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
            # Create a mock terminal size object
            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            # Test very narrow terminals
            for width in [20, 30, 35, 40]:
                mock_get_size.return_value = MockTerminalSize(width)
                display = ProgressDisplay(quiet=True)

                bar_width = display.calculate_bar_width()
                assert bar_width >= 10, (
                    f"Bar width {bar_width} is below minimum of 10 for terminal width {width}"
                )

    def test_bar_width_maximum_enforced(self):
        """
        Test that maximum bar width of 60 characters is enforced.

        Requirement 16.5: Maximum bar width of 60 characters
        """
        from streamdown.cli.progress_display import ProgressDisplay

        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
            # Create a mock terminal size object
            class MockTerminalSize:
                def __init__(self, columns, lines=24):
                    self.columns = columns
                    self.lines = lines

            # Test very wide terminals
            for width in [200, 250, 300]:
                mock_get_size.return_value = MockTerminalSize(width)
                display = ProgressDisplay(quiet=True)

                bar_width = display.calculate_bar_width()
                assert bar_width <= 60, (
                    f"Bar width {bar_width} exceeds maximum of 60 for terminal width {width}"
                )

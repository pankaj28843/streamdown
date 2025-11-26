"""Unit tests for CLI default values and argument parsing."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
                "-o", "output.zip",
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
                "-s", "4",
                "-x", "8",
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
                "-k", "invalid",
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
                "--streaming-mode", "invalid",
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
                "--log-level", "invalid",
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
                "-d", "/tmp/downloads",
                "-s", "16",
                "-k", "2M",
                "--streaming-mode", "inorder",
                "-j", "2",
                "--max-tries", "3",
                "--retry-wait", "1.5",
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
                "-j", "2",
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
                "-o", "output.zip",
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
                "-s", "4",
                "-x", "8",
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

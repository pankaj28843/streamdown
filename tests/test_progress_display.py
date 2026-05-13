"""Property-based tests for ProgressDisplay terminal width detection."""

from io import StringIO
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st
from rich.cells import cell_len
from rich.console import Console

from streamdown.cli import progress_display
from streamdown.cli.progress_display import DownloadTracker, ProgressDisplay
from streamdown.domain.enums import DownloadStatus


class FakeProgress:
    """Small Progress test double that records update and refresh calls."""

    def __init__(self) -> None:
        self.update_calls: list[tuple[object, dict[str, object]]] = []
        self.refresh_count = 0

    def update(self, task_id, **kwargs) -> None:
        self.update_calls.append((task_id, kwargs))

    def refresh(self) -> None:
        self.refresh_count += 1


# Feature: streamdown, Property 36: Terminal width detection
@settings(deadline=500)
@given(
    terminal_width=st.integers(min_value=20, max_value=300),
)
def test_terminal_width_detection(terminal_width: int):
    """
    For any terminal environment, the system must correctly detect the terminal
    width and apply narrow-screen adaptations when width is less than 80 columns.

    This test verifies:
    1. get_terminal_width() correctly detects and returns terminal width
    2. is_narrow_terminal() returns True when width < 80
    3. is_narrow_terminal() returns False when width >= 80
    4. Terminal width is cached in instance variable

    **Validates: Requirements 16.1**
    """
    # Mock shutil.get_terminal_size to return our test width
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
        # Create a mock terminal size object
        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        mock_get_size.return_value = MockTerminalSize(terminal_width)

        # Create progress display instance
        display = ProgressDisplay(quiet=True)

        # Test get_terminal_width()
        detected_width = display.get_terminal_width()
        assert detected_width == terminal_width, (
            f"Expected terminal width {terminal_width}, got {detected_width}"
        )

        # Verify width is cached in instance variable
        assert display._terminal_width == terminal_width, (
            f"Terminal width not cached correctly: expected {terminal_width}, "
            f"got {display._terminal_width}"
        )

        # Test is_narrow_terminal()
        is_narrow = display.is_narrow_terminal()

        if terminal_width < 80:
            assert is_narrow is True, (
                f"Terminal with width {terminal_width} should be considered narrow (< 80)"
            )
        else:
            assert is_narrow is False, (
                f"Terminal with width {terminal_width} should not be considered narrow (>= 80)"
            )


def test_update_progress_forces_refresh_on_five_second_cadence(monkeypatch):
    """A visible refresh should be forced at most once per status interval."""
    display = ProgressDisplay(quiet=False)
    fake_progress = FakeProgress()
    display.progress = fake_progress  # type: ignore[assignment]
    display.downloads["https://example.com/file.bin"] = DownloadTracker(
        url="https://example.com/file.bin",
        filename="file.bin",
        task_id=1,  # type: ignore[arg-type]
        status=DownloadStatus.RUNNING,
        total_bytes=100,
        downloaded_bytes=0,
        start_time=0.0,
    )
    times = iter([100.0, 104.0, 105.0])
    monkeypatch.setattr(progress_display.time, "monotonic", lambda: next(times))

    display.update_progress("https://example.com/file.bin", 10, 100)
    display.update_progress("https://example.com/file.bin", 20, 100)
    display.update_progress("https://example.com/file.bin", 30, 100)

    assert fake_progress.refresh_count == 2


def test_terminal_width_fallback_on_error():
    """
    Test that get_terminal_width() falls back to cached value when
    shutil.get_terminal_size() raises an exception.

    This ensures the system handles environments where terminal size
    cannot be determined (e.g., non-TTY environments).
    """
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
        # First call succeeds
        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        mock_get_size.return_value = MockTerminalSize(100)

        display = ProgressDisplay(quiet=True)
        width = display.get_terminal_width()
        assert width == 100

        # Second call fails, should return cached value
        mock_get_size.side_effect = OSError("No terminal")
        width = display.get_terminal_width()
        assert width == 100  # Should return cached value


def test_terminal_width_default_on_initial_error():
    """
    Test that the default width (80) is used when terminal size
    cannot be determined on first call.
    """
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
        mock_get_size.side_effect = OSError("No terminal")

        display = ProgressDisplay(quiet=True)
        width = display.get_terminal_width()
        assert width == 80  # Should return default


def test_narrow_terminal_boundary_conditions():
    """
    Test boundary conditions for narrow terminal detection.

    Specifically tests widths around the 80-column threshold.
    """
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:

        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        # Test width = 79 (narrow)
        mock_get_size.return_value = MockTerminalSize(79)
        display = ProgressDisplay(quiet=True)
        assert display.is_narrow_terminal() is True

        # Test width = 80 (not narrow)
        mock_get_size.return_value = MockTerminalSize(80)
        display = ProgressDisplay(quiet=True)
        assert display.is_narrow_terminal() is False

        # Test width = 81 (not narrow)
        mock_get_size.return_value = MockTerminalSize(81)
        display = ProgressDisplay(quiet=True)
        assert display.is_narrow_terminal() is False


# Feature: streamdown, Property 37: Filename truncation preserves extension
@settings(deadline=500)
@given(
    filename=st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs", "Cc"),  # Exclude surrogates and control chars
            blacklist_characters=("\x00", "/", "\\", "\n", "\r", "\t"),
        ),
        min_size=1,
        max_size=500,
    ),
    max_width=st.integers(min_value=20, max_value=200),
)
def test_filename_truncation_preserves_extension(filename: str, max_width: int):
    """
    For any filename displayed on a narrow terminal, if truncation is needed,
    the file extension must be preserved and the truncated name must fit within
    the allocated space.

    This test verifies:
    1. Truncated filename length does not exceed max_width
    2. If filename has an extension, it is preserved in the truncated version
    3. Minimum width of 20 characters is enforced
    4. Filenames shorter than max_width are returned unchanged
    5. Truncation uses middle ellipsis pattern: "start...end"

    **Validates: Requirements 16.2**
    """
    display = ProgressDisplay(quiet=True)

    # Format the filename
    formatted = display.format_filename(filename, max_width)

    # Property 1: Formatted filename must not exceed max_width
    # (but enforce minimum of 20)
    effective_max_width = max(max_width, 20)
    assert len(formatted) <= effective_max_width, (
        f"Formatted filename '{formatted}' (length {len(formatted)}) "
        f"exceeds max_width {effective_max_width}"
    )

    # Property 2: If filename is short enough, it should be unchanged
    if len(filename) <= max_width:
        assert formatted == filename, (
            f"Short filename should not be modified: expected '{filename}', got '{formatted}'"
        )
    else:
        # Property 3: If truncation occurred, check for ellipsis
        if len(filename) > effective_max_width:
            assert "..." in formatted, f"Truncated filename should contain ellipsis: '{formatted}'"

            # Property 4: Extension preservation (last 15 chars)
            # The last 15 characters of the original filename should appear
            # at the end of the truncated version
            expected_end = filename[-15:]
            assert formatted.endswith(expected_end), (
                f"Truncated filename should preserve last 15 chars: "
                f"expected end '{expected_end}', got '{formatted}'"
            )

            # Property 5: Start of filename should be preserved
            # The formatted string should start with some prefix of the original
            # (before the ellipsis)
            ellipsis_pos = formatted.find("...")
            if ellipsis_pos > 0:
                start_portion = formatted[:ellipsis_pos]
                assert filename.startswith(start_portion), (
                    f"Truncated filename should start with original prefix: "
                    f"expected start '{start_portion}' in '{filename}'"
                )


def test_format_filename_examples():
    """
    Test specific examples of filename truncation to verify expected behavior.
    """
    display = ProgressDisplay(quiet=True)

    # Test 1: Short filename should not be truncated
    result = display.format_filename("short.txt", 50)
    assert result == "short.txt"

    # Test 2: Long filename should be truncated with extension preserved
    long_name = "Writing.With.Fire.2021.1080p.WEBRip.x264.AAC-[YTS.MX].mp4"
    result = display.format_filename(long_name, 30)
    assert len(result) <= 30
    assert "..." in result
    assert result.endswith("YTS.MX].mp4")  # Last 15 chars preserved
    assert result.startswith("Writing")  # Start preserved

    # Test 3: Minimum width enforcement
    result = display.format_filename("verylongfilename.txt", 10)
    assert len(result) == 20  # Minimum width enforced

    # Test 4: Exact fit
    result = display.format_filename("exactly20chars.txt", 20)
    assert result == "exactly20chars.txt"
    assert len(result) == 18  # Actual length

    # Test 5: One character over (21 chars, max 20)
    filename_21 = "a" * 21 + ".txt"  # 25 chars total
    result = display.format_filename(filename_21, 20)
    assert len(result) == 20
    assert "..." in result


def test_format_filename_edge_cases():
    """
    Test edge cases for filename truncation.
    """
    display = ProgressDisplay(quiet=True)

    # Test 1: Empty filename
    result = display.format_filename("", 50)
    assert result == ""

    # Test 2: Very short max_width (below minimum)
    long_filename = "a" * 100 + ".txt"
    result = display.format_filename(long_filename, 5)
    assert len(result) == 20  # Minimum enforced

    # Test 3: Filename with no extension
    result = display.format_filename("a" * 100, 30)
    assert len(result) == 30
    assert "..." in result

    # Test 4: Filename exactly at max_width
    filename = "a" * 50
    result = display.format_filename(filename, 50)
    assert result == filename

    # Test 5: Unicode characters
    result = display.format_filename("文件名.txt", 50)
    assert result == "文件名.txt"

    # Test 6: Very long filename with unicode
    long_unicode = "文" * 100 + ".txt"
    result = display.format_filename(long_unicode, 30)
    assert len(result) <= 30
    assert "..." in result


# Feature: streamdown, Property 40: Progress bar scales with terminal width
@settings(deadline=500)
@given(
    terminal_width=st.integers(min_value=20, max_value=300),
)
def test_progress_bar_scales_with_terminal_width(terminal_width: int):
    """
    For any progress bar on a narrow terminal, the bar width must scale
    proportionally to available space while maintaining a minimum readable width.

    This test verifies:
    1. Bar width is at least 10 characters (minimum readable)
    2. On narrow terminals (<80 cols): bar width is 10-20 chars
    3. On wide terminals (≥80 cols): bar width is 40-60 chars
    4. Bar width scales proportionally with terminal width
    5. Bar width never exceeds maximum bounds

    **Validates: Requirements 16.5**
    """
    # Mock shutil.get_terminal_size to return our test width
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
        # Create a mock terminal size object
        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        mock_get_size.return_value = MockTerminalSize(terminal_width)

        # Create progress display instance
        display = ProgressDisplay(quiet=True)

        # Calculate bar width
        bar_width = display.calculate_bar_width()

        # Property 1: Minimum readable bar width of 10 characters
        assert bar_width >= 10, (
            f"Bar width {bar_width} is below minimum of 10 chars "
            f"for terminal width {terminal_width}"
        )

        # Property 2: Bar width constraints based on terminal width
        if terminal_width < 80:
            # Narrow terminal: bar should be 10-20 chars
            assert 10 <= bar_width <= 20, (
                f"For narrow terminal (width {terminal_width}), "
                f"bar width {bar_width} should be between 10-20 chars"
            )
        else:
            # Wide terminal: bar should be 40-60 chars
            assert 40 <= bar_width <= 60, (
                f"For wide terminal (width {terminal_width}), "
                f"bar width {bar_width} should be between 40-60 chars"
            )

        # Property 3: Bar width scales proportionally
        # For narrow terminals: as width increases from 40 to 80, bar goes from 10 to 20
        # For wide terminals: as width increases from 80 to 160+, bar goes from 40 to 60
        if 40 <= terminal_width < 80:
            # Narrow terminal scaling
            expected_max = 10 + int((terminal_width - 40) * 0.25)
            expected_max = max(expected_max, 10)  # Ensure minimum
            assert bar_width == expected_max, (
                f"For terminal width {terminal_width}, expected bar width {expected_max}, "
                f"got {bar_width}"
            )
        elif terminal_width >= 80:
            # Wide terminal scaling
            expected = 40 + int((terminal_width - 80) * 0.25)
            expected = min(expected, 60)  # Cap at maximum
            assert bar_width == expected, (
                f"For terminal width {terminal_width}, expected bar width {expected}, "
                f"got {bar_width}"
            )

        # Property 4: Bar width never exceeds 60 chars (maximum bound)
        assert bar_width <= 60, (
            f"Bar width {bar_width} exceeds maximum of 60 chars for terminal width {terminal_width}"
        )


def test_calculate_bar_width_examples():
    """
    Test specific examples of bar width calculation to verify expected behavior.
    """
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:

        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        display = ProgressDisplay(quiet=True)

        # Test 1: Very narrow terminal (40 cols) -> 10 char bar (minimum)
        mock_get_size.return_value = MockTerminalSize(40)
        assert display.calculate_bar_width() == 10

        # Test 2: Narrow terminal (60 cols) -> 15 char bar
        mock_get_size.return_value = MockTerminalSize(60)
        assert display.calculate_bar_width() == 15

        # Test 3: Boundary at 80 cols -> 40 char bar (wide terminal starts)
        mock_get_size.return_value = MockTerminalSize(80)
        assert display.calculate_bar_width() == 40

        # Test 4: Medium wide terminal (120 cols) -> 50 char bar
        mock_get_size.return_value = MockTerminalSize(120)
        assert display.calculate_bar_width() == 50

        # Test 5: Very wide terminal (200 cols) -> 60 char bar (maximum)
        mock_get_size.return_value = MockTerminalSize(200)
        assert display.calculate_bar_width() == 60

        # Test 6: Extremely wide terminal (300 cols) -> still 60 char bar (capped)
        mock_get_size.return_value = MockTerminalSize(300)
        assert display.calculate_bar_width() == 60

        # Test 7: Very narrow terminal (20 cols) -> 10 char bar (minimum enforced)
        mock_get_size.return_value = MockTerminalSize(20)
        assert display.calculate_bar_width() == 10


def test_calculate_bar_width_boundary_conditions():
    """
    Test boundary conditions for bar width calculation.
    """
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:

        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        display = ProgressDisplay(quiet=True)

        # Test width = 79 (narrow, just below threshold)
        mock_get_size.return_value = MockTerminalSize(79)
        bar_width = display.calculate_bar_width()
        assert 10 <= bar_width <= 20
        assert bar_width == 19  # 10 + (79-40)*0.25 = 10 + 9.75 = 19

        # Test width = 80 (wide, at threshold)
        mock_get_size.return_value = MockTerminalSize(80)
        bar_width = display.calculate_bar_width()
        assert 40 <= bar_width <= 60
        assert bar_width == 40

        # Test width = 81 (wide, just above threshold)
        mock_get_size.return_value = MockTerminalSize(81)
        bar_width = display.calculate_bar_width()
        assert 40 <= bar_width <= 60
        assert bar_width == 40  # 40 + (81-80)*0.25 = 40 + 0.25 = 40 (int)


class MockTerminalSize:
    """Small stand-in for shutil terminal size results."""

    def __init__(self, columns: int, lines: int = 24):
        self.columns = columns
        self.lines = lines


def make_recording_console(width: int) -> Console:
    """Create a deterministic Rich console for progress render tests."""
    return Console(
        width=width,
        record=True,
        force_terminal=False,
        color_system=None,
        file=StringIO(),
    )


def render_progress_lines(display: ProgressDisplay, width: int) -> list[str]:
    """Render the current progress display and return non-empty text lines."""
    assert display.progress is not None
    console = make_recording_console(width)
    console.print(display.progress.get_renderable())
    text = console.export_text(styles=False)
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def assert_lines_fit_width(lines: list[str], width: int) -> None:
    """Assert rendered lines do not exceed a terminal width in visible cells."""
    for line in lines:
        assert cell_len(line) <= width, (
            f"Rendered line exceeds width {width}: {cell_len(line)} cells in {line!r}"
        )


def test_narrow_progress_render_uses_multi_row_blocks_without_wrapping():
    """
    Active narrow-terminal downloads render as stable multi-row blocks.

    This covers the acceptance target at 40, 60, and 79 columns: no rendered
    line should exceed the terminal width, and the layout should no longer be a
    crowded single row.
    """
    url = "https://example.test/movie.mkv"
    filename = "A.Very.Long.Movie.Title.2024.1080p.BluRay.x265.HEVC.10bit.AAC-[GROUP].mkv"
    total_bytes = 100_000_000
    downloaded_bytes = 42_000_000

    for width in [40, 60, 79]:
        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_size:
            mock_size.return_value = MockTerminalSize(width)
            display = ProgressDisplay(quiet=False)
            display.console = make_recording_console(width)
            display.__enter__()
            try:
                display.add_download(url, filename, total_bytes)
                display.update_status(url, DownloadStatus.RUNNING)
                display.update_progress(url, downloaded_bytes, total_bytes)

                lines = render_progress_lines(display, width)

                assert len(lines) == 2
                assert_lines_fit_width(lines, width)
                rendered_text = "\n".join(lines)
                assert "A." in rendered_text
                assert ".mkv" in rendered_text
                assert "42.0%" in rendered_text
                assert "40MB" in rendered_text
                assert "downloading" in rendered_text
            finally:
                if display.progress is not None:
                    display.progress.__exit__(None, None, None)


def test_narrow_progress_row_count_stays_stable_across_status_transitions():
    """
    Narrow progress blocks keep the same row count as status labels change.
    """
    url = "https://example.test/archive.zip"
    filename = "Very.Long.Release.Name.With.Many.Parts.And.Metadata-[TEAM].zip"
    total_bytes = 10_000_000

    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_size:
        mock_size.return_value = MockTerminalSize(40)
        display = ProgressDisplay(quiet=False)
        display.console = make_recording_console(40)
        display.__enter__()
        try:
            display.add_download(url, filename, total_bytes)
            snapshots: list[list[str]] = []

            snapshots.append(render_progress_lines(display, 40))
            display.update_status(url, DownloadStatus.RUNNING)
            display.update_progress(url, 5_000_000, total_bytes)
            snapshots.append(render_progress_lines(display, 40))
            display.update_status(url, DownloadStatus.COMPLETED)
            display.update_progress(url, total_bytes, total_bytes)
            snapshots.append(render_progress_lines(display, 40))
            display.update_status(url, DownloadStatus.FAILED)
            snapshots.append(render_progress_lines(display, 40))

            row_counts = {len(lines) for lines in snapshots}
            assert row_counts == {2}
            for lines in snapshots:
                assert_lines_fit_width(lines, 40)
        finally:
            if display.progress is not None:
                display.progress.__exit__(None, None, None)


def test_narrow_progress_render_handles_multiple_concurrent_downloads():
    """Multiple narrow-mode downloads render as deterministic two-row blocks."""
    downloads = [
        (
            "https://example.test/movie.mkv",
            "A.Very.Long.Movie.Title.2024.1080p.BluRay.x265.HEVC.10bit.AAC-[GROUP].mkv",
            100_000_000,
            25_000_000,
            ".mkv",
        ),
        (
            "https://example.test/source.tar.gz",
            "streamdown-source-package-with-a-very-long-release-name-v1.2.3.tar.gz",
            80_000_000,
            40_000_000,
            ".tar.gz",
        ),
        (
            "https://example.test/archive.zip",
            "Very.Long.Release.Name.With.Many.Parts.And.Metadata-[TEAM].zip",
            50_000_000,
            45_000_000,
            ".zip",
        ),
    ]

    for width in [40, 60]:
        with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_size:
            mock_size.return_value = MockTerminalSize(width)
            display = ProgressDisplay(quiet=False)
            display.console = make_recording_console(width)
            display.__enter__()
            try:
                for url, filename, total_bytes, downloaded_bytes, _suffix in downloads:
                    display.add_download(url, filename, total_bytes)
                    display.update_status(url, DownloadStatus.RUNNING)
                    display.update_progress(url, downloaded_bytes, total_bytes)

                lines = render_progress_lines(display, width)

                assert len(lines) == len(downloads) * 2
                assert_lines_fit_width(lines, width)
                rendered_text = "\n".join(lines)
                assert rendered_text.count("downloading") == len(downloads)
                assert rendered_text.count("%") == len(downloads)
                for *_download_fields, suffix in downloads:
                    assert suffix in rendered_text
            finally:
                if display.progress is not None:
                    display.progress.__exit__(None, None, None)


def test_narrow_progress_render_uses_current_width_after_resize():
    """Narrow progress rendering recalculates layout after terminal resize."""
    url = "https://example.test/movie.mkv"
    filename = "A.Very.Long.Movie.Title.2024.1080p.BluRay.x265.HEVC.10bit.AAC-[GROUP].mkv"
    total_bytes = 100_000_000

    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_size:
        mock_size.return_value = MockTerminalSize(79)
        display = ProgressDisplay(quiet=False)
        display.console = make_recording_console(79)
        display.__enter__()
        try:
            display.add_download(url, filename, total_bytes)
            display.update_status(url, DownloadStatus.RUNNING)
            display.update_progress(url, 42_000_000, total_bytes)

            wide_narrow_lines = render_progress_lines(display, 79)
            assert len(wide_narrow_lines) == 2
            assert_lines_fit_width(wide_narrow_lines, 79)

            mock_size.return_value = MockTerminalSize(40)
            resized_lines = render_progress_lines(display, 40)

            assert len(resized_lines) == 2
            assert_lines_fit_width(resized_lines, 40)
            resized_text = "\n".join(resized_lines)
            assert ".mkv" in resized_text
            assert "downloading" in resized_text
        finally:
            if display.progress is not None:
                display.progress.__exit__(None, None, None)


# Feature: streamdown, Property 38: Essential information prioritized on narrow terminals
@settings(deadline=500)
@given(
    terminal_width=st.integers(min_value=20, max_value=300),
    downloaded_bytes=st.integers(min_value=0, max_value=10**10),
)
def test_essential_information_prioritized_on_narrow_terminals(
    terminal_width: int, downloaded_bytes: int
):
    """
    For any progress display on a narrow terminal, essential information
    (filename, percentage, status) must be visible while less critical
    information may be omitted.

    This test verifies:
    1. On narrow terminals (<80 cols): compact size format is used
    2. On wide terminals (≥80 cols): full display with all information
    3. Compact size format has no spaces and uses compact units (e.g., "1.7GB")
    4. Essential information is always present regardless of terminal width
    5. The display adapts correctly based on terminal width detection

    **Validates: Requirements 16.3**
    """
    # Mock shutil.get_terminal_size to return our test width
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
        # Create a mock terminal size object
        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        mock_get_size.return_value = MockTerminalSize(terminal_width)

        # Create progress display instance
        display = ProgressDisplay(quiet=True)

        # Test compact size formatting
        compact_size = display.format_size_compact(downloaded_bytes)

        # Property 1: Compact size must not contain spaces
        assert " " not in compact_size, f"Compact size '{compact_size}' should not contain spaces"

        # Property 2: Compact size must use standard units
        valid_units = ["B", "KB", "MB", "GB", "TB"]
        has_valid_unit = any(compact_size.endswith(unit) for unit in valid_units)
        assert has_valid_unit, (
            f"Compact size '{compact_size}' must end with a valid unit: {valid_units}"
        )

        # Property 3: Compact size format is consistent
        # For values >= 1024, should have at most 1 decimal place for values >= 10
        # or 1 decimal place for values < 10
        if downloaded_bytes >= 1024:
            # Extract numeric part (everything before the unit)
            numeric_part = compact_size.rstrip("KMGTB")
            try:
                float_value = float(numeric_part)
                # Check decimal places
                if "." in numeric_part:
                    decimal_places = len(numeric_part.split(".")[1])
                    if float_value >= 10:
                        assert decimal_places == 0, (
                            f"For values >= 10, compact size should have no decimals: "
                            f"'{compact_size}' has {decimal_places} decimal places"
                        )
                    else:
                        assert decimal_places <= 1, (
                            f"For values < 10, compact size should have at most 1 decimal: "
                            f"'{compact_size}' has {decimal_places} decimal places"
                        )
            except ValueError as exc:
                # If we can't parse it, that's a problem
                raise AssertionError(
                    f"Could not parse numeric part of compact size: '{compact_size}'"
                ) from exc

        # Property 4: Verify terminal width detection affects display mode
        is_narrow = display.is_narrow_terminal()
        if terminal_width < 80:
            assert is_narrow is True, (
                f"Terminal width {terminal_width} should be detected as narrow"
            )
        else:
            assert is_narrow is False, (
                f"Terminal width {terminal_width} should not be detected as narrow"
            )

        # Property 5: Compact size is reasonable for the byte value
        # Verify the conversion is mathematically correct
        if downloaded_bytes < 1024:
            assert compact_size == f"{downloaded_bytes}B"
        elif downloaded_bytes < 1024 * 1024:
            kb = downloaded_bytes / 1024
            if kb >= 10:
                expected = f"{kb:.0f}KB"
            else:
                expected = f"{kb:.1f}KB"
            assert compact_size == expected, (
                f"Expected '{expected}' for {downloaded_bytes} bytes, got '{compact_size}'"
            )
        elif downloaded_bytes < 1024 * 1024 * 1024:
            mb = downloaded_bytes / (1024 * 1024)
            if mb >= 10:
                expected = f"{mb:.0f}MB"
            else:
                expected = f"{mb:.1f}MB"
            assert compact_size == expected, (
                f"Expected '{expected}' for {downloaded_bytes} bytes, got '{compact_size}'"
            )
        elif downloaded_bytes < 1024 * 1024 * 1024 * 1024:
            gb = downloaded_bytes / (1024 * 1024 * 1024)
            if gb >= 10:
                expected = f"{gb:.0f}GB"
            else:
                expected = f"{gb:.1f}GB"
            assert compact_size == expected, (
                f"Expected '{expected}' for {downloaded_bytes} bytes, got '{compact_size}'"
            )
        else:
            tb = downloaded_bytes / (1024 * 1024 * 1024 * 1024)
            if tb >= 10:
                expected = f"{tb:.0f}TB"
            else:
                expected = f"{tb:.1f}TB"
            assert compact_size == expected, (
                f"Expected '{expected}' for {downloaded_bytes} bytes, got '{compact_size}'"
            )


def test_format_size_compact_examples():
    """
    Test specific examples of compact size formatting to verify expected behavior.
    """
    display = ProgressDisplay(quiet=True)

    # Test 1: Bytes
    assert display.format_size_compact(0) == "0B"
    assert display.format_size_compact(512) == "512B"
    assert display.format_size_compact(1023) == "1023B"

    # Test 2: Kilobytes
    assert display.format_size_compact(1024) == "1.0KB"
    assert display.format_size_compact(5200) == "5.1KB"
    assert display.format_size_compact(10240) == "10KB"
    assert display.format_size_compact(102400) == "100KB"

    # Test 3: Megabytes
    assert display.format_size_compact(1024 * 1024) == "1.0MB"
    assert display.format_size_compact(5 * 1024 * 1024) == "5.0MB"
    assert display.format_size_compact(234 * 1024 * 1024) == "234MB"

    # Test 4: Gigabytes
    assert display.format_size_compact(1024 * 1024 * 1024) == "1.0GB"
    assert display.format_size_compact(int(1.7 * 1024 * 1024 * 1024)) == "1.7GB"
    assert display.format_size_compact(68 * 1024 * 1024 * 1024) == "68GB"

    # Test 5: Terabytes
    assert display.format_size_compact(1024 * 1024 * 1024 * 1024) == "1.0TB"
    assert display.format_size_compact(int(5.5 * 1024 * 1024 * 1024 * 1024)) == "5.5TB"

    # Test 6: No spaces in any format
    for size in [0, 1024, 1024**2, 1024**3, 1024**4]:
        result = display.format_size_compact(size)
        assert " " not in result, f"Compact size '{result}' should not contain spaces"


def test_format_size_compact_edge_cases():
    """
    Test edge cases for compact size formatting.
    """
    display = ProgressDisplay(quiet=True)

    # Test 1: Very large values
    huge_value = 10**15  # ~909 TB
    result = display.format_size_compact(huge_value)
    assert "TB" in result
    assert " " not in result

    # Test 2: Boundary values between units
    result = display.format_size_compact(1023)  # Just below 1 KB
    assert result == "1023B"

    result = display.format_size_compact(1024)  # Exactly 1 KB
    assert result == "1.0KB"

    result = display.format_size_compact(1024 * 1024 - 1)  # Just below 1 MB
    assert "KB" in result

    result = display.format_size_compact(1024 * 1024)  # Exactly 1 MB
    assert result == "1.0MB"

    # Test 3: Values that round to different decimal places
    result = display.format_size_compact(int(9.9 * 1024 * 1024))  # 9.9 MB
    assert result == "9.9MB"

    result = display.format_size_compact(int(10.1 * 1024 * 1024))  # 10.1 MB
    assert result == "10MB"  # Should round to no decimals for >= 10


# Feature: streamdown, Property 39: URL display prevents wrapping
@settings(deadline=500)
@given(
    url=st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs", "Cc"),  # Exclude surrogates and control chars
            blacklist_characters=("\x00", "\n", "\r", "\t"),
        ),
        min_size=10,
        max_size=500,
    ),
    terminal_width=st.integers(min_value=20, max_value=300),
)
def test_url_display_prevents_wrapping(url: str, terminal_width: int):
    """
    For any URL displayed on a narrow terminal, the URL must be truncated or
    omitted to prevent line wrapping beyond the terminal width.

    This test verifies:
    1. On narrow terminals (<80 cols): URLs are truncated to fit within terminal width
    2. On wide terminals (≥80 cols): URLs may be displayed in full if they fit
    3. Formatted URL length never exceeds the specified max_width
    4. URLs shorter than max_width are returned unchanged
    5. Truncation uses ellipsis to indicate truncation

    **Validates: Requirements 16.4**
    """
    # Mock shutil.get_terminal_size to return our test width
    with patch("streamdown.cli.progress_display.shutil.get_terminal_size") as mock_get_size:
        # Create a mock terminal size object
        class MockTerminalSize:
            def __init__(self, columns, lines=24):
                self.columns = columns
                self.lines = lines

        mock_get_size.return_value = MockTerminalSize(terminal_width)

        # Create progress display instance
        display = ProgressDisplay(quiet=True)

        # Calculate max width for URL display
        # On narrow terminals, we need to be more conservative with space
        is_narrow = display.is_narrow_terminal()

        if is_narrow:
            # On narrow terminals, allocate less space for URLs
            # Reserve space for essential info, use remaining for URL
            max_url_width = max(20, terminal_width - 40)  # At least 20 chars
        else:
            # On wide terminals, can use more space
            max_url_width = max(40, terminal_width - 40)

        # Format the URL
        formatted_url = display.format_url(url, max_url_width)

        # Property 1: Formatted URL must not exceed max_url_width
        assert len(formatted_url) <= max_url_width, (
            f"Formatted URL '{formatted_url}' (length {len(formatted_url)}) "
            f"exceeds max_url_width {max_url_width}"
        )

        # Property 2: If URL is short enough, it should be unchanged
        if len(url) <= max_url_width:
            assert formatted_url == url, (
                f"Short URL should not be modified: expected '{url}', got '{formatted_url}'"
            )
        else:
            # Property 3: If truncation occurred, check for ellipsis
            assert "..." in formatted_url, (
                f"Truncated URL should contain ellipsis: '{formatted_url}'"
            )

            # Property 4: Truncated URL should start with beginning of original
            ellipsis_pos = formatted_url.find("...")
            if ellipsis_pos > 0:
                start_portion = formatted_url[:ellipsis_pos]
                assert url.startswith(start_portion), (
                    f"Truncated URL should start with original prefix: "
                    f"expected start '{start_portion}' in '{url}'"
                )

        # Property 5: On narrow terminals, URLs should be more aggressively truncated
        if is_narrow and len(url) > max_url_width:
            # Verify truncation happened
            assert len(formatted_url) <= max_url_width, (
                f"On narrow terminal (width {terminal_width}), URL should be truncated "
                f"to fit within {max_url_width} chars, got {len(formatted_url)}"
            )


def test_format_url_examples():
    """
    Test specific examples of URL formatting to verify expected behavior.
    """
    display = ProgressDisplay(quiet=True)

    # Test 1: Short URL should not be truncated
    result = display.format_url("https://example.com/file.zip", 50)
    assert result == "https://example.com/file.zip"

    # Test 2: Long URL should be truncated
    long_url = "https://example.com/very/long/path/to/some/file/that/has/many/segments/video.mp4"
    result = display.format_url(long_url, 40)
    assert len(result) <= 40
    assert "..." in result
    assert result.startswith("https://example.com")

    # Test 3: Very long URL on narrow terminal
    very_long_url = "https://cdn.example.com/downloads/2024/11/26/very-long-filename-with-many-words.mp4?token=abc123"
    result = display.format_url(very_long_url, 30)
    assert len(result) <= 30
    assert "..." in result

    # Test 4: URL exactly at max_width
    url_40 = "https://example.com/file12345678.zip"  # 37 chars
    result = display.format_url(url_40, 40)
    assert result == url_40

    # Test 5: Minimum width enforcement
    result = display.format_url("https://example.com/very/long/url", 10)
    assert len(result) >= 10  # Should enforce minimum


def test_format_url_edge_cases():
    """
    Test edge cases for URL formatting.
    """
    display = ProgressDisplay(quiet=True)

    # Test 1: Empty URL
    result = display.format_url("", 50)
    assert result == ""

    # Test 2: Very short max_width
    long_url = "https://example.com/file.zip"
    result = display.format_url(long_url, 5)
    assert len(result) >= 5  # Should have minimum

    # Test 3: URL with query parameters
    url_with_query = "https://example.com/file.zip?download=true&token=abc123"
    result = display.format_url(url_with_query, 30)
    assert len(result) <= 30
    if len(url_with_query) > 30:
        assert "..." in result

    # Test 4: URL with unicode characters
    unicode_url = "https://example.com/文件.zip"
    result = display.format_url(unicode_url, 50)
    # Should handle unicode gracefully
    assert len(result) <= 50

    # Test 5: Very long URL with unicode
    long_unicode_url = "https://example.com/" + "文" * 100 + ".zip"
    result = display.format_url(long_unicode_url, 30)
    assert len(result) <= 30
    assert "..." in result

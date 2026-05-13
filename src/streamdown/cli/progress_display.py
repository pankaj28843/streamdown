"""Progress display using rich for terminal UI."""

import asyncio
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rich.cells import cell_len, get_character_cell_size
from rich.console import Console, Group
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    Task,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.progress_bar import ProgressBar
from rich.table import Column, Table
from rich.text import Text

from streamdown.domain.enums import DownloadStatus


@dataclass
class DownloadTracker:
    """Tracks state for a single download in the progress display."""

    url: str
    filename: str
    task_id: TaskID
    status: DownloadStatus
    total_bytes: int
    downloaded_bytes: int
    start_time: float
    error_message: str | None = None


_NARROW_TERMINAL_WIDTH = 80
_NARROW_STATUS_WIDTH = len("downloading")
_NARROW_META_WIDTH = len("100.0% 909TB")
_FORCED_REFRESH_INTERVAL_SECONDS = 5.0
_MIDDLE_ELLIPSIS = "…"


def _take_cell_prefix(text: str, max_cells: int) -> str:
    """Return a prefix that fits within max_cells terminal cells."""
    if max_cells <= 0:
        return ""

    cells = 0
    chars: list[str] = []
    for char in text:
        char_cells = get_character_cell_size(char)
        if cells + char_cells > max_cells:
            break
        chars.append(char)
        cells += char_cells
    return "".join(chars)


def _take_cell_suffix(text: str, max_cells: int) -> str:
    """Return a suffix that fits within max_cells terminal cells."""
    if max_cells <= 0:
        return ""

    cells = 0
    chars: list[str] = []
    for char in reversed(text):
        char_cells = get_character_cell_size(char)
        if cells + char_cells > max_cells:
            break
        chars.append(char)
        cells += char_cells
    return "".join(reversed(chars))


def _truncate_middle_cells(text: str, max_cells: int) -> str:
    """Truncate text to max_cells, preserving useful prefix and suffix cells."""
    if max_cells <= 0:
        return ""
    if cell_len(text) <= max_cells:
        return text
    if max_cells <= cell_len(_MIDDLE_ELLIPSIS) + 2:
        return _take_cell_prefix(text, max_cells)

    ellipsis_width = cell_len(_MIDDLE_ELLIPSIS)
    suffix_width = min(15, max(4, max_cells // 2))
    prefix_width = max_cells - ellipsis_width - suffix_width
    if prefix_width < 1:
        prefix_width = 1
        suffix_width = max_cells - ellipsis_width - prefix_width

    prefix = _take_cell_prefix(text, prefix_width)
    suffix = _take_cell_suffix(text, suffix_width)
    return f"{prefix}{_MIDDLE_ELLIPSIS}{suffix}"


def _task_field(task: Task, name: str, default: str = "") -> str:
    """Read a Rich task field as a string."""
    value = task.fields.get(name, default)
    return default if value is None else str(value)


def _render_narrow_task_header(task: Task, terminal_width: int) -> Table:
    """Render the filename/status row for one narrow progress task."""
    status_plain = _task_field(task, "status_plain", "HEAD")
    status_style = _task_field(task, "status_style", "yellow")
    status_width = min(_NARROW_STATUS_WIDTH, max(4, terminal_width // 3))
    filename_width = max(1, terminal_width - status_width - 2)
    filename = (
        _task_field(task, "original_filename")
        or _task_field(task, "filename")
        or str(task.description)
    )
    display_filename = _truncate_middle_cells(filename, filename_width)

    header = Table.grid(
        Column(ratio=1, no_wrap=True, overflow="ellipsis"),
        Column(width=status_width, no_wrap=True, overflow="ellipsis", justify="right"),
        padding=(0, 1),
        expand=True,
    )
    header.add_row(
        Text(display_filename, style="bold blue", no_wrap=True, overflow="ellipsis"),
        Text(status_plain, style=f"bold {status_style}", justify="right", no_wrap=True),
    )
    return header


def _render_narrow_task_bar(task: Task, terminal_width: int) -> Table:
    """Render the progress bar/metadata row for one narrow progress task."""
    compact_size = _task_field(task, "compact_size", "0B")
    metadata = f"{task.percentage:>5.1f}% {compact_size}"
    metadata_width = min(_NARROW_META_WIDTH, max(8, terminal_width // 2))

    bar_row = Table.grid(
        Column(ratio=1, no_wrap=True, overflow="crop"),
        Column(width=metadata_width, no_wrap=True, overflow="ellipsis", justify="right"),
        padding=(0, 1),
        expand=True,
    )
    bar_row.add_row(
        ProgressBar(total=task.total, completed=task.completed, width=None),
        Text(metadata, justify="right", no_wrap=True, overflow="ellipsis"),
    )
    return bar_row


def _render_narrow_task(task: Task, terminal_width: int) -> Group:
    """Render one task as a two-row narrow-terminal block."""
    return Group(
        _render_narrow_task_header(task, terminal_width),
        _render_narrow_task_bar(task, terminal_width),
    )


class _NarrowProgress(Progress):
    """Progress renderer that gives each task a compact multi-row block."""

    def __init__(self, *, console: Console, width_getter: Callable[[], int]):
        self._width_getter = width_getter
        super().__init__(console=console, expand=True, auto_refresh=False)

    def _current_width(self) -> int:
        try:
            return max(1, int(self._width_getter()))
        except (TypeError, ValueError, OSError):
            return max(1, int(self.console.size.width))

    def get_renderables(self):
        """Yield narrow multi-row task blocks instead of one task table."""
        terminal_width = self._current_width()
        visible_tasks = [task for task in self.tasks if task.visible]
        for index, task in enumerate(visible_tasks):
            if index > 0:
                yield Text("")
            yield _render_narrow_task(task, terminal_width)


class ProgressDisplay:
    """
    Rich terminal interface for displaying download progress.

    Responsibilities:
    - Display progress bar for each download with filename, percentage, speed, ETA
    - Update progress bars as chunks complete
    - Show status indicators (HEAD, downloading, complete, failed)
    - Aggregate and display total throughput for multiple downloads
    - Support quiet mode to suppress progress bars

    Requirements: 6.1, 6.2, 6.3, 6.4
    """

    def __init__(self, quiet: bool = False):
        """
        Initialize progress display.

        Args:
            quiet: If True, suppress progress bars and only show final results
        """
        self.quiet = quiet
        self.console = Console()
        self.progress: Progress | None = None
        self.downloads: dict[str, DownloadTracker] = {}
        self._lock: asyncio.Lock | None = None  # Created lazily when needed
        self._total_bytes_downloaded = 0
        self._start_time: float | None = None
        self._terminal_width: int = 80  # Default width, updated on each render
        self._last_forced_refresh_time = 0.0

    def __enter__(self):
        """Enter context manager."""
        if not self.quiet:
            # Requirement 6.1: Display progress bar with filename, percentage, speed, ETA
            # Requirement 16.5: Scale bar width based on terminal width
            # Requirement 16.3: Prioritize essential information on narrow terminals
            bar_width = self.calculate_bar_width()
            is_narrow = self.is_narrow_terminal()

            if is_narrow:
                # Narrow terminal: each task renders as a compact two-row block.
                # This avoids Rich's default single-row table folding/cropping.
                self.progress = _NarrowProgress(
                    console=self.console,
                    width_getter=self.get_terminal_width,
                )
            else:
                # Wide terminal: Full display
                self.progress = Progress(
                    TextColumn("[bold blue]{task.fields[filename]}", justify="left"),
                    BarColumn(bar_width=bar_width),
                    "[progress.percentage]{task.percentage:>3.1f}%",
                    "•",
                    DownloadColumn(),
                    "•",
                    TransferSpeedColumn(),
                    "•",
                    TimeRemainingColumn(),
                    "•",
                    TextColumn("[bold]{task.fields[status]}"),
                    console=self.console,
                    expand=False,  # Don't expand to prevent wrapping
                    auto_refresh=False,
                )
            self.progress.__enter__()

        # Use time.time() instead of event loop time since loop may not exist yet
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

        # Show final summary
        if not self.quiet:
            self._display_summary()

    def add_download(
        self,
        url: str,
        filename: str,
        total_bytes: int,
    ) -> None:
        """
        Add a new download to track.

        Requirement 6.2: Display separate progress bars for each download

        Args:
            url: URL being downloaded
            filename: Output filename
            total_bytes: Total file size in bytes
        """
        if self.quiet:
            return

        if self.progress is None:
            return

        # Requirement 6.3: Show status indicators
        # Requirement 16.3: Include compact size for narrow terminals
        # Requirement 16.2: Truncate long filenames for narrow terminals
        compact_size = self.format_size_compact(0)  # Start with 0 bytes downloaded

        # Truncate filename if on narrow terminal
        display_filename = filename
        terminal_width = self.get_terminal_width()

        if self.is_narrow_terminal():
            # On narrow terminals, allocate reasonable space for filename
            # Calculate based on actual space used:
            # - bar_width + 1 space before bar
            # - " 100.0%" = 7 chars
            # - " • " = 3 chars (separator)
            # - "64GB" = ~6 chars (size, varies)
            # - " • " = 3 chars (separator)
            # - "complete" = ~12 chars (status, varies)
            # Total other elements: bar + 1 + 7 + 3 + 6 + 3 + 12 = bar + 32
            bar_width = self.calculate_bar_width()
            other_elements_width = bar_width + 1 + 32
            max_filename_width = max(
                20, terminal_width - other_elements_width - 2
            )  # -2 for safety margin
            display_filename = self.format_filename(filename, max_filename_width)
        else:
            # On wide terminals, also truncate but with more generous limit
            # Calculate based on: bar_width + percentage + download + speed + time + status + separators
            bar_width = self.calculate_bar_width()
            other_elements_width = bar_width + 70  # Approximate for all other columns
            max_filename_width = max(40, terminal_width - other_elements_width)
            if len(filename) > max_filename_width:
                display_filename = self.format_filename(filename, max_filename_width)

        task_id = self.progress.add_task(
            description=display_filename,
            total=total_bytes,
            filename=display_filename,
            original_filename=filename,
            status="HEAD",
            status_plain="HEAD",
            status_style="yellow",
            compact_size=compact_size,
        )
        self._force_refresh()

        self.downloads[url] = DownloadTracker(
            url=url,
            filename=filename,  # Store original filename
            task_id=task_id,
            status=DownloadStatus.PENDING,
            total_bytes=total_bytes,
            downloaded_bytes=0,
            start_time=time.time(),
        )

    def update_status(self, url: str, status: DownloadStatus) -> None:
        """
        Update the status indicator for a download.

        Requirement 6.3: Update progress bar with appropriate status indicators

        Args:
            url: URL of the download
            status: New status
        """
        if self.quiet or self.progress is None:
            return

        tracker = self.downloads.get(url)
        if tracker is None:
            return

        tracker.status = status

        # Map status to display strings
        status_str = self._format_status(status)
        status_plain, status_style = self._format_status_parts(status)

        self.progress.update(
            tracker.task_id,
            status=status_str,
            status_plain=status_plain,
            status_style=status_style,
        )
        self._force_refresh()

    def update_progress(
        self,
        url: str,
        downloaded_bytes: int,
        total_bytes: int | None = None,
    ) -> None:
        """
        Update download progress.

        Args:
            url: URL of the download
            downloaded_bytes: Number of bytes downloaded so far
            total_bytes: Total file size (if known)
        """
        if self.quiet or self.progress is None:
            return

        tracker = self.downloads.get(url)
        if tracker is None:
            return

        # Calculate bytes added since last update
        bytes_added = downloaded_bytes - tracker.downloaded_bytes
        self._total_bytes_downloaded += bytes_added

        tracker.downloaded_bytes = downloaded_bytes

        # Requirement 16.3: Update compact size for narrow terminals
        compact_size = self.format_size_compact(downloaded_bytes)

        if total_bytes is not None and total_bytes != tracker.total_bytes:
            tracker.total_bytes = total_bytes
            self.progress.update(
                tracker.task_id,
                total=total_bytes,
                compact_size=compact_size,
            )
        else:
            self.progress.update(
                tracker.task_id,
                completed=downloaded_bytes,
                compact_size=compact_size,
            )

        self._refresh_if_due()

    def mark_complete(self, url: str, final_path: Path) -> None:
        """
        Mark a download as complete.

        Args:
            url: URL of the download
            final_path: Final file path
        """
        self.update_status(url, DownloadStatus.COMPLETED)

    def mark_failed(self, url: str, error: str) -> None:
        """
        Mark a download as failed.

        Requirement 6.5: Display structured error messages

        Args:
            url: URL of the download
            error: Error message
        """
        # Check if download was added to progress display
        tracker = self.downloads.get(url)
        if tracker is not None and tracker.task_id is not None:
            # Download was added to progress bar, update its status
            self.update_status(url, DownloadStatus.FAILED)
            tracker.error_message = error
        elif tracker is not None:
            # Tracker exists but no task_id (shouldn't happen, but handle it)
            tracker.status = DownloadStatus.FAILED
            tracker.error_message = error
        else:
            # Download failed before being added (e.g., HEAD request failed)
            # Create a minimal tracker for error reporting
            # Extract filename from URL
            from urllib.parse import unquote, urlparse

            parsed = urlparse(url)
            filename = unquote(parsed.path.split("/")[-1])
            if not filename:
                filename = "download"

            # Create tracker without adding to progress bar
            self.downloads[url] = DownloadTracker(
                url=url,
                filename=filename,
                task_id=None,  # type: ignore  # No task ID since not added to progress
                status=DownloadStatus.FAILED,
                total_bytes=0,
                downloaded_bytes=0,
                start_time=time.time(),
                error_message=error,
            )

    def _force_refresh(self, now: float | None = None) -> None:
        """Refresh the display immediately without Rich's background thread."""
        if self.progress is None:
            return

        self.progress.refresh()
        self._last_forced_refresh_time = time.monotonic() if now is None else now

    def _refresh_if_due(self) -> None:
        """Force a visible refresh no more than once per status interval."""
        if self.progress is None:
            return

        now = time.monotonic()
        if now - self._last_forced_refresh_time < _FORCED_REFRESH_INTERVAL_SECONDS:
            return

        self._force_refresh(now)

    def _format_status(self, status: DownloadStatus) -> str:
        """
        Format status for display.

        Args:
            status: Download status

        Returns:
            Formatted status string with color
        """
        status_plain, status_style = self._format_status_parts(status)
        if status_style:
            return f"[{status_style}]{status_plain}[/{status_style}]"
        return status_plain

    def _format_status_parts(self, status: DownloadStatus) -> tuple[str, str]:
        """Return plain text and Rich style for a download status."""
        status_map = {
            DownloadStatus.PENDING: ("HEAD", "yellow"),
            DownloadStatus.RUNNING: ("downloading", "cyan"),
            DownloadStatus.COMPLETED: ("complete", "green"),
            DownloadStatus.FAILED: ("failed", "red"),
            DownloadStatus.CANCELLED: ("cancelled", "red"),
        }
        return status_map.get(status, (str(status), ""))

    def _display_summary(self) -> None:
        """
        Display final summary of all downloads.

        Requirement 6.4: Aggregate and display total throughput
        """
        if not self.downloads:
            return

        # Calculate statistics
        total_downloads = len(self.downloads)
        completed = sum(1 for d in self.downloads.values() if d.status == DownloadStatus.COMPLETED)
        failed = sum(1 for d in self.downloads.values() if d.status == DownloadStatus.FAILED)

        # Calculate total throughput
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            if elapsed > 0:
                throughput_mbps = (self._total_bytes_downloaded / elapsed) / (1024 * 1024)
            else:
                throughput_mbps = 0.0
        else:
            throughput_mbps = 0.0

        # Display summary table
        self.console.print()
        table = Table(title="Download Summary", show_header=True, header_style="bold")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Downloads", str(total_downloads))
        table.add_row("Completed", f"[green]{completed}[/green]")
        table.add_row("Failed", f"[red]{failed}[/red]")
        table.add_row("Total Downloaded", f"{self._total_bytes_downloaded / (1024 * 1024):.2f} MiB")
        table.add_row("Average Throughput", f"{throughput_mbps:.2f} MiB/s")

        self.console.print(table)

        # Display errors for failed downloads
        failed_downloads = [d for d in self.downloads.values() if d.status == DownloadStatus.FAILED]
        if failed_downloads:
            self.console.print()
            self.console.print("[bold red]Failed Downloads:[/bold red]")
            for download in failed_downloads:
                self.console.print(f"  [red]✗[/red] {download.url}")
                if download.error_message:
                    self.console.print(f"    Error: {download.error_message}")

    def get_terminal_width(self) -> int:
        """
        Get the current terminal width.

        Uses shutil.get_terminal_size() to detect terminal dimensions.
        Updates the internal terminal width cache.

        Requirement 16.1: Detect terminal width for responsive display

        Returns:
            Terminal width in columns
        """
        try:
            size = shutil.get_terminal_size()
            self._terminal_width = size.columns
            return size.columns
        except (AttributeError, ValueError, OSError):
            # Fallback to default if terminal size cannot be determined
            return self._terminal_width

    def is_narrow_terminal(self) -> bool:
        """
        Check if the terminal is narrow (< 80 columns).

        Requirement 16.1: Terminals < 80 columns are considered narrow

        Returns:
            True if terminal width is less than 80 columns, False otherwise
        """
        width = self.get_terminal_width()
        return width < _NARROW_TERMINAL_WIDTH

    def calculate_bar_width(self) -> int:
        """
        Calculate appropriate progress bar width based on terminal width.

        Implements adaptive bar sizing:
        - Wide terminals (≥80 cols): 40-60 char bar
        - Narrow terminals (<80 cols): 10-20 char bar (proportional to width)
        - Minimum readable bar: 10 chars

        Requirement 16.5: Progress bar scales with terminal width

        Returns:
            Progress bar width in characters
        """
        terminal_width = self.get_terminal_width()

        if terminal_width >= _NARROW_TERMINAL_WIDTH:
            # Wide terminal: use 40-60 char bar
            # Scale proportionally: 80 cols -> 40 chars, 160+ cols -> 60 chars
            bar_width = 40 + int((terminal_width - _NARROW_TERMINAL_WIDTH) * 0.25)
            return min(bar_width, 60)
        else:
            # Narrow terminal: use 10-20 char bar proportional to width
            # Scale: 40 cols -> 10 chars, 80 cols -> 20 chars
            # Formula: 10 + (width - 40) * (10 / 40)
            bar_width = 10 + int((terminal_width - 40) * 0.25)
            return max(bar_width, 10)  # Ensure minimum of 10 chars

    def format_filename(self, filename: str, max_width: int) -> str:
        """
        Format filename for display, truncating if necessary to fit within max_width.

        Uses middle truncation with ellipsis to preserve both the start of the filename
        and the file extension. The extension (last 15 chars including the dot) is
        always preserved when truncation is needed.

        Requirement 16.2: Truncate long filenames while preserving file extension

        Args:
            filename: The filename to format
            max_width: Maximum width in characters for the formatted filename

        Returns:
            Formatted filename that fits within max_width characters

        Examples:
            >>> display = ProgressDisplay()
            >>> display.format_filename("short.txt", 50)
            'short.txt'
            >>> display.format_filename("Writing.With.Fire.2021.1080p.WEBRip.x264.AAC-[YTS.MX].mp4", 30)
            'Writing...YTS.MX].mp4'
        """
        # Ensure minimum width of 20 characters
        if max_width < 20:
            max_width = 20

        # If filename fits within max_width, return as-is
        if len(filename) <= max_width:
            return filename

        # Preserve last 15 characters (including extension)
        extension_length = 15
        ellipsis = "..."

        # Calculate space available for the start portion
        # max_width = start_length + len(ellipsis) + extension_length
        start_length = max_width - len(ellipsis) - extension_length

        # Ensure we have at least some characters for the start
        if start_length < 1:
            # If max_width is too small, just truncate from the end
            return filename[:max_width]

        # Extract start and end portions
        start = filename[:start_length]
        end = filename[-extension_length:]

        # Combine with ellipsis
        return f"{start}{ellipsis}{end}"

    def format_size_compact(self, bytes_value: int) -> str:
        """
        Format byte size in compact format for narrow terminals.

        Formats sizes without spaces and with minimal precision:
        - "1.7GB" instead of "1.7 GB / 68.2 GB"
        - Uses B, KB, MB, GB, TB units
        - One decimal place for values >= 10, two for values < 10

        Requirement 16.3: Format sizes compactly on narrow terminals

        Args:
            bytes_value: Size in bytes

        Returns:
            Compact formatted size string (e.g., "1.7GB", "234MB", "5.2KB")

        Examples:
            >>> display = ProgressDisplay()
            >>> display.format_size_compact(1700000000)
            '1.7GB'
            >>> display.format_size_compact(234000000)
            '234MB'
            >>> display.format_size_compact(5200)
            '5.2KB'
        """
        if bytes_value < 1024:
            return f"{bytes_value}B"
        elif bytes_value < 1024 * 1024:
            kb = bytes_value / 1024
            if kb >= 10:
                return f"{kb:.0f}KB"
            else:
                return f"{kb:.1f}KB"
        elif bytes_value < 1024 * 1024 * 1024:
            mb = bytes_value / (1024 * 1024)
            if mb >= 10:
                return f"{mb:.0f}MB"
            else:
                return f"{mb:.1f}MB"
        elif bytes_value < 1024 * 1024 * 1024 * 1024:
            gb = bytes_value / (1024 * 1024 * 1024)
            if gb >= 10:
                return f"{gb:.0f}GB"
            else:
                return f"{gb:.1f}GB"
        else:
            tb = bytes_value / (1024 * 1024 * 1024 * 1024)
            if tb >= 10:
                return f"{tb:.0f}TB"
            else:
                return f"{tb:.1f}TB"

    def format_url(self, url: str, max_width: int) -> str:
        """
        Format URL for display, truncating if necessary to fit within max_width.

        On narrow terminals, URLs should be truncated or omitted to prevent wrapping.
        This method truncates long URLs using ellipsis while preserving the beginning
        of the URL (protocol and domain).

        Requirement 16.4: Truncate or omit URLs to prevent wrapping on narrow terminals

        Args:
            url: The URL to format
            max_width: Maximum width in characters for the formatted URL

        Returns:
            Formatted URL that fits within max_width characters

        Examples:
            >>> display = ProgressDisplay()
            >>> display.format_url("https://example.com/file.zip", 50)
            'https://example.com/file.zip'
            >>> display.format_url("https://example.com/very/long/path/to/file.mp4", 30)
            'https://example.com/very...'
        """
        # Ensure minimum width of 10 characters
        if max_width < 10:
            max_width = 10

        # If URL fits within max_width, return as-is
        if len(url) <= max_width:
            return url

        # Truncate with ellipsis
        ellipsis = "..."

        # Calculate space available for the URL portion
        # We want to preserve the beginning of the URL (protocol + domain)
        available_length = max_width - len(ellipsis)

        # Ensure we have at least some characters for the URL
        if available_length < 1:
            # If max_width is too small, just truncate from the end
            return url[:max_width]

        # Extract the beginning portion and add ellipsis
        truncated = url[:available_length] + ellipsis

        return truncated

"""Progress display using rich for terminal UI."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

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

    def __enter__(self):
        """Enter context manager."""
        if not self.quiet:
            # Requirement 6.1: Display progress bar with filename, percentage, speed, ETA
            self.progress = Progress(
                TextColumn("[bold blue]{task.fields[filename]}", justify="left"),
                BarColumn(bar_width=None),
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
                expand=True,
            )
            self.progress.__enter__()

        # Use time.time() instead of event loop time since loop may not exist yet
        import time
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
        task_id = self.progress.add_task(
            description=filename,
            total=total_bytes,
            filename=filename,
            status="HEAD",
        )

        import time
        self.downloads[url] = DownloadTracker(
            url=url,
            filename=filename,
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

        # Map status to display string
        status_str = self._format_status(status)

        self.progress.update(
            tracker.task_id,
            status=status_str,
        )

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

        if total_bytes is not None and total_bytes != tracker.total_bytes:
            tracker.total_bytes = total_bytes
            self.progress.update(
                tracker.task_id,
                total=total_bytes,
            )

        self.progress.update(
            tracker.task_id,
            completed=downloaded_bytes,
        )

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
            import time
            
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

    def _format_status(self, status: DownloadStatus) -> str:
        """
        Format status for display.

        Args:
            status: Download status

        Returns:
            Formatted status string with color
        """
        status_map = {
            DownloadStatus.PENDING: "[yellow]HEAD[/yellow]",
            DownloadStatus.RUNNING: "[cyan]downloading[/cyan]",
            DownloadStatus.COMPLETED: "[green]complete[/green]",
            DownloadStatus.FAILED: "[red]failed[/red]",
            DownloadStatus.CANCELLED: "[red]cancelled[/red]",
        }
        return status_map.get(status, str(status))

    def _display_summary(self) -> None:
        """
        Display final summary of all downloads.

        Requirement 6.4: Aggregate and display total throughput
        """
        if not self.downloads:
            return

        # Calculate statistics
        total_downloads = len(self.downloads)
        completed = sum(
            1 for d in self.downloads.values()
            if d.status == DownloadStatus.COMPLETED
        )
        failed = sum(
            1 for d in self.downloads.values()
            if d.status == DownloadStatus.FAILED
        )

        # Calculate total throughput
        import time
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
        table.add_row(
            "Total Downloaded",
            f"{self._total_bytes_downloaded / (1024 * 1024):.2f} MiB"
        )
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

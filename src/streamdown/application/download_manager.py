"""Download manager for coordinating multiple downloads."""

import asyncio
from typing import TYPE_CHECKING

from streamdown.application.download_coordinator import DownloadCoordinator
from streamdown.application.dtos import DownloadOptions, DownloadResult
from streamdown.domain.enums import StreamingMode
from streamdown.domain.services import ChunkPlanner, ResumePolicy
from streamdown.infrastructure.file_writer import PartFileWriter
from streamdown.infrastructure.http_client import HttpDownloader
from streamdown.infrastructure.metadata_repository import MetadataRepository
from streamdown.infrastructure.netrc_provider import NetrcCredentialProvider

if TYPE_CHECKING:
    from streamdown.cli.progress_display import ProgressDisplay


class DownloadManager:
    """
    Manages multiple concurrent downloads with bounded concurrency.

    Responsibilities:
    - Queue all provided URLs
    - Spawn up to max_concurrent_downloads coordinators
    - Start next download when one completes or fails
    - Aggregate statistics across all downloads
    - Return results for all downloads

    Requirements: 5.1, 5.2, 5.3, 5.4
    """

    def __init__(
        self,
        options: DownloadOptions,
        max_concurrent_downloads: int = 4,
        streaming_mode: StreamingMode = StreamingMode.DEFAULT,
        progress_display: "ProgressDisplay | None" = None,
    ):
        """
        Initialize download manager.

        Args:
            options: Download configuration options
            max_concurrent_downloads: Maximum number of simultaneous downloads
            streaming_mode: Chunk selection strategy
            progress_display: Optional progress display for UI updates
        """
        self.options = options
        self.max_concurrent_downloads = max_concurrent_downloads
        self.streaming_mode = streaming_mode
        self.progress_display = progress_display

    async def download_all(self, urls: list[str]) -> list[DownloadResult]:
        """
        Download all URLs with bounded concurrency.

        This method implements the core multi-download logic:
        1. Queue all URLs (Requirement 5.1)
        2. Limit active downloads to max_concurrent_downloads (Requirement 5.2)
        3. Start next download when one completes/fails (Requirement 5.3)
        4. Return status for all downloads (Requirement 5.4)

        Args:
            urls: List of URLs to download

        Returns:
            List of DownloadResult, one per URL in the same order
        """
        if not urls:
            return []

        # Requirement 5.1: Queue all provided URLs
        # Create a queue of URLs to process
        url_queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
        for idx, url in enumerate(urls):
            await url_queue.put((idx, url))

        # Results storage - use dict to maintain order
        results: dict[int, DownloadResult] = {}
        results_lock = asyncio.Lock()

        # Requirement 5.2: Limit active downloads to max_concurrent_downloads
        semaphore = asyncio.Semaphore(self.max_concurrent_downloads)

        async def download_worker() -> None:
            """
            Worker that processes URLs from the queue.

            Implements Requirement 5.3: Start next download when one completes/fails
            """
            while True:
                try:
                    # Get next URL from queue (non-blocking check)
                    idx, url = url_queue.get_nowait()
                except asyncio.QueueEmpty:
                    # No more URLs to process
                    break

                async with semaphore:
                    # Create coordinator for this download
                    coordinator = self._create_coordinator(url)

                    # Execute download
                    result = await coordinator.download()

                    # Update progress display
                    if self.progress_display is not None:
                        if result.final_path:
                            self.progress_display.mark_complete(url, result.final_path)
                        elif result.error:
                            self.progress_display.mark_failed(url, result.error)

                    # Store result
                    async with results_lock:
                        results[idx] = result

                # Mark task as done
                url_queue.task_done()

        # Spawn worker tasks
        # We spawn max_concurrent_downloads workers, but they'll only run
        # as many concurrent downloads as the semaphore allows
        num_workers = min(len(urls), self.max_concurrent_downloads)
        workers = [asyncio.create_task(download_worker()) for _ in range(num_workers)]

        # Wait for all workers to complete
        await asyncio.gather(*workers)

        # Requirement 5.4: Return status for all downloads
        # Convert results dict back to list in original order
        return [results[idx] for idx in range(len(urls))]

    def _create_coordinator(self, url: str) -> DownloadCoordinator:
        """
        Create a download coordinator for a single URL.

        Args:
            url: URL to download

        Returns:
            Configured DownloadCoordinator instance
        """
        # Create netrc credential provider based on options
        # Requirement 15.1: Load netrc credentials at startup if enabled
        credential_provider = None
        if not self.options.no_netrc:
            credential_provider = NetrcCredentialProvider(
                netrc_path=self.options.netrc_path,
                enabled=True,
            )
        
        # Create infrastructure dependencies
        http_client = HttpDownloader(
            connect_timeout=self.options.connect_timeout,
            read_timeout=self.options.read_timeout,
            user_agent=self.options.user_agent,
            verify_ssl=not self.options.insecure,
            max_connections=self.options.max_connections_per_host,
            credential_provider=credential_provider,
        )
        file_writer = PartFileWriter()
        metadata_repo = MetadataRepository()
        chunk_planner = ChunkPlanner(mode=self.streaming_mode)
        resume_policy = ResumePolicy()

        return DownloadCoordinator(
            url=url,
            options=self.options,
            http_client=http_client,
            file_writer=file_writer,
            metadata_repo=metadata_repo,
            chunk_planner=chunk_planner,
            resume_policy=resume_policy,
            progress_display=self.progress_display,
        )

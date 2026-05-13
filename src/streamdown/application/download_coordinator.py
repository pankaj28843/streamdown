"""Download coordinator for managing a single download."""

import asyncio
import logging
import os
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from streamdown.application.chunk_worker import download_chunk_with_retry
from streamdown.application.dtos import DownloadOptions, DownloadResult
from streamdown.domain.entities import Chunk, DownloadJob
from streamdown.domain.enums import ChunkStatus, DownloadStatus, ResumeDecision
from streamdown.domain.services import (
    ChunkPlanner,
    HeadResponse,
    ResumePolicy,
)
from streamdown.domain.services import (
    DownloadMetadata as DomainDownloadMetadata,
)
from streamdown.domain.value_objects import (
    ChunkId,
    FilePath,
    Url,
    new_download_id,
)
from streamdown.infrastructure.file_writer import PartFileWriter
from streamdown.infrastructure.http_client import HttpDownloader
from streamdown.infrastructure.metadata_repository import (
    DownloadMetadata,
    MetadataRepository,
)

logger = logging.getLogger("streamdown.coordinator")

_PROGRESS_HEARTBEAT_INTERVAL_SECONDS = 30.0
_PROGRESS_REFRESH_INTERVAL_ENV = "STREAMDOWN_PROGRESS_REFRESH_INTERVAL"


def _progress_heartbeat_interval_seconds() -> float:
    """Return the configured progress heartbeat interval."""
    configured = os.environ.get(_PROGRESS_REFRESH_INTERVAL_ENV)
    if configured is None:
        return _PROGRESS_HEARTBEAT_INTERVAL_SECONDS

    try:
        interval = float(configured)
    except ValueError:
        return _PROGRESS_HEARTBEAT_INTERVAL_SECONDS

    return interval if interval > 0 else _PROGRESS_HEARTBEAT_INTERVAL_SECONDS


if TYPE_CHECKING:
    from streamdown.cli.progress_display import ProgressDisplay


class DownloadCoordinator:
    """
    Coordinates a single download with parallel chunk workers.

    Responsibilities:
    - Perform HEAD request to get file metadata
    - Check for existing metadata and attempt resume if enabled
    - Plan chunks using ChunkPlanner
    - Spawn worker tasks for parallel chunk downloads
    - Enforce max_connections_per_host limit
    - Update metadata after each chunk completion
    - Finalize download when all chunks complete

    Requirements: 1.1, 1.2, 1.3, 1.4, 2.2, 2.3, 2.5, 8.1
    """

    def __init__(
        self,
        url: str,
        options: DownloadOptions,
        http_client: HttpDownloader,
        file_writer: PartFileWriter,
        metadata_repo: MetadataRepository,
        chunk_planner: ChunkPlanner,
        resume_policy: ResumePolicy,
        progress_display: "ProgressDisplay | None" = None,
    ):
        """
        Initialize download coordinator.

        Args:
            url: URL to download
            options: Download configuration options
            http_client: HTTP client for fetching data
            file_writer: File writer for persisting chunks
            metadata_repo: Repository for metadata persistence
            chunk_planner: Service for planning chunk selection
            resume_policy: Service for resume validation
            progress_display: Optional progress display for UI updates
        """
        self.url = url
        self.options = options
        self.http_client = http_client
        self.file_writer = file_writer
        self.metadata_repo = metadata_repo
        self.chunk_planner = chunk_planner
        self.resume_policy = resume_policy
        self.progress_display = progress_display

    async def download(self) -> DownloadResult:
        """
        Execute the download with all coordination logic.

        Returns:
            DownloadResult with status and metadata
        """
        start_time = time.time()

        # Use http_client as context manager
        async with self.http_client:
            try:
                # Requirement 1.1: Perform HEAD request to get file metadata
                logger.info(f"Starting download: {self.url}")
                logger.debug(f"Fetching metadata for {self.url}")

                # Determine output filename for progress display (before HEAD request)
                if self.options.output_name:
                    filename = self.options.output_name
                else:
                    from urllib.parse import unquote, urlparse

                    parsed = urlparse(self.url)
                    filename = unquote(parsed.path.split("/")[-1])
                    if not filename:
                        filename = "download"

                head_response = await self.http_client.fetch_head(self.url)

                # Add to progress display
                if self.progress_display is not None and head_response.content_length is not None:
                    self.progress_display.add_download(
                        url=self.url,
                        filename=filename,
                        total_bytes=head_response.content_length,
                    )

                if head_response.content_length is None:
                    logger.error(f"Server did not provide Content-Length for {self.url}")
                    return DownloadResult(
                        url=self.url,
                        status=DownloadStatus.FAILED,
                        final_path=None,
                        error="Server did not provide Content-Length",
                        bytes_downloaded=0,
                        duration=time.time() - start_time,
                    )

                # Determine output paths
                target_path, part_path, meta_path = self._determine_paths(head_response)

                # Check if target file already exists
                if target_path.exists() and not self.options.allow_overwrite:
                    logger.error(f"File already exists: {target_path}")
                    return DownloadResult(
                        url=self.url,
                        status=DownloadStatus.FAILED,
                        final_path=None,
                        error=f"File already exists: {target_path}",
                        bytes_downloaded=0,
                        duration=time.time() - start_time,
                    )

                # Create download job
                download_job = await self._create_or_resume_job(
                    head_response,
                    target_path,
                    part_path,
                    meta_path,
                )

                if download_job is None:
                    logger.error(f"Failed to create download job for {self.url}")
                    return DownloadResult(
                        url=self.url,
                        status=DownloadStatus.FAILED,
                        final_path=None,
                        error="Failed to create download job",
                        bytes_downloaded=0,
                        duration=time.time() - start_time,
                    )

                # Update status to downloading
                if self.progress_display is not None:
                    self.progress_display.update_status(self.url, DownloadStatus.RUNNING)

                # Download all chunks
                download_job = await self._download_chunks(download_job, part_path.value)

                # Check if all chunks completed
                if download_job.is_complete():
                    # Requirement 1.4: Rename part file to final filename
                    logger.info(f"Download completed: {self.url}")
                    await self.file_writer.finalize(part_path.value, target_path)

                    # Clean up metadata file
                    await self.metadata_repo.delete(meta_path.value)

                    progress = download_job.compute_progress()
                    logger.debug(
                        f"Downloaded {progress.downloaded_bytes} bytes in {time.time() - start_time:.2f}s"
                    )

                    return DownloadResult(
                        url=self.url,
                        status=DownloadStatus.COMPLETED,
                        final_path=target_path,
                        error=None,
                        bytes_downloaded=progress.downloaded_bytes,
                        duration=time.time() - start_time,
                    )
                else:
                    # Some chunks failed
                    progress = download_job.compute_progress()
                    logger.error(f"Download failed: {self.url} - Some chunks failed to download")

                    return DownloadResult(
                        url=self.url,
                        status=DownloadStatus.FAILED,
                        final_path=None,
                        error="Some chunks failed to download",
                        bytes_downloaded=progress.downloaded_bytes,
                        duration=time.time() - start_time,
                    )

            except Exception as e:
                logger.error(f"Download failed with exception: {self.url}", exc_info=True)

                # Mark as failed in progress display
                if self.progress_display is not None:
                    self.progress_display.mark_failed(self.url, str(e))

                return DownloadResult(
                    url=self.url,
                    status=DownloadStatus.FAILED,
                    final_path=None,
                    error=str(e),
                    bytes_downloaded=0,
                    duration=time.time() - start_time,
                )

    def _determine_paths(
        self,
        head_response: "HttpDownloader.HeadResponse",
    ) -> tuple[Path, FilePath, FilePath]:
        """
        Determine target, part, and metadata file paths.

        Args:
            head_response: Response from HEAD request

        Returns:
            Tuple of (target_path, part_path, meta_path)
        """
        # Determine output filename
        if self.options.output_name:
            filename = self.options.output_name
        else:
            # Extract filename from URL
            from urllib.parse import unquote, urlparse

            parsed = urlparse(self.url)
            filename = unquote(parsed.path.split("/")[-1])
            if not filename:
                filename = "download"

        # Build target path
        target_path = self.options.directory / filename
        part_path = FilePath(target_path.with_suffix(target_path.suffix + ".part"))
        meta_path = FilePath(target_path.with_suffix(target_path.suffix + ".part.meta.json"))

        return target_path, part_path, meta_path

    async def _create_or_resume_job(
        self,
        head_response: "HttpDownloader.HeadResponse",
        target_path: Path,
        part_path: FilePath,
        meta_path: FilePath,
    ) -> DownloadJob | None:
        """
        Create a new download job or resume from existing metadata.

        Args:
            head_response: Response from HEAD request
            target_path: Final target file path
            part_path: Part file path
            meta_path: Metadata file path

        Returns:
            DownloadJob ready for downloading, or None on error
        """
        download_id = new_download_id()

        # Requirement 2.2, 2.3: Check for existing metadata and attempt resume
        if self.options.continue_download and meta_path.exists():
            metadata = await self.metadata_repo.load(meta_path.value)

            if metadata is not None:
                # Validate compatibility
                metadata_obj = DomainDownloadMetadata(
                    url=Url(metadata.url),
                    total_length=metadata.total_length,
                    etag=metadata.etag,
                    last_modified=metadata.last_modified,
                )

                head_obj = HeadResponse(
                    total_length=head_response.content_length,
                    etag=head_response.etag,
                    last_modified=head_response.last_modified,
                    accepts_ranges=head_response.accept_ranges,
                )

                decision = self.resume_policy.can_resume(metadata_obj, head_obj)

                if decision == ResumeDecision.CAN_RESUME:
                    # Resume from existing metadata
                    logger.info(f"Resuming download from existing metadata: {self.url}")
                    return metadata.to_download_job(
                        download_id=download_id,
                        target_path=FilePath(target_path),
                        part_path=part_path,
                        meta_path=meta_path,
                    )
                else:
                    logger.info(
                        f"Cannot resume download (incompatible metadata), starting fresh: {self.url}"
                    )

        # Requirement 2.5: Fresh start (continue disabled or no valid metadata)
        # Delete existing part file if continue is disabled
        if not self.options.continue_download and part_path.exists():
            part_path.value.unlink()

        # Create new download job
        # Requirement 1.2: Plan chunks based on file size and piece size
        chunks_list = self.chunk_planner.plan_chunks(
            total_length=head_response.content_length,
            piece_size=self.options.piece_size,
            num_splits=self.options.splits,
        )

        chunks_dict = {chunk.id: chunk for chunk in chunks_list}

        download_job = DownloadJob(
            id=download_id,
            url=Url(self.url),
            target_path=FilePath(target_path),
            part_path=part_path,
            meta_path=meta_path,
            total_length=head_response.content_length,
            piece_size=self.options.piece_size,
            chunks=chunks_dict,
            status=DownloadStatus.PENDING,
            etag=head_response.etag,
            last_modified=head_response.last_modified,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            resume_allowed=True,
        )

        # Save initial metadata
        metadata = DownloadMetadata.from_download_job(download_job)
        await self.metadata_repo.save(meta_path.value, metadata)

        return download_job

    async def _download_chunks(
        self,
        download_job: DownloadJob,
        part_file_path: Path,
    ) -> DownloadJob:
        """
        Download all chunks with parallel workers.

        Requirements:
        - 1.3: Maintain up to splits concurrent connections
        - 8.1: Enforce max_connections_per_host limit

        Args:
            download_job: Download job with chunks to download
            part_file_path: Path to part file

        Returns:
            Updated download job with chunk statuses
        """
        # Determine actual concurrency limit
        # Requirement 8.1: Respect max_connections_per_host
        max_concurrent = min(self.options.splits, self.options.max_connections_per_host)

        # Track in-flight chunks and use a lock for updating download_job
        in_flight: set[ChunkId] = set()
        in_progress_bytes: dict[ChunkId, int] = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        update_lock = asyncio.Lock()

        def bytes_downloaded_with_in_progress(job: DownloadJob) -> int:
            """Return completed bytes plus bytes currently streamed by workers."""
            progress = job.compute_progress()
            downloaded_bytes = progress.downloaded_bytes + sum(in_progress_bytes.values())
            return min(downloaded_bytes, progress.total_bytes)

        def publish_progress_locked() -> None:
            """Publish current progress while update_lock is held."""
            if self.progress_display is None:
                return

            progress = download_job.compute_progress()
            self.progress_display.update_progress(
                url=self.url,
                downloaded_bytes=bytes_downloaded_with_in_progress(download_job),
                total_bytes=progress.total_bytes,
            )

        async def progress_heartbeat() -> None:
            """Refresh progress display periodically even when no buffers arrive."""
            while True:
                await asyncio.sleep(_progress_heartbeat_interval_seconds())
                async with update_lock:
                    publish_progress_locked()

        async def update_in_flight_progress(chunk_id: ChunkId, chunk_bytes: int) -> None:
            """Update display progress for bytes streamed before chunk completion."""
            if self.progress_display is None:
                return

            async with update_lock:
                if chunk_bytes > 0:
                    in_progress_bytes[chunk_id] = chunk_bytes
                else:
                    in_progress_bytes.pop(chunk_id, None)

                publish_progress_locked()

        # Create tasks for all pending chunks
        async def download_chunk_task(chunk: Chunk) -> tuple[ChunkId, bool]:
            """Download a single chunk and return its ID and success status."""
            nonlocal download_job

            async with semaphore:
                in_flight.add(chunk.id)
                try:
                    await download_chunk_with_retry(
                        url=self.url,
                        chunk=chunk,
                        http_client=self.http_client,
                        file_writer=self.file_writer,
                        part_file_path=part_file_path,
                        max_tries=self.options.max_tries,
                        retry_wait=self.options.retry_wait,
                        progress_callback=update_in_flight_progress,
                    )

                    # Update download job and metadata after chunk completion
                    async with update_lock:
                        in_progress_bytes.pop(chunk.id, None)
                        download_job = download_job.mark_chunk_completed(chunk.id)
                        metadata = DownloadMetadata.from_download_job(download_job)
                        await self.metadata_repo.save(download_job.meta_path.value, metadata)

                        # Update progress display
                        if self.progress_display is not None:
                            progress = download_job.compute_progress()
                            self.progress_display.update_progress(
                                url=self.url,
                                downloaded_bytes=progress.downloaded_bytes,
                                total_bytes=progress.total_bytes,
                            )

                    return (chunk.id, True)

                except Exception:
                    # Chunk failed after all retries
                    async with update_lock:
                        in_progress_bytes.pop(chunk.id, None)
                        publish_progress_locked()
                    return (chunk.id, False)

                finally:
                    in_flight.discard(chunk.id)

        # Find all pending chunks
        pending_chunks = [
            chunk for chunk in download_job.chunks.values() if chunk.status == ChunkStatus.PENDING
        ]

        # Download all chunks concurrently, with a periodic UI heartbeat for stalls.
        tasks = [asyncio.create_task(download_chunk_task(chunk)) for chunk in pending_chunks]
        heartbeat_task = (
            asyncio.create_task(progress_heartbeat())
            if self.progress_display is not None and tasks
            else None
        )
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat_task

        # No need to update download_job here since it's already updated in the tasks

        return download_job

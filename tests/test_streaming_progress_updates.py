"""Tests for in-flight download progress updates."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from streamdown.application.download_coordinator import DownloadCoordinator
from streamdown.application.dtos import DownloadOptions
from streamdown.domain.enums import DownloadStatus, StreamingMode
from streamdown.domain.services import ChunkPlanner, ResumePolicy
from streamdown.infrastructure.file_writer import PartFileWriter
from streamdown.infrastructure.http_client import HeadResponse
from streamdown.infrastructure.metadata_repository import MetadataRepository


class StreamingHttpClient:
    """HTTP client that yields one chunk as several delayed buffers."""

    def __init__(self, buffer_sizes: list[int]):
        self.buffer_sizes = buffer_sizes

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def fetch_head(self, url):
        return HeadResponse(
            content_length=sum(self.buffer_sizes),
            accept_ranges=True,
            etag="test-etag",
            last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
        )

    async def fetch_range(self, url, byte_range, buffer_size=64 * 1024):
        for size in self.buffer_sizes:
            await asyncio.sleep(0)
            yield b"x" * size


class RecordingProgressDisplay:
    """Minimal progress display test double."""

    def __init__(self):
        self.progress_values: list[int] = []
        self.statuses: list[DownloadStatus] = []

    def add_download(self, url: str, filename: str, total_bytes: int) -> None:
        self.progress_values.append(0)

    def update_status(self, url: str, status: DownloadStatus) -> None:
        self.statuses.append(status)

    def update_progress(
        self,
        url: str,
        downloaded_bytes: int,
        total_bytes: int | None = None,
    ) -> None:
        self.progress_values.append(downloaded_bytes)

    def mark_complete(self, url: str, final_path: Path) -> None:
        self.statuses.append(DownloadStatus.COMPLETED)

    def mark_failed(self, url: str, error: str) -> None:
        self.statuses.append(DownloadStatus.FAILED)


def create_options(directory: Path) -> DownloadOptions:
    """Create options that force a single chunk made of multiple buffers."""
    return DownloadOptions(
        directory=directory,
        output_name="test.bin",
        splits=1,
        max_connections_per_host=1,
        piece_size=1024 * 1024,
        continue_download=False,
        allow_overwrite=True,
        auto_file_renaming=False,
        max_concurrent_downloads=1,
        streaming_mode=StreamingMode.DEFAULT,
        connect_timeout=60.0,
        read_timeout=300.0,
        max_tries=1,
        retry_wait=0.0,
        user_agent="streamdown-test/0.1.0",
        quiet=False,
        log_level="info",
        insecure=False,
        no_netrc=False,
        netrc_path=None,
    )


@pytest.mark.asyncio
async def test_progress_updates_while_single_chunk_streams() -> None:
    """Progress display should receive in-flight buffer-level updates."""
    progress_display = RecordingProgressDisplay()

    with tempfile.TemporaryDirectory() as tmpdir:
        coordinator = DownloadCoordinator(
            url="https://example.com/test.bin",
            options=create_options(Path(tmpdir)),
            http_client=StreamingHttpClient([100, 100, 100, 100]),
            file_writer=PartFileWriter(),
            metadata_repo=MetadataRepository(),
            chunk_planner=ChunkPlanner(StreamingMode.DEFAULT),
            resume_policy=ResumePolicy(),
            progress_display=progress_display,  # type: ignore[arg-type]
        )

        result = await coordinator.download()

    assert result.status == DownloadStatus.COMPLETED
    assert any(0 < value < 400 for value in progress_display.progress_values), (
        "progress jumped directly from 0 to complete without in-flight updates"
    )
    assert progress_display.progress_values[-1] == 400

"""Domain events for download lifecycle."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from streamdown.domain.value_objects import ChunkId, DownloadId, FilePath, Url


@dataclass(frozen=True)
class DownloadStarted:
    """Event emitted when a download begins."""

    download_id: DownloadId
    url: Url
    timestamp: datetime


@dataclass(frozen=True)
class ChunkCompleted:
    """Event emitted when a chunk completes successfully."""

    download_id: DownloadId
    chunk_id: ChunkId
    bytes_downloaded: int
    timestamp: datetime


@dataclass(frozen=True)
class DownloadCompleted:
    """Event emitted when a download completes successfully."""

    download_id: DownloadId
    final_path: FilePath
    total_bytes: int
    duration: timedelta
    timestamp: datetime


@dataclass(frozen=True)
class DownloadFailed:
    """Event emitted when a download fails."""

    download_id: DownloadId
    error: str
    timestamp: datetime

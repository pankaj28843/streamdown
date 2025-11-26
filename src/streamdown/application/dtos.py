"""Application layer Data Transfer Objects (DTOs)."""

from dataclasses import dataclass
from pathlib import Path

from streamdown.domain.enums import DownloadStatus, StreamingMode


@dataclass
class DownloadOptions:
    """
    Options for configuring a download.

    This DTO encapsulates all configuration options that can be specified
    via the CLI or programmatically when initiating a download.

    Requirements: 11.2
    """

    directory: Path
    output_name: str | None
    splits: int
    max_connections_per_host: int
    piece_size: int
    continue_download: bool
    allow_overwrite: bool
    auto_file_renaming: bool
    max_concurrent_downloads: int
    streaming_mode: StreamingMode
    connect_timeout: float
    read_timeout: float
    max_tries: int
    retry_wait: float
    user_agent: str
    quiet: bool
    log_level: str
    insecure: bool
    no_netrc: bool
    netrc_path: Path | None


@dataclass
class DownloadResult:
    """
    Result of a download operation.

    This DTO contains the outcome of a download attempt, including
    success/failure status, final file path, error information, and
    performance metrics.

    Requirements: 11.2
    """

    url: str
    status: DownloadStatus
    final_path: Path | None
    error: str | None
    bytes_downloaded: int
    duration: float


@dataclass
class DownloadProgress:
    """
    Progress tracking information for a download.

    This DTO provides real-time progress information for display
    in the UI, including bytes downloaded, percentage complete,
    and chunk completion status.

    Note: This is also defined in domain.entities for domain use.
    This application-layer version can be used for UI/API purposes.

    Requirements: 11.2
    """

    total_bytes: int
    downloaded_bytes: int
    completed_chunks: int
    total_chunks: int
    percentage: float

    @property
    def is_complete(self) -> bool:
        """Check if download is complete."""
        return self.downloaded_bytes >= self.total_bytes

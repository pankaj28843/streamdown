"""Domain layer - Core business logic and entities."""

from .entities import Chunk, DownloadJob, DownloadProgress
from .enums import ChunkStatus, DownloadStatus, ResumeDecision, StreamingMode
from .events import ChunkCompleted, DownloadCompleted, DownloadFailed, DownloadStarted
from .exceptions import (
    FileSystemError,
    HttpError,
    NetworkError,
    ResumeError,
    StreamdownError,
    ValidationError,
)
from .services import ChunkPlanner, DownloadMetadata, HeadResponse, ResumePolicy
from .value_objects import (
    ByteRange,
    ChunkId,
    DownloadId,
    FilePath,
    Url,
    new_download_id,
)

__all__ = [
    # Value objects
    "DownloadId",
    "ChunkId",
    "Url",
    "FilePath",
    "ByteRange",
    "new_download_id",
    # Enums
    "DownloadStatus",
    "ChunkStatus",
    "StreamingMode",
    "ResumeDecision",
    # Entities
    "Chunk",
    "DownloadJob",
    "DownloadProgress",
    # Services
    "ChunkPlanner",
    "ResumePolicy",
    "DownloadMetadata",
    "HeadResponse",
    # Events
    "DownloadStarted",
    "ChunkCompleted",
    "DownloadCompleted",
    "DownloadFailed",
    # Exceptions
    "StreamdownError",
    "NetworkError",
    "HttpError",
    "FileSystemError",
    "ResumeError",
    "ValidationError",
]

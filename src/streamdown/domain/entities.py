"""Domain entities for download management."""

from dataclasses import dataclass, field
from datetime import datetime

from streamdown.domain.enums import ChunkStatus, DownloadStatus
from streamdown.domain.value_objects import (
    ByteRange,
    ChunkId,
    DownloadId,
    FilePath,
    Url,
)


@dataclass
class Chunk:
    """Individual chunk of a file being downloaded."""

    id: ChunkId
    range: ByteRange
    status: ChunkStatus = ChunkStatus.PENDING
    retries: int = 0
    last_error: str | None = None

    def mark_in_progress(self) -> "Chunk":
        """Mark chunk as in progress."""
        return Chunk(
            id=self.id,
            range=self.range,
            status=ChunkStatus.IN_PROGRESS,
            retries=self.retries,
            last_error=self.last_error,
        )

    def mark_completed(self) -> "Chunk":
        """Mark chunk as completed."""
        return Chunk(
            id=self.id,
            range=self.range,
            status=ChunkStatus.COMPLETED,
            retries=self.retries,
            last_error=None,
        )

    def mark_failed(self, error: str) -> "Chunk":
        """Mark chunk as failed with error message."""
        return Chunk(
            id=self.id,
            range=self.range,
            status=ChunkStatus.FAILED,
            retries=self.retries + 1,
            last_error=error,
        )


@dataclass
class DownloadProgress:
    """Progress information for a download."""

    total_bytes: int
    downloaded_bytes: int
    completed_chunks: int
    total_chunks: int
    percentage: float

    @property
    def is_complete(self) -> bool:
        """Check if download is complete."""
        return self.downloaded_bytes >= self.total_bytes


@dataclass
class DownloadJob:
    """Aggregate root for a download job."""

    id: DownloadId
    url: Url
    target_path: FilePath
    part_path: FilePath
    meta_path: FilePath
    total_length: int | None
    piece_size: int
    chunks: dict[ChunkId, Chunk] = field(default_factory=dict)
    status: DownloadStatus = DownloadStatus.PENDING
    etag: str | None = None
    last_modified: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resume_allowed: bool = True

    def mark_chunk_completed(self, chunk_id: ChunkId) -> "DownloadJob":
        """
        Mark a chunk as completed and return updated job.

        This method creates a new DownloadJob instance with the specified
        chunk marked as completed. The updated_at timestamp is refreshed.
        """
        if chunk_id not in self.chunks:
            raise ValueError(f"Chunk {chunk_id} not found in download job")

        # Create updated chunks dict with the completed chunk
        updated_chunks = self.chunks.copy()
        updated_chunks[chunk_id] = self.chunks[chunk_id].mark_completed()

        # Return new DownloadJob with updated state
        return DownloadJob(
            id=self.id,
            url=self.url,
            target_path=self.target_path,
            part_path=self.part_path,
            meta_path=self.meta_path,
            total_length=self.total_length,
            piece_size=self.piece_size,
            chunks=updated_chunks,
            status=self.status,
            etag=self.etag,
            last_modified=self.last_modified,
            created_at=self.created_at,
            updated_at=datetime.now(),
            resume_allowed=self.resume_allowed,
        )

    def is_complete(self) -> bool:
        """
        Check if all chunks are completed.

        Returns True if all chunks have status COMPLETED, False otherwise.
        """
        if not self.chunks:
            return False

        return all(chunk.status == ChunkStatus.COMPLETED for chunk in self.chunks.values())

    def compute_progress(self) -> DownloadProgress:
        """
        Compute current download progress.

        Returns a DownloadProgress object with statistics about the download.
        """
        if self.total_length is None or self.total_length == 0:
            return DownloadProgress(
                total_bytes=0,
                downloaded_bytes=0,
                completed_chunks=0,
                total_chunks=len(self.chunks),
                percentage=0.0,
            )

        completed_chunks = sum(
            1 for chunk in self.chunks.values() if chunk.status == ChunkStatus.COMPLETED
        )

        downloaded_bytes = sum(
            chunk.range.size
            for chunk in self.chunks.values()
            if chunk.status == ChunkStatus.COMPLETED
        )

        percentage = (downloaded_bytes / self.total_length) * 100.0 if self.total_length > 0 else 0.0

        return DownloadProgress(
            total_bytes=self.total_length,
            downloaded_bytes=downloaded_bytes,
            completed_chunks=completed_chunks,
            total_chunks=len(self.chunks),
            percentage=percentage,
        )

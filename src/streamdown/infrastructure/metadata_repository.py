"""Metadata repository for persisting download state."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from streamdown.domain.entities import Chunk, DownloadJob
from streamdown.domain.enums import ChunkStatus, DownloadStatus
from streamdown.domain.value_objects import (
    ByteRange,
    ChunkId,
    DownloadId,
    FilePath,
    Url,
)


@dataclass
class DownloadMetadata:
    """Serializable metadata for a download job."""

    version: int
    url: str
    total_length: int | None
    etag: str | None
    last_modified: str | None
    piece_size: int
    chunks: list[dict[str, Any]]
    created_at: str
    updated_at: str

    def to_download_job(
        self,
        download_id: DownloadId,
        target_path: FilePath,
        part_path: FilePath,
        meta_path: FilePath,
    ) -> DownloadJob:
        """Convert metadata to DownloadJob entity."""
        chunks_dict: dict[ChunkId, Chunk] = {}

        for chunk_data in self.chunks:
            chunk_id = ChunkId(chunk_data["id"])
            chunks_dict[chunk_id] = Chunk(
                id=chunk_id,
                range=ByteRange(
                    start=chunk_data["start"],
                    end=chunk_data["end"],
                ),
                status=ChunkStatus[chunk_data["status"]],
                retries=chunk_data.get("retries", 0),
                last_error=chunk_data.get("last_error"),
            )

        return DownloadJob(
            id=download_id,
            url=Url(self.url),
            target_path=target_path,
            part_path=part_path,
            meta_path=meta_path,
            total_length=self.total_length,
            piece_size=self.piece_size,
            chunks=chunks_dict,
            status=DownloadStatus.PENDING,
            etag=self.etag,
            last_modified=self.last_modified,
            created_at=datetime.fromisoformat(self.created_at),
            updated_at=datetime.fromisoformat(self.updated_at),
            resume_allowed=True,
        )

    @classmethod
    def from_download_job(cls, job: DownloadJob) -> "DownloadMetadata":
        """Create metadata from DownloadJob entity."""
        chunks_list = []
        for chunk in job.chunks.values():
            chunks_list.append({
                "id": chunk.id,
                "start": chunk.range.start,
                "end": chunk.range.end,
                "status": chunk.status.name,
                "retries": chunk.retries,
                "last_error": chunk.last_error,
            })

        return cls(
            version=1,
            url=str(job.url),
            total_length=job.total_length,
            etag=job.etag,
            last_modified=job.last_modified,
            piece_size=job.piece_size,
            chunks=chunks_list,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
        )


class MetadataRepository:
    """Repository for persisting and loading download metadata."""

    async def save(self, meta_path: Path, metadata: DownloadMetadata) -> None:
        """
        Save metadata to disk using atomic write operation.

        Uses temp file + rename pattern for crash safety:
        1. Write to temporary file
        2. Flush to disk
        3. Atomically rename to target (atomic on POSIX)

        Args:
            meta_path: Path to metadata file
            metadata: Metadata to save
        """
        # Ensure parent directory exists
        meta_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temporary file in same directory for atomic rename
        temp_path = meta_path.with_suffix(meta_path.suffix + ".tmp")

        try:
            # Write to temporary file
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                json_data = json.dumps(asdict(metadata), indent=2)
                await f.write(json_data)
                await f.flush()

            # Atomically rename to target
            temp_path.rename(meta_path)

        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise

    async def load(self, meta_path: Path) -> DownloadMetadata | None:
        """
        Load metadata from disk.

        Handles corrupted metadata gracefully by returning None.

        Args:
            meta_path: Path to metadata file

        Returns:
            DownloadMetadata if file exists and is valid, None otherwise
        """
        if not meta_path.exists():
            return None

        try:
            async with aiofiles.open(meta_path, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            # Validate required fields
            required_fields = [
                "version",
                "url",
                "piece_size",
                "chunks",
                "created_at",
                "updated_at",
            ]
            for field in required_fields:
                if field not in data:
                    # Corrupted metadata - missing required field
                    return None

            # Validate version
            if data["version"] != 1:
                # Unsupported version
                return None

            return DownloadMetadata(
                version=data["version"],
                url=data["url"],
                total_length=data.get("total_length"),
                etag=data.get("etag"),
                last_modified=data.get("last_modified"),
                piece_size=data["piece_size"],
                chunks=data["chunks"],
                created_at=data["created_at"],
                updated_at=data["updated_at"],
            )

        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            # Corrupted or unreadable metadata
            return None

    async def delete(self, meta_path: Path) -> None:
        """
        Delete metadata file.

        Used for cleanup after successful download completion.

        Args:
            meta_path: Path to metadata file
        """
        if meta_path.exists():
            meta_path.unlink()

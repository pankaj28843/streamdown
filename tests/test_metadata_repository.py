"""Tests for metadata repository."""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from streamdown.domain.entities import Chunk, DownloadJob
from streamdown.domain.enums import ChunkStatus, DownloadStatus
from streamdown.domain.value_objects import (
    ByteRange,
    ChunkId,
    DownloadId,
    FilePath,
    Url,
)
from streamdown.infrastructure.metadata_repository import (
    DownloadMetadata,
    MetadataRepository,
)


# Hypothesis strategies for generating test data
@st.composite
def download_metadata_strategy(draw):
    """Generate random but valid DownloadMetadata."""
    num_chunks = draw(st.integers(min_value=1, max_value=20))
    piece_size = draw(st.integers(min_value=1024, max_value=10 * 1024 * 1024))
    total_length = num_chunks * piece_size

    chunks = []
    for i in range(num_chunks):
        start = i * piece_size
        end = min(start + piece_size - 1, total_length - 1)
        chunks.append({
            "id": i,
            "start": start,
            "end": end,
            "status": draw(st.sampled_from(["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"])),
            "retries": draw(st.integers(min_value=0, max_value=5)),
            "last_error": draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        })

    return DownloadMetadata(
        version=1,
        url=draw(st.from_regex(r"https?://[a-z]+\.[a-z]+/[a-z]+", fullmatch=True)),
        total_length=total_length,
        etag=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        last_modified=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        piece_size=piece_size,
        chunks=chunks,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )


# Feature: streamdown, Property 25: Atomic metadata writes
@given(metadata=download_metadata_strategy())
@pytest.mark.asyncio
async def test_atomic_metadata_writes(metadata: DownloadMetadata):
    """
    **Feature: streamdown, Property 25: Atomic metadata writes**
    **Validates: Requirements 12.1**

    For any metadata write operation, the metadata file must be written
    atomically (temp file + rename) to ensure crash safety.

    This test verifies that:
    1. After save completes, the metadata file exists and is valid
    2. No temporary files are left behind
    3. The saved data matches what was written
    """
    import tempfile

    repo = MetadataRepository()

    # Create a temporary directory for this test
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        meta_path = tmp_path / "test.part.meta.json"

        # Save metadata
        await repo.save(meta_path, metadata)

        # Verify metadata file exists
        assert meta_path.exists(), "Metadata file should exist after save"

        # Verify no temp files left behind
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0, "No temporary files should remain after save"

        # Verify file is valid JSON and matches what we saved
        with open(meta_path) as f:
            saved_data = json.load(f)

        assert saved_data["version"] == metadata.version
        assert saved_data["url"] == metadata.url
        assert saved_data["total_length"] == metadata.total_length
        assert saved_data["piece_size"] == metadata.piece_size
        assert len(saved_data["chunks"]) == len(metadata.chunks)

        # Verify we can load it back
        loaded = await repo.load(meta_path)
        assert loaded is not None, "Should be able to load saved metadata"
        assert loaded.url == metadata.url
        assert loaded.total_length == metadata.total_length
        assert loaded.piece_size == metadata.piece_size


# Unit test for basic save/load functionality
# Feature: streamdown, Property 26: Metadata cleanup on success
@given(metadata=download_metadata_strategy())
@pytest.mark.asyncio
async def test_metadata_cleanup_on_success(metadata: DownloadMetadata):
    """
    **Feature: streamdown, Property 26: Metadata cleanup on success**
    **Validates: Requirements 12.4**

    For any successfully completed download, the metadata file must be removed.

    This test verifies that:
    1. After a metadata file is created, it exists
    2. After delete is called, the metadata file no longer exists
    3. Delete operation is idempotent (can be called on non-existent files)
    """
    import tempfile

    repo = MetadataRepository()

    # Create a temporary directory for this test
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        meta_path = tmp_path / "test.part.meta.json"

        # Save metadata
        await repo.save(meta_path, metadata)

        # Verify it exists
        assert meta_path.exists(), "Metadata file should exist after save"

        # Delete it (simulating successful download completion)
        await repo.delete(meta_path)

        # Verify it's gone
        assert not meta_path.exists(), "Metadata file should be removed after delete"

        # Verify delete is idempotent (doesn't error on non-existent file)
        await repo.delete(meta_path)  # Should not raise


@pytest.mark.asyncio
async def test_save_and_load_metadata(tmp_path: Path):
    """Test basic save and load operations."""
    repo = MetadataRepository()
    meta_path = tmp_path / "test.part.meta.json"

    # Create test metadata
    metadata = DownloadMetadata(
        version=1,
        url="https://example.com/file.zip",
        total_length=1024000,
        etag="abc123",
        last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
        piece_size=1024,
        chunks=[
            {
                "id": 0,
                "start": 0,
                "end": 1023,
                "status": "COMPLETED",
                "retries": 0,
                "last_error": None,
            },
            {
                "id": 1,
                "start": 1024,
                "end": 2047,
                "status": "PENDING",
                "retries": 0,
                "last_error": None,
            },
        ],
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    # Save metadata
    await repo.save(meta_path, metadata)

    # Load metadata
    loaded = await repo.load(meta_path)

    assert loaded is not None
    assert loaded.version == 1
    assert loaded.url == "https://example.com/file.zip"
    assert loaded.total_length == 1024000
    assert loaded.etag == "abc123"
    assert loaded.piece_size == 1024
    assert len(loaded.chunks) == 2


@pytest.mark.asyncio
async def test_load_nonexistent_metadata(tmp_path: Path):
    """Test loading metadata that doesn't exist returns None."""
    repo = MetadataRepository()
    meta_path = tmp_path / "nonexistent.part.meta.json"

    loaded = await repo.load(meta_path)
    assert loaded is None


@pytest.mark.asyncio
async def test_load_corrupted_metadata(tmp_path: Path):
    """Test loading corrupted metadata returns None."""
    repo = MetadataRepository()
    meta_path = tmp_path / "corrupted.part.meta.json"

    # Write invalid JSON
    with open(meta_path, "w") as f:
        f.write("{ invalid json }")

    loaded = await repo.load(meta_path)
    assert loaded is None


@pytest.mark.asyncio
async def test_load_incomplete_metadata(tmp_path: Path):
    """Test loading metadata with missing required fields returns None."""
    repo = MetadataRepository()
    meta_path = tmp_path / "incomplete.part.meta.json"

    # Write JSON missing required fields
    with open(meta_path, "w") as f:
        json.dump({"version": 1, "url": "https://example.com/file.zip"}, f)

    loaded = await repo.load(meta_path)
    assert loaded is None


@pytest.mark.asyncio
async def test_delete_metadata(tmp_path: Path):
    """Test deleting metadata file."""
    repo = MetadataRepository()
    meta_path = tmp_path / "test.part.meta.json"

    # Create a metadata file
    metadata = DownloadMetadata(
        version=1,
        url="https://example.com/file.zip",
        total_length=1024,
        etag=None,
        last_modified=None,
        piece_size=1024,
        chunks=[],
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    await repo.save(meta_path, metadata)
    assert meta_path.exists()

    # Delete it
    await repo.delete(meta_path)
    assert not meta_path.exists()


@pytest.mark.asyncio
async def test_delete_nonexistent_metadata(tmp_path: Path):
    """Test deleting nonexistent metadata doesn't raise error."""
    repo = MetadataRepository()
    meta_path = tmp_path / "nonexistent.part.meta.json"

    # Should not raise
    await repo.delete(meta_path)


@pytest.mark.asyncio
async def test_metadata_to_download_job_conversion(tmp_path: Path):
    """Test converting metadata to DownloadJob entity."""
    metadata = DownloadMetadata(
        version=1,
        url="https://example.com/file.zip",
        total_length=2048,
        etag="abc123",
        last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
        piece_size=1024,
        chunks=[
            {
                "id": 0,
                "start": 0,
                "end": 1023,
                "status": "COMPLETED",
                "retries": 0,
                "last_error": None,
            },
            {
                "id": 1,
                "start": 1024,
                "end": 2047,
                "status": "PENDING",
                "retries": 1,
                "last_error": "Network error",
            },
        ],
        created_at="2025-11-25T10:30:00",
        updated_at="2025-11-25T10:35:00",
    )

    download_id = DownloadId(uuid4())
    target_path = FilePath.from_str(str(tmp_path / "file.zip"))
    part_path = FilePath.from_str(str(tmp_path / "file.zip.part"))
    meta_path = FilePath.from_str(str(tmp_path / "file.zip.part.meta.json"))

    job = metadata.to_download_job(download_id, target_path, part_path, meta_path)

    assert job.id == download_id
    assert str(job.url) == "https://example.com/file.zip"
    assert job.total_length == 2048
    assert job.etag == "abc123"
    assert job.piece_size == 1024
    assert len(job.chunks) == 2

    # Check first chunk
    chunk0 = job.chunks[ChunkId(0)]
    assert chunk0.range.start == 0
    assert chunk0.range.end == 1023
    assert chunk0.status == ChunkStatus.COMPLETED
    assert chunk0.retries == 0

    # Check second chunk
    chunk1 = job.chunks[ChunkId(1)]
    assert chunk1.range.start == 1024
    assert chunk1.range.end == 2047
    assert chunk1.status == ChunkStatus.PENDING
    assert chunk1.retries == 1
    assert chunk1.last_error == "Network error"


@pytest.mark.asyncio
async def test_download_job_to_metadata_conversion():
    """Test converting DownloadJob to metadata."""
    download_id = DownloadId(uuid4())
    url = Url("https://example.com/file.zip")
    target_path = FilePath.from_str("/tmp/file.zip")
    part_path = FilePath.from_str("/tmp/file.zip.part")
    meta_path = FilePath.from_str("/tmp/file.zip.part.meta.json")

    chunks = {
        ChunkId(0): Chunk(
            id=ChunkId(0),
            range=ByteRange(0, 1023),
            status=ChunkStatus.COMPLETED,
            retries=0,
            last_error=None,
        ),
        ChunkId(1): Chunk(
            id=ChunkId(1),
            range=ByteRange(1024, 2047),
            status=ChunkStatus.PENDING,
            retries=1,
            last_error="Network error",
        ),
    }

    job = DownloadJob(
        id=download_id,
        url=url,
        target_path=target_path,
        part_path=part_path,
        meta_path=meta_path,
        total_length=2048,
        piece_size=1024,
        chunks=chunks,
        status=DownloadStatus.RUNNING,
        etag="abc123",
        last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
        created_at=datetime(2025, 11, 25, 10, 30, 0),
        updated_at=datetime(2025, 11, 25, 10, 35, 0),
        resume_allowed=True,
    )

    metadata = DownloadMetadata.from_download_job(job)

    assert metadata.version == 1
    assert metadata.url == "https://example.com/file.zip"
    assert metadata.total_length == 2048
    assert metadata.etag == "abc123"
    assert metadata.piece_size == 1024
    assert len(metadata.chunks) == 2

    # Check chunks
    chunk0_data = next(c for c in metadata.chunks if c["id"] == 0)
    assert chunk0_data["start"] == 0
    assert chunk0_data["end"] == 1023
    assert chunk0_data["status"] == "COMPLETED"

    chunk1_data = next(c for c in metadata.chunks if c["id"] == 1)
    assert chunk1_data["start"] == 1024
    assert chunk1_data["end"] == 2047
    assert chunk1_data["status"] == "PENDING"
    assert chunk1_data["retries"] == 1
    assert chunk1_data["last_error"] == "Network error"

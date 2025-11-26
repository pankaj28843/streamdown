"""Property-based tests for domain entities."""

from datetime import datetime
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from streamdown.domain import (
    ByteRange,
    Chunk,
    ChunkId,
    ChunkStatus,
    DownloadJob,
    DownloadStatus,
    FilePath,
    Url,
    new_download_id,
)


# Strategies for generating test data
@st.composite
def chunk_strategy(draw):
    """Generate a valid Chunk."""
    chunk_id = ChunkId(draw(st.integers(min_value=0, max_value=1000)))
    start = draw(st.integers(min_value=0, max_value=10**9))
    end = draw(st.integers(min_value=start, max_value=start + 10**6))
    status = draw(st.sampled_from(list(ChunkStatus)))
    retries = draw(st.integers(min_value=0, max_value=10))
    last_error = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))

    return Chunk(
        id=chunk_id,
        range=ByteRange(start=start, end=end),
        status=status,
        retries=retries,
        last_error=last_error,
    )


@st.composite
def download_job_strategy(draw):
    """Generate a valid DownloadJob with chunks."""
    download_id = new_download_id()
    url = Url("https://example.com/file.bin")
    target_path = FilePath(Path("/tmp/file.bin"))
    part_path = FilePath(Path("/tmp/file.bin.part"))
    meta_path = FilePath(Path("/tmp/file.bin.part.meta.json"))

    total_length = draw(st.integers(min_value=1, max_value=10**9))
    piece_size = draw(st.integers(min_value=1024, max_value=10**6))

    # Generate chunks
    num_chunks = draw(st.integers(min_value=1, max_value=20))
    chunks = {}
    offset = 0
    for i in range(num_chunks):
        chunk_id = ChunkId(i)
        chunk_size = min(piece_size, total_length - offset)
        if chunk_size <= 0:
            break
        chunks[chunk_id] = Chunk(
            id=chunk_id,
            range=ByteRange(start=offset, end=offset + chunk_size - 1),
            status=draw(st.sampled_from(list(ChunkStatus))),
            retries=0,
            last_error=None,
        )
        offset += chunk_size
        if offset >= total_length:
            break

    return DownloadJob(
        id=download_id,
        url=url,
        target_path=target_path,
        part_path=part_path,
        meta_path=meta_path,
        total_length=total_length,
        piece_size=piece_size,
        chunks=chunks,
        status=DownloadStatus.RUNNING,
        etag=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        last_modified=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        resume_allowed=draw(st.booleans()),
    )


# Feature: streamdown, Property 27: Metadata persistence before chunk completion
@given(job=download_job_strategy())
def test_chunk_completion_is_atomic(job: DownloadJob):
    """
    For any chunk completion, the operation must be atomic and maintain consistency.

    This test verifies that when mark_chunk_completed is called:
    1. The chunk status is updated to COMPLETED
    2. The updated_at timestamp is refreshed
    3. The original job remains unchanged (immutability)
    4. All other chunks remain unchanged

    **Validates: Requirements 12.5**

    Note: This tests the domain model behavior. The actual metadata persistence
    ordering will be enforced at the application/infrastructure layer where
    the metadata repository persists state before calling mark_chunk_completed.
    """
    if not job.chunks:
        return  # Skip if no chunks

    # Pick a chunk to complete
    chunk_id = next(iter(job.chunks.keys()))
    original_chunk = job.chunks[chunk_id]
    original_updated_at = job.updated_at

    # Mark chunk as completed
    updated_job = job.mark_chunk_completed(chunk_id)

    # Verify the chunk is marked as completed in the new job
    assert updated_job.chunks[chunk_id].status == ChunkStatus.COMPLETED
    assert updated_job.chunks[chunk_id].last_error is None

    # Verify updated_at was refreshed
    assert updated_job.updated_at >= original_updated_at

    # Verify original job is unchanged (immutability)
    assert job.chunks[chunk_id].status == original_chunk.status
    assert job.updated_at == original_updated_at

    # Verify all other chunks remain unchanged
    for cid, chunk in job.chunks.items():
        if cid != chunk_id:
            assert updated_job.chunks[cid].status == chunk.status
            assert updated_job.chunks[cid].retries == chunk.retries
            assert updated_job.chunks[cid].last_error == chunk.last_error

    # Verify other job fields remain unchanged
    assert updated_job.id == job.id
    assert updated_job.url == job.url
    assert updated_job.total_length == job.total_length
    assert updated_job.status == job.status


# Additional property tests for entity behavior
@given(chunk=chunk_strategy())
def test_chunk_mark_completed_clears_error(chunk: Chunk):
    """For any chunk, marking it as completed must clear the last_error field."""
    completed_chunk = chunk.mark_completed()

    assert completed_chunk.status == ChunkStatus.COMPLETED
    assert completed_chunk.last_error is None
    assert completed_chunk.id == chunk.id
    assert completed_chunk.range == chunk.range


@given(chunk=chunk_strategy(), error_msg=st.text(min_size=1, max_size=100))
def test_chunk_mark_failed_increments_retries(chunk: Chunk, error_msg: str):
    """For any chunk, marking it as failed must increment retries and store error."""
    original_retries = chunk.retries
    failed_chunk = chunk.mark_failed(error_msg)

    assert failed_chunk.status == ChunkStatus.FAILED
    assert failed_chunk.retries == original_retries + 1
    assert failed_chunk.last_error == error_msg
    assert failed_chunk.id == chunk.id
    assert failed_chunk.range == chunk.range


@given(job=download_job_strategy())
def test_is_complete_requires_all_chunks_completed(job: DownloadJob):
    """For any download job, is_complete returns True only if all chunks are COMPLETED."""
    # Test the actual state
    expected = all(chunk.status == ChunkStatus.COMPLETED for chunk in job.chunks.values()) if job.chunks else False
    assert job.is_complete() == expected


@given(job=download_job_strategy())
def test_compute_progress_accuracy(job: DownloadJob):
    """For any download job, compute_progress must accurately reflect completed chunks."""
    progress = job.compute_progress()

    if job.total_length is None or job.total_length == 0:
        assert progress.total_bytes == 0
        assert progress.downloaded_bytes == 0
        assert progress.percentage == 0.0
        return

    # Count completed chunks manually
    expected_completed = sum(
        1 for chunk in job.chunks.values() if chunk.status == ChunkStatus.COMPLETED
    )
    expected_bytes = sum(
        chunk.range.size
        for chunk in job.chunks.values()
        if chunk.status == ChunkStatus.COMPLETED
    )

    assert progress.total_bytes == job.total_length
    assert progress.downloaded_bytes == expected_bytes
    assert progress.completed_chunks == expected_completed
    assert progress.total_chunks == len(job.chunks)

    # Verify percentage calculation
    if job.total_length > 0:
        expected_percentage = (expected_bytes / job.total_length) * 100.0
        assert abs(progress.percentage - expected_percentage) < 0.01  # Allow small floating point error

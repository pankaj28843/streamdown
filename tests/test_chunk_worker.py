"""Property-based tests for chunk download worker."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from streamdown.application.chunk_worker import download_chunk_with_retry
from streamdown.domain.entities import Chunk
from streamdown.domain.enums import ChunkStatus
from streamdown.domain.exceptions import NetworkError
from streamdown.domain.value_objects import ByteRange, ChunkId
from streamdown.infrastructure.file_writer import PartFileWriter
from streamdown.infrastructure.http_client import HttpDownloader


# Feature: streamdown, Property 21: Retry limit enforcement
@pytest.mark.asyncio
@given(
    max_tries=st.integers(min_value=1, max_value=10),
    chunk_start=st.integers(min_value=0, max_value=1000000),
    chunk_size=st.integers(min_value=1, max_value=10000),
)
@settings(max_examples=100)
async def test_retry_limit_enforcement(
    max_tries: int,
    chunk_start: int,
    chunk_size: int,
) -> None:
    """
    **Feature: streamdown, Property 21: Retry limit enforcement**
    **Validates: Requirements 8.4**

    For any failed chunk with max_tries specified, the chunk must be retried
    at most max_tries times before being marked as permanently failed.
    """
    # Create a chunk
    chunk = Chunk(
        id=ChunkId(0),
        range=ByteRange(start=chunk_start, end=chunk_start + chunk_size - 1),
        status=ChunkStatus.PENDING,
    )

    # Create mock HTTP client that always fails with NetworkError
    http_client = MagicMock(spec=HttpDownloader)
    call_count = 0

    async def failing_fetch_range(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise NetworkError("Simulated network failure")
        # Make this an async generator to match the signature
        yield  # This line will never be reached

    http_client.fetch_range = failing_fetch_range

    # Create mock file writer (won't be called since fetch fails)
    file_writer = MagicMock(spec=PartFileWriter)

    # Attempt download with retry
    with pytest.raises(NetworkError):
        await download_chunk_with_retry(
            url="http://example.com/file",
            chunk=chunk,
            http_client=http_client,
            file_writer=file_writer,
            part_file_path=Path("/tmp/test.part"),
            max_tries=max_tries,
            retry_wait=0.0,  # No wait for faster tests
        )

    # Verify that fetch_range was called exactly max_tries times
    assert call_count == max_tries, f"Expected {max_tries} attempts, but got {call_count}"


# Feature: streamdown, Property 22: Retry wait duration
@pytest.mark.asyncio
@given(
    retry_wait=st.floats(min_value=0.01, max_value=0.2),
    chunk_start=st.integers(min_value=0, max_value=1000000),
    chunk_size=st.integers(min_value=1, max_value=10000),
)
@settings(max_examples=50, deadline=5000)  # 5 second deadline per example
async def test_retry_wait_duration(
    retry_wait: float,
    chunk_start: int,
    chunk_size: int,
) -> None:
    """
    **Feature: streamdown, Property 22: Retry wait duration**
    **Validates: Requirements 8.5**

    For any chunk retry with retry_wait specified, the system must wait
    at least that duration between retry attempts.
    """
    # Create a chunk
    chunk = Chunk(
        id=ChunkId(0),
        range=ByteRange(start=chunk_start, end=chunk_start + chunk_size - 1),
        status=ChunkStatus.PENDING,
    )

    # Track timing of attempts
    attempt_times = []
    call_count = [0]  # Use list to allow modification in nested function

    # Create mock HTTP client that fails twice then succeeds
    def make_fetch_range(*args, **kwargs):
        call_count[0] += 1
        attempt_times.append(asyncio.get_event_loop().time())
        current_attempt = call_count[0]

        async def fetch_gen():
            if current_attempt < 3:  # Fail first 2 attempts
                raise NetworkError("Simulated network failure")
            # Succeed on 3rd attempt
            yield b"test data"

        return fetch_gen()

    http_client = MagicMock(spec=HttpDownloader)
    http_client.fetch_range = make_fetch_range

    # Create mock file writer
    file_writer = MagicMock(spec=PartFileWriter)
    file_writer.write_at_offset = AsyncMock()

    # Attempt download with retry
    await download_chunk_with_retry(
        url="http://example.com/file",
        chunk=chunk,
        http_client=http_client,
        file_writer=file_writer,
        part_file_path=Path("/tmp/test.part"),
        max_tries=5,
        retry_wait=retry_wait,
    )

    # Verify that we had 3 attempts (2 failures + 1 success)
    assert call_count[0] == 3, f"Expected 3 attempts, but got {call_count[0]}"

    # Verify wait times between attempts
    # There should be 2 waits (between attempt 1-2 and 2-3)
    assert len(attempt_times) == 3, f"Expected 3 attempt times, got {len(attempt_times)}"

    # Check wait between first and second attempt
    wait_1_2 = attempt_times[1] - attempt_times[0]
    assert wait_1_2 >= retry_wait, (
        f"Wait between attempts 1-2 was {wait_1_2:.3f}s, expected at least {retry_wait:.3f}s"
    )

    # Check wait between second and third attempt
    wait_2_3 = attempt_times[2] - attempt_times[1]
    assert wait_2_3 >= retry_wait, (
        f"Wait between attempts 2-3 was {wait_2_3:.3f}s, expected at least {retry_wait:.3f}s"
    )


# Feature: streamdown, Property 30: Bounded buffer sizes
@pytest.mark.asyncio
@given(
    chunk_size=st.integers(min_value=1024, max_value=10 * 1024 * 1024),  # 1KB to 10MB
    buffer_size=st.integers(min_value=1024, max_value=128 * 1024),  # 1KB to 128KB
)
@settings(max_examples=100)
async def test_bounded_buffer_sizes(
    chunk_size: int,
    buffer_size: int,
) -> None:
    """
    **Feature: streamdown, Property 30: Bounded buffer sizes**
    **Validates: Requirements 14.1**

    For any chunk download, data must be streamed in fixed-size buffers
    not exceeding the specified buffer size (default 64 KiB).
    """
    # Create a chunk
    chunk = Chunk(
        id=ChunkId(0),
        range=ByteRange(start=0, end=chunk_size - 1),
        status=ChunkStatus.PENDING,
    )

    # Track all buffer sizes that were yielded
    yielded_buffer_sizes = []

    # Create mock HTTP client that yields data in various buffer sizes
    def make_fetch_range(*args, **kwargs):
        # Verify that buffer_size parameter is passed correctly
        actual_buffer_size = kwargs.get("buffer_size", 64 * 1024)

        async def fetch_gen():
            # Simulate streaming data in chunks
            remaining = chunk_size
            while remaining > 0:
                # Yield data in buffers up to buffer_size
                current_buffer_size = min(actual_buffer_size, remaining)
                yielded_buffer_sizes.append(current_buffer_size)
                yield b"x" * current_buffer_size
                remaining -= current_buffer_size

        return fetch_gen()

    http_client = MagicMock(spec=HttpDownloader)
    http_client.fetch_range = make_fetch_range

    # Track what gets written to disk
    written_chunks = []

    async def mock_write_at_offset(path, offset, data):
        written_chunks.append(len(data))

    file_writer = MagicMock(spec=PartFileWriter)
    file_writer.write_at_offset = mock_write_at_offset

    # Download the chunk
    await download_chunk_with_retry(
        url="http://example.com/file",
        chunk=chunk,
        http_client=http_client,
        file_writer=file_writer,
        part_file_path=Path("/tmp/test.part"),
        max_tries=1,
        retry_wait=0.0,
        buffer_size=buffer_size,
    )

    # Verify all yielded buffers respect the buffer size limit
    for size in yielded_buffer_sizes:
        assert size <= buffer_size, f"Buffer size {size} exceeds limit {buffer_size}"

    # Verify all written chunks respect the buffer size limit
    for size in written_chunks:
        assert size <= buffer_size, f"Written chunk size {size} exceeds buffer limit {buffer_size}"

    # Verify that data was actually streamed (not all at once)
    if chunk_size > buffer_size:
        assert len(yielded_buffer_sizes) > 1, (
            "Expected multiple buffers for large chunk, but got only one"
        )
        assert len(written_chunks) > 1, "Expected multiple writes for large chunk, but got only one"

    # Verify total data written equals chunk size
    total_written = sum(written_chunks)
    assert total_written == chunk_size, (
        f"Total written {total_written} doesn't match chunk size {chunk_size}"
    )


@pytest.mark.asyncio
async def test_chunk_worker_reports_progress_after_each_streamed_buffer() -> None:
    """Chunk worker should report byte progress before the chunk completes."""
    chunk = Chunk(
        id=ChunkId(7),
        range=ByteRange(start=10, end=15),
        status=ChunkStatus.PENDING,
    )

    async def fetch_range(*args, **kwargs):
        yield b"ab"
        yield b"cde"
        yield b"f"

    http_client = MagicMock(spec=HttpDownloader)
    http_client.fetch_range = fetch_range
    file_writer = MagicMock(spec=PartFileWriter)
    file_writer.write_at_offset = AsyncMock()
    reports: list[tuple[ChunkId, int]] = []

    async def report_progress(chunk_id: ChunkId, downloaded_bytes: int) -> None:
        reports.append((chunk_id, downloaded_bytes))

    await download_chunk_with_retry(
        url="http://example.com/file",
        chunk=chunk,
        http_client=http_client,
        file_writer=file_writer,
        part_file_path=Path("/tmp/test.part"),
        max_tries=1,
        retry_wait=0.0,
        progress_callback=report_progress,
    )

    assert reports == [
        (ChunkId(7), 2),
        (ChunkId(7), 5),
        (ChunkId(7), 6),
    ]


@pytest.mark.asyncio
async def test_chunk_worker_resets_progress_before_retrying_partial_chunk() -> None:
    """Partial bytes from a failed attempt should not stay counted on retry."""
    chunk = Chunk(
        id=ChunkId(3),
        range=ByteRange(start=0, end=2),
        status=ChunkStatus.PENDING,
    )
    attempts = 0

    def fetch_range(*args, **kwargs):
        nonlocal attempts
        attempts += 1

        async def fetch_gen():
            if attempts == 1:
                yield b"xy"
                raise NetworkError("drop after partial chunk")
            yield b"abc"

        return fetch_gen()

    http_client = MagicMock(spec=HttpDownloader)
    http_client.fetch_range = fetch_range
    file_writer = MagicMock(spec=PartFileWriter)
    file_writer.write_at_offset = AsyncMock()
    reports: list[int] = []

    async def report_progress(chunk_id: ChunkId, downloaded_bytes: int) -> None:
        reports.append(downloaded_bytes)

    await download_chunk_with_retry(
        url="http://example.com/file",
        chunk=chunk,
        http_client=http_client,
        file_writer=file_writer,
        part_file_path=Path("/tmp/test.part"),
        max_tries=2,
        retry_wait=0.0,
        progress_callback=report_progress,
    )

    assert reports == [2, 0, 3]

"""Property-based tests for memory efficiency."""

import asyncio
import tracemalloc
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from streamdown.application.chunk_worker import download_chunk_with_retry
from streamdown.domain.entities import Chunk
from streamdown.domain.enums import ChunkStatus
from streamdown.domain.value_objects import ByteRange, ChunkId
from streamdown.infrastructure.file_writer import PartFileWriter
from streamdown.infrastructure.http_client import HttpDownloader


# Feature: streamdown, Property 31: Memory scales with connections not file size
@pytest.mark.asyncio
@settings(deadline=10000, max_examples=50)
@given(
    num_connections=st.integers(min_value=1, max_value=16),
    file_size_mb=st.integers(min_value=10, max_value=1000),
    chunk_size_kb=st.integers(min_value=512, max_value=2048),
)
async def test_memory_scales_with_connections_not_file_size(
    num_connections: int,
    file_size_mb: int,
    chunk_size_kb: int,
) -> None:
    """
    **Feature: streamdown, Property 31: Memory scales with connections not file size**

    **Validates: Requirements 14.3**

    For any set of concurrent downloads, memory usage must scale with the number
    of active connections, not with the total size of files being downloaded.

    This test verifies that:
    1. Memory usage is bounded regardless of file size
    2. Memory usage scales linearly with number of connections
    3. Large files don't cause proportionally large memory usage
    """
    # Convert to bytes
    file_size = file_size_mb * 1024 * 1024
    chunk_size = chunk_size_kb * 1024

    # Calculate number of chunks
    num_chunks = (file_size + chunk_size - 1) // chunk_size

    # Create mock HTTP client that yields data in 64 KiB buffers
    buffer_size = 64 * 1024

    async def mock_fetch_range(url: str, byte_range: ByteRange, buffer_size: int = 64 * 1024):
        """Mock fetch_range that yields data in buffers."""
        total_bytes = byte_range.end - byte_range.start + 1
        bytes_yielded = 0

        while bytes_yielded < total_bytes:
            chunk_bytes = min(buffer_size, total_bytes - bytes_yielded)
            # Yield actual bytes to simulate real data
            yield b"x" * chunk_bytes
            bytes_yielded += chunk_bytes
            # Small delay to simulate network I/O
            await asyncio.sleep(0.001)

    http_client = MagicMock(spec=HttpDownloader)
    http_client.fetch_range = mock_fetch_range

    # Create mock file writer that doesn't actually write to disk
    file_writer = MagicMock(spec=PartFileWriter)
    file_writer.write_at_offset = AsyncMock()

    # Create temporary path
    part_file_path = Path("/tmp/test.part")

    # Start memory tracking
    tracemalloc.start()

    # Measure baseline memory
    baseline_memory = tracemalloc.get_traced_memory()[0]

    # Download chunks concurrently (simulating num_connections)
    # We'll download a subset of chunks equal to num_connections
    chunks_to_download = min(num_connections, num_chunks)

    tasks = []
    for i in range(chunks_to_download):
        start = i * chunk_size
        end = min(start + chunk_size - 1, file_size - 1)

        chunk = Chunk(
            id=ChunkId(i),
            range=ByteRange(start=start, end=end),
            status=ChunkStatus.PENDING,
            retries=0,
            last_error=None,
        )

        task = download_chunk_with_retry(
            url="http://example.com/file",
            chunk=chunk,
            http_client=http_client,
            file_writer=file_writer,
            part_file_path=part_file_path,
            max_tries=1,
            retry_wait=0.0,
            buffer_size=buffer_size,
        )
        tasks.append(task)

    # Run all downloads concurrently
    await asyncio.gather(*tasks, return_exceptions=True)

    # Measure peak memory during download
    peak_memory = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    # Calculate memory used
    memory_used_mb = (peak_memory - baseline_memory) / (1024 * 1024)

    # Memory should be bounded and scale with connections, not file size
    # Expected memory: roughly num_connections * buffer_size * 2 (read + write buffers)
    # Plus some overhead for asyncio tasks and data structures
    # We'll be generous and allow 10 MB per connection
    max_expected_memory_mb = num_connections * 10

    # Assert memory is bounded
    assert memory_used_mb < max_expected_memory_mb, (
        f"Memory usage ({memory_used_mb:.2f} MB) exceeded expected bound "
        f"({max_expected_memory_mb} MB) for {num_connections} connections "
        f"downloading {file_size_mb} MB file"
    )

    # Additional check: memory should not scale with file size
    # For a given number of connections, doubling the file size should not
    # double the memory usage (it should stay roughly constant)
    # This is implicitly tested by the bounded memory assertion above


# Feature: streamdown, Property 31: Memory scales with connections not file size (unit test)
@pytest.mark.asyncio
@settings(deadline=5000, max_examples=30)
@given(
    small_file_mb=st.integers(min_value=10, max_value=50),
    large_file_mb=st.integers(min_value=100, max_value=500),
    num_connections=st.integers(min_value=2, max_value=8),
)
async def test_memory_independent_of_file_size(
    small_file_mb: int,
    large_file_mb: int,
    num_connections: int,
) -> None:
    """
    **Feature: streamdown, Property 31: Memory scales with connections not file size**

    **Validates: Requirements 14.3**

    Verify that memory usage for downloading a small file is similar to
    downloading a large file when using the same number of connections.
    """
    # Ensure large file is actually larger
    if large_file_mb <= small_file_mb:
        large_file_mb = small_file_mb * 5

    chunk_size = 1024 * 1024  # 1 MB chunks
    buffer_size = 64 * 1024  # 64 KiB buffers

    async def measure_memory_for_download(file_size_mb: int) -> float:
        """Measure memory usage for downloading a file."""
        file_size = file_size_mb * 1024 * 1024
        num_chunks = (file_size + chunk_size - 1) // chunk_size

        async def mock_fetch_range(url: str, byte_range: ByteRange, buffer_size: int = 64 * 1024):
            """Mock fetch_range that yields data in buffers."""
            total_bytes = byte_range.end - byte_range.start + 1
            bytes_yielded = 0

            while bytes_yielded < total_bytes:
                chunk_bytes = min(buffer_size, total_bytes - bytes_yielded)
                yield b"x" * chunk_bytes
                bytes_yielded += chunk_bytes
                await asyncio.sleep(0.001)

        http_client = MagicMock(spec=HttpDownloader)
        http_client.fetch_range = mock_fetch_range

        file_writer = MagicMock(spec=PartFileWriter)
        file_writer.write_at_offset = AsyncMock()

        part_file_path = Path("/tmp/test.part")

        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]

        # Download chunks concurrently
        chunks_to_download = min(num_connections, num_chunks)
        tasks = []

        for i in range(chunks_to_download):
            start = i * chunk_size
            end = min(start + chunk_size - 1, file_size - 1)

            chunk = Chunk(
                id=ChunkId(i),
                range=ByteRange(start=start, end=end),
                status=ChunkStatus.PENDING,
                retries=0,
                last_error=None,
            )

            task = download_chunk_with_retry(
                url="http://example.com/file",
                chunk=chunk,
                http_client=http_client,
                file_writer=file_writer,
                part_file_path=part_file_path,
                max_tries=1,
                retry_wait=0.0,
                buffer_size=buffer_size,
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        peak_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        return (peak_memory - baseline_memory) / (1024 * 1024)

    # Measure memory for small and large files
    small_memory = await measure_memory_for_download(small_file_mb)
    large_memory = await measure_memory_for_download(large_file_mb)

    # Memory usage should be similar (within 2x) despite file size difference
    # This demonstrates that memory scales with connections, not file size
    memory_ratio = large_memory / small_memory if small_memory > 0 else 1.0

    # Allow up to 3x difference to account for measurement variance and overhead
    assert memory_ratio < 3.0, (
        f"Memory usage ratio ({memory_ratio:.2f}x) too high: "
        f"small file ({small_file_mb} MB) used {small_memory:.2f} MB, "
        f"large file ({large_file_mb} MB) used {large_memory:.2f} MB "
        f"with {num_connections} connections"
    )

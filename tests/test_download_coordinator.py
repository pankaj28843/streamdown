"""Property-based tests for DownloadCoordinator."""

import asyncio
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from streamdown.application.download_coordinator import DownloadCoordinator
from streamdown.application.dtos import DownloadOptions
from streamdown.domain.enums import StreamingMode
from streamdown.domain.services import ChunkPlanner, ResumePolicy
from streamdown.infrastructure.file_writer import PartFileWriter
from streamdown.infrastructure.http_client import HeadResponse


def create_test_options(**overrides) -> DownloadOptions:
    """Create DownloadOptions with sensible test defaults."""
    defaults = {
        "directory": Path("/tmp/test"),
        "output_name": None,
        "splits": 4,
        "max_connections_per_host": 4,
        "piece_size": 1024 * 1024,
        "continue_download": True,
        "allow_overwrite": False,
        "auto_file_renaming": False,
        "max_concurrent_downloads": 4,
        "streaming_mode": StreamingMode.DEFAULT,
        "connect_timeout": 60.0,
        "read_timeout": 300.0,
        "max_tries": 3,
        "retry_wait": 0.0,
        "user_agent": "streamdown-test/0.1.0",
        "quiet": False,
        "log_level": "info",
        "insecure": False,
        "no_netrc": False,
        "netrc_path": None,
    }
    defaults.update(overrides)
    return DownloadOptions(**defaults)
from streamdown.infrastructure.metadata_repository import MetadataRepository


# Feature: streamdown, Property 3: Concurrent connection limit
@pytest.mark.asyncio
@settings(deadline=5000, max_examples=20)
@given(
    total_length=st.integers(min_value=100_000, max_value=1_000_000),
    piece_size=st.integers(min_value=50_000, max_value=100_000),
    splits=st.integers(min_value=2, max_value=8),
)
async def test_concurrent_connection_limit(total_length: int, piece_size: int, splits: int):
    """
    For any download with specified splits, the number of active concurrent
    connections must never exceed the splits value.

    This test verifies:
    1. At most 'splits' chunks are downloaded concurrently
    2. The semaphore correctly limits concurrent operations
    3. All chunks eventually complete

    **Validates: Requirements 1.3**
    """
    # Track maximum concurrent downloads
    max_concurrent_observed = 0
    current_concurrent = 0
    concurrent_lock = asyncio.Lock()

    # Create a custom HTTP client that tracks concurrency
    class TrackingHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def fetch_head(self, url):
            return HeadResponse(
                content_length=total_length,
                accept_ranges=True,
                etag="test-etag",
                last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
            )

        async def fetch_range(self, url, byte_range, buffer_size=64*1024):
            nonlocal max_concurrent_observed, current_concurrent

            async with concurrent_lock:
                current_concurrent += 1
                max_concurrent_observed = max(max_concurrent_observed, current_concurrent)

            try:
                # Simulate download time
                await asyncio.sleep(0.001)
                # Yield data
                yield b"x" * byte_range.size
            finally:
                async with concurrent_lock:
                    current_concurrent -= 1

    http_client = TrackingHttpClient()

    # Use temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock file writer
        file_writer = PartFileWriter()

        # Mock metadata repository
        metadata_repo = MetadataRepository()

        # Create coordinator
        options = create_test_options(
            directory=Path(tmpdir),
            output_name="test.bin",
            splits=splits,
            max_connections_per_host=splits,
            piece_size=piece_size,
            continue_download=False,
            allow_overwrite=True,
            max_tries=1,
            retry_wait=0.0,
        )

        coordinator = DownloadCoordinator(
            url="https://example.com/file.bin",
            options=options,
            http_client=http_client,
            file_writer=file_writer,
            metadata_repo=metadata_repo,
            chunk_planner=ChunkPlanner(StreamingMode.DEFAULT),
            resume_policy=ResumePolicy(),
        )

        # Run download
        await coordinator.download()

        # Verify concurrent connection limit was respected
        assert max_concurrent_observed <= splits, (
            f"Maximum concurrent connections ({max_concurrent_observed}) "
            f"exceeded splits limit ({splits})"
        )


# Feature: streamdown, Property 18: Per-host connection limit
@pytest.mark.asyncio
@settings(deadline=5000, max_examples=20)
@given(
    total_length=st.integers(min_value=100_000, max_value=1_000_000),
    piece_size=st.integers(min_value=50_000, max_value=100_000),
    splits=st.integers(min_value=4, max_value=16),
    max_connections_per_host=st.integers(min_value=1, max_value=8),
)
async def test_per_host_connection_limit(
    total_length: int,
    piece_size: int,
    splits: int,
    max_connections_per_host: int,
):
    """
    For any download with max-connections-per-host specified, concurrent
    connections to each host must not exceed that value.

    This test verifies:
    1. The effective limit is min(splits, max_connections_per_host)
    2. Concurrent connections never exceed max_connections_per_host
    3. The coordinator respects the per-host limit

    **Validates: Requirements 8.1**
    """
    # Track maximum concurrent downloads
    max_concurrent_observed = 0
    current_concurrent = 0
    concurrent_lock = asyncio.Lock()

    class TrackingHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def fetch_head(self, url):
            return HeadResponse(
                content_length=total_length,
                accept_ranges=True,
                etag="test-etag",
                last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
            )

        async def fetch_range(self, url, byte_range, buffer_size=64*1024):
            nonlocal max_concurrent_observed, current_concurrent

            async with concurrent_lock:
                current_concurrent += 1
                max_concurrent_observed = max(max_concurrent_observed, current_concurrent)

            try:
                await asyncio.sleep(0.001)
                yield b"x" * byte_range.size
            finally:
                async with concurrent_lock:
                    current_concurrent -= 1

    http_client = TrackingHttpClient()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_writer = PartFileWriter()
        metadata_repo = MetadataRepository()

        options = create_test_options(
            directory=Path(tmpdir),
            output_name="test.bin",
            splits=splits,
            max_connections_per_host=max_connections_per_host,
            piece_size=piece_size,
            continue_download=False,
            allow_overwrite=True,
            max_tries=1,
            retry_wait=0.0,
        )

        coordinator = DownloadCoordinator(
            url="https://example.com/file.bin",
            options=options,
            http_client=http_client,
            file_writer=file_writer,
            metadata_repo=metadata_repo,
            chunk_planner=ChunkPlanner(StreamingMode.DEFAULT),
            resume_policy=ResumePolicy(),
        )

        await coordinator.download()

        # The effective limit should be min(splits, max_connections_per_host)
        effective_limit = min(splits, max_connections_per_host)

        # Verify concurrent connection limit was respected
        assert max_concurrent_observed <= effective_limit, (
            f"Maximum concurrent connections ({max_concurrent_observed}) "
            f"exceeded effective limit ({effective_limit})"
        )

        # Specifically verify per-host limit
        assert max_concurrent_observed <= max_connections_per_host, (
            f"Maximum concurrent connections ({max_concurrent_observed}) "
            f"exceeded per-host limit ({max_connections_per_host})"
        )


# Feature: streamdown, Property 4: Successful completion renames part file
@pytest.mark.asyncio
@settings(deadline=5000, max_examples=20)
@given(
    total_length=st.integers(min_value=50_000, max_value=500_000),
    piece_size=st.integers(min_value=50_000, max_value=100_000),
)
async def test_part_file_rename_on_success(total_length: int, piece_size: int):
    """
    For any download where all chunks complete successfully, the part file
    must be renamed to the final target filename.

    This test verifies:
    1. The part file is renamed to the target file
    2. Metadata file is deleted after successful completion
    3. Download completes successfully

    **Validates: Requirements 1.4**
    """
    class SimpleHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def fetch_head(self, url):
            return HeadResponse(
                content_length=total_length,
                accept_ranges=True,
                etag="test-etag",
                last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
            )

        async def fetch_range(self, url, byte_range, buffer_size=64*1024):
            yield b"x" * byte_range.size

    http_client = SimpleHttpClient()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_writer = PartFileWriter()
        metadata_repo = MetadataRepository()

        options = create_test_options(
            directory=Path(tmpdir),
            output_name="test.bin",
            splits=2,
            max_connections_per_host=2,
            piece_size=piece_size,
            continue_download=False,
            allow_overwrite=True,
            max_tries=1,
            retry_wait=0.0,
        )

        coordinator = DownloadCoordinator(
            url="https://example.com/file.bin",
            options=options,
            http_client=http_client,
            file_writer=file_writer,
            metadata_repo=metadata_repo,
            chunk_planner=ChunkPlanner(StreamingMode.DEFAULT),
            resume_policy=ResumePolicy(),
        )

        result = await coordinator.download()

        # Verify result indicates success
        from streamdown.domain.enums import DownloadStatus
        assert result.status == DownloadStatus.COMPLETED, (
            f"Expected COMPLETED status, got {result.status}"
        )
        assert result.final_path is not None, "Expected final_path to be set"
        assert result.error is None, f"Expected no error, got: {result.error}"

        # Verify final file exists
        assert result.final_path.exists(), "Final file should exist"

        # Verify part file does not exist
        part_path = Path(tmpdir) / "test.bin.part"
        assert not part_path.exists(), "Part file should be removed"

        # Verify metadata file does not exist
        meta_path = Path(tmpdir) / "test.bin.part.meta.json"
        assert not meta_path.exists(), "Metadata file should be removed"


# Feature: streamdown, Property 7: Fresh start with continue disabled
@pytest.mark.asyncio
@settings(deadline=5000, max_examples=20)
@given(
    total_length=st.integers(min_value=50_000, max_value=500_000),
    piece_size=st.integers(min_value=50_000, max_value=100_000),
)
async def test_fresh_start_with_continue_disabled(total_length: int, piece_size: int):
    """
    For any download with continue disabled, existing part files must be
    overwritten and all chunks downloaded from scratch.

    This test verifies:
    1. Existing part files are deleted when continue is disabled
    2. All chunks are downloaded fresh
    3. Download completes successfully

    **Validates: Requirements 2.5**
    """
    class SimpleHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def fetch_head(self, url):
            return HeadResponse(
                content_length=total_length,
                accept_ranges=True,
                etag="test-etag",
                last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
            )

        async def fetch_range(self, url, byte_range, buffer_size=64*1024):
            yield b"x" * byte_range.size

    http_client = SimpleHttpClient()

    with tempfile.TemporaryDirectory() as tmpdir:
        file_writer = PartFileWriter()
        metadata_repo = MetadataRepository()

        # Create an existing part file to simulate interrupted download
        part_path = Path(tmpdir) / "test.bin.part"
        part_path.write_bytes(b"old data")
        assert part_path.exists(), "Part file should exist before test"

        # Create coordinator with continue_download=False
        options = create_test_options(
            directory=Path(tmpdir),
            output_name="test.bin",
            splits=2,
            max_connections_per_host=2,
            piece_size=piece_size,
            continue_download=False,  # Key: continue disabled
            allow_overwrite=True,
            max_tries=1,
            retry_wait=0.0,
        )

        coordinator = DownloadCoordinator(
            url="https://example.com/file.bin",
            options=options,
            http_client=http_client,
            file_writer=file_writer,
            metadata_repo=metadata_repo,
            chunk_planner=ChunkPlanner(StreamingMode.DEFAULT),
            resume_policy=ResumePolicy(),
        )

        result = await coordinator.download()

        # The download should complete successfully
        from streamdown.domain.enums import DownloadStatus
        assert result.status == DownloadStatus.COMPLETED, (
            f"Expected COMPLETED status, got {result.status}"
        )

        # Verify final file exists
        final_path = Path(tmpdir) / "test.bin"
        assert final_path.exists(), "Final file should exist"

        # Verify the file was downloaded fresh (not old data)
        file_content = final_path.read_bytes()
        assert file_content != b"old data", "File should contain new data, not old data"

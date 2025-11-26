"""Property-based tests for application use cases."""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from streamdown.application.dtos import DownloadOptions
from streamdown.application.use_cases import _generate_unique_filename, _prepare_download_path
from streamdown.domain.enums import DownloadStatus, StreamingMode


# Feature: streamdown, Property 11: Overwrite with flag enabled
@settings(deadline=1000)
@given(
    filename=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_.",
        ),
        min_size=1,
        max_size=50,
    ).filter(lambda x: x not in (".", "..")),
    file_content=st.binary(min_size=0, max_size=1000),
)
@pytest.mark.asyncio
async def test_overwrite_with_flag_enabled(filename: str, file_content: bytes):
    """
    For any download with allow-overwrite enabled, an existing complete file
    at the target path must be replaced by the new download.

    This test verifies:
    1. When allow_overwrite is True, existing files don't cause errors
    2. The download can proceed even when target file exists
    3. No error is returned from path preparation
    4. Auto-renaming is not triggered when allow_overwrite is True

    **Validates: Requirements 4.2**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Create an existing file
        existing_file = target_dir / filename
        existing_file.write_bytes(file_content)

        assert existing_file.exists(), "Test file should exist"

        # Create options with allow_overwrite enabled
        options = DownloadOptions(
            directory=target_dir,
            output_name=filename,
            splits=8,
            max_connections_per_host=8,
            piece_size=1024 * 1024,
            continue_download=True,
            allow_overwrite=True,  # Key flag
            auto_file_renaming=False,
            max_concurrent_downloads=4,
            streaming_mode=StreamingMode.DEFAULT,
            connect_timeout=60.0,
            read_timeout=300.0,
            max_tries=5,
            retry_wait=0.0,
            user_agent="streamdown/test",
            quiet=False,
            log_level="info",
            insecure=False,
            no_netrc=False,
            netrc_path=None,
        )

        # Prepare download path
        result = await _prepare_download_path("https://example.com/file", options)

        # Should return None (no error) - download can proceed
        assert result is None, (
            f"Expected None (download can proceed), but got error result: {result}"
        )

        # Verify the original filename is still used (not renamed)
        assert options.output_name == filename, (
            f"Filename should not be changed when allow_overwrite is True. "
            f"Expected {filename}, got {options.output_name}"
        )


# Feature: streamdown, Property 11: Overwrite with flag enabled (without auto-rename)
@settings(deadline=1000)
@given(
    filename=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_.",
        ),
        min_size=1,
        max_size=50,
    ).filter(lambda x: x not in (".", "..")),
)
@pytest.mark.asyncio
async def test_overwrite_flag_takes_precedence_over_auto_rename(filename: str):
    """
    For any download with both allow-overwrite and auto-file-renaming enabled,
    auto-renaming should take precedence to avoid data loss.

    This test verifies:
    1. When both flags are set, auto-renaming is used
    2. Original file is preserved
    3. New unique filename is generated

    **Validates: Requirements 4.2, 4.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Create an existing file
        existing_file = target_dir / filename
        existing_file.write_bytes(b"original content")

        # Create options with both flags enabled
        options = DownloadOptions(
            directory=target_dir,
            output_name=filename,
            splits=8,
            max_connections_per_host=8,
            piece_size=1024 * 1024,
            continue_download=True,
            allow_overwrite=True,
            auto_file_renaming=True,  # Both flags enabled
            max_concurrent_downloads=4,
            streaming_mode=StreamingMode.DEFAULT,
            connect_timeout=60.0,
            read_timeout=300.0,
            max_tries=5,
            retry_wait=0.0,
            user_agent="streamdown/test",
            quiet=False,
            log_level="info",
            insecure=False,
            no_netrc=False,
            netrc_path=None,
        )

        # Prepare download path
        result = await _prepare_download_path("https://example.com/file", options)

        # Should return None (download can proceed)
        assert result is None, "Download should be able to proceed"

        # Verify filename was changed (auto-rename took precedence)
        assert options.output_name != filename, (
            f"Filename should be changed when both flags are set. "
            f"Expected different from {filename}, got {options.output_name}"
        )


# Feature: streamdown, Property 11: Error without overwrite flag
@settings(deadline=1000)
@given(
    filename=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_.",
        ),
        min_size=1,
        max_size=50,
    ).filter(lambda x: x not in (".", "..")),
)
@pytest.mark.asyncio
async def test_error_when_file_exists_without_overwrite_flag(filename: str):
    """
    For any download where a file exists and allow-overwrite is disabled,
    an error must be returned.

    This test verifies:
    1. When allow_overwrite is False and file exists, error is returned
    2. Error status is FAILED
    3. Error message indicates file already exists

    **Validates: Requirements 4.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Create an existing file
        existing_file = target_dir / filename
        existing_file.write_bytes(b"existing content")

        # Create options with allow_overwrite disabled
        options = DownloadOptions(
            directory=target_dir,
            output_name=filename,
            splits=8,
            max_connections_per_host=8,
            piece_size=1024 * 1024,
            continue_download=True,
            allow_overwrite=False,  # Overwrite disabled
            auto_file_renaming=False,  # Auto-rename also disabled
            max_concurrent_downloads=4,
            streaming_mode=StreamingMode.DEFAULT,
            connect_timeout=60.0,
            read_timeout=300.0,
            max_tries=5,
            retry_wait=0.0,
            user_agent="streamdown/test",
            quiet=False,
            log_level="info",
            insecure=False,
            no_netrc=False,
            netrc_path=None,
        )

        # Prepare download path
        result = await _prepare_download_path("https://example.com/file", options)

        # Should return error result
        assert result is not None, "Should return error when file exists and overwrite disabled"
        assert result.status == DownloadStatus.FAILED, (
            f"Status should be FAILED, got {result.status}"
        )
        assert "already exists" in result.error.lower(), (
            f"Error message should mention file exists, got: {result.error}"
        )


# Feature: streamdown, Property 12: Auto-renaming generates unique filename
@settings(deadline=1000)
@given(
    filename=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_.",
        ),
        min_size=1,
        max_size=50,
    ).filter(lambda x: x not in (".", "..")),
    num_existing=st.integers(min_value=0, max_value=10),
)
@pytest.mark.asyncio
async def test_auto_renaming_generates_unique_filename(filename: str, num_existing: int):
    """
    For any download with auto-file-renaming enabled where the target file exists,
    the system must generate a unique filename by appending a numeric suffix.

    This test verifies:
    1. Auto-renaming generates a unique filename
    2. The new filename doesn't conflict with existing files
    3. Numeric suffix is appended correctly
    4. Works with multiple existing files (file.1, file.2, etc.)

    **Validates: Requirements 4.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Create existing files with numeric suffixes
        base_file = target_dir / filename
        base_file.write_bytes(b"original")

        # Create additional numbered files
        for i in range(1, num_existing + 1):
            # Split filename into stem and suffix
            stem = base_file.stem
            suffix = base_file.suffix
            numbered_file = target_dir / f"{stem}.{i}{suffix}"
            numbered_file.write_bytes(b"existing")

        # Create options with auto-file-renaming enabled
        options = DownloadOptions(
            directory=target_dir,
            output_name=filename,
            splits=8,
            max_connections_per_host=8,
            piece_size=1024 * 1024,
            continue_download=True,
            allow_overwrite=False,
            auto_file_renaming=True,  # Auto-rename enabled
            max_concurrent_downloads=4,
            streaming_mode=StreamingMode.DEFAULT,
            connect_timeout=60.0,
            read_timeout=300.0,
            max_tries=5,
            retry_wait=0.0,
            user_agent="streamdown/test",
            quiet=False,
            log_level="info",
            insecure=False,
            no_netrc=False,
            netrc_path=None,
        )

        # Prepare download path
        result = await _prepare_download_path("https://example.com/file", options)

        # Should return None (download can proceed)
        assert result is None, "Download should be able to proceed with auto-rename"

        # Verify filename was changed
        assert options.output_name != filename, (
            f"Filename should be changed with auto-rename. "
            f"Expected different from {filename}, got {options.output_name}"
        )

        # Verify the new filename doesn't exist yet
        new_path = target_dir / options.output_name
        assert not new_path.exists(), (
            f"New filename should not exist yet: {new_path}"
        )

        # Verify the new filename follows the pattern (has numeric suffix)
        # Extract the number from the filename
        stem = base_file.stem
        suffix = base_file.suffix
        expected_number = num_existing + 1
        expected_name = f"{stem}.{expected_number}{suffix}"

        assert options.output_name == expected_name, (
            f"Expected filename {expected_name}, got {options.output_name}"
        )


# Feature: streamdown, Property 12: Unique filename generation (unit test)
@settings(deadline=1000)
@given(
    filename=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_.",
        ),
        min_size=1,
        max_size=50,
    ).filter(lambda x: x not in (".", "..")),
    num_conflicts=st.integers(min_value=0, max_value=20),
)
def test_generate_unique_filename(filename: str, num_conflicts: int):
    """
    For any filename and number of existing conflicts, _generate_unique_filename
    must produce a filename that doesn't exist.

    This test verifies:
    1. Function generates unique filenames
    2. Handles multiple existing numbered files
    3. Returns correct numeric suffix
    4. Works with various filename patterns

    **Validates: Requirements 4.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Create base file
        base_path = target_dir / filename
        base_path.write_bytes(b"base")

        # Create numbered conflicts
        stem = base_path.stem
        suffix = base_path.suffix

        for i in range(1, num_conflicts + 1):
            conflict_path = target_dir / f"{stem}.{i}{suffix}"
            conflict_path.write_bytes(b"conflict")

        # Generate unique filename
        unique_path = _generate_unique_filename(base_path)

        # Verify it doesn't exist
        assert not unique_path.exists(), (
            f"Generated path should not exist: {unique_path}"
        )

        # Verify it's in the same directory
        assert unique_path.parent == target_dir, (
            "Generated path should be in same directory"
        )

        # Verify it has the expected numeric suffix
        expected_number = num_conflicts + 1
        expected_name = f"{stem}.{expected_number}{suffix}"

        assert unique_path.name == expected_name, (
            f"Expected {expected_name}, got {unique_path.name}"
        )


# Feature: streamdown, Property 12: Unique filename when no conflict
def test_generate_unique_filename_no_conflict():
    """
    For any filename that doesn't exist, _generate_unique_filename should
    return the original path unchanged.

    **Validates: Requirements 4.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Create a path that doesn't exist
        non_existent = target_dir / "nonexistent.txt"

        # Generate unique filename
        result = _generate_unique_filename(non_existent)

        # Should return the same path
        assert result == non_existent, (
            f"Should return original path when it doesn't exist. "
            f"Expected {non_existent}, got {result}"
        )

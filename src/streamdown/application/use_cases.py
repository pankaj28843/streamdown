"""Application layer use cases for download operations."""

from pathlib import Path
from typing import TYPE_CHECKING

from streamdown.application.download_manager import DownloadManager
from streamdown.application.dtos import DownloadOptions, DownloadResult
from streamdown.domain.enums import DownloadStatus

if TYPE_CHECKING:
    from streamdown.cli.progress_display import ProgressDisplay


async def start_download(
    urls: list[str],
    options: DownloadOptions,
    progress_display: "ProgressDisplay | None" = None,
) -> list[DownloadResult]:
    """
    Orchestrate multiple downloads with bounded concurrency.

    This use case coordinates the entire download process:
    1. Validates and prepares file paths
    2. Handles file overwrite logic (allow-overwrite, auto-file-renaming)
    3. Creates download manager
    4. Executes downloads with concurrency control
    5. Returns results for each URL

    Args:
        urls: List of URLs to download
        options: Download configuration options
        progress_display: Optional progress display for UI updates

    Returns:
        List of DownloadResult, one per URL in the same order

    Requirements: 4.1, 4.2, 4.3, 11.2
    """
    if not urls:
        return []

    # Handle file path preparation for each URL
    prepared_results: list[DownloadResult | None] = []
    prepared_urls: list[str] = []

    for url in urls:
        # Check if we need to handle file conflicts
        result = await _prepare_download_path(url, options)

        if result is not None:
            # File conflict detected and couldn't be resolved
            prepared_results.append(result)
        else:
            # Path is ready for download
            prepared_results.append(None)
            prepared_urls.append(url)

    # Download all prepared URLs
    download_results: list[DownloadResult] = []
    if prepared_urls:
        manager = DownloadManager(
            options=options,
            max_concurrent_downloads=options.max_concurrent_downloads,
            streaming_mode=options.streaming_mode,
            progress_display=progress_display,
        )
        download_results = await manager.download_all(prepared_urls)

    # Merge results - replace None entries with actual download results
    final_results: list[DownloadResult] = []
    download_idx = 0

    for prepared_result in prepared_results:
        if prepared_result is not None:
            # This was a file conflict that was handled early
            final_results.append(prepared_result)
        else:
            # This was downloaded
            final_results.append(download_results[download_idx])
            download_idx += 1

    return final_results


async def resume_or_start(
    url: str,
    options: DownloadOptions,
    progress_display: "ProgressDisplay | None" = None,
) -> DownloadResult:
    """
    Attempt to resume a download if metadata exists and is compatible,
    otherwise start a fresh download.

    This use case:
    1. Checks for existing metadata file
    2. If metadata exists and continue is enabled, attempts resume
    3. If resume fails or continue is disabled, starts fresh
    4. Handles file overwrite logic

    Args:
        url: URL to download
        options: Download configuration options
        progress_display: Optional progress display for UI updates

    Returns:
        DownloadResult with status and metadata

    Requirements: 4.1, 4.2, 4.3, 11.2
    """
    # Prepare download path (handles overwrite logic)
    result = await _prepare_download_path(url, options)

    if result is not None:
        # File conflict that couldn't be resolved
        return result

    # Execute download (coordinator will handle resume logic internally)
    results = await start_download([url], options, progress_display)
    return results[0]


async def _prepare_download_path(
    url: str,
    options: DownloadOptions,
) -> DownloadResult | None:
    """
    Prepare download path and handle file conflicts.

    This function implements the file overwrite logic:
    - Requirement 4.1: Error if file exists and allow-overwrite is disabled
    - Requirement 4.2: Replace file if allow-overwrite is enabled
    - Requirement 4.3: Auto-rename if auto-file-renaming is enabled

    Args:
        url: URL being downloaded
        options: Download configuration options

    Returns:
        DownloadResult with error if file conflict couldn't be resolved,
        None if path is ready for download
    """
    # Determine output filename
    if options.output_name:
        filename = options.output_name
    else:
        # Extract filename from URL
        from urllib.parse import unquote, urlparse

        parsed = urlparse(url)
        filename = unquote(parsed.path.split("/")[-1])
        if not filename:
            filename = "download"

    # Build target path
    target_path = options.directory / filename

    # Check if file already exists
    if target_path.exists():
        # Requirement 4.2: Allow overwrite if flag is enabled
        if options.allow_overwrite:
            # File will be overwritten - this is handled by the coordinator
            # Just ensure we're not in auto-rename mode
            if options.auto_file_renaming:
                # Both flags set - auto-rename takes precedence
                new_path = _generate_unique_filename(target_path)
                # Update options with new filename
                options.output_name = new_path.name
            # Otherwise, allow overwrite to proceed
            return None

        # Requirement 4.3: Auto-rename if enabled
        if options.auto_file_renaming:
            new_path = _generate_unique_filename(target_path)
            # Update options with new filename
            options.output_name = new_path.name
            return None

        # Requirement 4.1: Error if file exists and no overwrite/rename flags
        return DownloadResult(
            url=url,
            status=DownloadStatus.FAILED,
            final_path=None,
            error=f"File already exists: {target_path}",
            bytes_downloaded=0,
            duration=0.0,
        )

    # Path doesn't exist - ready for download
    return None


def _generate_unique_filename(path: Path) -> Path:
    """
    Generate a unique filename by appending numeric suffix.

    If file.txt exists, tries file.1.txt, file.2.txt, etc.

    Args:
        path: Original file path

    Returns:
        Unique file path that doesn't exist

    Requirement 4.3: Auto-renaming generates unique filename
    """
    if not path.exists():
        return path

    # Split filename and extension
    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    # Try incrementing numbers until we find one that doesn't exist
    counter = 1
    while True:
        new_name = f"{stem}.{counter}{suffix}"
        new_path = parent / new_name

        if not new_path.exists():
            return new_path

        counter += 1

        # Safety check to prevent infinite loop
        if counter > 10000:
            raise RuntimeError(f"Could not generate unique filename for {path}")

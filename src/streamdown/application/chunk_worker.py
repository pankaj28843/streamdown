"""Chunk download worker with retry logic."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from streamdown.domain.entities import Chunk
from streamdown.domain.exceptions import HttpError, NetworkError
from streamdown.domain.value_objects import ChunkId
from streamdown.infrastructure.file_writer import PartFileWriter
from streamdown.infrastructure.http_client import HttpDownloader

logger = logging.getLogger("streamdown.chunk_worker")


async def download_chunk_with_retry(
    url: str,
    chunk: Chunk,
    http_client: HttpDownloader,
    file_writer: PartFileWriter,
    part_file_path: Path,
    max_tries: int = 5,
    retry_wait: float = 0.0,
    buffer_size: int = 64 * 1024,  # 64 KiB
    progress_callback: Callable[[ChunkId, int], Awaitable[None]] | None = None,
) -> None:
    """
    Download a single chunk with retry logic.

    This function implements the retry strategy for downloading individual chunks.
    It streams data in fixed-size buffers (64 KiB) and writes to disk incrementally
    to maintain bounded memory usage.

    Args:
        url: URL to download from
        chunk: Chunk entity containing range and metadata
        http_client: HTTP client for fetching data
        file_writer: File writer for persisting data
        part_file_path: Path to the .part file
        max_tries: Maximum number of retry attempts (default 5)
        retry_wait: Delay in seconds between retry attempts (default 0.0)
        buffer_size: Size of read buffers in bytes (default 64 KiB)
        progress_callback: Optional async callback receiving chunk ID and bytes
            streamed for the current attempt.

    Raises:
        NetworkError: If all retry attempts fail with network errors
        HttpError: If all retry attempts fail with HTTP errors
        FileSystemError: If disk write fails (non-retryable)

    Requirements:
        - 8.4: Retry failed chunks up to max_tries
        - 8.5: Wait retry_wait duration between attempts
        - 9.1: Retry network errors up to max_tries
        - 9.2: Mark download failed after max_tries exhausted
        - 14.1: Stream data in fixed 64 KiB buffers
        - 14.5: Write to disk promptly and release buffers
    """
    last_error: Exception | None = None

    async def report_progress(downloaded_bytes: int) -> None:
        if progress_callback is not None:
            await progress_callback(chunk.id, downloaded_bytes)

    for attempt in range(max_tries):
        try:
            # Stream the chunk data and write incrementally
            offset = chunk.range.start

            logger.debug(
                f"Downloading chunk {chunk.id} (attempt {attempt + 1}/{max_tries}): bytes {chunk.range.start}-{chunk.range.end}"
            )

            async for data in http_client.fetch_range(
                url=url,
                byte_range=chunk.range,
                buffer_size=buffer_size,
            ):
                # Write data at current offset
                await file_writer.write_at_offset(
                    path=part_file_path,
                    offset=offset,
                    data=data,
                )
                # Update offset for next buffer
                offset += len(data)
                await report_progress(offset - chunk.range.start)

            # Success - chunk downloaded completely
            logger.debug(f"Chunk {chunk.id} completed successfully")
            return

        except NetworkError as e:
            # Network errors are always retryable
            last_error = e
            logger.warning(
                f"Chunk {chunk.id} failed with network error (attempt {attempt + 1}/{max_tries}): {e}"
            )
            await report_progress(0)
            if attempt < max_tries - 1:
                # Wait before retrying (if retry_wait > 0)
                if retry_wait > 0:
                    await asyncio.sleep(retry_wait)
                continue
            # Max tries exhausted, will raise below

        except HttpError as e:
            # HTTP errors may or may not be retryable
            last_error = e
            logger.warning(
                f"Chunk {chunk.id} failed with HTTP error (attempt {attempt + 1}/{max_tries}): {e}"
            )
            await report_progress(0)
            if e.is_retryable() and attempt < max_tries - 1:
                # Wait before retrying (if retry_wait > 0)
                if retry_wait > 0:
                    await asyncio.sleep(retry_wait)
                continue
            # Either non-retryable or max tries exhausted, will raise below

        # Note: FileSystemError is not caught - it propagates immediately
        # as it's a fatal error that shouldn't be retried

    # If we get here, all retries failed
    if last_error:
        logger.error(f"Chunk {chunk.id} failed after {max_tries} attempts: {last_error}")
        raise last_error
    else:
        # This shouldn't happen, but handle it gracefully
        logger.error(f"Chunk {chunk.id} failed after {max_tries} attempts with unknown error")
        raise RuntimeError(f"Chunk download failed after {max_tries} attempts")

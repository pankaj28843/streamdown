"""File writer adapter for writing downloaded chunks to disk."""

from pathlib import Path

import aiofiles


class PartFileWriter:
    """
    Handles writing downloaded chunks to part files with proper offset management.

    Uses aiofiles for async I/O with buffering to ensure efficient disk writes
    while maintaining bounded memory usage.
    """

    def __init__(self, buffer_size: int = 256 * 1024):
        """
        Initialize file writer.

        Args:
            buffer_size: Size of write buffers (default 256 KiB)
        """
        self._buffer_size = buffer_size

    async def write_at_offset(
        self,
        path: Path,
        offset: int,
        data: bytes,
    ) -> None:
        """
        Write data to file at specified offset.

        Creates parent directories if they don't exist. Opens file in binary
        read-write mode, seeks to offset, and writes data.

        Args:
            path: Path to file to write to
            offset: Byte offset to write at
            data: Data to write

        Raises:
            OSError: If file operations fail
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure file exists - create empty file if needed
        if not path.exists():
            path.touch()

        # Open file in binary read-write mode
        # Use buffering for efficient I/O
        async with aiofiles.open(
            path,
            mode="r+b",
            buffering=self._buffer_size,
        ) as f:
            await f.seek(offset)
            await f.write(data)
            # Flush to ensure data is written
            await f.flush()

    async def finalize(self, part_path: Path, final_path: Path) -> None:
        """
        Finalize download by renaming part file to final filename.

        This is an atomic operation on POSIX systems. If the final path
        already exists, it will be overwritten.

        Args:
            part_path: Path to .part file
            final_path: Final target path

        Raises:
            OSError: If rename operation fails
        """
        # Ensure parent directory of final path exists
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Rename is atomic on POSIX systems
        part_path.rename(final_path)

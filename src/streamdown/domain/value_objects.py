"""Domain value objects with validation."""

from dataclasses import dataclass
from pathlib import Path
from typing import NewType
from urllib.parse import urlparse
from uuid import UUID, uuid4

# Simple type aliases for identifiers
DownloadId = NewType("DownloadId", UUID)
ChunkId = NewType("ChunkId", int)


def new_download_id() -> DownloadId:
    """Generate a new unique download ID."""
    return DownloadId(uuid4())


@dataclass(frozen=True)
class Url:
    """Validated HTTP(S) URL value object."""

    value: str

    def __post_init__(self) -> None:
        """Validate URL on construction."""
        if not self.value:
            raise ValueError("URL cannot be empty")

        parsed = urlparse(self.value)

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL must use http or https scheme, got: {parsed.scheme}")

        if not parsed.netloc:
            raise ValueError("URL must have a valid host")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class FilePath:
    """Validated filesystem path value object."""

    value: Path

    def __post_init__(self) -> None:
        """Validate path on construction."""
        # Convert to Path if string was provided
        if isinstance(self.value, str):
            object.__setattr__(self, "value", Path(self.value))

        # Basic validation - path should not be empty
        path_str = str(self.value)
        if not path_str or path_str == ".":
            raise ValueError("File path cannot be empty")

    @classmethod
    def from_str(cls, path_str: str) -> "FilePath":
        """Create FilePath from string."""
        return cls(Path(path_str))

    def __str__(self) -> str:
        return str(self.value)

    def exists(self) -> bool:
        """Check if path exists."""
        return self.value.exists()

    def parent(self) -> "FilePath":
        """Get parent directory."""
        return FilePath(self.value.parent)

    def with_suffix(self, suffix: str) -> "FilePath":
        """Create new FilePath with different suffix."""
        return FilePath(self.value.with_suffix(suffix))

    def with_name(self, name: str) -> "FilePath":
        """Create new FilePath with different name."""
        return FilePath(self.value.with_name(name))


@dataclass(frozen=True)
class ByteRange:
    """Byte range for HTTP range requests."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Validate byte range on construction."""
        if self.start < 0:
            raise ValueError(f"Start byte must be non-negative, got: {self.start}")

        if self.end < 0:
            raise ValueError(f"End byte must be non-negative, got: {self.end}")

        if self.start > self.end:
            raise ValueError(
                f"Start byte ({self.start}) must be less than or equal to end byte ({self.end})"
            )

    @property
    def size(self) -> int:
        """Calculate the size of this byte range (inclusive)."""
        return self.end - self.start + 1

    def to_header_value(self) -> str:
        """Convert to HTTP Range header value."""
        return f"bytes={self.start}-{self.end}"

    def __str__(self) -> str:
        return f"[{self.start}-{self.end}]"

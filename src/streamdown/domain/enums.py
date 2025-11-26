"""Domain enums for status and mode tracking."""

from enum import Enum, auto


class DownloadStatus(Enum):
    """Status of a download job."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

    def is_terminal(self) -> bool:
        """Check if this is a terminal status (no further transitions)."""
        return self in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)

    def is_active(self) -> bool:
        """Check if download is actively running."""
        return self == DownloadStatus.RUNNING


class ChunkStatus(Enum):
    """Status of an individual chunk."""

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()

    def is_terminal(self) -> bool:
        """Check if this is a terminal status."""
        return self in (ChunkStatus.COMPLETED, ChunkStatus.FAILED)

    def is_active(self) -> bool:
        """Check if chunk is actively downloading."""
        return self == ChunkStatus.IN_PROGRESS


class StreamingMode(Enum):
    """Chunk selection strategy for downloads."""

    DEFAULT = auto()  # Round-robin chunk selection
    INORDER = auto()  # Sequential from beginning (sliding window)
    GEOM = auto()     # Geometric spacing (dense at start, exponential gaps)

    @classmethod
    def from_string(cls, mode_str: str) -> "StreamingMode":
        """Parse streaming mode from string."""
        mode_str = mode_str.upper()
        try:
            return cls[mode_str]
        except KeyError as e:
            valid_modes = ", ".join(m.name.lower() for m in cls)
            raise ValueError(
                f"Invalid streaming mode: {mode_str}. Valid modes: {valid_modes}"
            ) from e


class ResumeDecision(Enum):
    """Decision result from resume policy validation."""

    CAN_RESUME = auto()    # Metadata is compatible, can resume
    MUST_RESTART = auto()  # Metadata incompatible, must restart
    ERROR = auto()         # Error occurred during validation

    def should_resume(self) -> bool:
        """Check if download should resume."""
        return self == ResumeDecision.CAN_RESUME

    def should_restart(self) -> bool:
        """Check if download should restart from scratch."""
        return self == ResumeDecision.MUST_RESTART

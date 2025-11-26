"""Domain services for download management."""

import math
from dataclasses import dataclass

from streamdown.domain.entities import Chunk
from streamdown.domain.enums import ChunkStatus, ResumeDecision, StreamingMode
from streamdown.domain.value_objects import ByteRange, ChunkId, Url


class ChunkPlanner:
    """
    Domain service for planning and selecting chunks based on streaming strategy.

    Supports three strategies:
    - DEFAULT: Round-robin chunk selection to minimize connection churn
    - INORDER: Sequential from beginning (sliding window) for video streaming
    - GEOM: Geometric spacing (dense at start, exponential gaps) for preview
    """

    def __init__(self, mode: StreamingMode):
        """Initialize chunk planner with specified streaming mode."""
        self.mode = mode

    def plan_chunks(
        self,
        total_length: int,
        piece_size: int,
        num_splits: int
    ) -> list[Chunk]:
        """
        Calculate chunk byte ranges for a file.

        Args:
            total_length: Total file size in bytes
            piece_size: Size of each chunk in bytes
            num_splits: Number of parallel connections (not used for planning, only for selection)

        Returns:
            List of Chunk objects with calculated byte ranges

        The number of chunks is ceil(total_length / piece_size).
        Each chunk covers a contiguous, non-overlapping byte range.
        The last chunk may be smaller than piece_size.
        """
        if total_length <= 0:
            raise ValueError(f"Total length must be positive, got: {total_length}")

        if piece_size <= 0:
            raise ValueError(f"Piece size must be positive, got: {piece_size}")

        chunks = []
        num_chunks = math.ceil(total_length / piece_size)

        for i in range(num_chunks):
            start = i * piece_size
            # End is inclusive, so subtract 1. Also ensure we don't exceed total_length
            end = min(start + piece_size - 1, total_length - 1)

            chunk = Chunk(
                id=ChunkId(i),
                range=ByteRange(start=start, end=end),
                status=ChunkStatus.PENDING,
                retries=0,
                last_error=None,
            )
            chunks.append(chunk)

        return chunks

    def select_next_chunk(
        self,
        chunks: dict[ChunkId, Chunk],
        in_flight: set[ChunkId]
    ) -> ChunkId | None:
        """
        Select the next chunk to download based on the streaming strategy.

        Args:
            chunks: Dictionary of all chunks by ID
            in_flight: Set of chunk IDs currently being downloaded

        Returns:
            ChunkId of next chunk to download, or None if no chunks available

        Strategy behavior:
        - DEFAULT: Simple round-robin, returns lowest-ID pending chunk
        - INORDER: Always select lowest-index pending chunk (sequential)
        - GEOM: Geometric spacing starting from beginning
        """
        # Find all pending chunks not currently in flight
        available_chunks = [
            (chunk_id, chunk)
            for chunk_id, chunk in chunks.items()
            if chunk.status == ChunkStatus.PENDING and chunk_id not in in_flight
        ]

        if not available_chunks:
            return None

        if self.mode == StreamingMode.DEFAULT:
            # Simple round-robin: select lowest ID
            return min(available_chunks, key=lambda x: x[0])[0]

        elif self.mode == StreamingMode.INORDER:
            # Sequential from beginning: always select lowest ID
            return min(available_chunks, key=lambda x: x[0])[0]

        elif self.mode == StreamingMode.GEOM:
            # Geometric spacing: prioritize early chunks with exponential gaps
            return self._select_geometric(available_chunks)

        else:
            raise ValueError(f"Unknown streaming mode: {self.mode}")

    def _select_geometric(
        self,
        available_chunks: list[tuple[ChunkId, Chunk]]
    ) -> ChunkId:
        """
        Select chunk using geometric spacing strategy.

        The geometric strategy prioritizes chunks at the beginning of the file
        with exponentially increasing gaps. This allows video players to get
        enough data to start playback while also sampling later portions.

        Algorithm:
        1. Calculate a priority score for each chunk based on its position
        2. Earlier chunks get higher priority (lower score)
        3. Priority decreases geometrically: score = log2(chunk_id + 1)
        4. Select the chunk with the lowest score (highest priority)
        """
        if not available_chunks:
            raise ValueError("No available chunks to select from")

        # Calculate priority scores: log2(id + 1) gives geometric spacing
        # Adding 1 to avoid log(0) and ensures chunk 0 has priority 0
        scored_chunks = [
            (chunk_id, math.log2(chunk_id + 1))
            for chunk_id, _ in available_chunks
        ]

        # Select chunk with lowest score (highest priority)
        selected_id = min(scored_chunks, key=lambda x: x[1])[0]
        return selected_id



@dataclass
class DownloadMetadata:
    """
    Metadata about a download for resume validation.

    This represents the persisted state of a download that can be
    loaded from a metadata file to determine if resume is possible.
    """
    url: Url
    total_length: int | None
    etag: str | None
    last_modified: str | None


@dataclass
class HeadResponse:
    """
    Response from HTTP HEAD request.

    Contains server-provided metadata needed for resume validation.
    """
    total_length: int | None
    etag: str | None
    last_modified: str | None
    accepts_ranges: bool


class ResumePolicy:
    """
    Domain service for validating whether a download can be resumed.

    Compares persisted metadata with current server response to determine
    if the file has changed. Uses ETag and Last-Modified headers for
    validation when available.
    """

    def can_resume(
        self,
        metadata: DownloadMetadata,
        head_response: HeadResponse
    ) -> ResumeDecision:
        """
        Determine if a download can be resumed based on metadata compatibility.

        Args:
            metadata: Persisted download metadata from previous attempt
            head_response: Current server response from HEAD request

        Returns:
            ResumeDecision indicating whether to resume, restart, or error

        Validation rules:
        1. URLs must match (already validated by caller)
        2. Total length must match if both are known
        3. ETag must match if present in both
        4. Last-Modified must match if present in both and no ETag
        5. If no validators available, must restart for safety
        """
        # Validate total length if both are known
        if metadata.total_length is not None and head_response.total_length is not None:
            if metadata.total_length != head_response.total_length:
                # File size changed, must restart
                return ResumeDecision.MUST_RESTART

        # ETag is the strongest validator - check it first
        if metadata.etag is not None and head_response.etag is not None:
            if metadata.etag == head_response.etag:
                # ETags match, safe to resume
                return ResumeDecision.CAN_RESUME
            else:
                # ETags differ, file has changed
                return ResumeDecision.MUST_RESTART

        # If no ETag, fall back to Last-Modified
        if metadata.last_modified is not None and head_response.last_modified is not None:
            if metadata.last_modified == head_response.last_modified:
                # Last-Modified matches, safe to resume
                return ResumeDecision.CAN_RESUME
            else:
                # Last-Modified differs, file has changed
                return ResumeDecision.MUST_RESTART

        # If we have ETag in metadata but not in response (or vice versa),
        # we can't validate reliably, so restart for safety
        if metadata.etag is not None or head_response.etag is not None:
            return ResumeDecision.MUST_RESTART

        # If we have Last-Modified in metadata but not in response (or vice versa),
        # we can't validate reliably, so restart for safety
        if metadata.last_modified is not None or head_response.last_modified is not None:
            return ResumeDecision.MUST_RESTART

        # No validators available at all - must restart for safety
        # We can't determine if the file has changed
        return ResumeDecision.MUST_RESTART

"""Property-based tests for ChunkPlanner domain service."""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from streamdown.domain import ChunkPlanner, ChunkStatus, StreamingMode


# Feature: streamdown, Property 2: Chunk calculation correctness
@settings(deadline=500)  # Allow up to 500ms for large file calculations
@given(
    total_length=st.integers(min_value=1, max_value=100_000_000),  # 100MB max for testing
    piece_size=st.integers(min_value=1024, max_value=10**6),
    num_splits=st.integers(min_value=1, max_value=32),
)
def test_chunk_calculation_correctness(total_length: int, piece_size: int, num_splits: int):
    """
    For any file with known length, chunks must be non-overlapping and cover entire file.

    This test verifies:
    1. Number of chunks equals ceil(total_length / piece_size)
    2. Chunks are contiguous (no gaps)
    3. Chunks don't overlap
    4. First chunk starts at byte 0
    5. Last chunk ends at byte total_length - 1
    6. All chunks have valid byte ranges

    **Validates: Requirements 1.2**
    """
    planner = ChunkPlanner(StreamingMode.DEFAULT)
    chunks = planner.plan_chunks(total_length, piece_size, num_splits)

    # Verify chunk count
    expected_count = math.ceil(total_length / piece_size)
    assert len(chunks) == expected_count, (
        f"Expected {expected_count} chunks, got {len(chunks)}"
    )

    # Verify all chunks are initially PENDING
    assert all(chunk.status == ChunkStatus.PENDING for chunk in chunks)

    # Verify no overlaps and contiguous coverage
    for i, chunk in enumerate(chunks[:-1]):
        next_chunk = chunks[i + 1]
        # End of current chunk + 1 should equal start of next chunk
        assert chunk.range.end + 1 == next_chunk.range.start, (
            f"Gap or overlap between chunk {i} and {i+1}: "
            f"chunk {i} ends at {chunk.range.end}, "
            f"chunk {i+1} starts at {next_chunk.range.start}"
        )

    # Verify complete coverage
    assert chunks[0].range.start == 0, (
        f"First chunk should start at 0, got {chunks[0].range.start}"
    )
    assert chunks[-1].range.end == total_length - 1, (
        f"Last chunk should end at {total_length - 1}, got {chunks[-1].range.end}"
    )

    # Verify all chunk IDs are sequential starting from 0
    for i, chunk in enumerate(chunks):
        assert chunk.id == i, f"Chunk {i} has incorrect ID: {chunk.id}"

    # Verify each chunk size is correct (piece_size or smaller for last chunk)
    for i, chunk in enumerate(chunks[:-1]):
        assert chunk.range.size == piece_size, (
            f"Chunk {i} has incorrect size: {chunk.range.size}, expected {piece_size}"
        )

    # Last chunk can be smaller or equal to piece_size
    last_chunk_size = chunks[-1].range.size
    assert last_chunk_size <= piece_size, (
        f"Last chunk size {last_chunk_size} exceeds piece_size {piece_size}"
    )
    assert last_chunk_size > 0, "Last chunk must have positive size"

    # Verify total coverage equals file size
    total_covered = sum(chunk.range.size for chunk in chunks)
    assert total_covered == total_length, (
        f"Total chunk coverage {total_covered} doesn't match file size {total_length}"
    )



# Feature: streamdown, Property 8: Inorder chunk selection
@settings(deadline=500)
@given(
    total_length=st.integers(min_value=10_000, max_value=1_000_000),  # Reduced for performance
    piece_size=st.integers(min_value=10_000, max_value=100_000),  # Larger pieces = fewer chunks
    num_splits=st.integers(min_value=1, max_value=16),
)
def test_inorder_chunk_selection(total_length: int, piece_size: int, num_splits: int):
    """
    For any download with streaming mode set to inorder, chunks must be selected
    in ascending order by chunk ID (lowest pending chunk first).

    This test verifies:
    1. Each call to select_next_chunk returns the lowest-ID pending chunk
    2. Chunks are selected sequentially: 0, 1, 2, 3, ...
    3. In-flight chunks are skipped
    4. Already completed chunks are skipped

    **Validates: Requirements 3.1**
    """
    planner = ChunkPlanner(StreamingMode.INORDER)
    chunks_list = planner.plan_chunks(total_length, piece_size, num_splits)

    # Convert to dict for select_next_chunk
    chunks = {chunk.id: chunk for chunk in chunks_list}

    # Test 1: With no in-flight chunks, should always select chunk 0
    next_chunk = planner.select_next_chunk(chunks, set())
    assert next_chunk == 0, f"First selection should be chunk 0, got {next_chunk}"

    # Test 2: With chunk 0 in-flight, should select chunk 1
    next_chunk = planner.select_next_chunk(chunks, {0})
    if len(chunks) > 1:
        assert next_chunk == 1, f"With chunk 0 in-flight, should select chunk 1, got {next_chunk}"

    # Test 3: With chunks 0 and 1 completed, should select chunk 2
    if len(chunks) > 2:
        chunks[0] = chunks[0].mark_completed()
        chunks[1] = chunks[1].mark_completed()
        next_chunk = planner.select_next_chunk(chunks, set())
        assert next_chunk == 2, f"With 0,1 completed, should select chunk 2, got {next_chunk}"

    # Test 4: Verify monotonic selection across multiple calls
    # Reset chunks to pending
    chunks = {chunk.id: chunk for chunk in chunks_list}
    in_flight: set[int] = set()
    selected_order = []

    # Select up to 10 chunks or all chunks, whichever is smaller
    max_selections = min(10, len(chunks))
    for _ in range(max_selections):
        next_chunk_id = planner.select_next_chunk(chunks, in_flight)
        if next_chunk_id is None:
            break

        selected_order.append(next_chunk_id)

        # Verify this is the lowest-ID pending chunk
        pending_ids = [
            cid for cid, chunk in chunks.items()
            if chunk.status == ChunkStatus.PENDING and cid not in in_flight
        ]
        assert next_chunk_id == min(pending_ids), (
            f"Expected to select chunk {min(pending_ids)}, but got {next_chunk_id}"
        )

        # Mark as in-flight
        in_flight.add(next_chunk_id)

    # Verify chunks were selected in ascending order
    for i in range(len(selected_order) - 1):
        assert selected_order[i] < selected_order[i + 1], (
            f"Chunks not selected in order: {selected_order[i]} followed by {selected_order[i + 1]}"
        )



# Feature: streamdown, Property 9: Geometric chunk selection
@settings(deadline=500)
@given(
    total_length=st.integers(min_value=100_000, max_value=10_000_000),
    piece_size=st.integers(min_value=10_000, max_value=100_000),
    num_splits=st.integers(min_value=1, max_value=16),
)
def test_geometric_chunk_selection(total_length: int, piece_size: int, num_splits: int):
    """
    For any download with streaming mode set to geom, chunk selection must follow
    geometric spacing with dense coverage at the beginning and exponentially
    increasing gaps.

    This test verifies:
    1. Earlier chunks are prioritized over later chunks
    2. The selection follows a geometric pattern based on log2(chunk_id + 1)
    3. Chunk 0 has highest priority (score 0)
    4. Priority decreases geometrically as chunk ID increases

    **Validates: Requirements 3.2**
    """
    planner = ChunkPlanner(StreamingMode.GEOM)
    chunks_list = planner.plan_chunks(total_length, piece_size, num_splits)

    # Need at least a few chunks to test geometric spacing
    if len(chunks_list) < 4:
        return

    # Convert to dict for select_next_chunk
    chunks = {chunk.id: chunk for chunk in chunks_list}

    # Test 1: With all chunks pending, chunk 0 should be selected first
    # (it has the lowest score: log2(0 + 1) = 0)
    next_chunk = planner.select_next_chunk(chunks, set())
    assert next_chunk == 0, f"First selection should be chunk 0, got {next_chunk}"

    # Test 2: With chunk 0 in-flight, chunk 1 should be selected
    # (it has score log2(2) ≈ 1, which is lower than any other chunk)
    next_chunk = planner.select_next_chunk(chunks, {0})
    assert next_chunk == 1, f"With chunk 0 in-flight, should select chunk 1, got {next_chunk}"

    # Test 3: Verify geometric priority ordering
    # Calculate priority scores for all chunks
    chunk_scores = [(cid, math.log2(cid + 1)) for cid in chunks.keys()]
    chunk_scores.sort(key=lambda x: x[1])  # Sort by score (ascending = higher priority)

    # Select chunks one by one and verify they follow priority order
    in_flight: set[int] = set()
    selected_order = []

    # Select up to 10 chunks to verify the pattern
    max_selections = min(10, len(chunks))
    for _ in range(max_selections):
        next_chunk_id = planner.select_next_chunk(chunks, in_flight)
        if next_chunk_id is None:
            break

        selected_order.append(next_chunk_id)

        # Verify this chunk has the lowest score among available chunks
        available_scores = [
            (cid, math.log2(cid + 1))
            for cid, chunk in chunks.items()
            if chunk.status == ChunkStatus.PENDING and cid not in in_flight
        ]

        if available_scores:
            expected_id = min(available_scores, key=lambda x: x[1])[0]
            assert next_chunk_id == expected_id, (
                f"Expected to select chunk {expected_id}, but got {next_chunk_id}"
            )

        in_flight.add(next_chunk_id)

    # Test 4: Verify early chunks are prioritized
    # The first few selections should be low-numbered chunks
    if len(selected_order) >= 3:
        # The first 3 selections should all be from the first half of chunks
        first_three = selected_order[:3]
        midpoint = len(chunks) // 2
        early_chunks = sum(1 for cid in first_three if cid < midpoint)

        # At least 2 of the first 3 should be from the early half
        assert early_chunks >= 2, (
            f"Geometric selection should prioritize early chunks, "
            f"but first 3 selections were {first_three} with midpoint {midpoint}"
        )

    # Test 5: Verify geometric spacing property
    # For any two chunks i and j where i < j, if both are available,
    # chunk i should be selected before chunk j
    # (because log2(i+1) < log2(j+1) for i < j)
    chunks = {chunk.id: chunk for chunk in chunks_list}  # Reset

    # Test with specific pairs
    if len(chunks) >= 8:
        # Compare chunk 2 vs chunk 7
        # log2(3) ≈ 1.58, log2(8) = 3.0
        # So chunk 2 should be selected before chunk 7
        in_flight = {0, 1}  # Block the first two
        next_chunk = planner.select_next_chunk(chunks, in_flight)
        assert next_chunk == 2, f"With 0,1 in-flight, should select 2, got {next_chunk}"

        # Now with 0,1,2 in-flight, should select 3
        in_flight = {0, 1, 2}
        next_chunk = planner.select_next_chunk(chunks, in_flight)
        assert next_chunk == 3, f"With 0,1,2 in-flight, should select 3, got {next_chunk}"

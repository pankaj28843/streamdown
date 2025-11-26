"""Property-based tests for ResumePolicy domain service."""

from hypothesis import given
from hypothesis import strategies as st

from streamdown.domain import (
    DownloadMetadata,
    HeadResponse,
    ResumeDecision,
    ResumePolicy,
    Url,
)


# Strategies for generating test data
@st.composite
def metadata_strategy(draw):
    """Generate valid DownloadMetadata."""
    url = Url("https://example.com/file.bin")
    total_length = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10**9)))
    etag = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    last_modified = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))

    return DownloadMetadata(
        url=url,
        total_length=total_length,
        etag=etag,
        last_modified=last_modified,
    )


@st.composite
def head_response_strategy(draw):
    """Generate valid HeadResponse."""
    total_length = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10**9)))
    etag = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    last_modified = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    accepts_ranges = draw(st.booleans())

    return HeadResponse(
        total_length=total_length,
        etag=etag,
        last_modified=last_modified,
        accepts_ranges=accepts_ranges,
    )


# Feature: streamdown, Property 6: Resume skips completed chunks
@given(
    metadata=metadata_strategy(),
    head_response=head_response_strategy(),
)
def test_resume_validation_consistency(
    metadata: DownloadMetadata,
    head_response: HeadResponse,
):
    """
    For any download with compatible metadata and continue enabled,
    completed chunks from the metadata must not be re-downloaded.

    This test verifies the ResumePolicy correctly validates metadata
    compatibility by checking:
    1. Total length matches if both are known
    2. ETag matches if present in both
    3. Last-Modified matches if present in both
    4. Returns MUST_RESTART when validators don't match
    5. Returns CAN_RESUME only when validators match

    **Validates: Requirements 2.2, 2.3**
    """
    policy = ResumePolicy()
    decision = policy.can_resume(metadata, head_response)

    # Verify decision is one of the valid enum values
    assert decision in (
        ResumeDecision.CAN_RESUME,
        ResumeDecision.MUST_RESTART,
        ResumeDecision.ERROR,
    )

    # If total lengths are known and differ, must restart
    if (metadata.total_length is not None and
        head_response.total_length is not None and
        metadata.total_length != head_response.total_length):
        assert decision == ResumeDecision.MUST_RESTART
        return

    # If ETags are present in both
    if metadata.etag is not None and head_response.etag is not None:
        if metadata.etag == head_response.etag:
            # Matching ETags means we can resume
            assert decision == ResumeDecision.CAN_RESUME
        else:
            # Different ETags means file changed, must restart
            assert decision == ResumeDecision.MUST_RESTART
        return

    # If Last-Modified is present in both (and no ETag)
    if metadata.last_modified is not None and head_response.last_modified is not None:
        if metadata.last_modified == head_response.last_modified:
            # Matching Last-Modified means we can resume
            assert decision == ResumeDecision.CAN_RESUME
        else:
            # Different Last-Modified means file changed, must restart
            assert decision == ResumeDecision.MUST_RESTART
        return

    # If validators are mismatched or missing, must restart for safety
    assert decision == ResumeDecision.MUST_RESTART


@given(
    total_length=st.integers(min_value=1, max_value=10**9),
    etag=st.text(min_size=1, max_size=50),
)
def test_matching_etag_allows_resume(total_length: int, etag: str):
    """
    For any download where ETag matches between metadata and server,
    resume should be allowed.
    """
    url = Url("https://example.com/file.bin")

    metadata = DownloadMetadata(
        url=url,
        total_length=total_length,
        etag=etag,
        last_modified=None,
    )

    head_response = HeadResponse(
        total_length=total_length,
        etag=etag,
        last_modified=None,
        accepts_ranges=True,
    )

    policy = ResumePolicy()
    decision = policy.can_resume(metadata, head_response)

    assert decision == ResumeDecision.CAN_RESUME


@given(
    total_length=st.integers(min_value=1, max_value=10**9),
    etag1=st.text(min_size=1, max_size=50),
    etag2=st.text(min_size=1, max_size=50),
)
def test_different_etag_requires_restart(total_length: int, etag1: str, etag2: str):
    """
    For any download where ETag differs between metadata and server,
    restart must be required.
    """
    if etag1 == etag2:
        return  # Skip if ETags happen to match

    url = Url("https://example.com/file.bin")

    metadata = DownloadMetadata(
        url=url,
        total_length=total_length,
        etag=etag1,
        last_modified=None,
    )

    head_response = HeadResponse(
        total_length=total_length,
        etag=etag2,
        last_modified=None,
        accepts_ranges=True,
    )

    policy = ResumePolicy()
    decision = policy.can_resume(metadata, head_response)

    assert decision == ResumeDecision.MUST_RESTART


@given(
    total_length=st.integers(min_value=1, max_value=10**9),
    last_modified=st.text(min_size=1, max_size=50),
)
def test_matching_last_modified_allows_resume(total_length: int, last_modified: str):
    """
    For any download where Last-Modified matches and no ETag is present,
    resume should be allowed.
    """
    url = Url("https://example.com/file.bin")

    metadata = DownloadMetadata(
        url=url,
        total_length=total_length,
        etag=None,
        last_modified=last_modified,
    )

    head_response = HeadResponse(
        total_length=total_length,
        etag=None,
        last_modified=last_modified,
        accepts_ranges=True,
    )

    policy = ResumePolicy()
    decision = policy.can_resume(metadata, head_response)

    assert decision == ResumeDecision.CAN_RESUME


@given(
    length1=st.integers(min_value=1, max_value=10**9),
    length2=st.integers(min_value=1, max_value=10**9),
)
def test_different_length_requires_restart(length1: int, length2: int):
    """
    For any download where total length differs between metadata and server,
    restart must be required.
    """
    if length1 == length2:
        return  # Skip if lengths happen to match

    url = Url("https://example.com/file.bin")

    metadata = DownloadMetadata(
        url=url,
        total_length=length1,
        etag=None,
        last_modified=None,
    )

    head_response = HeadResponse(
        total_length=length2,
        etag=None,
        last_modified=None,
        accepts_ranges=True,
    )

    policy = ResumePolicy()
    decision = policy.can_resume(metadata, head_response)

    assert decision == ResumeDecision.MUST_RESTART


def test_no_validators_requires_restart():
    """
    For any download with no validators (no ETag, no Last-Modified),
    restart must be required for safety.
    """
    url = Url("https://example.com/file.bin")

    metadata = DownloadMetadata(
        url=url,
        total_length=1000,
        etag=None,
        last_modified=None,
    )

    head_response = HeadResponse(
        total_length=1000,
        etag=None,
        last_modified=None,
        accepts_ranges=True,
    )

    policy = ResumePolicy()
    decision = policy.can_resume(metadata, head_response)

    assert decision == ResumeDecision.MUST_RESTART

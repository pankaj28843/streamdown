"""Tests for domain exceptions."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from streamdown.domain import (
    FileSystemError,
    HttpError,
    NetworkError,
    ResumeError,
    StreamdownError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_all_exceptions_inherit_from_streamdown_error(self):
        """Test that all custom exceptions inherit from StreamdownError."""
        assert issubclass(NetworkError, StreamdownError)
        assert issubclass(HttpError, StreamdownError)
        assert issubclass(FileSystemError, StreamdownError)
        assert issubclass(ResumeError, StreamdownError)
        assert issubclass(ValidationError, StreamdownError)

    def test_streamdown_error_inherits_from_exception(self):
        """Test that StreamdownError inherits from Exception."""
        assert issubclass(StreamdownError, Exception)


class TestNetworkError:
    """Tests for NetworkError."""

    def test_network_error_can_be_raised(self):
        """Test that NetworkError can be raised with a message."""
        with pytest.raises(NetworkError, match="Connection failed"):
            raise NetworkError("Connection failed")


class TestFileSystemError:
    """Tests for FileSystemError."""

    def test_filesystem_error_can_be_raised(self):
        """Test that FileSystemError can be raised with a message."""
        with pytest.raises(FileSystemError, match="Disk full"):
            raise FileSystemError("Disk full")


class TestResumeError:
    """Tests for ResumeError."""

    def test_resume_error_can_be_raised(self):
        """Test that ResumeError can be raised with a message."""
        with pytest.raises(ResumeError, match="Metadata incompatible"):
            raise ResumeError("Metadata incompatible")


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_can_be_raised(self):
        """Test that ValidationError can be raised with a message."""
        with pytest.raises(ValidationError, match="Invalid URL"):
            raise ValidationError("Invalid URL")


class TestHttpError:
    """Tests for HttpError."""

    def test_http_error_stores_status_code(self):
        """Test that HttpError stores the status code."""
        error = HttpError(404, "Not Found")
        assert error.status_code == 404
        assert "Not Found" in str(error)

    def test_http_error_default_message(self):
        """Test that HttpError generates default message from status code."""
        error = HttpError(500)
        assert error.status_code == 500
        assert "500" in str(error)

    def test_http_error_custom_message(self):
        """Test that HttpError accepts custom message."""
        error = HttpError(403, "Access denied")
        assert error.status_code == 403
        assert "Access denied" in str(error)


# Feature: streamdown, Property 24: HTTP error categorization
@given(status_code=st.integers(min_value=100, max_value=599))
def test_http_error_categorization(status_code: int):
    """
    Property 24: HTTP error categorization.

    For any HTTP error response, the system must categorize the error
    and determine retry appropriateness:
    - 4xx client errors: non-retryable (except 429)
    - 5xx server errors: retryable
    - 429 Too Many Requests: retryable

    Validates: Requirements 9.3
    """
    error = HttpError(status_code)

    # 5xx server errors should be retryable
    if 500 <= status_code < 600:
        assert error.is_retryable(), f"5xx error {status_code} should be retryable"

    # 429 Too Many Requests should be retryable
    elif status_code == 429:
        assert error.is_retryable(), "429 Too Many Requests should be retryable"

    # 4xx client errors (except 429) should not be retryable
    elif 400 <= status_code < 500:
        assert not error.is_retryable(), f"4xx error {status_code} (except 429) should not be retryable"

    # Other status codes (1xx, 2xx, 3xx) should not be retryable
    else:
        assert not error.is_retryable(), f"Status code {status_code} should not be retryable"


# Additional unit tests for specific status codes
class TestHttpErrorRetryLogic:
    """Unit tests for specific HTTP error retry scenarios."""

    def test_500_internal_server_error_is_retryable(self):
        """Test that 500 Internal Server Error is retryable."""
        error = HttpError(500)
        assert error.is_retryable()

    def test_502_bad_gateway_is_retryable(self):
        """Test that 502 Bad Gateway is retryable."""
        error = HttpError(502)
        assert error.is_retryable()

    def test_503_service_unavailable_is_retryable(self):
        """Test that 503 Service Unavailable is retryable."""
        error = HttpError(503)
        assert error.is_retryable()

    def test_429_too_many_requests_is_retryable(self):
        """Test that 429 Too Many Requests is retryable."""
        error = HttpError(429)
        assert error.is_retryable()

    def test_400_bad_request_is_not_retryable(self):
        """Test that 400 Bad Request is not retryable."""
        error = HttpError(400)
        assert not error.is_retryable()

    def test_401_unauthorized_is_not_retryable(self):
        """Test that 401 Unauthorized is not retryable."""
        error = HttpError(401)
        assert not error.is_retryable()

    def test_403_forbidden_is_not_retryable(self):
        """Test that 403 Forbidden is not retryable."""
        error = HttpError(403)
        assert not error.is_retryable()

    def test_404_not_found_is_not_retryable(self):
        """Test that 404 Not Found is not retryable."""
        error = HttpError(404)
        assert not error.is_retryable()

    def test_200_ok_is_not_retryable(self):
        """Test that 200 OK is not retryable (not an error scenario)."""
        error = HttpError(200)
        assert not error.is_retryable()

    def test_301_moved_permanently_is_not_retryable(self):
        """Test that 301 Moved Permanently is not retryable."""
        error = HttpError(301)
        assert not error.is_retryable()

"""Domain exceptions for error handling."""


class StreamdownError(Exception):
    """Base exception for all Streamdown errors."""

    pass


class NetworkError(StreamdownError):
    """
    Network-related errors.

    Includes:
    - Connection failures
    - DNS resolution failures
    - Timeout errors

    These errors are retryable up to max-tries.
    """

    pass


class HttpError(StreamdownError):
    """
    HTTP protocol errors with status codes.

    Includes:
    - 4xx client errors (non-retryable except 429)
    - 5xx server errors (retryable)
    - 429 Too Many Requests (retryable with backoff)
    """

    def __init__(self, status_code: int, message: str = ""):
        """
        Initialize HTTP error with status code.

        Args:
            status_code: HTTP status code
            message: Optional error message
        """
        self.status_code = status_code
        self.message = message or f"HTTP error {status_code}"
        super().__init__(self.message)

    def is_retryable(self) -> bool:
        """
        Determine if this HTTP error is retryable.

        Returns:
            True if the error should be retried, False otherwise.

        Retry logic:
        - 5xx server errors: retryable
        - 429 Too Many Requests: retryable
        - 4xx client errors: non-retryable (except 429)
        """
        # 5xx server errors are retryable
        if 500 <= self.status_code < 600:
            return True

        # 429 Too Many Requests is retryable
        if self.status_code == 429:
            return True

        # All other errors (including 4xx) are non-retryable
        return False


class FileSystemError(StreamdownError):
    """
    File system errors.

    Includes:
    - Disk full
    - Permission denied
    - Path too long

    These errors are fatal and non-retryable.
    """

    pass


class ResumeError(StreamdownError):
    """
    Resume-related errors.

    Includes:
    - Metadata incompatible
    - Metadata corrupted

    These errors are non-retryable but should trigger a restart.
    """

    pass


class ValidationError(StreamdownError):
    """
    Validation errors for user input.

    Includes:
    - Invalid URL
    - Invalid options

    These errors are non-retryable and indicate user error.
    """

    pass

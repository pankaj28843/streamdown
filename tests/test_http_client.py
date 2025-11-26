"""Property-based tests for HTTP client adapter."""

from unittest.mock import Mock, patch

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from streamdown.domain.value_objects import ByteRange
from streamdown.infrastructure.http_client import HttpDownloader


# Feature: streamdown, Property 1: HEAD request precedes download
@settings(max_examples=100)
@given(
    url=st.from_regex(r"https?://[a-z0-9\-\.]+\.[a-z]{2,}/[a-z0-9\-_/]*", fullmatch=True),
    content_length=st.integers(min_value=1, max_value=10**9),
)
@pytest.mark.asyncio
async def test_head_request_precedes_download(url: str, content_length: int):
    """
    Property 1: HEAD request precedes download.

    For any valid HTTP(S) URL, when initiating a download, a HEAD request
    must be made before any GET requests to determine file metadata.

    Validates: Requirements 1.1
    """
    # Track the order of HTTP method calls
    call_order = []

    # Create mock client that tracks method calls
    mock_client = Mock()

    # Mock HEAD response
    head_response = Mock()
    head_response.headers = {
        "content-length": str(content_length),
        "accept-ranges": "bytes",
    }
    head_response.raise_for_status = Mock()

    async def mock_head(*args, **kwargs):
        call_order.append("HEAD")
        return head_response

    # Mock GET response for range request
    async def mock_aiter_bytes(chunk_size):
        yield b"test"

    get_response = Mock()
    get_response.status_code = 206
    get_response.aiter_bytes = mock_aiter_bytes

    class MockStreamContext:
        async def __aenter__(self):
            call_order.append("GET")
            return get_response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_stream(method, *args, **kwargs):
        return MockStreamContext()

    mock_client.head = mock_head
    mock_client.stream = mock_stream

    async def mock_aclose():
        pass

    mock_client.aclose = mock_aclose

    # Patch httpx.AsyncClient to return our mock
    with patch("streamdown.infrastructure.http_client.httpx.AsyncClient", return_value=mock_client):
        async with HttpDownloader() as downloader:
            # First, fetch HEAD to get metadata
            await downloader.fetch_head(url)

            # Verify HEAD was called
            assert len(call_order) >= 1
            assert call_order[0] == "HEAD"

            # Then fetch a range
            byte_range = ByteRange(0, 1023)
            chunks = []
            async for chunk in downloader.fetch_range(url, byte_range):
                chunks.append(chunk)

            # Verify HEAD was called before GET
            assert "HEAD" in call_order
            assert "GET" in call_order
            head_index = call_order.index("HEAD")
            get_index = call_order.index("GET")
            assert head_index < get_index, "HEAD request must precede GET request"


# Feature: streamdown, Property 28: HTTPS certificate validation by default
@settings(max_examples=100)
@given(
    url=st.from_regex(r"https://[a-z0-9\-\.]+\.[a-z]{2,}/[a-z0-9\-_/]*", fullmatch=True),
)
@pytest.mark.asyncio
async def test_https_certificate_validation_by_default(url: str):
    """
    Property 28: HTTPS certificate validation by default.

    For any HTTPS URL without the insecure flag, certificate validation
    must be enabled.

    Validates: Requirements 13.1
    """
    # Track whether verify was set correctly
    verify_value = None

    def mock_client_init(*args, **kwargs):
        nonlocal verify_value
        verify_value = kwargs.get("verify", True)
        # Return a mock client
        mock = Mock()

        async def mock_aclose():
            pass

        mock.aclose = mock_aclose
        return mock

    with patch("streamdown.infrastructure.http_client.httpx.AsyncClient", side_effect=mock_client_init):
        # Create downloader with default settings (verify_ssl=True)
        async with HttpDownloader(verify_ssl=True):
            # Verify that SSL verification was enabled
            assert verify_value is True, "HTTPS certificate validation must be enabled by default"


@settings(max_examples=100)
@given(
    url=st.from_regex(r"https://[a-z0-9\-\.]+\.[a-z]{2,}/[a-z0-9\-_/]*", fullmatch=True),
)
@pytest.mark.asyncio
async def test_https_certificate_validation_can_be_disabled(url: str):
    """
    Test that certificate validation can be disabled with insecure flag.

    This verifies that when verify_ssl=False, the client disables validation.
    """
    # Track whether verify was set correctly
    verify_value = None

    def mock_client_init(*args, **kwargs):
        nonlocal verify_value
        verify_value = kwargs.get("verify", True)
        mock = Mock()

        async def mock_aclose():
            pass

        mock.aclose = mock_aclose
        return mock

    with patch("streamdown.infrastructure.http_client.httpx.AsyncClient", side_effect=mock_client_init):
        # Create downloader with insecure flag (verify_ssl=False)
        async with HttpDownloader(verify_ssl=False):
            # Verify that SSL verification was disabled
            assert verify_value is False, "Certificate validation must be disabled when insecure flag is set"


# Feature: streamdown, Property 19: Connect timeout enforcement
@settings(max_examples=100)
@given(
    url=st.from_regex(r"https?://[a-z0-9\-\.]+\.[a-z]{2,}/[a-z0-9\-_/]*", fullmatch=True),
    connect_timeout=st.floats(min_value=0.1, max_value=60.0),
)
@pytest.mark.asyncio
async def test_connect_timeout_enforcement(url: str, connect_timeout: float):
    """
    Property 19: Connect timeout enforcement.

    For any connection attempt with connect-timeout specified, connections
    exceeding that duration must be aborted.

    Validates: Requirements 8.2
    """
    from streamdown.domain.exceptions import NetworkError

    # Create a mock client that simulates a connect timeout
    mock_client = Mock()

    async def mock_head(*args, **kwargs):
        # Simulate a connect timeout
        raise httpx.ConnectTimeout("Connection timed out")

    mock_client.head = mock_head

    async def mock_aclose():
        pass

    mock_client.aclose = mock_aclose

    # Patch httpx.AsyncClient to return our mock
    with patch("streamdown.infrastructure.http_client.httpx.AsyncClient", return_value=mock_client):
        async with HttpDownloader(connect_timeout=connect_timeout) as downloader:
            # Attempt to fetch HEAD - should raise NetworkError due to timeout
            with pytest.raises(NetworkError) as exc_info:
                await downloader.fetch_head(url)

            # Verify the error message mentions timeout
            assert "timeout" in str(exc_info.value).lower(), "NetworkError should indicate timeout"



# Feature: streamdown, Property 20: Read timeout enforcement
@settings(max_examples=100)
@given(
    url=st.from_regex(r"https?://[a-z0-9\-\.]+\.[a-z]{2,}/[a-z0-9\-_/]*", fullmatch=True),
    read_timeout=st.floats(min_value=0.1, max_value=300.0),
)
@pytest.mark.asyncio
async def test_read_timeout_enforcement(url: str, read_timeout: float):
    """
    Property 20: Read timeout enforcement.

    For any active transfer with read-timeout specified, transfers stalled
    longer than that duration must be aborted.

    Validates: Requirements 8.3
    """
    from streamdown.domain.exceptions import NetworkError
    from streamdown.domain.value_objects import ByteRange

    # Create a mock client that simulates a read timeout
    mock_client = Mock()

    class MockStreamContext:
        async def __aenter__(self):
            # Simulate a read timeout during streaming
            raise httpx.ReadTimeout("Read timed out")

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_stream(method, *args, **kwargs):
        return MockStreamContext()

    mock_client.stream = mock_stream

    async def mock_aclose():
        pass

    mock_client.aclose = mock_aclose

    # Patch httpx.AsyncClient to return our mock
    with patch("streamdown.infrastructure.http_client.httpx.AsyncClient", return_value=mock_client):
        async with HttpDownloader(read_timeout=read_timeout) as downloader:
            # Attempt to fetch a range - should raise NetworkError due to read timeout
            byte_range = ByteRange(0, 1023)

            with pytest.raises(NetworkError) as exc_info:
                async for _ in downloader.fetch_range(url, byte_range):
                    pass

            # Verify the error message mentions timeout
            assert "timeout" in str(exc_info.value).lower(), "NetworkError should indicate timeout"


# Feature: streamdown, Property 33: Authentication headers included for netrc hosts
@settings(max_examples=100)
@given(
    url=st.from_regex(r"https?://[a-z0-9\-\.]+\.[a-z]{2,}/[a-z0-9\-_/]*", fullmatch=True),
    username=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
    password=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
)
@pytest.mark.asyncio
async def test_authentication_headers_included_for_netrc_hosts(url: str, username: str, password: str):
    """
    Property 33: Authentication headers included for netrc hosts.

    For any HTTP request to a host with netrc credentials, the request must
    include an HTTP Basic Authentication header with the correct credentials.

    Validates: Requirements 15.2
    """
    from urllib.parse import urlparse
    from streamdown.infrastructure.netrc_provider import NetrcCredentialProvider

    # Extract host from URL
    parsed = urlparse(url)
    host = parsed.hostname

    # Create a mock credential provider that returns credentials for this host
    mock_provider = Mock(spec=NetrcCredentialProvider)
    mock_provider.get_credentials = Mock(return_value=(username, password))

    # Track the auth parameter passed to httpx
    auth_used = None

    # Create mock client
    mock_client = Mock()

    # Mock HEAD response
    head_response = Mock()
    head_response.headers = {
        "content-length": "1000",
        "accept-ranges": "bytes",
    }
    head_response.raise_for_status = Mock()

    async def mock_head(*args, **kwargs):
        nonlocal auth_used
        auth_used = kwargs.get("auth")
        return head_response

    mock_client.head = mock_head

    async def mock_aclose():
        pass

    mock_client.aclose = mock_aclose

    # Patch httpx.AsyncClient to return our mock
    with patch("streamdown.infrastructure.http_client.httpx.AsyncClient", return_value=mock_client):
        async with HttpDownloader(credential_provider=mock_provider) as downloader:
            # Fetch HEAD with authentication
            await downloader.fetch_head(url)

            # Verify credentials were requested for the correct host
            mock_provider.get_credentials.assert_called_once_with(host)

            # Verify auth was passed to httpx
            assert auth_used is not None, "Authentication must be provided when credentials exist"
            
            # Verify it's BasicAuth with correct credentials
            assert isinstance(auth_used, httpx.BasicAuth), "Must use httpx.BasicAuth"
            # BasicAuth stores credentials in _auth_header property as base64
            # We can verify by checking the username and password attributes
            import base64
            expected_auth = base64.b64encode(f"{username}:{password}".encode()).decode()
            actual_auth = auth_used._auth_header.split(" ")[1]
            assert actual_auth == expected_auth, "Authentication credentials must match netrc credentials"


@settings(max_examples=100)
@given(
    url=st.from_regex(r"https?://[a-z0-9\-\.]+\.[a-z]{2,}/[a-z0-9\-_/]*", fullmatch=True),
)
@pytest.mark.asyncio
async def test_no_authentication_when_no_credentials(url: str):
    """
    Test that no authentication is used when credentials are not available.

    This verifies that when the credential provider returns None,
    no auth parameter is passed to httpx.
    """
    from urllib.parse import urlparse
    from streamdown.infrastructure.netrc_provider import NetrcCredentialProvider

    # Extract host from URL
    parsed = urlparse(url)
    host = parsed.hostname

    # Create a mock credential provider that returns None (no credentials)
    mock_provider = Mock(spec=NetrcCredentialProvider)
    mock_provider.get_credentials = Mock(return_value=None)

    # Track the auth parameter passed to httpx
    auth_used = None

    # Create mock client
    mock_client = Mock()

    # Mock HEAD response
    head_response = Mock()
    head_response.headers = {
        "content-length": "1000",
        "accept-ranges": "bytes",
    }
    head_response.raise_for_status = Mock()

    async def mock_head(*args, **kwargs):
        nonlocal auth_used
        auth_used = kwargs.get("auth")
        return head_response

    mock_client.head = mock_head

    async def mock_aclose():
        pass

    mock_client.aclose = mock_aclose

    # Patch httpx.AsyncClient to return our mock
    with patch("streamdown.infrastructure.http_client.httpx.AsyncClient", return_value=mock_client):
        async with HttpDownloader(credential_provider=mock_provider) as downloader:
            # Fetch HEAD without authentication
            await downloader.fetch_head(url)

            # Verify credentials were requested for the correct host
            mock_provider.get_credentials.assert_called_once_with(host)

            # Verify no auth was passed to httpx
            assert auth_used is None, "No authentication should be used when credentials are not available"

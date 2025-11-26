"""HTTP client adapter for downloading files."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from streamdown.domain.exceptions import NetworkError
from streamdown.domain.value_objects import ByteRange


@dataclass
class HeadResponse:
    """Response from HEAD request containing file metadata."""

    content_length: int | None
    accept_ranges: bool
    etag: str | None
    last_modified: str | None


class HttpDownloader:
    """HTTP client adapter using httpx for downloading files."""

    def __init__(
        self,
        connect_timeout: float = 60.0,
        read_timeout: float = 300.0,
        user_agent: str = "streamdown/0.1.0",
        verify_ssl: bool = True,
        max_connections: int = 100,
        credential_provider: Optional["NetrcCredentialProvider"] = None,
    ):
        """
        Initialize HTTP downloader.

        Args:
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
            user_agent: User-Agent header value
            verify_ssl: Whether to verify SSL certificates
            max_connections: Maximum number of connections in pool
            credential_provider: Optional netrc credential provider for authentication
        """
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._user_agent = user_agent
        self._verify_ssl = verify_ssl
        self._max_connections = max_connections
        self._credential_provider = credential_provider
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HttpDownloader":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self._connect_timeout,
                read=self._read_timeout,
                write=None,
                pool=None,
            ),
            headers={"User-Agent": self._user_agent},
            verify=self._verify_ssl,
            limits=httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=self._max_connections,
            ),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_auth_for_url(self, url: str) -> Optional[httpx.BasicAuth]:
        """
        Get HTTP Basic Auth for URL from credential provider.

        Args:
            url: URL to get credentials for

        Returns:
            httpx.BasicAuth if credentials exist, None otherwise
        """
        if not self._credential_provider:
            return None

        # Extract host from URL
        parsed = urlparse(url)
        host = parsed.hostname

        if not host:
            return None

        # Get credentials from provider
        credentials = self._credential_provider.get_credentials(host)
        if credentials:
            username, password = credentials
            return httpx.BasicAuth(username, password)

        return None

    async def fetch_head(self, url: str) -> HeadResponse:
        """
        Fetch file metadata using HEAD request.

        Args:
            url: URL to fetch metadata for

        Returns:
            HeadResponse with file metadata

        Raises:
            NetworkError: If connection fails or times out
            httpx.HTTPError: If request fails
        """
        if not self._client:
            raise RuntimeError("HttpDownloader must be used as async context manager")

        # Get authentication for this URL
        auth = self._get_auth_for_url(url)

        try:
            response = await self._client.head(url, auth=auth)
            response.raise_for_status()
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout) as e:
            # Convert timeout exceptions to NetworkError
            raise NetworkError(f"Timeout while fetching HEAD for {url}: {e}") from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            # Convert network exceptions to NetworkError
            raise NetworkError(f"Network error while fetching HEAD for {url}: {e}") from e

        # Parse Content-Length
        content_length = None
        if "content-length" in response.headers:
            try:
                content_length = int(response.headers["content-length"])
            except ValueError:
                pass

        # Check if server supports range requests
        accept_ranges = response.headers.get("accept-ranges", "").lower() == "bytes"

        # Get ETag and Last-Modified for resume validation
        etag = response.headers.get("etag")
        last_modified = response.headers.get("last-modified")

        return HeadResponse(
            content_length=content_length,
            accept_ranges=accept_ranges,
            etag=etag,
            last_modified=last_modified,
        )

    async def fetch_range(
        self,
        url: str,
        byte_range: ByteRange,
        buffer_size: int = 64 * 1024,  # 64 KiB
    ) -> AsyncIterator[bytes]:
        """
        Fetch a byte range from URL as async generator.

        This method streams data in fixed-size buffers to maintain
        bounded memory usage regardless of chunk size.

        Args:
            url: URL to download from
            byte_range: Byte range to fetch
            buffer_size: Size of read buffers (default 64 KiB)

        Yields:
            Chunks of data from the byte range

        Raises:
            NetworkError: If connection fails or times out
            httpx.HTTPError: If request fails
        """
        if not self._client:
            raise RuntimeError("HttpDownloader must be used as async context manager")

        headers = {"Range": byte_range.to_header_value()}
        
        # Get authentication for this URL
        auth = self._get_auth_for_url(url)

        try:
            async with self._client.stream("GET", url, headers=headers, auth=auth) as response:
                # Accept both 206 (Partial Content) and 200 (OK for full file)
                if response.status_code not in (200, 206):
                    # Convert HTTP errors to domain HttpError
                    from streamdown.domain.exceptions import HttpError
                    raise HttpError(
                        status_code=response.status_code,
                        message=f"HTTP {response.status_code} while fetching {url}"
                    )

                async for chunk in response.aiter_bytes(chunk_size=buffer_size):
                    yield chunk
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout) as e:
            # Convert timeout exceptions to NetworkError
            raise NetworkError(f"Timeout while fetching range {byte_range} from {url}: {e}") from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            # Convert network exceptions to NetworkError
            raise NetworkError(f"Network error while fetching range {byte_range} from {url}: {e}") from e

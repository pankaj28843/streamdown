"""Tests for domain value objects."""

from pathlib import Path
from uuid import UUID

import pytest

from streamdown.domain import (
    ByteRange,
    ChunkId,
    FilePath,
    Url,
    new_download_id,
)


class TestUrl:
    """Tests for Url value object."""

    def test_valid_http_url(self):
        """Test creating a valid HTTP URL."""
        url = Url("http://example.com/file.txt")
        assert url.value == "http://example.com/file.txt"
        assert str(url) == "http://example.com/file.txt"

    def test_valid_https_url(self):
        """Test creating a valid HTTPS URL."""
        url = Url("https://example.com/file.txt")
        assert url.value == "https://example.com/file.txt"

    def test_empty_url_raises_error(self):
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError, match="URL cannot be empty"):
            Url("")

    def test_invalid_scheme_raises_error(self):
        """Test that non-HTTP(S) scheme raises ValueError."""
        with pytest.raises(ValueError, match="must use http or https scheme"):
            Url("ftp://example.com/file.txt")

    def test_missing_host_raises_error(self):
        """Test that URL without host raises ValueError."""
        with pytest.raises(ValueError, match="must have a valid host"):
            Url("http://")

    def test_url_is_immutable(self):
        """Test that Url is immutable (frozen dataclass)."""
        url = Url("http://example.com")
        with pytest.raises(AttributeError):
            url.value = "http://other.com"


class TestFilePath:
    """Tests for FilePath value object."""

    def test_create_from_path(self):
        """Test creating FilePath from Path object."""
        path = FilePath(Path("/tmp/file.txt"))
        assert path.value == Path("/tmp/file.txt")

    def test_create_from_string(self):
        """Test creating FilePath from string using from_str."""
        path = FilePath.from_str("/tmp/file.txt")
        assert path.value == Path("/tmp/file.txt")
        assert str(path) == "/tmp/file.txt"

    def test_empty_path_raises_error(self):
        """Test that empty path raises ValueError."""
        with pytest.raises(ValueError, match="File path cannot be empty"):
            FilePath(Path(""))

    def test_parent_method(self):
        """Test getting parent directory."""
        path = FilePath.from_str("/tmp/subdir/file.txt")
        parent = path.parent()
        assert parent.value == Path("/tmp/subdir")

    def test_with_suffix(self):
        """Test changing file suffix."""
        path = FilePath.from_str("/tmp/file.txt")
        new_path = path.with_suffix(".part")
        assert new_path.value == Path("/tmp/file.part")

    def test_with_name(self):
        """Test changing file name."""
        path = FilePath.from_str("/tmp/file.txt")
        new_path = path.with_name("other.txt")
        assert new_path.value == Path("/tmp/other.txt")

    def test_filepath_is_immutable(self):
        """Test that FilePath is immutable."""
        path = FilePath.from_str("/tmp/file.txt")
        with pytest.raises(AttributeError):
            path.value = Path("/other/path")


class TestByteRange:
    """Tests for ByteRange value object."""

    def test_valid_byte_range(self):
        """Test creating a valid byte range."""
        br = ByteRange(0, 1023)
        assert br.start == 0
        assert br.end == 1023
        assert br.size == 1024

    def test_single_byte_range(self):
        """Test byte range for a single byte."""
        br = ByteRange(100, 100)
        assert br.size == 1

    def test_negative_start_raises_error(self):
        """Test that negative start raises ValueError."""
        with pytest.raises(ValueError, match="Start byte must be non-negative"):
            ByteRange(-1, 100)

    def test_negative_end_raises_error(self):
        """Test that negative end raises ValueError."""
        with pytest.raises(ValueError, match="End byte must be non-negative"):
            ByteRange(0, -1)

    def test_start_greater_than_end_raises_error(self):
        """Test that start > end raises ValueError."""
        with pytest.raises(ValueError, match="Start byte .* must be less than or equal to end byte"):
            ByteRange(100, 50)

    def test_to_header_value(self):
        """Test converting to HTTP Range header value."""
        br = ByteRange(0, 1023)
        assert br.to_header_value() == "bytes=0-1023"

    def test_str_representation(self):
        """Test string representation."""
        br = ByteRange(100, 200)
        assert str(br) == "[100-200]"

    def test_byterange_is_immutable(self):
        """Test that ByteRange is immutable."""
        br = ByteRange(0, 100)
        with pytest.raises(AttributeError):
            br.start = 50


class TestDownloadId:
    """Tests for DownloadId type."""

    def test_new_download_id_creates_uuid(self):
        """Test that new_download_id creates a valid UUID."""
        download_id = new_download_id()
        assert isinstance(download_id, UUID)

    def test_download_ids_are_unique(self):
        """Test that multiple calls create unique IDs."""
        id1 = new_download_id()
        id2 = new_download_id()
        assert id1 != id2


class TestChunkId:
    """Tests for ChunkId type."""

    def test_chunk_id_is_int(self):
        """Test that ChunkId wraps an integer."""
        chunk_id = ChunkId(42)
        assert chunk_id == 42

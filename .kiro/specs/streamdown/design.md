# Design Document

## Overview

Streamdown is a pure-Python asyncio-based HTTP(S) downloader that implements intelligent multi-connection downloads with streaming-optimized chunk selection. The system follows Domain-Driven Design principles with clear separation between domain logic, application orchestration, and infrastructure concerns.

### Key Design Goals

1. **Streaming-First Architecture**: Prioritize early file segments to enable video playback during download
2. **Robust Resume**: Crash-safe metadata persistence with compatibility validation
3. **Pure Python**: No mandatory C extensions, compatible with uv and modern Python tooling
4. **Structured Concurrency**: Leverage Python 3.11+ asyncio.TaskGroup for clean async patterns
5. **Rich UX**: Beautiful terminal interface with real-time progress tracking

### Technology Stack

- **Python**: 3.11+ (required for TaskGroup and modern asyncio features)
- **HTTP Client**: httpx (pure Python, excellent async support)
- **CLI Framework**: typer (modern, type-hint based CLI)
- **TUI**: rich (progress bars, logging, formatting)
- **File I/O**: aiofiles (async file operations)
- **Netrc**: Python stdlib netrc module (credential parsing)
- **Testing**: pytest + pytest-asyncio
- **Code Quality**: ruff (formatting and linting)

## Architecture

### Layered Architecture (DDD)

```
┌─────────────────────────────────────────┐
│         Interface Layer (CLI)           │
│  - Argument parsing (typer)             │
│  - Progress display (rich)              │
│  - User interaction                     │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│       Application Layer                 │
│  - Use cases (start_download, resume)   │
│  - Orchestration logic                  │
│  - DTO transformations                  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Domain Layer                    │
│  - Entities (DownloadJob, Chunk)        │
│  - Value Objects (ByteRange, Url)       │
│  - Domain Services (ChunkPlanner)       │
│  - Domain Events                        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│      Infrastructure Layer               │
│  - HTTP client adapter (httpx)          │
│  - File repository (metadata)           │
│  - File writer (part files)             │
│  - Logging adapter                      │
└─────────────────────────────────────────┘
```

### Concurrency Model

The system uses Python 3.11+ structured concurrency with asyncio.TaskGroup:

1. **Download Manager**: Coordinates multiple downloads with bounded concurrency
2. **Download Coordinator**: Manages a single download's lifecycle
3. **Chunk Workers**: Download individual byte ranges in parallel
4. **Metadata Writer**: Persists state asynchronously

Concurrency limits:
- Global: `max_concurrent_downloads` (default 4)
- Per-download: `splits` (default 8)
- Per-host: `max_connections_per_host` (default 8, must be ≤ splits)

## Components and Interfaces

### Domain Layer

#### Entities

**DownloadJob** (Aggregate Root)
```python
@dataclass
class DownloadJob:
    id: DownloadId
    url: Url
    target_path: FilePath
    part_path: FilePath
    meta_path: FilePath
    total_length: int | None
    piece_size: int
    chunks: dict[ChunkId, Chunk]
    status: DownloadStatus
    etag: str | None
    last_modified: str | None
    created_at: datetime
    updated_at: datetime
    resume_allowed: bool
    
    def plan_chunks(self, planner: ChunkPlanner) -> None: ...
    def mark_chunk_completed(self, chunk_id: ChunkId, size: int) -> DownloadJob: ...
    def is_complete(self) -> bool: ...
    def compute_progress(self) -> DownloadProgress: ...
```

**Chunk**
```python
@dataclass
class Chunk:
    id: ChunkId
    range: ByteRange
    status: ChunkStatus
    retries: int
    last_error: str | None
```

#### Value Objects

- **DownloadId**: UUID identifier
- **Url**: Validated HTTP(S) URL
- **FilePath**: Validated filesystem path
- **ByteRange**: (start: int, end: int) byte positions
- **ChunkId**: Integer chunk identifier
- **DownloadStatus**: Enum (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- **ChunkStatus**: Enum (PENDING, IN_PROGRESS, COMPLETED, FAILED)
- **StreamingMode**: Enum (DEFAULT, INORDER, GEOM)

#### Domain Services

**ChunkPlanner**
```python
class ChunkPlanner:
    def __init__(self, mode: StreamingMode): ...
    
    def plan_chunks(
        self, 
        total_length: int, 
        piece_size: int, 
        num_splits: int
    ) -> list[Chunk]: ...
    
    def select_next_chunk(
        self, 
        chunks: dict[ChunkId, Chunk],
        in_flight: set[ChunkId]
    ) -> ChunkId | None: ...
```

Strategies:
- **DEFAULT**: Simple round-robin, minimize connection churn
- **INORDER**: Always select lowest-index pending chunk (sliding window)
- **GEOM**: Geometric spacing (dense at start, exponential gaps)

**ResumePolicy**
```python
class ResumePolicy:
    def can_resume(
        self,
        metadata: DownloadMetadata,
        head_response: HeadResponse
    ) -> ResumeDecision: ...
```

Returns: `CAN_RESUME`, `MUST_RESTART`, `ERROR`

Validation checks:
- URL matches
- Total length matches (if known)
- ETag matches (if present)
- Last-Modified matches (if present)

#### Domain Events

```python
@dataclass
class DownloadStarted:
    download_id: DownloadId
    url: Url
    timestamp: datetime

@dataclass
class ChunkCompleted:
    download_id: DownloadId
    chunk_id: ChunkId
    bytes_downloaded: int
    timestamp: datetime

@dataclass
class DownloadCompleted:
    download_id: DownloadId
    final_path: FilePath
    total_bytes: int
    duration: timedelta
    timestamp: datetime

@dataclass
class DownloadFailed:
    download_id: DownloadId
    error: str
    timestamp: datetime
```

### Application Layer

#### Use Cases

**start_download**
```python
async def start_download(
    urls: list[str],
    options: DownloadOptions
) -> list[DownloadResult]:
    """
    Orchestrates multiple downloads with bounded concurrency.
    Returns results for each URL.
    """
```

**resume_or_start**
```python
async def resume_or_start(
    url: str,
    options: DownloadOptions
) -> DownloadResult:
    """
    Attempts resume if metadata exists and is compatible,
    otherwise starts fresh download.
    """
```

#### DTOs

**DownloadOptions**
```python
@dataclass
class DownloadOptions:
    directory: Path
    output_name: str | None
    splits: int
    max_connections_per_host: int
    piece_size: int
    continue_download: bool
    allow_overwrite: bool
    auto_file_renaming: bool
    max_concurrent_downloads: int
    streaming_mode: StreamingMode
    connect_timeout: float
    read_timeout: float
    max_tries: int
    retry_wait: float
    user_agent: str
    quiet: bool
    log_level: str
    insecure: bool
    no_netrc: bool
    netrc_path: Path | None
```

### Infrastructure Layer

#### HTTP Adapter

**HttpDownloader** (implements DownloadGateway protocol)
```python
class HttpDownloader:
    async def fetch_head(self, url: str) -> HeadResponse: ...
    
    async def fetch_range(
        self,
        url: str,
        range: ByteRange,
        headers: dict[str, str]
    ) -> AsyncIterator[bytes]: ...
```

Uses httpx.AsyncClient with:
- Connection pooling
- Timeout configuration
- Certificate validation (configurable)
- Custom User-Agent
- HTTP Basic Authentication from netrc (when enabled)

#### Netrc Adapter

**NetrcCredentialProvider**
```python
class NetrcCredentialProvider:
    def __init__(self, netrc_path: Path | None = None, enabled: bool = True): ...
    
    def get_credentials(self, host: str) -> tuple[str, str] | None: ...
    
    def load_netrc(self) -> None: ...
```

Responsibilities:
- Load and parse netrc file at initialization
- Validate file permissions (must be 600)
- Extract credentials for specific hosts
- Handle missing or malformed netrc files gracefully
- Log warnings for permission or syntax issues

#### File Repository

**MetadataRepository**
```python
class MetadataRepository:
    async def load(self, meta_path: Path) -> DownloadMetadata | None: ...
    async def save(self, meta_path: Path, metadata: DownloadMetadata) -> None: ...
    async def delete(self, meta_path: Path) -> None: ...
```

Atomic writes:
1. Write to temporary file
2. fsync
3. Rename to target (atomic on POSIX)

#### File Writer

**PartFileWriter**
```python
class PartFileWriter:
    async def write_at_offset(
        self,
        path: Path,
        offset: int,
        data: bytes
    ) -> None: ...
    
    async def finalize(self, part_path: Path, final_path: Path) -> None: ...
```

Uses aiofiles for async I/O with buffering.

## Data Models

### Metadata File Format

File: `<target>.part.meta.json`

```json
{
  "version": 1,
  "url": "https://example.com/file.mp4",
  "total_length": 104857600,
  "etag": "\"abc123\"",
  "last_modified": "Wed, 21 Oct 2015 07:28:00 GMT",
  "piece_size": 1048576,
  "chunks": [
    {
      "id": 0,
      "start": 0,
      "end": 1048575,
      "status": "COMPLETED"
    },
    {
      "id": 1,
      "start": 1048576,
      "end": 2097151,
      "status": "PENDING"
    }
  ],
  "created_at": "2025-11-25T10:30:00Z",
  "updated_at": "2025-11-25T10:35:00Z"
}
```

### Part File Structure

File: `<target>.part`

- Binary file with holes (sparse file support on supported filesystems)
- Chunks written at correct byte offsets
- File size set to total_length on creation
- Compatible with video players for streaming playback

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Acceptance Criteria Testing Prework

1.1 WHEN a user provides an HTTP(S) URL THEN Streamdown SHALL initiate a HEAD request to determine file size and range support
Thoughts: This is about what happens for any valid URL. We can generate random URLs and verify that a HEAD request is made before downloading.
Testable: yes - property

1.2 WHEN the server supports byte ranges THEN Streamdown SHALL split the file into chunks based on the specified split count and piece size
Thoughts: This is a rule that applies to all files with range support. We can test with various file sizes and verify chunk calculation.
Testable: yes - property

1.3 WHEN downloading with multiple splits THEN Streamdown SHALL maintain up to the specified number of concurrent connections per download
Thoughts: This is about concurrency limits applying to all downloads. We can verify connection count doesn't exceed the limit.
Testable: yes - property

1.4 WHEN all chunks complete successfully THEN Streamdown SHALL rename the part file to the final output filename
Thoughts: This is a rule for all successful downloads. We can verify the file rename happens.
Testable: yes - property

1.5 WHEN the server does not support byte ranges THEN Streamdown SHALL fall back to single-stream download with progress tracking
Thoughts: This is testing behavior for a specific server capability. This is an edge case our tests should handle.
Testable: edge-case

2.1 WHEN a download is interrupted THEN Streamdown SHALL persist chunk completion state to a metadata file
Thoughts: This applies to all interrupted downloads. We can verify metadata exists after interruption.
Testable: yes - property

2.2 WHEN resuming with continue enabled THEN Streamdown SHALL load the metadata file and validate compatibility using ETag and Last-Modified headers
Thoughts: This is about resume behavior for all downloads. We can test that validation occurs.
Testable: yes - property

2.3 WHEN metadata is compatible THEN Streamdown SHALL skip completed chunks and download only pending chunks
Thoughts: This is a rule about resume behavior. We can verify completed chunks aren't re-downloaded.
Testable: yes - property

2.4 WHEN metadata is incompatible with server response THEN Streamdown SHALL restart the download from the beginning
Thoughts: This is an edge case for incompatible metadata.
Testable: edge-case

2.5 WHEN continue is disabled THEN Streamdown SHALL overwrite existing part files and start fresh
Thoughts: This is about behavior when continue flag is false. We can test this applies to all downloads.
Testable: yes - property

3.1 WHEN streaming mode is set to inorder THEN Streamdown SHALL prioritize chunks sequentially from the beginning of the file
Thoughts: This is about chunk selection order for all files in inorder mode. We can verify chunk IDs are selected in ascending order.
Testable: yes - property

3.2 WHEN streaming mode is set to geom THEN Streamdown SHALL select chunks using geometric spacing starting from the beginning
Thoughts: This is about chunk selection for geom mode. We can verify the geometric pattern.
Testable: yes - property

3.3 WHEN early chunks complete THEN Streamdown SHALL write them to the part file at correct offsets to maintain file structure
Thoughts: This is about file writing for all chunks. We can verify data is written at the correct byte offset.
Testable: yes - property

3.4 WHEN a video player opens the part file THEN the file SHALL contain valid header data and sequential early content
Thoughts: This is about the resulting file structure, which depends on our chunk prioritization working correctly. If 3.1 and 3.3 work, this should work.
Testable: no (redundant with 3.1 and 3.3)

3.5 WHILE downloading continues THEN Streamdown SHALL maintain the streaming priority strategy for remaining chunks
Thoughts: This is about maintaining strategy consistency, which is covered by 3.1 and 3.2.
Testable: no (redundant)

4.1 WHEN a complete file exists at the target path and allow-overwrite is disabled THEN Streamdown SHALL report an error and refuse to download
Thoughts: This is about error handling for a specific condition. This is an important edge case.
Testable: edge-case

4.2 WHEN a complete file exists and allow-overwrite is enabled THEN Streamdown SHALL replace the existing file with the new download
Thoughts: This is about overwrite behavior. We can test this applies to all downloads with this flag.
Testable: yes - property

4.3 WHEN auto-file-renaming is enabled and a file exists THEN Streamdown SHALL append a numeric suffix to create a unique filename
Thoughts: This is about filename generation. We can test that the generated name is unique.
Testable: yes - property

4.4 WHEN a part file exists and continue is enabled THEN Streamdown SHALL attempt to resume the download
Thoughts: This is covered by 2.2 and 2.3.
Testable: no (redundant)

4.5 WHEN the output directory does not exist THEN Streamdown SHALL create the directory before starting the download
Thoughts: This is about directory creation for all downloads. We can verify the directory exists after attempting download.
Testable: yes - property

5.1 WHEN multiple URLs are provided THEN Streamdown SHALL queue all downloads for processing
Thoughts: This is about queueing behavior for all multi-URL invocations. We can verify all URLs are queued.
Testable: yes - property

5.2 WHEN max-concurrent-downloads is specified THEN Streamdown SHALL limit active downloads to that number
Thoughts: This is about concurrency limits for all multi-download scenarios. We can verify the limit is respected.
Testable: yes - property

5.3 WHEN a download completes or fails THEN Streamdown SHALL start the next queued download if any remain
Thoughts: This is about queue processing behavior. We can verify downloads progress through the queue.
Testable: yes - property

5.4 WHEN all downloads complete THEN Streamdown SHALL report the final status of each download
Thoughts: This is about reporting behavior. We can verify all statuses are reported.
Testable: yes - property

5.5 WHILE multiple downloads run THEN Streamdown SHALL aggregate and display total throughput statistics
Thoughts: This is about UI display behavior, not core logic.
Testable: no

6.1-6.5: All UI/display requirements
Thoughts: These are about terminal display and user interface, not testable as properties of core logic.
Testable: no

7.1 WHEN no directory is specified THEN Streamdown SHALL download to the current working directory
Thoughts: This is about default value behavior. This is a specific example to test.
Testable: yes - example

7.2 WHEN no split count is specified THEN Streamdown SHALL use 8 parallel chunks by default
Thoughts: This is about default value behavior. This is a specific example to test.
Testable: yes - example

7.3 WHEN no piece size is specified THEN Streamdown SHALL use 1 MiB chunks by default
Thoughts: This is about default value behavior. This is a specific example to test.
Testable: yes - example

7.4 WHEN no continue flag is specified THEN Streamdown SHALL enable resume by default
Thoughts: This is about default value behavior. This is a specific example to test.
Testable: yes - example

7.5 WHEN no overwrite flag is specified THEN Streamdown SHALL prevent overwriting existing complete files by default
Thoughts: This is about default value behavior. This is a specific example to test.
Testable: yes - example

8.1 WHEN max-connections-per-host is specified THEN Streamdown SHALL limit concurrent connections to each host to that value
Thoughts: This is about connection limiting for all downloads. We can verify the limit is respected.
Testable: yes - property

8.2 WHEN connect-timeout is specified THEN Streamdown SHALL abort connection attempts exceeding that duration
Thoughts: This is about timeout behavior. We can test with slow servers.
Testable: yes - property

8.3 WHEN read-timeout is specified THEN Streamdown SHALL abort stalled transfers exceeding that duration
Thoughts: This is about timeout behavior. We can test with stalled connections.
Testable: yes - property

8.4 WHEN max-tries is specified THEN Streamdown SHALL retry failed chunks up to that number of attempts
Thoughts: This is about retry behavior for all failed chunks. We can verify retry count.
Testable: yes - property

8.5 WHEN retry-wait is specified THEN Streamdown SHALL wait that duration between retry attempts
Thoughts: This is about timing between retries. We can verify the wait duration.
Testable: yes - property

9.1 WHEN a chunk download fails with a network error THEN Streamdown SHALL retry the chunk up to max-tries attempts
Thoughts: This is covered by 8.4.
Testable: no (redundant)

9.2 WHEN a chunk exceeds max-tries THEN Streamdown SHALL mark the download as failed and report the error
Thoughts: This is about failure handling after retries exhausted. We can test this behavior.
Testable: yes - property

9.3 WHEN an HTTP error status is received THEN Streamdown SHALL categorize the error and determine if retry is appropriate
Thoughts: This is about error categorization logic. We can test with various HTTP status codes.
Testable: yes - property

9.4 WHEN a connection times out THEN Streamdown SHALL treat it as a retryable error
Thoughts: This is a specific case of 9.3.
Testable: edge-case

9.5 WHEN disk write fails THEN Streamdown SHALL report a fatal error and halt the download
Thoughts: This is about error handling for disk failures. This is an edge case.
Testable: edge-case

10.1-10.5: Installation and packaging requirements
Thoughts: These are about packaging and installation, not runtime behavior we can property test.
Testable: no

11.1-11.5: Architecture requirements
Thoughts: These are about code organization, not functional behavior we can property test.
Testable: no

12.1 WHEN metadata is written THEN Streamdown SHALL use atomic file operations or crash-safe techniques
Thoughts: This is about the implementation technique. We can verify atomicity by checking file states.
Testable: yes - property

12.2 WHEN a crash occurs during metadata write THEN the metadata file SHALL either be valid or absent
Thoughts: This is about crash safety. This is an edge case to test.
Testable: edge-case

12.3 WHEN loading corrupted metadata THEN Streamdown SHALL detect the corruption and restart the download
Thoughts: This is about error handling for corrupted data. This is an edge case.
Testable: edge-case

12.4 WHEN a download completes successfully THEN Streamdown SHALL remove the metadata file
Thoughts: This is about cleanup behavior for all successful downloads. We can verify metadata is removed.
Testable: yes - property

12.5 WHEN chunk completion is recorded THEN Streamdown SHALL persist the update before considering the chunk complete
Thoughts: This is about ordering of operations. We can verify persistence happens before status change.
Testable: yes - property

13.1 WHEN downloading from HTTPS URLs THEN Streamdown SHALL validate server certificates by default
Thoughts: This is about default security behavior for all HTTPS downloads. We can verify validation occurs.
Testable: yes - property

13.2 WHEN certificate validation fails THEN Streamdown SHALL abort the download with a security error
Thoughts: This is an edge case for invalid certificates.
Testable: edge-case

13.3 WHEN an insecure flag is provided THEN Streamdown SHALL disable certificate validation and display a warning
Thoughts: This is about flag behavior. We can test this applies to all downloads with the flag.
Testable: yes - property

13.4 WHEN downloading from HTTP URLs THEN Streamdown SHALL proceed without certificate validation
Thoughts: This is about HTTP vs HTTPS behavior. This is an edge case.
Testable: edge-case

13.5 WHEN custom CA certificates are needed THEN Streamdown SHALL respect system certificate stores
Thoughts: This is about system integration, difficult to property test in isolation.
Testable: no

14.1 WHEN downloading file chunks THEN Streamdown SHALL stream data in fixed-size buffers rather than loading entire chunks in memory
Thoughts: This is about memory management implementation. We can verify buffer sizes are bounded.
Testable: yes - property

14.2 WHEN writing to disk THEN Streamdown SHALL use buffered I/O with reasonable buffer sizes
Thoughts: This is about implementation details of I/O.
Testable: no

14.3 WHEN multiple downloads are active THEN memory usage SHALL scale linearly with concurrent connections, not file sizes
Thoughts: This is about memory scaling behavior. We can measure memory usage.
Testable: yes - property

14.4 WHEN a file is gigabytes in size THEN Streamdown SHALL maintain memory usage under 100 MiB regardless of file size
Thoughts: This is a specific performance requirement. This is an example to test.
Testable: yes - example

14.5 WHEN chunk data is received THEN Streamdown SHALL write it to disk promptly and release the buffer
Thoughts: This is about implementation behavior that ensures 14.1 works.
Testable: no (redundant)

15.1 WHEN netrc support is enabled and a netrc file exists THEN Streamdown SHALL read authentication credentials from the netrc file at startup
Thoughts: This is about initialization behavior for all downloads with netrc enabled. We can verify credentials are loaded.
Testable: yes - property

15.2 WHEN downloading from a host with netrc credentials THEN Streamdown SHALL include HTTP Basic Authentication headers in requests
Thoughts: This is about authentication behavior for all hosts with credentials. We can verify the Authorization header is present.
Testable: yes - property

15.3 WHEN the netrc file has permissions other than 600 THEN Streamdown SHALL ignore the file and log a warning
Thoughts: This is about security validation. This is an important edge case.
Testable: edge-case

15.4 WHEN no-netrc is set to true THEN Streamdown SHALL disable netrc support and not read the netrc file
Thoughts: This is about flag behavior. We can verify netrc is not loaded when disabled.
Testable: yes - property

15.5 WHEN netrc-path is specified THEN Streamdown SHALL read credentials from the specified file instead of the default location
Thoughts: This is about custom path behavior. We can verify the custom path is used.
Testable: yes - property

15.6 WHEN the default netrc file does not exist and no custom path is specified THEN Streamdown SHALL proceed without netrc authentication
Thoughts: This is about graceful degradation. This is an edge case.
Testable: edge-case

15.7 WHEN netrc file contains invalid syntax THEN Streamdown SHALL log a warning and proceed without netrc authentication
Thoughts: This is about error handling for malformed files. This is an edge case.
Testable: edge-case

### Property Reflection

After reviewing all testable properties, I identify the following consolidations:

- Properties 2.2 and 2.3 can be combined into a single "resume skips completed chunks" property
- Properties 3.1 and 3.2 are distinct strategies, keep separate
- Property 4.4 is redundant with 2.2/2.3, remove
- Properties 9.1 is redundant with 8.4, remove
- Properties 3.4 and 3.5 are redundant with 3.1, 3.2, and 3.3, remove
- Property 14.5 is redundant with 14.1, remove

### Correctness Properties

Property 1: HEAD request precedes download
*For any* valid HTTP(S) URL, when initiating a download, a HEAD request must be made before any GET requests to determine file metadata.
**Validates: Requirements 1.1**

Property 2: Chunk calculation correctness
*For any* file with known length and range support, the number of chunks must equal ceil(total_length / piece_size), and each chunk's byte range must be valid and non-overlapping.
**Validates: Requirements 1.2**

Property 3: Concurrent connection limit
*For any* download with specified splits, the number of active concurrent connections must never exceed the splits value.
**Validates: Requirements 1.3**

Property 4: Successful completion renames part file
*For any* download where all chunks complete successfully, the part file must be renamed to the final target filename.
**Validates: Requirements 1.4**

Property 5: Metadata persistence on interruption
*For any* interrupted download, a metadata file must exist containing the current chunk completion state.
**Validates: Requirements 2.1**

Property 6: Resume skips completed chunks
*For any* download with compatible metadata and continue enabled, completed chunks from the metadata must not be re-downloaded.
**Validates: Requirements 2.2, 2.3**

Property 7: Fresh start with continue disabled
*For any* download with continue disabled, existing part files must be overwritten and all chunks downloaded from scratch.
**Validates: Requirements 2.5**

Property 8: Inorder chunk selection
*For any* download with streaming mode set to inorder, chunks must be selected in ascending order by chunk ID (lowest pending chunk first).
**Validates: Requirements 3.1**

Property 9: Geometric chunk selection
*For any* download with streaming mode set to geom, chunk selection must follow geometric spacing with dense coverage at the beginning and exponentially increasing gaps.
**Validates: Requirements 3.2**

Property 10: Chunk data written at correct offset
*For any* completed chunk, the data must be written to the part file at the byte offset matching the chunk's start position.
**Validates: Requirements 3.3**

Property 11: Overwrite with flag enabled
*For any* download with allow-overwrite enabled, an existing complete file at the target path must be replaced by the new download.
**Validates: Requirements 4.2**

Property 12: Auto-renaming generates unique filename
*For any* download with auto-file-renaming enabled where the target file exists, the system must generate a unique filename by appending a numeric suffix.
**Validates: Requirements 4.3**

Property 13: Directory creation
*For any* download where the output directory does not exist, the directory must be created before download begins.
**Validates: Requirements 4.5**

Property 14: All URLs queued
*For any* invocation with multiple URLs, all URLs must be added to the download queue.
**Validates: Requirements 5.1**

Property 15: Concurrent download limit
*For any* multi-download scenario with max-concurrent-downloads specified, the number of simultaneously active downloads must never exceed that limit.
**Validates: Requirements 5.2**

Property 16: Queue progression
*For any* download queue, when a download completes or fails, the next queued download must start if any remain.
**Validates: Requirements 5.3**

Property 17: All download statuses reported
*For any* multi-download invocation, the final output must include status for each URL provided.
**Validates: Requirements 5.4**

Property 18: Per-host connection limit
*For any* download with max-connections-per-host specified, concurrent connections to each host must not exceed that value.
**Validates: Requirements 8.1**

Property 19: Connect timeout enforcement
*For any* connection attempt with connect-timeout specified, connections exceeding that duration must be aborted.
**Validates: Requirements 8.2**

Property 20: Read timeout enforcement
*For any* active transfer with read-timeout specified, transfers stalled longer than that duration must be aborted.
**Validates: Requirements 8.3**

Property 21: Retry limit enforcement
*For any* failed chunk with max-tries specified, the chunk must be retried at most max-tries times before being marked as permanently failed.
**Validates: Requirements 8.4**

Property 22: Retry wait duration
*For any* chunk retry with retry-wait specified, the system must wait at least that duration between retry attempts.
**Validates: Requirements 8.5**

Property 23: Failure after retry exhaustion
*For any* chunk that fails max-tries times, the download must be marked as failed and an error reported.
**Validates: Requirements 9.2**

Property 24: HTTP error categorization
*For any* HTTP error response, the system must categorize the error and determine retry appropriateness (4xx = non-retryable, 5xx = retryable, 429 = retryable).
**Validates: Requirements 9.3**

Property 25: Atomic metadata writes
*For any* metadata write operation, the metadata file must be written atomically (temp file + rename) to ensure crash safety.
**Validates: Requirements 12.1**

Property 26: Metadata cleanup on success
*For any* successfully completed download, the metadata file must be removed.
**Validates: Requirements 12.4**

Property 27: Metadata persistence before chunk completion
*For any* chunk completion, the metadata must be persisted to disk before the chunk status is updated to COMPLETED.
**Validates: Requirements 12.5**

Property 28: HTTPS certificate validation by default
*For any* HTTPS URL without the insecure flag, certificate validation must be enabled.
**Validates: Requirements 13.1**

Property 29: Certificate validation disabled with insecure flag
*For any* download with the insecure flag set, certificate validation must be disabled.
**Validates: Requirements 13.3**

Property 30: Bounded buffer sizes
*For any* chunk download, data must be streamed in fixed-size buffers not exceeding 64 KiB per buffer.
**Validates: Requirements 14.1**

Property 31: Memory scales with connections not file size
*For any* set of concurrent downloads, memory usage must scale with the number of active connections, not with the total size of files being downloaded.
**Validates: Requirements 14.3**

Property 32: Netrc credentials loaded at startup
*For any* download with netrc enabled and a valid netrc file present, credentials must be loaded during initialization before any downloads begin.
**Validates: Requirements 15.1**

Property 33: Authentication headers included for netrc hosts
*For any* HTTP request to a host with netrc credentials, the request must include an HTTP Basic Authentication header with the correct credentials.
**Validates: Requirements 15.2**

Property 34: Netrc disabled with no-netrc flag
*For any* download with no-netrc set to true, the netrc file must not be read and no netrc credentials must be used.
**Validates: Requirements 15.4**

Property 35: Custom netrc path respected
*For any* download with netrc-path specified, credentials must be read from the specified path instead of the default ~/.netrc location.
**Validates: Requirements 15.5**

## Error Handling

### Error Categories

**NetworkError**
- Connection failures
- DNS resolution failures
- Timeout errors
- Retryable: Yes (up to max-tries)

**HttpError**
- 4xx client errors (non-retryable except 429)
- 5xx server errors (retryable)
- 429 Too Many Requests (retryable with backoff)
- Retryable: Depends on status code

**FileSystemError**
- Disk full
- Permission denied
- Path too long
- Retryable: No (fatal)

**ResumeError**
- Metadata incompatible
- Metadata corrupted
- Retryable: No (restart download)

**ValidationError**
- Invalid URL
- Invalid options
- Retryable: No (user error)

### Retry Strategy

```python
async def download_chunk_with_retry(
    chunk: Chunk,
    options: DownloadOptions
) -> bytes:
    for attempt in range(options.max_tries):
        try:
            return await download_chunk(chunk)
        except NetworkError as e:
            if attempt < options.max_tries - 1:
                await asyncio.sleep(options.retry_wait)
                continue
            raise
        except HttpError as e:
            if e.is_retryable() and attempt < options.max_tries - 1:
                await asyncio.sleep(options.retry_wait)
                continue
            raise
```

### Error Propagation

- Chunk-level errors: Retry up to max-tries, then fail the download
- Download-level errors: Fail immediately, report to user
- Multi-download errors: Fail individual download, continue with others

## Testing Strategy

### Unit Testing

Unit tests will cover:
- Domain model behavior (DownloadJob, Chunk state transitions)
- Chunk planner strategies (default, inorder, geom)
- Resume policy validation logic
- Metadata serialization/deserialization
- Error categorization logic
- URL parsing and validation
- File path handling and sanitization

Framework: pytest with standard assertions

### Property-Based Testing

Property-based tests will verify universal properties across all valid inputs using Hypothesis (Python's leading PBT library).

**Configuration:**
- Minimum 100 iterations per property test
- Each test tagged with: `# Feature: streamdown, Property N: <description>`
- Tests will generate random but valid inputs (URLs, file sizes, chunk configurations)

**Key Properties to Test:**
1. Chunk calculation (Property 2)
2. Concurrent connection limits (Properties 3, 15, 18)
3. Resume behavior (Properties 6, 7)
4. Chunk selection strategies (Properties 8, 9)
5. Offset correctness (Property 10)
6. Retry limits (Property 21)
7. Memory bounds (Properties 30, 31)

**Example Property Test Structure:**
```python
from hypothesis import given, strategies as st

# Feature: streamdown, Property 2: Chunk calculation correctness
@given(
    total_length=st.integers(min_value=1, max_value=10**9),
    piece_size=st.integers(min_value=1024, max_value=10**6)
)
def test_chunk_calculation_correctness(total_length: int, piece_size: int):
    """For any file with known length, chunks must be non-overlapping and cover entire file."""
    chunks = plan_chunks(total_length, piece_size, splits=8)
    
    # Verify no overlaps
    for i, chunk in enumerate(chunks[:-1]):
        assert chunk.range.end + 1 == chunks[i+1].range.start
    
    # Verify complete coverage
    assert chunks[0].range.start == 0
    assert chunks[-1].range.end == total_length - 1
    
    # Verify count
    expected_count = math.ceil(total_length / piece_size)
    assert len(chunks) == expected_count
```

### Integration Testing

Integration tests will use a local HTTP test server (aiohttp test server) to verify:
- Complete download flow (HEAD → GET ranges → write → rename)
- Resume from partial download
- Concurrent chunk downloads
- Timeout handling
- Retry logic with flaky server
- Range request handling
- Fallback to single-stream for non-range servers

### End-to-End Testing

E2E tests will verify:
- CLI argument parsing and validation
- Progress bar display (captured output)
- Multi-file downloads
- Error message formatting
- Exit codes

Framework: pytest with subprocess or typer.testing.CliRunner

### Test Coverage Goals

- Unit tests: 90%+ coverage of domain and application layers
- Property tests: All 31 correctness properties implemented
- Integration tests: All major user flows
- E2E tests: All CLI flags and combinations

## Performance Considerations

### Throughput Optimization

1. **Connection pooling**: Reuse HTTP connections via httpx client
2. **Parallel I/O**: Use aiofiles for non-blocking disk writes
3. **Buffer tuning**: 64 KiB read buffers, 256 KiB write buffers
4. **Chunk sizing**: Default 1 MiB balances overhead vs. granularity

### Memory Management

1. **Streaming**: Never buffer entire chunks in memory
2. **Bounded queues**: Limit in-flight chunks to prevent memory growth
3. **Prompt writes**: Write data to disk immediately upon receipt
4. **Buffer reuse**: Use buffer pools where possible

### Scalability

- Supports files up to 1 TB (limited by filesystem, not implementation)
- Handles 100+ concurrent downloads with bounded memory
- Efficient with slow connections (no busy-waiting)

## Security Considerations

1. **HTTPS by default**: Certificate validation enabled unless explicitly disabled
2. **Path traversal prevention**: Sanitize output filenames
3. **Symlink safety**: Resolve symlinks before writing
4. **Temp file security**: Use secure temp file creation
5. **No code execution**: No eval, exec, or dynamic imports of user data

## Deployment and Packaging

### Package Structure

```
streamdown/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── streamdown/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── events.py
│       │   └── services.py
│       ├── application/
│       │   ├── __init__.py
│       │   └── use_cases.py
│       └── infrastructure/
│           ├── __init__.py
│           ├── http_client.py
│           ├── file_repo.py
│           ├── file_writer.py
│           └── logging.py
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

### pyproject.toml

```toml
[project]
name = "streamdown"
version = "0.1.0"
description = "Modern asyncio HTTP(S) downloader with smart chunked streaming"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.25.0",
    "rich>=13.0.0",
    "typer>=0.9.0",
    "aiofiles>=23.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "hypothesis>=6.90.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[project.scripts]
streamdown = "streamdown.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
strict = true
```

### Installation

```bash
# Via uv (recommended)
uv tool install streamdown

# Via pip
pip install streamdown

# Development install
git clone https://github.com/user/streamdown
cd streamdown
uv pip install -e ".[dev]"
```

## Future Extensions

### Phase 2 Features

1. **Proxy support**: HTTP/HTTPS/SOCKS5 proxies
2. **Speed limiting**: Per-download and global bandwidth limits
3. **Checksum verification**: MD5, SHA256 verification
4. **Metalink support**: Parse .metalink files for mirrors
5. **Cookie support**: Cookie jar for authenticated downloads

### Phase 3 Features

1. **JSON-RPC interface**: Remote control like aria2c
2. **Plugin system**: Custom chunk planners and storage backends
3. **FTP/SFTP support**: Additional protocols
4. **Torrent support**: BitTorrent protocol (major addition)

### Extensibility Points

- **ChunkPlanner**: New strategies via strategy pattern
- **DownloadGateway**: New protocols via adapter pattern
- **FileWriter**: Alternative storage (S3, etc.) via adapter pattern
- **ProgressDisplay**: Custom UIs via observer pattern

## Appendix: CLI Reference

### Command Syntax

```bash
streamdown [OPTIONS] URL [URL...]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-d, --dir` | PATH | `.` | Download directory |
| `-o, --out` | TEXT | (from URL) | Output filename (single URL only) |
| `-s, --splits` | INT | 8 | Parallel chunks per download |
| `-x, --max-connections-per-host` | INT | 8 | Max connections per host |
| `-k, --piece-size` | SIZE | 1M | Chunk size (supports K, M suffixes) |
| `-c, --continue` | FLAG | true | Resume from existing .part |
| `--allow-overwrite` | FLAG | false | Allow overwriting complete files |
| `--auto-file-renaming` | FLAG | false | Auto-append .1, .2 to avoid conflicts |
| `-j, --max-concurrent-downloads` | INT | 4 | Concurrent downloads |
| `--streaming-mode` | CHOICE | default | Chunk selection: default\|inorder\|geom |
| `--connect-timeout` | FLOAT | 60.0 | Connection timeout (seconds) |
| `--read-timeout` | FLOAT | 300.0 | Read timeout (seconds) |
| `-m, --max-tries` | INT | 5 | Max retry attempts |
| `--retry-wait` | FLOAT | 0.0 | Wait between retries (seconds) |
| `--user-agent` | TEXT | streamdown/0.1.0 | HTTP User-Agent header |
| `-q, --quiet` | FLAG | false | Suppress progress bars |
| `--log-level` | CHOICE | info | Logging: debug\|info\|warn\|error |
| `--insecure` | FLAG | false | Disable HTTPS certificate validation |
| `-n, --no-netrc` | FLAG | false | Disable netrc support |
| `--netrc-path` | PATH | ~/.netrc | Path to netrc file |

### Examples

```bash
# Simple download
streamdown https://example.com/file.zip

# Custom output location
streamdown -d ~/Downloads -o video.mp4 https://example.com/video.mp4

# High-speed download with many connections
streamdown -s 16 -x 16 https://example.com/large-file.iso

# Video streaming mode
streamdown --streaming-mode inorder https://example.com/movie.mp4

# Multiple files
streamdown -j 2 https://example.com/file1.zip https://example.com/file2.zip

# Resume disabled, force fresh download
streamdown --no-continue https://example.com/file.zip

# Allow overwriting existing file
streamdown --allow-overwrite https://example.com/file.zip
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All downloads successful |
| 1 | One or more downloads failed |
| 2 | Invalid arguments or configuration |
| 3 | Fatal error (disk full, permission denied) |

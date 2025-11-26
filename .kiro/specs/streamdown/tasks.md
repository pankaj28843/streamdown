# Implementation Plan

- [x] 1. Set up project structure and tooling
  - Create pyproject.toml with Python 3.11+ requirement, dependencies (httpx, rich, typer, aiofiles), and dev dependencies (pytest, pytest-asyncio, hypothesis, ruff)
  - Set up src/streamdown package structure with domain, application, infrastructure, and cli modules
  - Configure ruff for linting and formatting
  - Create basic __init__.py files for all packages
  - _Requirements: 10.1, 10.3, 10.5_

- [x] 2. Implement domain layer value objects and enums
  - Create value objects: DownloadId, Url, FilePath, ByteRange, ChunkId
  - Create enums: DownloadStatus, ChunkStatus, StreamingMode, ResumeDecision
  - Add validation logic to value objects
  - _Requirements: 11.1_

- [x] 3. Implement domain entities
  - Create Chunk entity with id, range, status, retries, last_error fields
  - Create DownloadJob aggregate root with all required fields
  - Implement DownloadJob.compute_progress() method
  - Implement DownloadJob.is_complete() method
  - Implement DownloadJob.mark_chunk_completed() method
  - _Requirements: 11.1, 1.2_

- [x] 3.1 Write property test for chunk completion
  - **Property 27: Metadata persistence before chunk completion**
  - **Validates: Requirements 12.5**

- [x] 4. Implement ChunkPlanner domain service
  - Create ChunkPlanner base class with strategy pattern
  - Implement plan_chunks() method to calculate chunk byte ranges
  - Implement DEFAULT strategy (round-robin chunk selection)
  - Implement INORDER strategy (sequential from beginning)
  - Implement GEOM strategy (geometric spacing)
  - _Requirements: 1.2, 3.1, 3.2_

- [x] 4.1 Write property test for chunk calculation
  - **Property 2: Chunk calculation correctness**
  - **Validates: Requirements 1.2**

- [x] 4.2 Write property test for inorder selection
  - **Property 8: Inorder chunk selection**
  - **Validates: Requirements 3.1**

- [x] 4.3 Write property test for geometric selection
  - **Property 9: Geometric chunk selection**
  - **Validates: Requirements 3.2**

- [x] 5. Implement ResumePolicy domain service
  - Create ResumePolicy class
  - Implement can_resume() method with ETag and Last-Modified validation
  - Return appropriate ResumeDecision based on compatibility checks
  - _Requirements: 2.2, 2.4_

- [x] 5.1 Write property test for resume validation
  - **Property 6: Resume skips completed chunks**
  - **Validates: Requirements 2.2, 2.3**

- [x] 6. Implement domain events
  - Create DownloadStarted event
  - Create ChunkCompleted event
  - Create DownloadCompleted event
  - Create DownloadFailed event
  - _Requirements: 11.1_

- [x] 7. Implement infrastructure HTTP client adapter
  - Create HttpDownloader class using httpx.AsyncClient
  - Implement fetch_head() method to get Content-Length and Accept-Ranges
  - Implement fetch_range() async generator for streaming byte ranges
  - Configure timeouts, User-Agent, and certificate validation
  - Handle connection pooling and reuse
  - _Requirements: 1.1, 1.5, 8.2, 8.3, 13.1, 13.3_

- [x] 7.1 Write property test for HEAD before GET
  - **Property 1: HEAD request precedes download**
  - **Validates: Requirements 1.1**

- [x] 7.2 Write property test for certificate validation
  - **Property 28: HTTPS certificate validation by default**
  - **Validates: Requirements 13.1**

- [x] 8. Implement infrastructure file writer
  - Create PartFileWriter class using aiofiles
  - Implement write_at_offset() method with seek and write
  - Implement finalize() method to rename .part to final filename
  - Use buffered I/O with 256 KiB buffers
  - Handle directory creation if needed
  - _Requirements: 3.3, 1.4, 4.5, 14.1, 14.2_

- [x] 8.1 Write property test for offset correctness
  - **Property 10: Chunk data written at correct offset**
  - **Validates: Requirements 3.3**

- [x] 8.2 Write property test for directory creation
  - **Property 13: Directory creation**
  - **Validates: Requirements 4.5**

- [x] 9. Implement infrastructure metadata repository
  - Create MetadataRepository class
  - Implement save() method with atomic writes (temp file + rename)
  - Implement load() method with JSON parsing and validation
  - Implement delete() method for cleanup
  - Handle corrupted metadata gracefully
  - _Requirements: 2.1, 12.1, 12.2, 12.3, 12.4_

- [x] 9.1 Write property test for atomic metadata writes
  - **Property 25: Atomic metadata writes**
  - **Validates: Requirements 12.1**

- [x] 9.2 Write property test for metadata cleanup
  - **Property 26: Metadata cleanup on success**
  - **Validates: Requirements 12.4**

- [x] 10. Implement error handling classes
  - Create NetworkError exception class
  - Create HttpError exception class with status code and is_retryable() method
  - Create FileSystemError exception class
  - Create ResumeError exception class
  - Create ValidationError exception class
  - _Requirements: 9.3, 9.5_

- [x] 10.1 Write property test for HTTP error categorization
  - **Property 24: HTTP error categorization**
  - **Validates: Requirements 9.3**

- [x] 11. Implement chunk download worker with retry logic
  - Create download_chunk_with_retry() async function
  - Implement retry loop up to max_tries
  - Add retry_wait delay between attempts
  - Handle NetworkError and HttpError with appropriate retry logic
  - Stream data in 64 KiB buffers and write to disk incrementally
  - _Requirements: 8.4, 8.5, 9.1, 9.2, 14.1, 14.5_

- [x] 11.1 Write property test for retry limit
  - **Property 21: Retry limit enforcement**
  - **Validates: Requirements 8.4**

- [x] 11.2 Write property test for retry wait
  - **Property 22: Retry wait duration**
  - **Validates: Requirements 8.5**

- [x] 11.3 Write property test for bounded buffers
  - **Property 30: Bounded buffer sizes**
  - **Validates: Requirements 14.1**

- [x] 12. Implement single download coordinator
  - Create DownloadCoordinator class to manage one download
  - Implement HEAD request to get file metadata
  - Check for existing metadata and attempt resume if enabled
  - Plan chunks using ChunkPlanner
  - Spawn worker tasks for parallel chunk downloads (up to splits)
  - Enforce max_connections_per_host limit
  - Update metadata after each chunk completion
  - Finalize download when all chunks complete
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.2, 2.3, 2.5, 8.1_

- [x] 12.1 Write property test for concurrent connection limit
  - **Property 3: Concurrent connection limit**
  - **Validates: Requirements 1.3**

- [x] 12.2 Write property test for per-host connection limit
  - **Property 18: Per-host connection limit**
  - **Validates: Requirements 8.1**

- [x] 12.3 Write property test for part file rename
  - **Property 4: Successful completion renames part file**
  - **Validates: Requirements 1.4**

- [x] 12.4 Write property test for fresh start
  - **Property 7: Fresh start with continue disabled**
  - **Validates: Requirements 2.5**

- [x] 13. Implement download manager for multiple downloads
  - Create DownloadManager class
  - Queue all provided URLs
  - Spawn up to max_concurrent_downloads coordinators
  - Start next download when one completes or fails
  - Aggregate statistics across all downloads
  - Return results for all downloads
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 13.1 Write property test for URL queueing
  - **Property 14: All URLs queued**
  - **Validates: Requirements 5.1**

- [x] 13.2 Write property test for concurrent download limit
  - **Property 15: Concurrent download limit**
  - **Validates: Requirements 5.2**

- [x] 13.3 Write property test for queue progression
  - **Property 16: Queue progression**
  - **Validates: Requirements 5.3**

- [x] 13.4 Write property test for status reporting
  - **Property 17: All download statuses reported**
  - **Validates: Requirements 5.4**

- [x] 14. Implement application layer DTOs
  - Create DownloadOptions dataclass with all CLI options
  - Create DownloadResult dataclass for return values
  - Create DownloadProgress dataclass for progress tracking
  - _Requirements: 11.2_

- [x] 15. Implement application use cases
  - Create start_download() use case function
  - Create resume_or_start() use case function
  - Wire together domain services and infrastructure adapters
  - Handle file overwrite logic (allow-overwrite, auto-file-renaming)
  - _Requirements: 4.1, 4.2, 4.3, 11.2_

- [x] 15.1 Write property test for overwrite behavior
  - **Property 11: Overwrite with flag enabled**
  - **Validates: Requirements 4.2**

- [x] 15.2 Write property test for auto-renaming
  - **Property 12: Auto-renaming generates unique filename**
  - **Validates: Requirements 4.3**

- [x] 16. Implement CLI with typer
  - Create main CLI app with typer
  - Define all command-line options matching the spec
  - Parse piece-size with K/M suffix support
  - Validate option combinations (e.g., -o with multiple URLs)
  - Convert CLI args to DownloadOptions DTO
  - Call application layer use cases
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 16.1 Write unit tests for default values
  - Test default directory is current working directory
  - Test default splits is 8
  - Test default piece size is 1 MiB
  - Test default continue is enabled
  - Test default allow-overwrite is disabled
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 17. Implement progress display with rich
  - Create ProgressDisplay class using rich.progress
  - Display progress bar for each download with filename, percentage, speed, ETA
  - Update progress bars as chunks complete
  - Show status indicators (HEAD, downloading, complete, failed)
  - Aggregate and display total throughput for multiple downloads
  - Support quiet mode to suppress progress bars
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 18. Implement logging with rich
  - Configure logging with rich.logging.RichHandler
  - Support log levels: debug, info, warn, error
  - Log key events: download start, chunk completion, errors
  - Format error messages with structured information
  - _Requirements: 6.5_

- [x] 19. Implement timeout handling
  - Add connect_timeout to httpx client configuration
  - Add read_timeout to httpx client configuration
  - Catch timeout exceptions and convert to NetworkError
  - _Requirements: 8.2, 8.3, 9.4_

- [x] 19.1 Write property test for connect timeout
  - **Property 19: Connect timeout enforcement**
  - **Validates: Requirements 8.2**

- [x] 19.2 Write property test for read timeout
  - **Property 20: Read timeout enforcement**
  - **Validates: Requirements 8.3**

- [x] 20. Implement memory efficiency measures
  - Ensure streaming with fixed 64 KiB read buffers
  - Verify no chunk data is held in memory after writing
  - Use bounded queues for in-flight chunks
  - _Requirements: 14.1, 14.3, 14.4_

- [x] 20.1 Write property test for memory scaling
  - **Property 31: Memory scales with connections not file size**
  - **Validates: Requirements 14.3**

- [x] 21. Add __main__.py entry point
  - Create __main__.py to enable `python -m streamdown`
  - Call CLI app from __main__
  - _Requirements: 10.2_

- [x] 22. Write integration tests
  - Set up aiohttp test server for integration tests
  - Test complete download flow with range support
  - Test resume from partial download
  - Test fallback to single-stream without range support
  - Test concurrent chunk downloads
  - Test retry logic with flaky server
  - Test timeout handling
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.2, 2.3, 8.4, 8.5_

- [x] 23. Write E2E CLI tests
  - Test CLI argument parsing
  - Test multiple URLs with -j flag
  - Test output directory with -d flag
  - Test output filename with -o flag
  - Test invalid option combinations
  - Test error messages and exit codes
  - _Requirements: 5.1, 5.2, 7.1_

- [x] 24. Add README with usage examples
  - Document installation via uv and pip
  - Provide usage examples for common scenarios
  - Document all CLI options
  - Include troubleshooting section
  - _Requirements: 10.1_

- [x] 25. Add LICENSE file
  - Add MIT license
  - _Requirements: 10.1_

- [x] 26. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 27. Implement netrc credential provider
  - Create NetrcCredentialProvider class in infrastructure layer
  - Implement __init__ to accept netrc_path and enabled parameters
  - Implement load_netrc() to read and parse netrc file using stdlib netrc module
  - Validate file permissions (must be 600 on Unix systems)
  - Implement get_credentials(host) to return username/password tuple or None
  - Handle missing netrc file gracefully (return None for all hosts)
  - Handle malformed netrc file gracefully (log warning, return None)
  - Handle incorrect permissions (log warning, return None)
  - Use default path ~/.netrc when netrc_path is None
  - _Requirements: 15.1, 15.3, 15.4, 15.5, 15.6, 15.7_

- [x] 27.1 Write property test for netrc credentials loaded
  - **Property 32: Netrc credentials loaded at startup**
  - **Validates: Requirements 15.1**

- [x] 27.2 Write property test for netrc disabled
  - **Property 34: Netrc disabled with no-netrc flag**
  - **Validates: Requirements 15.4**

- [x] 27.3 Write property test for custom netrc path
  - **Property 35: Custom netrc path respected**
  - **Validates: Requirements 15.5**

- [x] 28. Integrate netrc with HTTP client
  - Update HttpDownloader to accept NetrcCredentialProvider in constructor
  - Extract host from URL before making requests
  - Call get_credentials(host) to retrieve credentials
  - Add HTTP Basic Authentication header when credentials are available
  - Use httpx auth parameter with httpx.BasicAuth for authentication
  - Ensure authentication works for both HEAD and GET requests
  - _Requirements: 15.2_

- [x] 28.1 Write property test for authentication headers
  - **Property 33: Authentication headers included for netrc hosts**
  - **Validates: Requirements 15.2**

- [x] 29. Update CLI to support netrc options
  - Add --no-netrc / -n flag (default: false, meaning netrc is enabled by default)
  - Add --netrc-path option (default: None, uses ~/.netrc)
  - Update DownloadOptions DTO with no_netrc and netrc_path fields
  - Pass netrc options to application layer
  - _Requirements: 15.4, 15.5_

- [x] 30. Update application layer to wire netrc support
  - Create NetrcCredentialProvider instance in use cases based on options
  - Pass credential provider to HttpDownloader
  - Ensure netrc is loaded before any downloads start
  - _Requirements: 15.1_

- [x] 31. Add integration tests for netrc
  - Test successful authentication with valid netrc file
  - Test authentication failure without netrc credentials
  - Test netrc disabled with --no-netrc flag
  - Test custom netrc path with --netrc-path
  - Test graceful handling of missing netrc file
  - Test graceful handling of malformed netrc file
  - Test permission validation (600 required)
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

- [x] 32. Update README with netrc documentation
  - Document netrc support and default behavior
  - Provide example netrc file format
  - Document --no-netrc and --netrc-path options
  - Include security note about file permissions
  - _Requirements: 15.1_

- [x] 33. Final checkpoint - Ensure all netrc tests pass
  - Ensure all tests pass, ask the user if questions arise.

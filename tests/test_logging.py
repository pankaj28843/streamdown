"""Tests for logging configuration."""

import logging

from streamdown.infrastructure.logging import configure_logging, get_logger


class TestLoggingConfiguration:
    """Test logging configuration with rich handler."""

    def test_configure_logging_sets_level_debug(self):
        """Test that configure_logging sets debug level correctly."""
        configure_logging("debug")
        logger = logging.getLogger("streamdown")
        assert logger.level == logging.DEBUG

    def test_configure_logging_sets_level_info(self):
        """Test that configure_logging sets info level correctly."""
        configure_logging("info")
        logger = logging.getLogger("streamdown")
        assert logger.level == logging.INFO

    def test_configure_logging_sets_level_warn(self):
        """Test that configure_logging sets warn level correctly."""
        configure_logging("warn")
        logger = logging.getLogger("streamdown")
        assert logger.level == logging.WARNING

    def test_configure_logging_sets_level_warning(self):
        """Test that configure_logging accepts 'warning' as alias for 'warn'."""
        configure_logging("warning")
        logger = logging.getLogger("streamdown")
        assert logger.level == logging.WARNING

    def test_configure_logging_sets_level_error(self):
        """Test that configure_logging sets error level correctly."""
        configure_logging("error")
        logger = logging.getLogger("streamdown")
        assert logger.level == logging.ERROR

    def test_configure_logging_defaults_to_info(self):
        """Test that invalid log level defaults to info."""
        configure_logging("invalid")
        logger = logging.getLogger("streamdown")
        assert logger.level == logging.INFO

    def test_configure_logging_case_insensitive(self):
        """Test that log level is case insensitive."""
        configure_logging("DEBUG")
        logger = logging.getLogger("streamdown")
        assert logger.level == logging.DEBUG

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "streamdown.test_module"

    def test_get_logger_inherits_streamdown_level(self):
        """Test that module loggers inherit streamdown logger level."""
        configure_logging("debug")
        logger = get_logger("test_module")
        # Module logger should inherit from streamdown logger
        assert logger.getEffectiveLevel() == logging.DEBUG

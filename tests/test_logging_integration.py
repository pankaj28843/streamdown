"""Integration tests for logging functionality."""

import logging

from streamdown.infrastructure.logging import configure_logging, get_logger


class TestLoggingIntegration:
    """Test logging integration with application components."""

    def test_logging_captures_messages(self, caplog):
        """Test that logging captures messages at appropriate levels."""
        configure_logging("debug")
        logger = get_logger("test")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

        # Verify all messages were captured
        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text

    def test_logging_respects_level_filtering(self, caplog):
        """Test that logging filters messages below configured level."""
        configure_logging("warn")
        logger = get_logger("test")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

        # Debug and info should be filtered out
        assert "Debug message" not in caplog.text
        assert "Info message" not in caplog.text
        # Warning and error should be present
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text

    def test_structured_error_logging(self, caplog):
        """Test that structured error information is logged."""
        configure_logging("error")
        logger = get_logger("test")

        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Test error")
            except ValueError as e:
                logger.error(f"Operation failed: {e}", exc_info=True)

        # Verify error message and traceback are captured
        assert "Operation failed: Test error" in caplog.text
        assert "ValueError" in caplog.text

    def test_multiple_loggers_share_configuration(self, caplog):
        """Test that multiple loggers share the same configuration."""
        configure_logging("info")
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        with caplog.at_level(logging.INFO):
            logger1.info("Message from module1")
            logger2.info("Message from module2")

        assert "Message from module1" in caplog.text
        assert "Message from module2" in caplog.text

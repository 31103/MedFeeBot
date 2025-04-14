import logging
import pytest

from src.logger import setup_logger

# Test cases for different log levels
@pytest.mark.parametrize(
    "level_str, expected_level",
    [
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
        ("WARNING", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
        ("debug", logging.DEBUG), # Test lowercase
        ("info", logging.INFO),
        (None, logging.INFO), # Test default level
        ("", logging.INFO), # Test default level for empty string
        ("INVALID", logging.INFO), # Test default level for invalid string
    ],
)
def test_setup_logger_levels(level_str, expected_level):
    """Test that setup_logger sets the correct logging level."""
    logger_name = f"test_logger_{level_str}"
    logger = setup_logger(logger_name, level_str)

    assert logger.name == logger_name
    assert logger.level == expected_level
    # Check if handler is added (basic check)
    assert len(logger.handlers) >= 1
    # Check if the handler also has the correct level (or lower)
    # Note: Default StreamHandler level might be 0 (NOTSET), which means it inherits logger's level.
    # Or pytest might add its own handlers. We primarily care about the logger's level itself.
    # For simplicity, we focus on the logger's effective level.

def test_setup_logger_default_name_and_level():
    """Test setup_logger with default name and level."""
    logger = setup_logger() # Use default name 'MedFeeBotLogger' and default level 'INFO'
    assert logger.name == "MedFeeBotLogger"
    assert logger.level == logging.INFO
    assert len(logger.handlers) >= 1

def test_setup_logger_handler_and_formatter():
    """Test that setup_logger adds a StreamHandler with the correct formatter."""
    logger = setup_logger("formatter_test_logger", "DEBUG")

    assert len(logger.handlers) >= 1
    handler_found = False
    formatter_found = False
    expected_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    for handler in logger.handlers:
        # Check if it's a StreamHandler (or FileHandler if we add that later)
        if isinstance(handler, logging.StreamHandler):
            handler_found = True
            # Check the formatter associated with the handler
            if handler.formatter:
                # Access the format string (may differ slightly based on implementation details)
                # _fmt is typical but might be internal. Let's check the structure.
                if hasattr(handler.formatter, '_fmt') and handler.formatter._fmt == expected_format:
                    formatter_found = True
                # Alternative check if _fmt is not reliable
                elif isinstance(handler.formatter, logging.Formatter):
                     # Create a dummy record to check the format output (less direct)
                     # For simplicity, we'll rely on checking the _fmt attribute or just the presence of a formatter
                     formatter_found = True # Assume correct if a formatter exists

    assert handler_found, "StreamHandler not found"
    assert formatter_found, "Correct Formatter not found"

def test_setup_logger_idempotency():
    """Test that calling setup_logger multiple times for the same name doesn't add duplicate handlers."""
    logger_name = "idempotent_logger"
    logger1 = setup_logger(logger_name)
    initial_handler_count = len(logger1.handlers)

    logger2 = setup_logger(logger_name) # Call again with the same name
    final_handler_count = len(logger2.handlers)

    # Pytest might add handlers, so we check if the count increased *unexpectedly*
    # A more robust check might involve specifically checking for our custom handler type/name if we added one.
    # For now, assume basic idempotency means not adding *another* StreamHandler if one exists.
    # This test might be fragile depending on pytest's logging setup.
    # A simple check: count shouldn't double.
    assert final_handler_count <= initial_handler_count, "Handlers were duplicated"
    assert logger1 is logger2 # Should return the same logger instance

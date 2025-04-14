import logging
import sys
# Import the load_config function and Config class
from .config import load_config, Config

DEFAULT_LOGGER_NAME = "MedFeeBotLogger"

def setup_logger(name: str = DEFAULT_LOGGER_NAME, level_str: str | None = None) -> logging.Logger:
    """
    Configures and returns a logger instance.

    Args:
        name (str): The name for the logger.
        level_str (str | None): The desired logging level as a string (e.g., "DEBUG", "INFO").
                                If None, loads config to get the default level.

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger(name)

    # Determine the log level
    final_level_str: str
    if level_str is None:
        # Load config only if level is not explicitly provided
        try:
            cfg = load_config()
            final_level_str = cfg.log_level
        except ValueError as e:
            # Handle case where config loading fails during logger setup
            logging.basicConfig(level=logging.INFO) # Basic fallback
            logger = logging.getLogger(name) # Get logger again after basicConfig
            logger.error(f"Failed to load config for logger level: {e}. Defaulting to INFO.")
            final_level_str = "INFO"
    else:
        final_level_str = str(level_str).upper()

    log_level = getattr(logging, final_level_str, logging.INFO) # Default to INFO if invalid
    logger.setLevel(log_level)

    # Prevent adding duplicate handlers if logger already configured
    if not logger.handlers:
        # Configure formatter
        log_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Configure handler (stdout)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(log_format)
        logger.addHandler(stdout_handler)

        # Optionally add file handler here if needed later
        # file_handler = logging.FileHandler('app.log')
        # file_handler.setFormatter(log_format)
        # logger.addHandler(file_handler)

        logger.debug(f"Logger '{name}' configured with level {logging.getLevelName(log_level)}.")

    return logger

# Create a default logger instance for convenience in other modules
# This will now load the config if needed (specifically for the log level)
logger = setup_logger()

# --- Example: Log output test ---
if __name__ == "__main__":
    # Use the default logger
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical error message.")
    print(f"Default logger '{logger.name}' is set to level '{logging.getLevelName(logger.level)}'.")

    # Create another logger with a different level
    test_logger = setup_logger("TestLogger", "DEBUG")
    test_logger.debug("This is a debug message from TestLogger.")
    print(f"Test logger '{test_logger.name}' is set to level '{logging.getLevelName(test_logger.level)}'.")

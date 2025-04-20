import logging
import sys
# Removed config import to break circular dependency

DEFAULT_LOGGER_NAME = "MedFeeBotLogger"
DEFAULT_LOG_LEVEL = "INFO"

# Global dictionary to hold configured loggers
_loggers = {}

def setup_logger(name: str = DEFAULT_LOGGER_NAME, level_str: str = DEFAULT_LOG_LEVEL) -> logging.Logger:
    """
    Configures and returns a logger instance. Avoids duplicate handlers.
    Log level must be provided.

    Args:
        name (str): The name for the logger.
        level_str (str): The desired logging level as a string (e.g., "DEBUG", "INFO").

    Returns:
        logging.Logger: The configured logger instance.
    """
    if name in _loggers:
        # If logger already exists, just ensure level is set (might change dynamically)
        logger = _loggers[name]
        log_level = getattr(logging, level_str.upper(), logging.INFO)
        if logger.level != log_level:
             logger.setLevel(log_level)
             logger.debug(f"Logger '{name}' level updated to {logging.getLevelName(log_level)}.")
        return logger

    logger = logging.getLogger(name)
    log_level = getattr(logging, level_str.upper(), logging.INFO) # Default to INFO if invalid
    logger.setLevel(log_level)

    # Prevent adding duplicate handlers if logger already configured externally
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

        logger.info(f"Logger '{name}' configured with level {logging.getLevelName(log_level)}.") # Use info level for setup message

    _loggers[name] = logger # Store the configured logger
    return logger

# Remove the default logger instance creation here.
# Modules should call setup_logger() with the desired level from config.
# logger = setup_logger() # REMOVED

# --- Example: Log output test ---
if __name__ == "__main__":
    # Example of how other modules would use it:
    # 1. Load config (in the main execution context)
    # from config import load_config # Assume this works now
    # try:
    #     cfg = load_config()
    #     log_level = cfg.log_level
    # except Exception as e:
    #     print(f"Error loading config: {e}")
    #     log_level = DEFAULT_LOG_LEVEL

    # 2. Setup logger with the level from config
    # logger = setup_logger(level_str=log_level)

    # For direct execution test, setup manually:
    logger_main = setup_logger(DEFAULT_LOGGER_NAME, "DEBUG") # Set level explicitly for test

    logger_main.debug("This is a debug message.")
    logger_main.info("This is an info message.")
    logger_main.warning("This is a warning message.")
    logger_main.error("This is an error message.")
    logger_main.critical("This is a critical error message.")
    print(f"Default logger '{logger_main.name}' is set to level '{logging.getLevelName(logger_main.level)}'.")

    # Create another logger
    test_logger = setup_logger("TestLogger", "INFO")
    test_logger.debug("This debug message from TestLogger should NOT appear.")
    test_logger.info("This info message from TestLogger SHOULD appear.")
    print(f"Test logger '{test_logger.name}' is set to level '{logging.getLevelName(test_logger.level)}'.")

    # Get the default logger again, should return the same instance
    logger_main_again = setup_logger(DEFAULT_LOGGER_NAME)
    print(f"Got logger '{logger_main_again.name}' again, level is '{logging.getLevelName(logger_main_again.level)}'.")
    assert logger_main is logger_main_again

import functions_framework
import flask
from .config import load_config, Config # Import load_config and Config
from .logger import logger
from . import fetcher
from . import parser
from . import storage
from . import notifier


def run_check(cfg: Config) -> bool:
    """
    Core logic: Fetches HTML, extracts PDF links, finds new ones, and notifies Slack.

    Args:
        cfg (Config): The application configuration.

    Returns:
        bool: True if the process completed without fatal errors, False otherwise.
    """
    logger.info("run_check: Starting check process.")
    try:
        # cfg = load_config() # Config is now passed as an argument

        # 1. Fetch HTML content
        html_content = fetcher.fetch_html(cfg) # Pass config object
        if not html_content:
            # Error logged in fetcher, potentially send admin alert
            notifier.send_admin_alert(f"HTML fetch failed: {cfg.target_url}", config=cfg) # Pass config
            logger.error("HTML fetch failed, aborting run_check.")
            return False # Indicate failure

        # 2. Extract PDF links from HTML
        current_pdf_links = parser.extract_pdf_links(html_content, cfg.target_url) # Pass target_url from cfg

        # 3. Find new PDF links by comparing with stored list (GCS)
        # This function now requires the config object
        new_urls = storage.find_new_urls(current_pdf_links, cfg) # Pass config

        # 4. Notify Slack if new links are found
        if new_urls:
            # Pass config to notifier as well, it might need it for admin alerts
            notifier.send_slack_notification(sorted(list(new_urls)), cfg) # Pass config
        else:
            logger.info("No new PDFs found. No Slack notification sent.")

        logger.info("run_check: Process completed successfully.")
        return True # Indicate success

    except Exception as e:
        # Catch unexpected errors during the process
        logger.exception(f"run_check: An unexpected error occurred: {e}")
        # Send admin alert, passing config if available (might fail if config load failed earlier)
        try:
            notifier.send_admin_alert(f"run_check: An unexpected error occurred.", error=e, config=cfg)
        except Exception as alert_e:
            logger.error(f"Failed to send admin alert about the error: {alert_e}")
        return False # Indicate failure


@functions_framework.http
def main_gcf(request: flask.Request):
    """
    Google Cloud Functions entry point (HTTP Trigger).
    Loads configuration and executes the main check logic.

    Args:
        request (flask.Request): The HTTP request object (not used directly).

    Returns:
        A tuple containing the response text and HTTP status code.
    """
    logger.info("Cloud Function execution started (HTTP Trigger).")
    try:
        # Load configuration for this function invocation
        function_config = load_config()
    except ValueError as e:
        logger.error(f"Configuration error in Cloud Function: {e}")
        # Return 500 Internal Server Error if config fails
        return (f"Configuration error: {e}", 500)
    except Exception as e:
        logger.exception(f"Unexpected error during config loading in Cloud Function: {e}")
        return (f"Unexpected configuration error: {e}", 500)

    # Execute the core logic
    success = run_check(function_config)

    if success:
        logger.info("Cloud Function execution finished successfully.")
        return ("Function executed successfully.", 200)
    else:
        logger.error("Cloud Function execution finished with errors.")
        # run_check already logged the specific error and sent admin alert
        return ("Function execution failed. Check logs.", 500)


if __name__ == "__main__":
    # Entry point for running the script directly (e.g., for local testing)
    logger.info("Script execution started directly.")
    try:
        main_config = load_config()
        success = run_check(main_config)
        if success:
            logger.info("Script execution finished successfully.")
        else:
            logger.error("Script execution finished with errors.")
            exit(1) # Exit with error code if run_check failed
    except ValueError as e: # Catch config loading errors specifically
        logger.error(f"Configuration error: {e}")
        exit(1)
    except Exception as e: # Catch any other unexpected errors during setup
        logger.exception(f"An unexpected error occurred during script execution: {e}")
        exit(1)

import functions_framework
import flask
from .config import load_config, Config # Import load_config and Config
from .logger import logger
from . import fetcher
from . import parser
from . import storage
from . import notifier


def process_url(url: str, cfg: Config) -> bool:
    """
    Processes a single URL based on its configuration: fetches, parses, detects changes, and notifies.

    Args:
        url (str): The URL to process.
        cfg (Config): The application configuration.

    Returns:
        bool: True if the URL was processed successfully (even if no changes found), False if an error occurred.
    """
    logger.info(f"Processing URL: {url}")
    url_config = cfg.url_configs.get(url)

    if not url_config:
        logger.warning(f"No configuration found for URL: {url}. Skipping.")
        return False # Indicate failure for this URL

    monitor_type = url_config.get('type')
    parser_func = url_config.get('parser')

    if not monitor_type or not callable(parser_func):
        logger.error(f"Invalid configuration for URL {url}: 'type' or 'parser' missing or invalid. Skipping.")
        return False # Indicate failure

    # 1. Fetch HTML
    try:
        html_content = fetcher.fetch_html(
            url=url,
            timeout=cfg.request_timeout,
            retries=cfg.request_retries,
            delay=cfg.request_retry_delay
        )
        if not html_content:
            notifier.send_admin_alert(f"HTML fetch failed: {url}", config=cfg)
            logger.error(f"HTML fetch failed for {url}.")
            return False # Indicate failure
    except Exception as e:
        logger.exception(f"Error fetching HTML for {url}: {e}")
        notifier.send_admin_alert(f"HTML fetch error for {url}", error=e, config=cfg)
        return False

    # 2. Parse HTML
    try:
        parse_result = parser_func(html_content, url)
        # Parser functions should return None on error, or the expected data structure
        if parse_result is None and monitor_type == 'meeting': # Meeting parser returns None on error/no table
             logger.warning(f"Parser returned None for meeting URL: {url}. Assuming no meeting data found or parse error.")
             # For meetings, None might be a valid state (no table yet), treat as success for this step.
             # If it was an actual parse error, it should have been logged by the parser.
        elif parse_result is None and monitor_type == 'pdf': # PDF parser returns list, None indicates error
             logger.error(f"Parser returned None (error) for PDF URL: {url}.")
             notifier.send_admin_alert(f"Parser error for PDF URL: {url}", config=cfg)
             return False # Indicate failure
        # Proceed if parse_result is not None (or if it's None for a meeting type)

    except Exception as e:
        logger.exception(f"Error executing parser for {url}: {e}")
        notifier.send_admin_alert(f"Parser execution error for {url}", error=e, config=cfg)
        return False

    # 3. Process based on type
    try:
        if monitor_type == 'pdf':
            if not isinstance(parse_result, list):
                 logger.error(f"Parser for PDF URL {url} did not return a list. Got: {type(parse_result)}")
                 return False
            document_infos = parse_result
            current_pdf_urls = {doc['url'] for doc in document_infos if isinstance(doc, dict) and 'url' in doc}
            new_pdf_urls = storage.find_new_pdf_urls(url, current_pdf_urls, cfg)

            if new_pdf_urls:
                new_documents = [doc for doc in document_infos if isinstance(doc, dict) and doc.get('url') in new_pdf_urls]
                logger.info(f"Found {len(new_documents)} new PDF documents for {url}. Sending notification...")
                notification_payload = {'type': 'pdf', 'data': new_documents, 'source_url': url}
                notifier.send_slack_notification(notification_payload, cfg)
            else:
                logger.info(f"No new PDF documents found for {url}.")

        elif monitor_type == 'meeting':
             if parse_result is None:
                 logger.info(f"No meeting data parsed for {url}. Skipping meeting check.")
                 return True # Not an error state if parser correctly returned None

             if not isinstance(parse_result, dict):
                 logger.error(f"Parser for meeting URL {url} did not return a dictionary. Got: {type(parse_result)}")
                 return False

             meeting_info = parse_result
             latest_meeting_id = meeting_info.get('id')

             if not latest_meeting_id:
                 logger.error(f"Meeting parser for {url} returned data without an 'id'. Data: {meeting_info}")
                 return False # Invalid data from parser

             # Load and save meeting IDs within the meeting check block
             all_latest_ids = storage.load_latest_meeting_ids(cfg)
             previous_meeting_id = all_latest_ids.get(url)

             if latest_meeting_id != previous_meeting_id:
                 logger.info(f"New meeting detected for {url}: ID changed from '{previous_meeting_id}' to '{latest_meeting_id}'. Sending notification...")
                 notification_payload = {'type': 'meeting', 'data': meeting_info, 'source_url': url}
                 notifier.send_slack_notification(notification_payload, cfg)

                 # Update and save the state
                 all_latest_ids[url] = latest_meeting_id
                 storage.save_latest_meeting_ids(all_latest_ids, cfg)
             else:
                 logger.info(f"No new meeting detected for {url} (Latest ID: {latest_meeting_id}).")

        else:
            logger.error(f"Unknown monitor type '{monitor_type}' for URL {url}. Skipping.")
            return False # Indicate failure

    except Exception as e:
        logger.exception(f"Error during {monitor_type} processing for {url}: {e}")
        notifier.send_admin_alert(f"Error during {monitor_type} processing for {url}", error=e, config=cfg)
        return False

    logger.info(f"Successfully processed URL: {url}")
    return True # Indicate success for this URL


def run_check(cfg: Config) -> bool:
    """
    Core logic: Iterates through configured URLs, processes each one,
    and aggregates the success status.

    Args:
        cfg (Config): The application configuration.

    Returns:
        bool: True if all configured URLs were processed without fatal errors, False otherwise.
    """
    logger.info("run_check: Starting check process for all configured URLs.")
    overall_success = True

    for url in cfg.target_urls:
        try:
            success = process_url(url, cfg)
            if not success:
                overall_success = False
                # Error for this specific URL is already logged by process_url
                logger.warning(f"Processing failed for URL: {url}")
        except Exception as e:
            # Catch unexpected errors during the processing of a single URL
            logger.exception(f"run_check: An unexpected error occurred while processing URL {url}: {e}")
            try:
                notifier.send_admin_alert(f"run_check: Unexpected error processing URL {url}", error=e, config=cfg)
            except Exception as alert_e:
                logger.error(f"Failed to send admin alert about the error during URL processing: {alert_e}")
            overall_success = False # Mark overall process as failed

    if overall_success:
        logger.info("run_check: Process completed successfully for all URLs.")
    else:
        logger.warning("run_check: Process completed, but errors occurred for one or more URLs.")

    return overall_success


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

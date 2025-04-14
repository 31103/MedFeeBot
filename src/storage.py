import json
from typing import Set
from google.cloud import storage
from google.cloud.exceptions import NotFound
from .logger import logger
from .config import Config # Import Config class

# GCS Client (initialized once per function invocation if needed)
storage_client = None

def _get_gcs_client():
    """Initializes and returns a GCS client."""
    global storage_client
    if storage_client is None:
        storage_client = storage.Client()
    return storage_client

def load_known_urls(config: Config) -> Set[str]:
    """
    Loads the list of known PDF URLs from Google Cloud Storage.

    Args:
        config (Config): Application configuration containing GCS details.

    Returns:
        Set[str]: Set of known URLs. Returns an empty set if the GCS object
                  doesn't exist (first run) or if GCS config is missing.

    Raises:
        ValueError: If GCS configuration is missing.
        Exception: For GCS download or JSON parsing errors (treated as fatal).
    """
    if not config.gcs_bucket_name or not config.gcs_object_name:
        logger.error("GCS bucket name or object name is not configured.")
        # Consider if falling back to local is desired for some scenarios,
        # but for Cloud Functions, this should likely be an error.
        raise ValueError("GCS configuration missing in Config object.")

    client = _get_gcs_client()
    bucket = client.bucket(config.gcs_bucket_name)
    blob = bucket.blob(config.gcs_object_name)
    known_urls: Set[str] = set()
    is_first_run = False

    try:
        logger.info(f"Attempting to load known URLs from gs://{config.gcs_bucket_name}/{config.gcs_object_name}")
        json_data = blob.download_as_string()
        urls_list = json.loads(json_data)
        if isinstance(urls_list, list):
            known_urls = set(urls_list)
            logger.info(f"Loaded {len(known_urls)} known URLs from GCS.")
        else:
            logger.error(f"Invalid format in GCS object gs://{config.gcs_bucket_name}/{config.gcs_object_name}. Expected a JSON list.")
            # Treat as fatal error as the state is corrupted
            raise ValueError("Invalid data format in GCS object.")
    except NotFound:
        logger.info(f"GCS object gs://{config.gcs_bucket_name}/{config.gcs_object_name} not found. Assuming first run.")
        is_first_run = True # Indicate first run based on file not found
        # Return empty set, saving will happen in find_new_urls if needed
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from GCS object gs://{config.gcs_bucket_name}/{config.gcs_object_name}: {e}")
        # Treat as fatal error
        raise ValueError("Failed to decode JSON from GCS object.") from e
    except Exception as e:
        logger.exception(f"Unexpected error loading known URLs from GCS: {e}")
        # Treat other GCS errors as fatal for loading
        raise # Re-raise the original exception

    # Return both the set and a flag indicating if it was the first run
    # The flag isn't strictly needed by the caller currently, but might be useful
    return known_urls #, is_first_run


def save_known_urls(urls_to_save: Set[str], config: Config):
    """
    Saves the list of known PDF URLs to Google Cloud Storage as a JSON list.

    Args:
        urls_to_save (Set[str]): The set of URLs to save.
        config (Config): Application configuration containing GCS details.

    Raises:
        ValueError: If GCS configuration is missing.
        Exception: For GCS upload errors (logged but allows continuation).
    """
    if not config.gcs_bucket_name or not config.gcs_object_name:
        logger.error("GCS bucket name or object name is not configured. Cannot save URLs.")
        raise ValueError("GCS configuration missing in Config object.")

    client = _get_gcs_client()
    bucket = client.bucket(config.gcs_bucket_name)
    blob = bucket.blob(config.gcs_object_name)

    try:
        urls_list = sorted(list(urls_to_save))
        json_data = json.dumps(urls_list, ensure_ascii=False, indent=2)
        blob.upload_from_string(json_data, content_type='application/json')
        logger.info(f"Saved {len(urls_list)} known URLs to gs://{config.gcs_bucket_name}/{config.gcs_object_name}")
    except Exception as e:
        logger.exception(f"Failed to save known URLs to GCS: {e}")
        # Do not raise here, allow the main process to continue if possible
        # Consider sending an admin notification here
        # notifier.send_admin_alert("Failed to save known URLs to GCS", error=e, config=config)


def find_new_urls(current_urls: Set[str], config: Config) -> Set[str]:
    """
    Compares current URLs with known URLs from GCS to find new ones.
    Handles the first run scenario and updates the known URLs list on GCS.

    Args:
        current_urls (Set[str]): Set of URLs found in the current fetch.
        config (Config): Application configuration.

    Returns:
        Set[str]: Set of newly found URLs.
    """
    known_urls: Set[str] = set()
    is_first_run_check = False
    try:
        # Load known URLs. This might raise exceptions for fatal GCS read errors.
        known_urls = load_known_urls(config)
    except NotFound: # Explicitly catch NotFound which indicates first run
         logger.info("find_new_urls: load_known_urls indicated first run (file not found).")
         is_first_run_check = True
    except ValueError as e: # Catch config errors or fatal load errors from load_known_urls
         logger.error(f"find_new_urls: Failed to load configuration or known URLs: {e}")
         return set() # Cannot proceed without known URLs or config
    except Exception as e: # Catch other unexpected load errors
         logger.exception(f"find_new_urls: Unexpected error loading known URLs: {e}")
         return set() # Cannot proceed

    # Determine new URLs
    new_urls = current_urls - known_urls

    # Handle first run or new URLs found
    if is_first_run_check and current_urls:
        logger.info("First run detected. Saving current URLs as known URLs. No notifications will be sent for these.")
        try:
            save_known_urls(current_urls, config)
        except Exception as e:
            # Logged in save_known_urls, but log context here too
            logger.error(f"find_new_urls: Failed to save known URLs during first run: {e}")
            # Even if save fails on first run, return empty set as per logic
        return set() # No "new" URLs on the very first run
    elif new_urls:
        logger.info(f"Found {len(new_urls)} new URLs.")
        updated_known_urls = known_urls.union(new_urls)
        try:
            save_known_urls(updated_known_urls, config)
        except Exception as e:
            # Logged in save_known_urls, but log context here too
            logger.error(f"find_new_urls: Failed to save updated known URLs, but proceeding with found new URLs: {e}")
            # Proceed to return new_urls even if save failed
    else:
        logger.info("No new URLs found.")

    return new_urls

# --- Example Usage (Requires GCS setup and authentication) ---
# if __name__ == "__main__":
#     # This block needs significant changes to work with GCS.
#     # It requires loading a valid Config object, potentially mocking GCS,
#     # or running against a real GCS bucket with proper authentication.
#     # Consider moving this logic to integration tests.
#
#     # from config import load_config
#     # try:
#     #     test_config = load_config() # Needs env vars for GCS bucket/object
#     # except ValueError as e:
#     #     print(f"Failed to load config for testing: {e}")
#     #     exit(1)
#
#     # # Dummy URLs for testing
#     # urls1 = {"http://example.com/gcs_a.pdf", "http://example.com/gcs_b.pdf"}
#     # urls2 = {"http://example.com/gcs_b.pdf", "http://example.com/gcs_c.pdf"}
#
#     # # Need to manage GCS state (e.g., delete object before first run)
#     # print("--- GCS Test Run 1 (First Run Scenario) ---")
#     # # Ensure the GCS object does not exist before this call
#     # new1 = find_new_urls(urls1, test_config)
#     # print(f"New URLs (Run 1): {new1}") # Should be empty
#     # print(f"Known URLs after Run 1: {load_known_urls(test_config)}") # Should be urls1
#
#     # print("\n--- GCS Test Run 2 ---")
#     # new2 = find_new_urls(urls2, test_config)
#     # print(f"New URLs (Run 2): {new2}") # Should be {'http://example.com/gcs_c.pdf'}
#     # print(f"Known URLs after Run 2: {load_known_urls(test_config)}") # Should be urls1 U urls2

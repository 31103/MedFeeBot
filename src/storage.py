import json
import os
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
    Loads the list of known PDF URLs from Google Cloud Storage or a local file.

    Args:
        config (Config): Application configuration.

    Returns:
        Set[str]: Set of known URLs. Returns an empty set if the storage object/file
                  doesn't exist (first run) or if configuration is missing for the chosen method.

    Raises:
        Exception: For storage download or JSON parsing errors (treated as fatal for GCS).
    """
    known_urls: Set[str] = set()

    if config.gcs_bucket_name and config.gcs_object_name:
        # Use GCS
        client = _get_gcs_client()
        bucket = client.bucket(config.gcs_bucket_name)
        blob = bucket.blob(config.gcs_object_name)

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
            # Return empty set, saving will happen in find_new_urls if needed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from GCS object gs://{config.gcs_bucket_name}/{config.gcs_object_name}: {e}")
            # Treat as fatal error
            raise ValueError("Failed to decode JSON from GCS object.") from e
        except Exception as e:
            logger.exception(f"Unexpected error loading known URLs from GCS: {e}")
            # Treat other GCS errors as fatal for loading
            raise # Re-raise the original exception
    elif config.known_urls_file_path:
        # Use local file
        file_path = config.known_urls_file_path
        try:
            logger.info(f"Attempting to load known URLs from local file: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                urls_list = json.load(f)
                if isinstance(urls_list, list):
                    known_urls = set(urls_list)
                    logger.info(f"Loaded {len(known_urls)} known URLs from local file.")
                else:
                    logger.error(f"Invalid format in local file {file_path}. Expected a JSON list.")
                    # Log error but don't raise, treat as empty known URLs
        except FileNotFoundError:
            logger.info(f"Local file {file_path} not found. Assuming first run.")
            # Return empty set, saving will happen in find_new_urls if needed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from local file {file_path}: {e}")
            # Log error but don't raise, treat as empty known URLs
        except Exception as e:
            logger.exception(f"Unexpected error loading known URLs from local file: {e}")
            # Log error but don't raise, treat as empty known URLs
    else:
        # Neither GCS nor local file path is configured
        logger.error("Neither GCS configuration nor local file path is configured for known URLs storage.")
        # Depending on desired behavior, could raise an error here.
        # For now, return empty set and log error.
        return set()


    return known_urls


def save_known_urls(urls_to_save: Set[str], config: Config):
    """
    Saves the list of known PDF URLs to Google Cloud Storage or a local file.

    Args:
        urls_to_save (Set[str]): The set of URLs to save.
        config (Config): Application configuration.

    Raises:
        Exception: For storage upload errors (logged but allows continuation).
    """
    if config.gcs_bucket_name and config.gcs_object_name:
        # Use GCS
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
    elif config.known_urls_file_path:
        # Use local file
        file_path = config.known_urls_file_path
        try:
            logger.info(f"Attempting to save known URLs to local file: {file_path}")
            # Ensure directory exists if path includes a directory
            dir_name = os.path.dirname(file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            urls_list = sorted(list(urls_to_save))
            json_data = json.dumps(urls_list, ensure_ascii=False, indent=2)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            logger.info(f"Saved {len(urls_list)} known URLs to local file: {file_path}")
        except Exception as e:
            logger.exception(f"Failed to save known URLs to local file {file_path}: {e}")
            # Log error but don't raise
    else:
        # Neither GCS nor local file path is configured
        logger.error("Neither GCS configuration nor local file path is configured for known URLs storage. Cannot save URLs.")


def find_new_urls(current_urls: Set[str], config: Config) -> Set[str]:
    """
    Compares current URLs with known URLs from storage to find new ones.
    Handles the first run scenario and updates the known URLs list.

    Args:
        current_urls (Set[str]): Set of URLs found in the current fetch.
        config (Config): Application configuration.

    Returns:
        Set[str]: Set of newly found URLs.
    """
    known_urls: Set[str] = set()
    is_first_run_check = False # This flag is now less critical as load_known_urls handles file not found

    try:
        # Load known URLs. This function now handles both GCS and local files
        known_urls = load_known_urls(config)
        # If load_known_urls returned an empty set AND current_urls is not empty,
        # and it wasn't due to a fatal error (like GCS JSON decode error),
        # we can infer this might be a first run or empty state.
        # A more robust check might involve checking the size of the loaded set.
        # For simplicity, we'll rely on the logic below which handles the union.

    except ValueError as e: # Catch fatal errors from load_known_urls (currently only GCS JSON decode)
         logger.error(f"find_new_urls: Fatal error loading known URLs: {e}")
         return set() # Cannot proceed

    except Exception as e: # Catch other unexpected load errors
         logger.exception(f"find_new_urls: Unexpected error loading known URLs: {e}")
         # Depending on severity, might return set() or proceed with empty known_urls
         # Proceeding with empty set allows finding all current_urls as new
         known_urls = set() # Ensure known_urls is an empty set if loading failed


    # Determine new URLs
    new_urls = current_urls - known_urls

    # If there are current URLs and no known URLs were loaded (or loading failed non-fatally),
    # treat this as a potential first run or reset and save the current URLs.
    # This logic is simplified; a true first run check might be more explicit.
    if current_urls and not known_urls:
         logger.info("No known URLs loaded. Saving current URLs as known URLs. No notifications will be sent for these.")
         try:
             save_known_urls(current_urls, config)
         except Exception as e:
             logger.error(f"find_new_urls: Failed to save known URLs during initial save: {e}")
         return set() # No "new" URLs on the initial save

    elif new_urls:
        logger.info(f"Found {len(new_urls)} new URLs.")
        updated_known_urls = known_urls.union(new_urls)
        try:
            save_known_urls(updated_known_urls, config)
        except Exception as e:
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

import json
import os
from typing import Set, Dict, List, Optional # Dict, List, Optional を追加
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

def load_known_urls(config: Config) -> Dict[str, List[str]]:
    """
    Loads the dictionary of known PDF URLs keyed by target URL
    from Google Cloud Storage or a local file.

    Args:
        config (Config): Application configuration.

    Returns:
        Dict[str, List[str]]: Dictionary where keys are target URLs and values are lists of known PDF URLs.
                               Returns an empty dictionary if the storage object/file doesn't exist,
                               is invalid, or configuration is missing.

    Raises:
        Exception: For critical storage download errors (treated as fatal for GCS).
                   JSON parsing errors or invalid format errors are logged but return an empty dict.
    """
    known_urls_dict: Dict[str, List[str]] = {}
    # Use the specific filename from config (assuming config.known_urls_file exists)
    storage_path = getattr(config, 'known_urls_file', None)

    if config.gcs_bucket_name and storage_path:
        # Use GCS
        client = _get_gcs_client()
        bucket = client.bucket(config.gcs_bucket_name)
        blob = bucket.blob(storage_path) # Use storage_path as object name

        try:
            logger.info(f"Attempting to load known PDF URLs from gs://{config.gcs_bucket_name}/{storage_path}")
            json_data = blob.download_as_string()
            loaded_data = json.loads(json_data)
            if isinstance(loaded_data, dict):
                # Validate structure: keys are strings, values are lists of strings
                valid_data = True
                temp_dict = {}
                for key, value in loaded_data.items():
                    if isinstance(key, str) and isinstance(value, list) and all(isinstance(item, str) for item in value):
                         temp_dict[key] = value # Keep as list
                    else:
                        valid_data = False
                        logger.error(f"Invalid structure in known_urls data for key '{key}'. Expected list of strings as value.")
                        break
                if valid_data:
                    known_urls_dict = temp_dict
                    logger.info(f"Loaded known PDF URLs for {len(known_urls_dict)} target URLs from GCS.")
                else:
                     logger.error(f"Invalid format in GCS object gs://{config.gcs_bucket_name}/{storage_path}. Expected a JSON dictionary of string keys to list-of-string values.")
                     # Treat format error as non-fatal, return empty dict
            else:
                logger.error(f"Invalid format in GCS object gs://{config.gcs_bucket_name}/{storage_path}. Expected a JSON dictionary.")
                # Treat format error as non-fatal, return empty dict
        except NotFound:
            logger.info(f"GCS object gs://{config.gcs_bucket_name}/{storage_path} not found. Assuming first run or empty state.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from GCS object gs://{config.gcs_bucket_name}/{storage_path}: {e}")
            # Treat JSON decode error as non-fatal, return empty dict
        except Exception as e:
            logger.exception(f"Unexpected error loading known PDF URLs from GCS: {e}")
            # Treat other GCS errors as fatal for loading
            raise # Re-raise the original exception
    # Local file handling needs adjustment if config structure changes
    # Assuming config.known_urls_file is just the filename, and local path needs construction
    elif storage_path: # Check if filename is provided
        # Construct local path (e.g., in a 'data' directory or similar)
        # For now, assume it's relative to the execution directory.
        local_file_path = storage_path # Simplistic assumption
        try:
            logger.info(f"Attempting to load known PDF URLs from local file: {local_file_path}")
            with open(local_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                     # Validate structure (similar to GCS)
                    valid_data = True
                    temp_dict = {}
                    for key, value in loaded_data.items():
                        if isinstance(key, str) and isinstance(value, list) and all(isinstance(item, str) for item in value):
                            temp_dict[key] = value
                        else:
                            valid_data = False
                            logger.error(f"Invalid structure in local known_urls data for key '{key}'.")
                            break
                    if valid_data:
                        known_urls_dict = temp_dict
                        logger.info(f"Loaded known PDF URLs for {len(known_urls_dict)} target URLs from local file.")
                    else:
                        logger.error(f"Invalid format in local file {local_file_path}. Expected a dict of string: list[string].")
                else:
                    logger.error(f"Invalid format in local file {local_file_path}. Expected a JSON dictionary.")
        except FileNotFoundError:
            logger.info(f"Local file {local_file_path} not found. Assuming first run or empty state.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from local file {local_file_path}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error loading known PDF URLs from local file: {e}")
            # Log error but don't raise, treat as empty known URLs
    else:
        # Check if the old local file path exists for backward compatibility or specific local setup
        old_local_path = getattr(config, 'known_urls_file_path', None)
        if old_local_path:
             logger.warning(f"Using deprecated 'known_urls_file_path': {old_local_path}. Consider migrating to 'known_urls_file'.")
             # Attempt to load from old path (logic similar to above)
             try:
                 with open(old_local_path, 'r', encoding='utf-8') as f:
                     # ... (validation logic as above) ...
                     pass # Placeholder for duplicated validation logic
             except FileNotFoundError:
                 logger.info(f"Local file {old_local_path} not found.")
             except Exception as e:
                 logger.exception(f"Error loading from {old_local_path}: {e}")
        else:
            logger.error("Storage path (known_urls_file) is not configured.")

    return known_urls_dict


def save_known_urls(known_urls_dict: Dict[str, List[str]], config: Config):
    """
    Saves the dictionary of known PDF URLs (keyed by target URL)
    to Google Cloud Storage or a local file.

    Args:
        known_urls_dict (Dict[str, List[str]]): The dictionary of URLs to save.
        config (Config): Application configuration.
    """
    storage_path = getattr(config, 'known_urls_file', None)

    # Sort lists within the dictionary for consistent output (optional but good practice)
    sorted_dict = {url: sorted(pdf_list) for url, pdf_list in known_urls_dict.items()}

    if config.gcs_bucket_name and storage_path:
        # Use GCS
        client = _get_gcs_client()
        bucket = client.bucket(config.gcs_bucket_name)
        blob = bucket.blob(storage_path) # Use storage_path as object name

        try:
            json_data = json.dumps(sorted_dict, ensure_ascii=False, indent=2)
            blob.upload_from_string(json_data, content_type='application/json')
            logger.info(f"Saved known PDF URLs for {len(sorted_dict)} target URLs to gs://{config.gcs_bucket_name}/{storage_path}")
        except Exception as e:
            logger.exception(f"Failed to save known PDF URLs to GCS: {e}")
            # Consider admin notification
    elif storage_path:
        # Use local file (assuming relative path)
        local_file_path = storage_path
        try:
            logger.info(f"Attempting to save known PDF URLs to local file: {local_file_path}")
            dir_name = os.path.dirname(local_file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            json_data = json.dumps(sorted_dict, ensure_ascii=False, indent=2)
            with open(local_file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            logger.info(f"Saved known PDF URLs for {len(sorted_dict)} target URLs to local file: {local_file_path}")
        except Exception as e:
            logger.exception(f"Failed to save known PDF URLs to local file {local_file_path}: {e}")
    else:
         # Check if the old local file path exists for backward compatibility or specific local setup
        old_local_path = getattr(config, 'known_urls_file_path', None)
        if old_local_path:
             logger.warning(f"Using deprecated 'known_urls_file_path' for saving: {old_local_path}. Consider migrating to 'known_urls_file'.")
             # Attempt to save to old path (logic similar to above)
             try:
                 dir_name = os.path.dirname(old_local_path)
                 if dir_name:
                     os.makedirs(dir_name, exist_ok=True)
                 json_data = json.dumps(sorted_dict, ensure_ascii=False, indent=2)
                 with open(old_local_path, 'w', encoding='utf-8') as f:
                     f.write(json_data)
                 logger.info(f"Saved known PDF URLs for {len(sorted_dict)} target URLs to local file: {old_local_path}")
             except Exception as e:
                 logger.exception(f"Failed to save known PDF URLs to local file {old_local_path}: {e}")
        else:
            logger.error("Storage path (known_urls_file) is not configured. Cannot save known URLs.")


def find_new_pdf_urls(target_url: str, current_pdf_urls: Set[str], config: Config) -> Set[str]:
    """
    Compares current PDF URLs for a specific target URL with the known URLs from storage.
    Handles the first run scenario for the target URL and updates the known URLs dictionary.

    Args:
        target_url (str): The specific URL being checked.
        current_pdf_urls (Set[str]): Set of PDF URLs found in the current fetch for the target_url.
        config (Config): Application configuration.

    Returns:
        Set[str]: Set of newly found PDF URLs for the target_url.
    """
    all_known_urls_dict: Dict[str, List[str]] = {}
    new_urls_for_target: Set[str] = set()

    try:
        all_known_urls_dict = load_known_urls(config)
    except Exception as e: # Catch fatal GCS load errors
        logger.error(f"find_new_pdf_urls: Fatal error loading known URLs, cannot proceed for {target_url}: {e}")
        return set() # Cannot determine new URLs

    known_urls_for_target: Set[str] = set(all_known_urls_dict.get(target_url, [])) # Get known URLs for this specific target

    new_urls_for_target = current_pdf_urls - known_urls_for_target

    # Check if this target URL is new or if there are new PDFs for it
    target_needs_update = False
    if target_url not in all_known_urls_dict and current_pdf_urls:
        logger.info(f"'{target_url}' is a new target URL or has no previous known URLs. Saving current PDFs. No notification for these.")
        all_known_urls_dict[target_url] = sorted(list(current_pdf_urls))
        target_needs_update = True
        new_urls_for_target = set() # No "new" URLs to notify on first save for this target
    elif new_urls_for_target:
        logger.info(f"Found {len(new_urls_for_target)} new PDF URLs for '{target_url}'.")
        updated_known_for_target = known_urls_for_target.union(new_urls_for_target)
        all_known_urls_dict[target_url] = sorted(list(updated_known_for_target))
        target_needs_update = True
    else:
        logger.info(f"No new PDF URLs found for '{target_url}'.")

    # Save the entire dictionary back if an update occurred
    if target_needs_update:
        try:
            save_known_urls(all_known_urls_dict, config)
        except Exception as e:
            logger.error(f"find_new_pdf_urls: Failed to save updated known URLs dictionary after processing '{target_url}', but proceeding. Error: {e}")
            # Proceed to return new_urls_for_target even if save failed

    return new_urls_for_target


# --- Functions for Meeting ID State ---

def load_latest_meeting_ids(config: Config) -> Dict[str, str]:
    """
    Loads the dictionary of latest meeting IDs keyed by target URL
    from Google Cloud Storage or a local file.

    Args:
        config (Config): Application configuration.

    Returns:
        Dict[str, str]: Dictionary where keys are target URLs and values are the latest meeting IDs.
                        Returns an empty dictionary if the storage object/file doesn't exist,
                        is invalid, or configuration is missing.
    """
    latest_ids_dict: Dict[str, str] = {}
    storage_path = getattr(config, 'latest_ids_file', None) # Use the specific filename from config

    if config.gcs_bucket_name and storage_path:
        # Use GCS
        client = _get_gcs_client()
        bucket = client.bucket(config.gcs_bucket_name)
        blob = bucket.blob(storage_path)

        try:
            logger.info(f"Attempting to load latest meeting IDs from gs://{config.gcs_bucket_name}/{storage_path}")
            json_data = blob.download_as_string()
            loaded_data = json.loads(json_data)
            if isinstance(loaded_data, dict):
                 # Validate structure: keys are strings, values are strings
                valid_data = True
                temp_dict = {}
                for key, value in loaded_data.items():
                    if isinstance(key, str) and isinstance(value, str):
                        temp_dict[key] = value
                    else:
                        valid_data = False
                        logger.error(f"Invalid structure in latest_ids data for key '{key}'. Expected string value.")
                        break
                if valid_data:
                    latest_ids_dict = temp_dict
                    logger.info(f"Loaded latest meeting IDs for {len(latest_ids_dict)} target URLs from GCS.")
                else:
                    logger.error(f"Invalid format in GCS object gs://{config.gcs_bucket_name}/{storage_path}. Expected a JSON dictionary of string: string.")
            else:
                logger.error(f"Invalid format in GCS object gs://{config.gcs_bucket_name}/{storage_path}. Expected a JSON dictionary.")
        except NotFound:
            logger.info(f"GCS object gs://{config.gcs_bucket_name}/{storage_path} not found. Assuming empty state.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from GCS object gs://{config.gcs_bucket_name}/{storage_path}: {e}")
        except Exception as e:
            # Treat GCS errors other than NotFound as potentially critical for loading state
            logger.exception(f"Unexpected error loading latest meeting IDs from GCS: {e}")
            # Depending on policy, could raise or return empty dict. Returning empty dict for now.
            # raise # Or return {}
    elif storage_path:
        # Use local file (assuming relative path)
        local_file_path = storage_path
        try:
            logger.info(f"Attempting to load latest meeting IDs from local file: {local_file_path}")
            with open(local_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    # Validate structure
                    valid_data = True
                    temp_dict = {}
                    for key, value in loaded_data.items():
                        if isinstance(key, str) and isinstance(value, str):
                            temp_dict[key] = value
                        else:
                            valid_data = False
                            logger.error(f"Invalid structure in local latest_ids data for key '{key}'.")
                            break
                    if valid_data:
                        latest_ids_dict = temp_dict
                        logger.info(f"Loaded latest meeting IDs for {len(latest_ids_dict)} target URLs from local file.")
                    else:
                        logger.error(f"Invalid format in local file {local_file_path}. Expected a dict of string: string.")
                else:
                    logger.error(f"Invalid format in local file {local_file_path}. Expected a JSON dictionary.")
        except FileNotFoundError:
            logger.info(f"Local file {local_file_path} not found. Assuming empty state.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from local file {local_file_path}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error loading latest meeting IDs from local file: {e}")
    else:
        logger.error("Storage path (latest_ids_file) is not configured.")

    return latest_ids_dict

def save_latest_meeting_ids(latest_ids_dict: Dict[str, str], config: Config):
    """
    Saves the dictionary of latest meeting IDs (keyed by target URL)
    to Google Cloud Storage or a local file.

    Args:
        latest_ids_dict (Dict[str, str]): The dictionary of meeting IDs to save.
        config (Config): Application configuration.
    """
    storage_path = getattr(config, 'latest_ids_file', None) # Use the specific filename from config

    if config.gcs_bucket_name and storage_path:
        # Use GCS
        client = _get_gcs_client()
        bucket = client.bucket(config.gcs_bucket_name)
        blob = bucket.blob(storage_path)

        try:
            # Sort dictionary by key for consistent output (optional)
            sorted_dict = dict(sorted(latest_ids_dict.items()))
            json_data = json.dumps(sorted_dict, ensure_ascii=False, indent=2)
            blob.upload_from_string(json_data, content_type='application/json')
            logger.info(f"Saved latest meeting IDs for {len(sorted_dict)} target URLs to gs://{config.gcs_bucket_name}/{storage_path}")
        except Exception as e:
            logger.exception(f"Failed to save latest meeting IDs to GCS: {e}")
            # Consider admin notification
    elif storage_path:
        # Use local file (assuming relative path)
        local_file_path = storage_path
        try:
            logger.info(f"Attempting to save latest meeting IDs to local file: {local_file_path}")
            dir_name = os.path.dirname(local_file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            # Sort dictionary by key for consistent output (optional)
            sorted_dict = dict(sorted(latest_ids_dict.items()))
            json_data = json.dumps(sorted_dict, ensure_ascii=False, indent=2)
            with open(local_file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            logger.info(f"Saved latest meeting IDs for {len(sorted_dict)} target URLs to local file: {local_file_path}")
        except Exception as e:
            logger.exception(f"Failed to save latest meeting IDs to local file {local_file_path}: {e}")
    else:
        logger.error("Storage path (latest_ids_file) is not configured. Cannot save latest meeting IDs.")


# --- Example Usage (Commented out as it needs significant updates) ---
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

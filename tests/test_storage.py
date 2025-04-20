import json
import pytest
from unittest.mock import patch, MagicMock
from google.cloud import storage as gcs # Use alias to avoid conflict
from google.cloud.exceptions import NotFound

# Assuming src is importable
from src import storage
from src.config import Config # Import Config class
from typing import Dict, List, Set # Import necessary types

# --- Constants ---
TEST_BUCKET_NAME = "test-medfeebot-bucket"
TEST_KNOWN_URLS_FILE = "data/known_urls_v2.json" # New filename for PDF state
TEST_LATEST_IDS_FILE = "data/latest_ids_v2.json" # New filename for meeting state
TARGET_URL_PDF = "http://pdf.example.com"
TARGET_URL_MEETING = "http://meeting.example.com"

# --- Fixtures ---

@pytest.fixture
def mock_gcs_client(mocker):
    """Mocks the google.cloud.storage Client and its methods."""
    mock_client = MagicMock(spec=gcs.Client)
    mock_bucket = MagicMock(spec=gcs.Bucket)
    mock_blob = MagicMock(spec=gcs.Blob)

    # Configure the mocks to return each other
    # mocker.patch('src.storage.storage.Client', return_value=mock_client) # Patch the internal getter instead
    mocker.patch('src.storage._get_gcs_client', return_value=mock_client) # Patch the getter function
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    # Return the individual mocks for configuration in tests
    return mock_client, mock_bucket, mock_blob

@pytest.fixture
def test_config() -> Config:
    """Provides a Config object for tests."""
    # Create a config instance with the new attributes
    # Note: target_urls and url_configs are not strictly needed for storage tests,
    # but we include dummy values for completeness.
    return Config(
        target_urls=[TARGET_URL_PDF, TARGET_URL_MEETING],
        url_configs={ # Dummy configs
            TARGET_URL_PDF: {"type": "pdf", "parser": lambda x, y: []},
            TARGET_URL_MEETING: {"type": "meeting", "parser": lambda x, y: None}
        },
        slack_api_token="dummy",
        slack_channel_id="dummy",
        gcs_bucket_name=TEST_BUCKET_NAME,
        known_urls_file=TEST_KNOWN_URLS_FILE, # Use new attribute
        latest_ids_file=TEST_LATEST_IDS_FILE, # Use new attribute
        log_level="DEBUG",
        admin_slack_channel_id=None,
        request_timeout=10,
        request_retries=3,
        request_retry_delay=1
    )

# --- Test Cases for load_known_urls ---

def test_load_known_urls_gcs_not_found(mock_gcs_client, test_config):
    """Test load_known_urls when the GCS object does not exist."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_blob.download_as_string.side_effect = NotFound("Object not found")

    known_urls_dict = storage.load_known_urls(test_config)

    assert known_urls_dict == {} # Should return empty dict
    mock_client.bucket.assert_called_once_with(TEST_BUCKET_NAME)
    mock_bucket.blob.assert_called_once_with(TEST_KNOWN_URLS_FILE) # Check correct filename
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_success(mock_gcs_client, test_config):
    """Test load_known_urls with a valid JSON dictionary from GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    urls_dict = {
        TARGET_URL_PDF: ["http://a.pdf", "http://b.pdf"],
        "http://another.example.com": ["http://c.pdf"]
    }
    mock_blob.download_as_string.return_value = json.dumps(urls_dict).encode('utf-8')
    mock_blob.download_as_string.side_effect = None

    known_urls_dict = storage.load_known_urls(test_config)

    assert known_urls_dict == urls_dict
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_empty_json_dict(mock_gcs_client, test_config):
    """Test load_known_urls with an empty JSON dictionary from GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_blob.download_as_string.return_value = json.dumps({}).encode('utf-8')
    mock_blob.download_as_string.side_effect = None

    known_urls_dict = storage.load_known_urls(test_config)

    assert known_urls_dict == {}
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_invalid_json(mock_gcs_client, test_config, mocker):
    """Test load_known_urls with invalid JSON content (returns empty dict, logs error)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_error = mocker.patch('src.storage.logger.error')
    mock_blob.download_as_string.return_value = b"{invalid json"
    mock_blob.download_as_string.side_effect = None

    # Should not raise, should return empty dict
    known_urls_dict = storage.load_known_urls(test_config)

    assert known_urls_dict == {}
    mock_blob.download_as_string.assert_called_once()
    mock_logger_error.assert_called_once() # Check error was logged

def test_load_known_urls_not_a_dict(mock_gcs_client, test_config, mocker):
    """Test load_known_urls when GCS JSON content is not a dict (returns empty dict, logs error)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_error = mocker.patch('src.storage.logger.error')
    mock_blob.download_as_string.return_value = json.dumps(["a", "b"]).encode('utf-8') # JSON list, not dict
    mock_blob.download_as_string.side_effect = None

    # Should not raise, should return empty dict
    known_urls_dict = storage.load_known_urls(test_config)

    assert known_urls_dict == {}
    mock_blob.download_as_string.assert_called_once()
    mock_logger_error.assert_called_once()

def test_load_known_urls_invalid_structure(mock_gcs_client, test_config, mocker):
    """Test load_known_urls with incorrect dict structure (returns empty dict, logs error)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_error = mocker.patch('src.storage.logger.error')
    invalid_dict = {
        TARGET_URL_PDF: "not_a_list", # Value should be a list
        "http://another.example.com": ["valid.pdf"]
    }
    mock_blob.download_as_string.return_value = json.dumps(invalid_dict).encode('utf-8')
    mock_blob.download_as_string.side_effect = None

    # Should not raise, should return empty dict
    known_urls_dict = storage.load_known_urls(test_config)

    assert known_urls_dict == {} # Invalid structure leads to empty dict
    mock_blob.download_as_string.assert_called_once()
    mock_logger_error.assert_called() # Error should be logged

def test_load_known_urls_gcs_download_error(mock_gcs_client, test_config):
    """Test load_known_urls handles critical GCS download errors (raises)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_blob.download_as_string.side_effect = Exception("GCS API error")

    with pytest.raises(Exception, match="GCS API error"):
        storage.load_known_urls(test_config)
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_missing_config(mock_app_config): # Use the correct fixture name
    """Test load_known_urls returns empty dict if config is missing GCS bucket."""
    # Create a new config instance with gcs_bucket_name=None
    config_no_gcs = Config(
        target_urls=mock_app_config.target_urls,
        url_configs=mock_app_config.url_configs,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file=mock_app_config.known_urls_file,
        latest_ids_file=mock_app_config.latest_ids_file,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
        gcs_bucket_name=None # Set to None for this test
    )
    known_urls_dict = storage.load_known_urls(config_no_gcs) # Pass the modified config
    assert known_urls_dict == {}

# --- Test Cases for save_known_urls ---

def test_save_known_urls_success(mock_gcs_client, test_config):
    """Test save_known_urls successfully saves a dictionary to GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    urls_dict_to_save: Dict[str, List[str]] = {
        TARGET_URL_PDF: ["http://c.pdf", "http://a.pdf"],
        "http://another.example.com": ["http://d.pdf"]
    }
    # Expected JSON should have sorted lists inside
    expected_dict_sorted = {
        TARGET_URL_PDF: ["http://a.pdf", "http://c.pdf"],
        "http://another.example.com": ["http://d.pdf"]
    }
    expected_json_string = json.dumps(expected_dict_sorted, ensure_ascii=False, indent=2)

    storage.save_known_urls(urls_dict_to_save, test_config)

    mock_client.bucket.assert_called_once_with(TEST_BUCKET_NAME)
    mock_bucket.blob.assert_called_once_with(TEST_KNOWN_URLS_FILE) # Check correct filename
    mock_blob.upload_from_string.assert_called_once_with(
        expected_json_string,
        content_type='application/json'
    )

def test_save_known_urls_empty_dict(mock_gcs_client, test_config):
    """Test save_known_urls with an empty dictionary."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    urls_dict_to_save: Dict[str, List[str]] = {}
    expected_json_string = json.dumps({}, ensure_ascii=False, indent=2)

    storage.save_known_urls(urls_dict_to_save, test_config)

    mock_blob.upload_from_string.assert_called_once_with(
        expected_json_string,
        content_type='application/json'
    )

def test_save_known_urls_gcs_upload_error(mock_gcs_client, test_config, mocker):
    """Test save_known_urls handles GCS upload errors (logs but doesn't raise)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_exception = mocker.patch('src.storage.logger.exception')
    urls_dict_to_save = {TARGET_URL_PDF: ["http://error.pdf"]}
    mock_blob.upload_from_string.side_effect = Exception("GCS upload failed")

    # Should not raise an exception
    storage.save_known_urls(urls_dict_to_save, test_config)

    mock_blob.upload_from_string.assert_called_once()
    mock_logger_exception.assert_called_once()

def test_save_known_urls_missing_config(mock_app_config, mocker): # Use the correct fixture name
    """Test save_known_urls logs error if config is missing GCS bucket."""
    mock_logger_error = mocker.patch('src.storage.logger.error')
    # Create a new config instance with gcs_bucket_name=None
    config_no_gcs = Config(
        target_urls=mock_app_config.target_urls,
        url_configs=mock_app_config.url_configs,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file=None, # Set storage path to None as well
        latest_ids_file=mock_app_config.latest_ids_file,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
        gcs_bucket_name=None # Set to None for this test
    )
    # When GCS bucket is None, and storage_path (local path) is None (default), it should log error
    storage.save_known_urls({}, config_no_gcs) # Pass the modified config
    # Expect the "invalid configuration" message when both GCS bucket and path are missing
    mock_logger_error.assert_called_with("Storage configuration invalid. Cannot save known URLs. Provide GCS bucket name or ensure local path is set without GCS bucket.")

# Test case where GCS is None but local path IS configured (should still log error as GCS takes precedence if bucket name was expected)
# This behavior might need refinement based on desired logic (e.g., fallback to local if GCS fails?)
# For now, assume if GCS bucket is configured (even if None), local path is ignored unless GCS fails non-critically.
# Let's refine the save function logic slightly first.


# --- Test Cases for find_new_pdf_urls ---

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_pdf_urls_first_run_for_target(mock_save, mock_load, test_config):
    """Test find_new_pdf_urls when the target URL is seen for the first time."""
    mock_load.return_value = {} # No known URLs initially
    current_urls = {"http://first.pdf", "http://second.pdf"}
    target_url = TARGET_URL_PDF

    new_urls = storage.find_new_pdf_urls(target_url, current_urls, test_config)

    assert new_urls == set() # No new URLs reported on first run for a target
    mock_load.assert_called_once_with(test_config)
    # Check save was called with the new target URL added
    expected_saved_dict = {target_url: sorted(list(current_urls))}
    mock_save.assert_called_once_with(expected_saved_dict, test_config)

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_pdf_urls_no_new(mock_save, mock_load, test_config):
    """Test find_new_pdf_urls when there are no new URLs for the target."""
    initial_dict = {TARGET_URL_PDF: ["http://a.pdf", "http://b.pdf"]}
    mock_load.return_value = initial_dict
    current_urls = {"http://b.pdf", "http://a.pdf"} # Same URLs
    target_url = TARGET_URL_PDF

    new_urls = storage.find_new_pdf_urls(target_url, current_urls, test_config)

    assert new_urls == set()
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_pdf_urls_with_new(mock_save, mock_load, test_config):
    """Test find_new_pdf_urls when new URLs are found for the target."""
    initial_dict = {
        TARGET_URL_PDF: ["http://a.pdf", "http://b.pdf"],
        "http://other.url": ["http://x.pdf"]
    }
    mock_load.return_value = initial_dict
    current_urls = {"http://b.pdf", "http://c.pdf", "http://d.pdf"}
    target_url = TARGET_URL_PDF
    expected_new = {"http://c.pdf", "http://d.pdf"}
    expected_saved_dict = {
        TARGET_URL_PDF: sorted(["http://a.pdf", "http://b.pdf", "http://c.pdf", "http://d.pdf"]),
        "http://other.url": ["http://x.pdf"]
    }

    new_urls = storage.find_new_pdf_urls(target_url, current_urls, test_config)

    assert new_urls == expected_new
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_called_once_with(expected_saved_dict, test_config)

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_pdf_urls_current_is_subset(mock_save, mock_load, test_config):
    """Test find_new_pdf_urls when current URLs are a subset."""
    initial_dict = {TARGET_URL_PDF: ["http://a.pdf", "http://b.pdf", "http://c.pdf"]}
    mock_load.return_value = initial_dict
    current_urls = {"http://b.pdf", "http://a.pdf"}
    target_url = TARGET_URL_PDF

    new_urls = storage.find_new_pdf_urls(target_url, current_urls, test_config)

    assert new_urls == set()
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_pdf_urls_empty_current(mock_save, mock_load, test_config):
    """Test find_new_pdf_urls when the current URL set is empty."""
    initial_dict = {TARGET_URL_PDF: ["http://a.pdf", "http://b.pdf"]}
    mock_load.return_value = initial_dict
    current_urls = set()
    target_url = TARGET_URL_PDF

    new_urls = storage.find_new_pdf_urls(target_url, current_urls, test_config)

    assert new_urls == set()
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_pdf_urls_load_error(mock_save, mock_load, test_config, mocker):
    """Test find_new_pdf_urls handles critical load errors."""
    mock_logger_error = mocker.patch('src.storage.logger.error')
    mock_load.side_effect = Exception("GCS Load Failed")
    current_urls = {"http://a.pdf"}
    target_url = TARGET_URL_PDF

    # Expect the exception to be raised
    with pytest.raises(Exception, match="GCS Load Failed"):
        storage.find_new_pdf_urls(target_url, current_urls, test_config)

    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()
    mock_logger_error.assert_called()

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_pdf_urls_save_error(mock_save, mock_load, test_config, mocker):
    """Test find_new_pdf_urls handles save errors but still returns new URLs."""
    mock_logger_error = mocker.patch('src.storage.logger.error')
    initial_dict = {TARGET_URL_PDF: ["http://a.pdf"]}
    mock_load.return_value = initial_dict
    current_urls = {"http://a.pdf", "http://b.pdf"}
    target_url = TARGET_URL_PDF
    expected_new = {"http://b.pdf"}
    expected_saved_dict = {TARGET_URL_PDF: sorted(["http://a.pdf", "http://b.pdf"])}

    mock_save.side_effect = Exception("GCS upload failed")

    new_urls = storage.find_new_pdf_urls(target_url, current_urls, test_config)

    assert new_urls == expected_new
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_called_once_with(expected_saved_dict, test_config)
    assert mock_logger_error.call_count >= 1


# --- Test Cases for load_latest_meeting_ids ---

def test_load_latest_meeting_ids_gcs_not_found(mock_gcs_client, test_config):
    """Test load_latest_meeting_ids when the GCS object does not exist."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_blob.download_as_string.side_effect = NotFound("Object not found")

    latest_ids_dict = storage.load_latest_meeting_ids(test_config)

    assert latest_ids_dict == {}
    mock_client.bucket.assert_called_once_with(TEST_BUCKET_NAME)
    mock_bucket.blob.assert_called_once_with(TEST_LATEST_IDS_FILE) # Check correct filename
    mock_blob.download_as_string.assert_called_once()

def test_load_latest_meeting_ids_success(mock_gcs_client, test_config):
    """Test load_latest_meeting_ids with a valid JSON dictionary."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    ids_dict = {TARGET_URL_MEETING: "ID_123", "http://other.meeting": "ID_456"}
    mock_blob.download_as_string.return_value = json.dumps(ids_dict).encode('utf-8')
    mock_blob.download_as_string.side_effect = None

    latest_ids_dict = storage.load_latest_meeting_ids(test_config)

    assert latest_ids_dict == ids_dict
    mock_blob.download_as_string.assert_called_once()

def test_load_latest_meeting_ids_empty_json_dict(mock_gcs_client, test_config):
    """Test load_latest_meeting_ids with an empty JSON dictionary."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_blob.download_as_string.return_value = json.dumps({}).encode('utf-8')
    mock_blob.download_as_string.side_effect = None

    latest_ids_dict = storage.load_latest_meeting_ids(test_config)

    assert latest_ids_dict == {}
    mock_blob.download_as_string.assert_called_once()

def test_load_latest_meeting_ids_invalid_json(mock_gcs_client, test_config, mocker):
    """Test load_latest_meeting_ids with invalid JSON (returns empty dict, logs error)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_error = mocker.patch('src.storage.logger.error')
    mock_blob.download_as_string.return_value = b"invalid json}"
    mock_blob.download_as_string.side_effect = None

    latest_ids_dict = storage.load_latest_meeting_ids(test_config)

    assert latest_ids_dict == {}
    mock_blob.download_as_string.assert_called_once()
    mock_logger_error.assert_called_once()

def test_load_latest_meeting_ids_not_a_dict(mock_gcs_client, test_config, mocker):
    """Test load_latest_meeting_ids when content is not a dict (returns empty dict, logs error)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_error = mocker.patch('src.storage.logger.error')
    mock_blob.download_as_string.return_value = json.dumps(["id1", "id2"]).encode('utf-8')
    mock_blob.download_as_string.side_effect = None

    latest_ids_dict = storage.load_latest_meeting_ids(test_config)

    assert latest_ids_dict == {}
    mock_blob.download_as_string.assert_called_once()
    mock_logger_error.assert_called_once()

def test_load_latest_meeting_ids_invalid_structure(mock_gcs_client, test_config, mocker):
    """Test load_latest_meeting_ids with incorrect dict structure (returns empty dict, logs error)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_error = mocker.patch('src.storage.logger.error')
    invalid_dict = {TARGET_URL_MEETING: ["not_a_string"]} # Value should be string
    mock_blob.download_as_string.return_value = json.dumps(invalid_dict).encode('utf-8')
    mock_blob.download_as_string.side_effect = None

    latest_ids_dict = storage.load_latest_meeting_ids(test_config)

    assert latest_ids_dict == {}
    mock_blob.download_as_string.assert_called_once()
    mock_logger_error.assert_called()

def test_load_latest_meeting_ids_gcs_download_error(mock_gcs_client, test_config, mocker):
    """Test load_latest_meeting_ids handles GCS download errors (logs exception, returns empty dict)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_exception = mocker.patch('src.storage.logger.exception')
    mock_blob.download_as_string.side_effect = Exception("GCS API error")

    # Should raise the exception
    with pytest.raises(Exception, match="GCS API error"):
        storage.load_latest_meeting_ids(test_config)

    mock_blob.download_as_string.assert_called_once()
    mock_logger_exception.assert_called_once()

def test_load_latest_meeting_ids_missing_config(mock_app_config): # Use the correct fixture name
    """Test load_latest_meeting_ids returns empty dict if config is missing GCS bucket."""
    # Create a new config instance with gcs_bucket_name=None
    config_no_gcs = Config(
        target_urls=mock_app_config.target_urls,
        url_configs=mock_app_config.url_configs,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file=mock_app_config.known_urls_file,
        latest_ids_file=mock_app_config.latest_ids_file,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
        gcs_bucket_name=None # Set to None for this test
    )
    latest_ids_dict = storage.load_latest_meeting_ids(config_no_gcs) # Pass the modified config
    assert latest_ids_dict == {}


# --- Test Cases for save_latest_meeting_ids ---

def test_save_latest_meeting_ids_success(mock_gcs_client, test_config):
    """Test save_latest_meeting_ids successfully saves a dictionary to GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    ids_dict_to_save: Dict[str, str] = {
        TARGET_URL_MEETING: "ID_789",
        "http://other.meeting": "ID_101"
    }
    # Expected JSON should be sorted by key
    expected_dict_sorted = dict(sorted(ids_dict_to_save.items()))
    expected_json_string = json.dumps(expected_dict_sorted, ensure_ascii=False, indent=2)

    storage.save_latest_meeting_ids(ids_dict_to_save, test_config)

    mock_client.bucket.assert_called_once_with(TEST_BUCKET_NAME)
    mock_bucket.blob.assert_called_once_with(TEST_LATEST_IDS_FILE) # Check correct filename
    mock_blob.upload_from_string.assert_called_once_with(
        expected_json_string,
        content_type='application/json'
    )

def test_save_latest_meeting_ids_empty_dict(mock_gcs_client, test_config):
    """Test save_latest_meeting_ids with an empty dictionary."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    ids_dict_to_save: Dict[str, str] = {}
    expected_json_string = json.dumps({}, ensure_ascii=False, indent=2)

    storage.save_latest_meeting_ids(ids_dict_to_save, test_config)

    mock_blob.upload_from_string.assert_called_once_with(
        expected_json_string,
        content_type='application/json'
    )

def test_save_latest_meeting_ids_gcs_upload_error(mock_gcs_client, test_config, mocker):
    """Test save_latest_meeting_ids handles GCS upload errors (logs but doesn't raise)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_exception = mocker.patch('src.storage.logger.exception')
    ids_dict_to_save = {TARGET_URL_MEETING: "ID_Error"}
    mock_blob.upload_from_string.side_effect = Exception("GCS upload failed")

    # Should not raise an exception
    storage.save_latest_meeting_ids(ids_dict_to_save, test_config)

    mock_blob.upload_from_string.assert_called_once()
    mock_logger_exception.assert_called_once()

def test_save_latest_meeting_ids_missing_config(mock_app_config, mocker): # Use the correct fixture name
    """Test save_latest_meeting_ids logs error if config is missing GCS bucket."""
    mock_logger_error = mocker.patch('src.storage.logger.error')
    # Create a new config instance with gcs_bucket_name=None
    config_no_gcs = Config(
        target_urls=mock_app_config.target_urls,
        url_configs=mock_app_config.url_configs,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file=mock_app_config.known_urls_file,
        latest_ids_file=None, # Set storage path to None as well
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
        gcs_bucket_name=None # Set to None for this test
    )
    # Similar to save_known_urls, if GCS bucket is None, it should log error
    storage.save_latest_meeting_ids({}, config_no_gcs) # Pass the modified config
    mock_logger_error.assert_called_with("Storage configuration invalid or missing. Cannot save latest meeting IDs. Provide GCS bucket name or ensure local path is set without GCS bucket.")

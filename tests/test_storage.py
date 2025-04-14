import json
import pytest
from unittest.mock import patch, MagicMock
from google.cloud import storage as gcs # Use alias to avoid conflict
from google.cloud.exceptions import NotFound

# Assuming src is importable
from src import storage
from src.config import Config # Import Config class

# --- Constants ---
TEST_BUCKET_NAME = "test-medfeebot-bucket"
TEST_OBJECT_NAME = "data/known_urls.json"

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
    return Config(
        target_url="dummy", # Not used in storage tests
        slack_api_token="dummy", # Not used
        slack_channel_id="dummy", # Not used
        known_urls_file_path=None, # Not used
        log_level="DEBUG",
        admin_slack_channel_id=None, # Not used
        gcs_bucket_name=TEST_BUCKET_NAME,
        gcs_object_name=TEST_OBJECT_NAME,
        request_timeout=10,
        request_retries=3,
        request_retry_delay=1
        # slack_secret_id is not part of Config dataclass
    )

# --- Test Cases for load_known_urls ---

def test_load_known_urls_gcs_not_found(mock_gcs_client, test_config):
    """Test load_known_urls when the GCS object does not exist (first run)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    # Set side effect specifically for this test
    mock_blob.download_as_string.side_effect = NotFound("Object not found")

    known_urls = storage.load_known_urls(test_config)

    assert known_urls == set()
    mock_client.bucket.assert_called_once_with(TEST_BUCKET_NAME)
    mock_bucket.blob.assert_called_once_with(TEST_OBJECT_NAME)
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_success(mock_gcs_client, test_config):
    """Test load_known_urls with a valid JSON list from GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    urls_list = ["http://a.pdf", "http://b.pdf"]
    # Set return value specifically for this test
    mock_blob.download_as_string.return_value = json.dumps(urls_list).encode('utf-8')
    # Reset side effect if set in other tests
    mock_blob.download_as_string.side_effect = None

    known_urls = storage.load_known_urls(test_config)

    assert known_urls == set(urls_list)
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_empty_json_list(mock_gcs_client, test_config):
    """Test load_known_urls with an empty JSON list from GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    # Set return value specifically for this test
    mock_blob.download_as_string.return_value = json.dumps([]).encode('utf-8')
    # Reset side effect if set in other tests
    mock_blob.download_as_string.side_effect = None

    known_urls = storage.load_known_urls(test_config)

    assert known_urls == set()
    mock_blob.download_as_string.assert_called_once()


def test_load_known_urls_invalid_json(mock_gcs_client, test_config):
    """Test load_known_urls with invalid JSON content from GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    # Set return value specifically for this test
    mock_blob.download_as_string.return_value = b"{invalid json"
    # Reset side effect if set in other tests
    mock_blob.download_as_string.side_effect = None

    with pytest.raises(ValueError, match="Failed to decode JSON"):
        storage.load_known_urls(test_config)
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_not_a_list(mock_gcs_client, test_config):
    """Test load_known_urls when GCS JSON content is not a list."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    # Set return value specifically for this test
    mock_blob.download_as_string.return_value = json.dumps({"key": "value"}).encode('utf-8')
    # Reset side effect if set in other tests
    mock_blob.download_as_string.side_effect = None

    with pytest.raises(ValueError, match="Invalid data format"):
        storage.load_known_urls(test_config)
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_gcs_download_error(mock_gcs_client, test_config):
    """Test load_known_urls handles GCS download errors."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    # Set side effect specifically for this test
    mock_blob.download_as_string.side_effect = Exception("GCS API error")

    with pytest.raises(Exception, match="GCS API error"):
        storage.load_known_urls(test_config)
    mock_blob.download_as_string.assert_called_once()

def test_load_known_urls_missing_gcs_config():
    """Test load_known_urls raises error if GCS config is missing."""
    # Provide dummy values for other required fields
    bad_config = Config(
        target_url="dummy",
        slack_api_token="dummy",
        slack_channel_id="dummy",
        known_urls_file_path="dummy",
        gcs_bucket_name=None,
        gcs_object_name=None
    )
    with pytest.raises(ValueError, match="GCS configuration missing"):
        storage.load_known_urls(bad_config)

# --- Test Cases for save_known_urls ---

def test_save_known_urls_success(mock_gcs_client, test_config):
    """Test save_known_urls successfully saves data to GCS."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    urls_to_save = {"http://c.pdf", "http://a.pdf", "http://b.pdf"}
    expected_json_string = json.dumps(sorted(list(urls_to_save)), ensure_ascii=False, indent=2)

    storage.save_known_urls(urls_to_save, test_config)

    mock_client.bucket.assert_called_once_with(TEST_BUCKET_NAME)
    mock_bucket.blob.assert_called_once_with(TEST_OBJECT_NAME)
    mock_blob.upload_from_string.assert_called_once_with(
        expected_json_string,
        content_type='application/json'
    )

def test_save_known_urls_empty_set(mock_gcs_client, test_config):
    """Test save_known_urls with an empty set."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    urls_to_save = set()
    expected_json_string = json.dumps([], ensure_ascii=False, indent=2)

    storage.save_known_urls(urls_to_save, test_config)

    mock_blob.upload_from_string.assert_called_once_with(
        expected_json_string,
        content_type='application/json'
    )

def test_save_known_urls_gcs_upload_error(mock_gcs_client, test_config, mocker):
    """Test save_known_urls handles GCS upload errors (logs but doesn't raise)."""
    mock_client, mock_bucket, mock_blob = mock_gcs_client
    mock_logger_exception = mocker.patch('src.storage.logger.exception')
    urls_to_save = {"http://error.pdf"}
    mock_blob.upload_from_string.side_effect = Exception("GCS upload failed")

    # Should not raise an exception
    storage.save_known_urls(urls_to_save, test_config)

    mock_blob.upload_from_string.assert_called_once()
    mock_logger_exception.assert_called_once() # Check that error was logged

def test_save_known_urls_missing_gcs_config():
    """Test save_known_urls raises error if GCS config is missing."""
    # Provide dummy values for other required fields
    bad_config = Config(
        target_url="dummy",
        slack_api_token="dummy",
        slack_channel_id="dummy",
        known_urls_file_path="dummy",
        gcs_bucket_name=None,
        gcs_object_name=None
    )
    with pytest.raises(ValueError, match="GCS configuration missing"):
        storage.save_known_urls(set(), bad_config)


# --- Test Cases for find_new_urls ---

# Patch load and save within the storage module itself for these tests
@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_first_run(mock_save, mock_load, test_config):
    """Test find_new_urls on the first run (load raises NotFound)."""
    mock_load.side_effect = NotFound("GCS object not found")
    current_urls = {"http://first.pdf", "http://second.pdf"}

    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == set() # No new URLs reported on first run
    mock_load.assert_called_once_with(test_config)
    # Check save was called with the current URLs for the first run
    mock_save.assert_called_once_with(current_urls, test_config)

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_no_new(mock_save, mock_load, test_config):
    """Test find_new_urls when there are no new URLs."""
    initial_urls = {"http://a.pdf", "http://b.pdf"}
    mock_load.return_value = initial_urls
    current_urls = {"http://b.pdf", "http://a.pdf"} # Same URLs

    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == set()
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called() # Save should not be called

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_with_new(mock_save, mock_load, test_config):
    """Test find_new_urls when new URLs are found."""
    initial_urls = {"http://a.pdf", "http://b.pdf"}
    mock_load.return_value = initial_urls
    current_urls = {"http://b.pdf", "http://c.pdf", "http://d.pdf"}
    expected_new = {"http://c.pdf", "http://d.pdf"}
    expected_saved = initial_urls.union(expected_new)

    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == expected_new
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_called_once_with(expected_saved, test_config)

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_current_is_subset(mock_save, mock_load, test_config):
    """Test find_new_urls when current URLs are a subset of known URLs."""
    initial_urls = {"http://a.pdf", "http://b.pdf", "http://c.pdf"}
    mock_load.return_value = initial_urls
    current_urls = {"http://b.pdf", "http://a.pdf"}

    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == set()
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_empty_current(mock_save, mock_load, test_config):
    """Test find_new_urls when the current URL list is empty."""
    initial_urls = {"http://a.pdf", "http://b.pdf"}
    mock_load.return_value = initial_urls
    current_urls = set()

    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == set()
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_load_error_valueerror(mock_save, mock_load, test_config, mocker):
    """Test find_new_urls handles ValueError during load."""
    mock_logger_error = mocker.patch('src.storage.logger.error')
    mock_load.side_effect = ValueError("Config missing")
    current_urls = {"http://a.pdf", "http://b.pdf"}

    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == set() # Should return empty set on load error
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()
    mock_logger_error.assert_called() # Check error was logged

@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_load_error_exception(mock_save, mock_load, test_config, mocker):
    """Test find_new_urls handles generic Exception during load."""
    mock_logger_exception = mocker.patch('src.storage.logger.exception')
    mock_load.side_effect = Exception("Unexpected GCS error")
    current_urls = {"http://a.pdf", "http://b.pdf"}

    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == set() # Should return empty set on load error
    mock_load.assert_called_once_with(test_config)
    mock_save.assert_not_called()
    mock_logger_exception.assert_called() # Check error was logged


@patch('src.storage.load_known_urls')
@patch('src.storage.save_known_urls')
def test_find_new_urls_save_error(mock_save, mock_load, test_config, mocker):
    """Test find_new_urls handles error during save_known_urls but still returns new URLs."""
    mock_logger_error = mocker.patch('src.storage.logger.error')
    initial_urls = {"http://a.pdf"}
    mock_load.return_value = initial_urls
    current_urls = {"http://a.pdf", "http://b.pdf"}
    expected_new = {"http://b.pdf"}
    expected_saved = initial_urls.union(expected_new)

    # Mock save_known_urls to simulate an error
    mock_save.side_effect = Exception("GCS upload failed")

    # Even if save fails, find_new_urls should still return the new URLs found
    new_urls = storage.find_new_urls(current_urls, test_config)

    assert new_urls == expected_new
    mock_load.assert_called_once_with(test_config)
    # Check that save was called (even though it failed)
    mock_save.assert_called_once_with(expected_saved, test_config)
    # Check that the error during save was logged
    assert mock_logger_error.call_count >= 1 # Error is logged in save_known_urls and find_new_urls

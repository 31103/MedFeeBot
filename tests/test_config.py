import os
from unittest.mock import patch, MagicMock

import pytest

# Assuming src is importable from tests directory
from src.config import load_config, Config
from src import parser # Import parser to check function references

# Mock environment variables for testing
# Define expected URLs for testing
PDF_URL = "https://www.hospital.or.jp/site/ministry/"
MEETING_URL = "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html"
UNCONFIGURED_URL = "http://unconfigured.example.com"

MOCK_ENV_VARS = {
    "TARGET_URLS": f"{PDF_URL},{MEETING_URL},{UNCONFIGURED_URL}", # Comma-separated URLs
    "SLACK_API_TOKEN": "xoxb-test-token",
    "SLACK_CHANNEL_ID": "C12345TEST",
    "KNOWN_URLS_FILE": "data/test_known_urls_v2.json", # New env var name
    "LATEST_IDS_FILE": "data/test_latest_ids_v2.json", # New env var name
    "LOG_LEVEL": "DEBUG",
    "ADMIN_SLACK_CHANNEL_ID": "CADMINTEST",
    "GCS_BUCKET_NAME": "test-bucket",
    # GCS_OBJECT_NAME is removed
    # KNOWN_URLS_FILE_PATH is removed
}

@pytest.fixture
def mock_load_dotenv(mocker) -> MagicMock:
    """Mocks load_dotenv in src.config and returns the mock object."""
    # Use return_value=True so the mocked function doesn't cause side effects
    return mocker.patch('src.config.load_dotenv', return_value=True)

# Remove mock_os_getenv fixture

# Remove apply_mocks fixture entirely

def test_load_config_success(mocker): # Add mocker argument back
    """
    Test that load_config successfully loads configuration from environment variables.
    """
    # Mock os.getenv using mocker
    def mock_getenv_side_effect(key, default=None):
        return MOCK_ENV_VARS.get(key, default)
    mocker.patch('src.config.os.getenv', side_effect=mock_getenv_side_effect)
    # Mock load_dotenv using mocker
    mocker.patch('src.config.load_dotenv', return_value=True)

    config = load_config()

    assert isinstance(config, Config)
    # Check target_urls (should exclude unconfigured URL)
    assert config.target_urls == [PDF_URL, MEETING_URL]
    # Check url_configs (should only contain configured URLs from target_urls)
    assert list(config.url_configs.keys()) == [PDF_URL, MEETING_URL]
    assert config.url_configs[PDF_URL]['type'] == 'pdf'
    assert config.url_configs[PDF_URL]['parser'] == parser.extract_hospital_document_info
    assert config.url_configs[MEETING_URL]['type'] == 'meeting'
    assert config.url_configs[MEETING_URL]['parser'] == parser.extract_latest_chuikyo_meeting

    assert config.slack_api_token == MOCK_ENV_VARS["SLACK_API_TOKEN"]
    assert config.slack_channel_id == MOCK_ENV_VARS["SLACK_CHANNEL_ID"]
    assert config.known_urls_file == MOCK_ENV_VARS["KNOWN_URLS_FILE"] # Check new attribute
    assert config.latest_ids_file == MOCK_ENV_VARS["LATEST_IDS_FILE"] # Check new attribute
    assert config.log_level == MOCK_ENV_VARS["LOG_LEVEL"]
    assert config.admin_slack_channel_id == MOCK_ENV_VARS["ADMIN_SLACK_CHANNEL_ID"]
    assert config.gcs_bucket_name == MOCK_ENV_VARS["GCS_BUCKET_NAME"]
    # assert config.gcs_object_name is removed
    # assert config.known_urls_file_path is removed

# Explicitly apply mocks
def test_load_config_missing_optional_vars(mocker):
    """
    Test that load_config handles missing optional environment variables gracefully
    (ADMIN_SLACK_CHANNEL_ID, GCS_BUCKET_NAME).
    """
    # Mock load_dotenv
    mocker.patch('src.config.load_dotenv', return_value=True)
    # Mock os.getenv with specific overrides for this test
    def side_effect_override(key, default=None):
        if key == "ADMIN_SLACK_CHANNEL_ID":
            return "" # Simulate empty env var
        if key == "GCS_BUCKET_NAME":
            return ""
        # GCS_OBJECT_NAME is removed
        # Fallback to the original mock's behavior
        return MOCK_ENV_VARS.get(key, default)

    with patch('src.config.os.getenv', side_effect=side_effect_override):
        config = load_config()

        assert config.admin_slack_channel_id is None # Expect None if empty
        assert config.gcs_bucket_name is None
        # assert config.gcs_object_name is removed
    # Check required vars are still loaded (use target_urls)
    assert config.target_urls == [PDF_URL, MEETING_URL] # Unconfigured URL is still filtered out

# Explicitly apply mocks
def test_load_config_calls_dotenv(mocker):
    """
    Test that load_config attempts to load a .env file by calling src.config.load_dotenv.
    """
    # Mock os.getenv to return minimal required values
    def side_effect_minimal(key, default=None):
        # Provide minimal required vars for the new structure
        if key == "TARGET_URLS": return PDF_URL # Provide at least one configured URL
        if key == "SLACK_API_TOKEN": return "minimal_token"
        if key == "SLACK_CHANNEL_ID": return "minimal_channel"
        return MOCK_ENV_VARS.get(key, default) # Use others if needed
    mocker.patch('src.config.os.getenv', side_effect=side_effect_minimal)
    # Mock load_dotenv and get the mock object
    load_dotenv_mock = mocker.patch('src.config.load_dotenv', return_value=True)

    # Reset call count (though patch creates a fresh mock)
    # load_dotenv_mock.reset_mock() # Not needed with fresh patch

    # Call the function that should trigger load_dotenv
    load_config()

    # Assert that the mocked load_dotenv within src.config was called
    load_dotenv_mock.assert_called_once()

def test_load_config_missing_target_urls(mocker):
    """Test load_config raises ValueError if TARGET_URLS is missing or empty."""
    def side_effect_missing(key, default=None):
        if key == "TARGET_URLS": return "" # Simulate empty
        return MOCK_ENV_VARS.get(key, default)
    mocker.patch('src.config.os.getenv', side_effect=side_effect_missing)
    mocker.patch('src.config.load_dotenv', return_value=True)

    with pytest.raises(ValueError, match="Environment variable 'TARGET_URLS' is not set or empty."):
        load_config()

def test_load_config_no_valid_urls(mocker):
    """Test load_config raises ValueError if no URLs in TARGET_URLS are configured."""
    def side_effect_unconfigured(key, default=None):
        if key == "TARGET_URLS": return UNCONFIGURED_URL # Only provide unconfigured URL
        return MOCK_ENV_VARS.get(key, default)
    mocker.patch('src.config.os.getenv', side_effect=side_effect_unconfigured)
    mocker.patch('src.config.load_dotenv', return_value=True)
    # Mock logger to check warning
    mock_logger_warning = mocker.patch('src.config.logging.warning')

    with pytest.raises(ValueError, match="No valid and configured URLs found in TARGET_URLS."):
        load_config()
    # Check that the warning for the unconfigured URL was logged
    mock_logger_warning.assert_called_with(
        f"URL '{UNCONFIGURED_URL}' is in TARGET_URLS but not configured in URL_CONFIGS. It will be ignored."
    )

def test_load_config_default_filenames(mocker):
    """Test that default filenames are used if env vars are not set."""
    def side_effect_defaults(key, default=None):
        # Exclude filename env vars
        if key == "KNOWN_URLS_FILE": return None
        if key == "LATEST_IDS_FILE": return None
        return MOCK_ENV_VARS.get(key, default)
    mocker.patch('src.config.os.getenv', side_effect=side_effect_defaults)
    mocker.patch('src.config.load_dotenv', return_value=True)

    config = load_config()

    assert config.known_urls_file == "known_urls.json" # Default value
    assert config.latest_ids_file == "latest_ids.json" # Default value

# Add tests for missing SLACK_API_TOKEN, SLACK_CHANNEL_ID if needed (should raise ValueError)

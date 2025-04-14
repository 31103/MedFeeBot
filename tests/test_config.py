import os
from unittest.mock import patch, MagicMock

import pytest

# Assuming src is importable from tests directory
from src.config import load_config, Config

# Mock environment variables for testing
MOCK_ENV_VARS = {
    "TARGET_URL": "http://example.com/test",
    "SLACK_API_TOKEN": "xoxb-test-token",
    "SLACK_CHANNEL_ID": "C12345TEST",
    "KNOWN_URLS_FILE_PATH": "data/test_known_urls.json",
    "LOG_LEVEL": "DEBUG",
    "ADMIN_SLACK_CHANNEL_ID": "CADMINTEST",
    "GCS_BUCKET_NAME": "test-bucket", # Added for future cloud phase
    "GCS_OBJECT_NAME": "test/known_urls.json" # Added for future cloud phase
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
    assert config.target_url == MOCK_ENV_VARS["TARGET_URL"]
    assert config.slack_api_token == MOCK_ENV_VARS["SLACK_API_TOKEN"]
    assert config.slack_channel_id == MOCK_ENV_VARS["SLACK_CHANNEL_ID"]
    assert config.known_urls_file_path == MOCK_ENV_VARS["KNOWN_URLS_FILE_PATH"]
    assert config.log_level == MOCK_ENV_VARS["LOG_LEVEL"]
    assert config.admin_slack_channel_id == MOCK_ENV_VARS["ADMIN_SLACK_CHANNEL_ID"]
    assert config.gcs_bucket_name == MOCK_ENV_VARS["GCS_BUCKET_NAME"]
    assert config.gcs_object_name == MOCK_ENV_VARS["GCS_OBJECT_NAME"]

# Explicitly apply mocks
def test_load_config_missing_optional_vars(mocker):
    """
    Test that load_config handles missing optional environment variables gracefully.
    ADMIN_SLACK_CHANNEL_ID, GCS_BUCKET_NAME, GCS_OBJECT_NAME are optional for local run.
    """
    # Mock load_dotenv
    mocker.patch('src.config.load_dotenv', return_value=True)
    # Mock os.getenv with specific overrides for this test
    def side_effect_override(key, default=None):
        if key == "ADMIN_SLACK_CHANNEL_ID":
            return "" # Simulate empty env var
        if key == "GCS_BUCKET_NAME":
            return ""
        if key == "GCS_OBJECT_NAME":
            return ""
        # Fallback to the original mock's behavior
        return MOCK_ENV_VARS.get(key, default)

    with patch('src.config.os.getenv', side_effect=side_effect_override):
        config = load_config()

        assert config.admin_slack_channel_id is None # Expect None if empty
        assert config.gcs_bucket_name is None
        assert config.gcs_object_name is None
    # Check required vars are still loaded
    assert config.target_url == MOCK_ENV_VARS["TARGET_URL"]

# Explicitly apply mocks
def test_load_config_calls_dotenv(mocker):
    """
    Test that load_config attempts to load a .env file by calling src.config.load_dotenv.
    """
    # Mock os.getenv to return minimal required values
    def side_effect_minimal(key, default=None):
        if key == "TARGET_URL": return "http://minimal.url"
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

# Add more tests later for missing required variables (should raise error)
# and potentially different log level values.

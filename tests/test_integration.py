import pytest
import json
import os # For path manipulation if needed
from unittest.mock import MagicMock, patch, ANY

# Modules to test
from src import main
from src.config import Config # Import Config class

# --- Constants ---
TEST_URL = "http://mock-mhlw.test/page"
MOCK_HTML = "<html><body><a href='doc1.pdf'>Doc 1</a> <a href='new_doc.pdf'>New Doc</a></body></html>"
KNOWN_URLS_INITIAL = {"http://mock-mhlw.test/doc1.pdf"}
CURRENT_URLS_FOUND = {"http://mock-mhlw.test/doc1.pdf", "http://mock-mhlw.test/new_doc.pdf"}
NEW_URLS_EXPECTED = {"http://mock-mhlw.test/new_doc.pdf"}
UPDATED_KNOWN_URLS = {"http://mock-mhlw.test/doc1.pdf", "http://mock-mhlw.test/new_doc.pdf"}

# --- Fixtures ---

@pytest.fixture
def mock_fetcher(mocker):
    return mocker.patch('src.main.fetcher.fetch_html')

@pytest.fixture
def mock_parser(mocker):
    return mocker.patch('src.main.parser.extract_pdf_links')

@pytest.fixture
def mock_storage(mocker, tmp_path):
    """Mocks storage functions and uses tmp_path for file operations."""
    storage_file = tmp_path / "integration_known_urls.json"
    mocker.patch('src.storage.LOCAL_STORAGE_PATH', str(storage_file))

    # Mock the functions themselves if needed, or let them run using the mocked path
    # Let's allow load/save to run against tmp_path for more realistic integration
    # We might need to mock os.path.exists within storage if it causes issues
    # mocker.patch('src.storage.os.path.exists', return_value=storage_file.exists()) # Example if needed

    # Ensure file is clean before each test using this fixture
    if storage_file.exists():
        storage_file.unlink()

    # Return path for setup within tests
    return storage_file

@pytest.fixture
def mock_notifier(mocker):
    """Mocks notifier functions."""
    mock_notify = mocker.patch('src.main.notifier.send_slack_notification')
    mock_alert = mocker.patch('src.main.notifier.send_admin_alert')
    return mock_notify, mock_alert

@pytest.fixture
def mock_app_config() -> Config:
    """Returns a mock Config object for integration tests."""
    # Note: mock_storage fixture handles the known_urls_file_path
    return Config(
        target_url=TEST_URL,
        slack_api_token="test-token",
        slack_channel_id="C123INTEGRATION",
        known_urls_file_path="will_be_mocked_by_mock_storage", # Placeholder
        log_level="DEBUG",
        admin_slack_channel_id="C456ADMININTEGRATION",
        # Other fields can be None or dummy values if not directly used by main.run_check
    )

@pytest.fixture(autouse=True)
def mock_load_config_in_modules(mocker, mock_app_config, mock_storage):
    """
    Mocks load_config where it's called by modules used in main.run_check.
    Also updates the mock_app_config with the correct temp storage path.
    """
    # Update the config object with the correct temp path from mock_storage
    # We need to create a mutable copy or recreate it if Config is frozen
    # Let's assume Config is frozen and recreate it
    temp_storage_path = mock_storage # Fixture returns the path string
    updated_config = Config(
        target_url=mock_app_config.target_url,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file_path=temp_storage_path, # Use the temp path
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
        gcs_bucket_name=mock_app_config.gcs_bucket_name,
        gcs_object_name=mock_app_config.gcs_object_name,
        request_timeout=mock_app_config.request_timeout,
        request_retries=mock_app_config.request_retries,
        request_retry_delay=mock_app_config.request_retry_delay,
    )

    # Mock load_config where it might be called by the modules used in main.run_check
    mocker.patch('src.fetcher.load_config', return_value=updated_config)
    # src.parser does not call load_config
    # Mock the internal _get_config in notifier to return our test config
    mocker.patch('src.notifier._get_config', return_value=updated_config)
    # Mock load_config called by logger (which might be called by storage or main)
    mocker.patch('src.logger.load_config', return_value=updated_config)
    # Mock load_config called by main itself (now called at the start of run_check)
    mocker.patch('src.main.load_config', return_value=updated_config)
    # Mock load_config called by storage (if any - currently none directly)
    # mocker.patch('src.storage.load_config', return_value=updated_config)
    # No longer need to mock src.main.config as main now uses load_config()
    # mocker.patch('src.main.config', updated_config)

    # Mock the load_config call within storage (if find_new_urls calls it - it does)
    # This is tricky because find_new_urls calls load_known_urls which uses the mocked path,
    # but find_new_urls itself doesn't directly load config. Let's assume it's okay for now.
    # If storage needs config later, we'd mock it there too.

# --- Test Cases ---

# Add mock_app_config fixture to tests that need its values
def test_run_check_success_new_urls(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow when new URLs are found."""
    mock_notify, mock_alert = mock_notifier
    storage_file = mock_storage # Get the temp file path

    # Setup initial state: known URLs file exists
    storage_file.write_text(json.dumps(sorted(list(KNOWN_URLS_INITIAL))), encoding='utf-8')

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = CURRENT_URLS_FOUND

    # Run the main function
    main.run_check()

    # Assertions
    # Use the config object from the fixture for assertions
    mock_fetcher.assert_called_once_with(mock_app_config.target_url)
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    # Check that storage functions used the mocked path correctly
    assert storage_file.exists()
    saved_data = set(json.loads(storage_file.read_text(encoding='utf-8')))
    assert saved_data == UPDATED_KNOWN_URLS # File should contain updated list
    # Check notifier calls
    mock_notify.assert_called_once_with(sorted(list(NEW_URLS_EXPECTED)))
    mock_alert.assert_not_called()

# Add mock_app_config fixture
def test_run_check_success_no_new_urls(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow when no new URLs are found."""
    mock_notify, mock_alert = mock_notifier
    storage_file = mock_storage

    # Setup initial state: known URLs file exists with current URLs
    storage_file.write_text(json.dumps(sorted(list(CURRENT_URLS_FOUND))), encoding='utf-8')
    initial_content = storage_file.read_text(encoding='utf-8')

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = CURRENT_URLS_FOUND # Same URLs as already known

    # Run the main function
    main.run_check()

    # Assertions
    mock_fetcher.assert_called_once_with(mock_app_config.target_url)
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    # Check storage file wasn't unnecessarily rewritten
    assert storage_file.read_text(encoding='utf-8') == initial_content
    # Check notifier calls
    mock_notify.assert_not_called()
    mock_alert.assert_not_called()

# Add mock_app_config fixture
def test_run_check_first_run(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow on the first execution (no known URLs file)."""
    mock_notify, mock_alert = mock_notifier
    storage_file = mock_storage

    # Ensure file does not exist initially
    assert not storage_file.exists()

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = CURRENT_URLS_FOUND

    # Run the main function
    main.run_check()

    # Assertions
    mock_fetcher.assert_called_once_with(mock_app_config.target_url)
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    # Check storage file was created with current URLs
    assert storage_file.exists()
    saved_data = set(json.loads(storage_file.read_text(encoding='utf-8')))
    assert saved_data == CURRENT_URLS_FOUND
    # Check notifier calls (should not notify on first run)
    mock_notify.assert_not_called()
    mock_alert.assert_not_called()

# Add mock_app_config fixture
def test_run_check_fetch_failure(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow when fetcher fails."""
    mock_notify, mock_alert = mock_notifier
    storage_file = mock_storage

    # Configure mocks
    mock_fetcher.return_value = None # Simulate fetch failure

    # Run the main function
    main.run_check()

    # Assertions
    mock_fetcher.assert_called_once_with(mock_app_config.target_url)
    mock_parser.assert_not_called() # Should not parse if fetch fails
    mock_notify.assert_not_called()
    mock_alert.assert_called_once_with(f"HTML取得失敗: {mock_app_config.target_url}") # Check admin alert

# Add mock_app_config fixture
def test_run_check_parser_returns_empty(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the flow when parser finds no links (or fails returning empty)."""
    mock_notify, mock_alert = mock_notifier
    storage_file = mock_storage

    # Setup initial state
    storage_file.write_text(json.dumps(sorted(list(KNOWN_URLS_INITIAL))), encoding='utf-8')
    initial_content = storage_file.read_text(encoding='utf-8')

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = set() # Simulate parser finding nothing

    # Run the main function
    main.run_check()

    # Assertions
    mock_fetcher.assert_called_once_with(mock_app_config.target_url)
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    # Check storage file wasn't rewritten
    assert storage_file.read_text(encoding='utf-8') == initial_content
    mock_notify.assert_not_called()
    mock_alert.assert_not_called() # Parser failure doesn't trigger admin alert in main

# Add mock_app_config fixture
def test_run_check_unexpected_exception(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow handles unexpected errors."""
    mock_notify, mock_alert = mock_notifier
    storage_file = mock_storage

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    test_exception = ValueError("Something unexpected happened")
    mock_parser.side_effect = test_exception # Simulate error during parsing

    # Run the main function
    main.run_check()

    # Assertions
    mock_fetcher.assert_called_once_with(mock_app_config.target_url)
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    mock_notify.assert_not_called() # Should not notify if error occurred before
    mock_alert.assert_called_once_with(
        "メイン処理中に予期せぬエラーが発生しました。",
        error=test_exception
    )

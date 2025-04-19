import pytest
import json
from unittest.mock import MagicMock, patch, ANY
from google.cloud.exceptions import NotFound # Import NotFound for first run simulation

# Modules to test
from src import main
from src.config import Config # Import Config class

# --- Constants ---
TEST_TARGET_URL = "http://mock-hospital.test/site/ministry/" # Updated URL for context
MOCK_HTML = """
<html><body>
<div class="isotope-wrap">
  <div class="col-12 isotope-item">
    <div class="fs13">2025.04.19</div>
    <div><p class="fs_p ic_140"><a href="doc1.pdf">Known Doc 1</a></p></div>
  </div>
<div class="col-12 isotope-item">
  <div class="fs13">2025.04.20</div>
  <div><p class="fs_p ic_140"><a href="new_doc.pdf">New Doc 1</a></p></div>
</div>
</body></html>
"""
# Expected data structure from the new parser
MOCK_DOC_INFO_KNOWN = {'date': '2025.04.19', 'title': 'Known Doc 1', 'url': 'http://mock-hospital.test/site/ministry/doc1.pdf'}
MOCK_DOC_INFO_NEW = {'date': '2025.04.20', 'title': 'New Doc 1', 'url': 'http://mock-hospital.test/site/ministry/new_doc.pdf'}
CURRENT_DOCS_FOUND = [MOCK_DOC_INFO_KNOWN, MOCK_DOC_INFO_NEW]
CURRENT_URLS_FOUND_SET = {doc['url'] for doc in CURRENT_DOCS_FOUND} # Set of URLs for storage comparison

KNOWN_URLS_INITIAL = {MOCK_DOC_INFO_KNOWN['url']} # Initial known URLs (set)
NEW_DOCS_EXPECTED_FOR_NOTIFY = [MOCK_DOC_INFO_NEW] # List of dicts for notifier
NEW_URLS_EXPECTED_SET = {MOCK_DOC_INFO_NEW['url']} # Set of new URLs for storage check
UPDATED_KNOWN_URLS_SET = KNOWN_URLS_INITIAL.union(NEW_URLS_EXPECTED_SET) # Updated set for storage save check

# --- Fixtures ---

@pytest.fixture
def mock_fetcher(mocker):
    return mocker.patch('src.main.fetcher.fetch_html')

@pytest.fixture
def mock_parser(mocker):
    # Mock the new parser function used in main.py
    return mocker.patch('src.main.parser.extract_hospital_document_info')

@pytest.fixture
def mock_storage(mocker):
    """Mocks storage functions load_known_urls and save_known_urls."""
    # Mock the functions called within main.run_check
    # Note: We mock them within src.main because that's where they are imported and used.
    mock_load = mocker.patch('src.main.storage.load_known_urls')
    mock_save = mocker.patch('src.main.storage.save_known_urls')
    # Mock the _get_gcs_client to avoid actual client creation if storage module is imported elsewhere
    mocker.patch('src.storage._get_gcs_client', return_value=MagicMock())
    return mock_load, mock_save

@pytest.fixture
def mock_notifier(mocker):
    """Mocks notifier functions."""
    mock_notify = mocker.patch('src.main.notifier.send_slack_notification')
    mock_alert = mocker.patch('src.main.notifier.send_admin_alert')
    return mock_notify, mock_alert

@pytest.fixture
def mock_app_config() -> Config:
    """Returns a mock Config object for integration tests."""
    # Use dummy GCS paths as storage functions are mocked
    return Config(
        target_url=TEST_TARGET_URL,
        slack_api_token="test-token",
        slack_channel_id="C123INTEGRATION",
        known_urls_file_path=None, # No longer used directly by mocked storage
        log_level="DEBUG",
        admin_slack_channel_id="C456ADMININTEGRATION",
        gcs_bucket_name="test-bucket", # Dummy value
        gcs_object_name="test/known_urls.json", # Dummy value
        request_timeout=10,
        request_retries=3,
        request_retry_delay=1
        # Ensure all required fields have values
        # slack_secret_id is not part of Config dataclass
    )

@pytest.fixture(autouse=True)
def mock_load_config_in_modules(mocker, mock_app_config, mock_storage):
    """
    Mocks load_config where it's called by modules used in main.run_check.
    Also updates the mock_app_config to reflect GCS usage (though values are dummy).
    """
    # mock_storage fixture now returns mocks, not a path
    # The config object from mock_app_config already has dummy GCS paths
    updated_config = mock_app_config # Use the config directly

    # Mock load_config where it's called by the modules used in main.run_check
    # Pass the updated_config which now includes dummy GCS paths
    mocker.patch('src.fetcher.load_config', return_value=updated_config)
    # src.parser does not call load_config
    # Mock the internal _get_config in notifier to return our test config
    mocker.patch('src.notifier._get_config', return_value=updated_config)
    # Mock load_config called by logger (which might be called by storage or main)
    mocker.patch('src.logger.load_config', return_value=updated_config)
    # Mock load_config called by main itself (at the start of run_check)
    mocker.patch('src.main.load_config', return_value=updated_config)
    # Mock load_config potentially called by storage functions (though they are mocked in main)
    # It's safer to mock it here in case storage is imported elsewhere and load_config is called
    mocker.patch('src.storage.load_config', return_value=updated_config, create=True) # Use create=True if load_config isn't directly in storage.py

# --- Test Cases ---

# Add mock_app_config fixture to tests that need its values
def test_run_check_success_new_urls(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow when new URLs are found."""
    mock_notify, mock_alert = mock_notifier
    mock_load, mock_save = mock_storage # Get the mocked storage functions

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = CURRENT_DOCS_FOUND # Parser returns list of dicts
    mock_load.return_value = KNOWN_URLS_INITIAL # Storage load returns set of URLs

    # Run the main function
    # Pass the config object explicitly to run_check
    main.run_check(mock_app_config)

    # Assertions
    # Check fetcher call with individual args
    mock_fetcher.assert_called_once_with(
        url=mock_app_config.target_url,
        timeout=mock_app_config.request_timeout,
        retries=mock_app_config.request_retries,
        delay=mock_app_config.request_retry_delay
    )
    # Check parser call (new function name)
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    # Check storage load call
    mock_load.assert_called_once_with(mock_app_config)
    # Check storage save call with the updated set of URLs
    mock_save.assert_called_once_with(UPDATED_KNOWN_URLS_SET, mock_app_config)
    # Check notifier call with the list of new document dicts
    mock_notify.assert_called_once_with(NEW_DOCS_EXPECTED_FOR_NOTIFY, mock_app_config)
    mock_alert.assert_not_called()

# Add mock_app_config fixture
def test_run_check_success_no_new_urls(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow when no new URLs are found."""
    mock_notify, mock_alert = mock_notifier
    mock_load, mock_save = mock_storage

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = CURRENT_DOCS_FOUND # Parser returns list of dicts
    mock_load.return_value = CURRENT_URLS_FOUND_SET # Storage load returns the same set of URLs

    # Run the main function
    main.run_check(mock_app_config)

    # Assertions
    mock_fetcher.assert_called_once_with(
        url=mock_app_config.target_url,
        timeout=mock_app_config.request_timeout,
        retries=mock_app_config.request_retries,
        delay=mock_app_config.request_retry_delay
    )
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    mock_load.assert_called_once_with(mock_app_config)
    mock_save.assert_not_called() # Save should not be called
    # Check notifier calls
    mock_notify.assert_not_called()
    mock_alert.assert_not_called()

# Add mock_app_config fixture
def test_run_check_first_run(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow on the first execution."""
    mock_notify, mock_alert = mock_notifier
    mock_load, mock_save = mock_storage

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = CURRENT_DOCS_FOUND # Parser returns list of dicts
    # Simulate GCS NotFound exception for first run
    mock_load.side_effect = NotFound("GCS object not found") # storage.load returns empty set in this case internally

    # Run the main function
    main.run_check(mock_app_config)

    # Assertions
    mock_fetcher.assert_called_once_with(
        url=mock_app_config.target_url,
        timeout=mock_app_config.request_timeout,
        retries=mock_app_config.request_retries,
        delay=mock_app_config.request_retry_delay
    )
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    mock_load.assert_called_once_with(mock_app_config)
    # Check save was called with the set of currently found URLs for the first run
    mock_save.assert_called_once_with(CURRENT_URLS_FOUND_SET, mock_app_config)
    # Check notifier calls (should not notify on first run)
    mock_notify.assert_not_called()
    mock_alert.assert_not_called()

# Add mock_app_config fixture
def test_run_check_fetch_failure(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow when fetcher fails."""
    mock_notify, mock_alert = mock_notifier
    mock_load, mock_save = mock_storage # Get mocks even if not used

    # Configure mocks
    mock_fetcher.return_value = None # Simulate fetch failure

    # Run the main function
    main.run_check(mock_app_config)

    # Assertions
    mock_fetcher.assert_called_once_with(
        url=mock_app_config.target_url,
        timeout=mock_app_config.request_timeout,
        retries=mock_app_config.request_retries,
        delay=mock_app_config.request_retry_delay
    )
    mock_parser.assert_not_called() # Should not parse if fetch fails
    mock_load.assert_not_called()   # Should not load if fetch fails
    mock_save.assert_not_called()   # Should not save if fetch fails
    mock_notify.assert_not_called()
    # Use the actual message from main.py
    mock_alert.assert_called_once_with(f"HTML fetch failed: {mock_app_config.target_url}", config=mock_app_config) # Check admin alert

# Add mock_app_config fixture
def test_run_check_parser_returns_empty(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the flow when parser finds no links."""
    mock_notify, mock_alert = mock_notifier
    mock_load, mock_save = mock_storage

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    mock_parser.return_value = [] # Simulate parser finding no documents (empty list)
    mock_load.return_value = KNOWN_URLS_INITIAL # Simulate loading initial URLs

    # Run the main function
    main.run_check(mock_app_config)

    # Assertions
    mock_fetcher.assert_called_once_with(
        url=mock_app_config.target_url,
        timeout=mock_app_config.request_timeout,
        retries=mock_app_config.request_retries,
        delay=mock_app_config.request_retry_delay
    )
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    mock_load.assert_called_once_with(mock_app_config)
    mock_save.assert_not_called() # Save should not be called if parser returns empty
    mock_notify.assert_not_called()
    mock_alert.assert_not_called()

# Add mock_app_config fixture
def test_run_check_unexpected_exception(mock_fetcher, mock_parser, mock_storage, mock_notifier, mock_app_config):
    """Test the main run_check flow handles unexpected errors during parsing."""
    mock_notify, mock_alert = mock_notifier
    mock_load, mock_save = mock_storage # Get mocks

    # Configure mocks
    mock_fetcher.return_value = MOCK_HTML
    test_exception = ValueError("Something unexpected happened")
    mock_parser.side_effect = test_exception # Simulate error during parsing
    # Load might still be called before parser error, depending on exact flow
    mock_load.return_value = KNOWN_URLS_INITIAL

    # Run the main function
    main.run_check(mock_app_config)

    # Assertions
    mock_fetcher.assert_called_once_with(
        url=mock_app_config.target_url,
        timeout=mock_app_config.request_timeout,
        retries=mock_app_config.request_retries,
        delay=mock_app_config.request_retry_delay
    )
    mock_parser.assert_called_once_with(MOCK_HTML, mock_app_config.target_url)
    # Load might still be called before parser error
    # mock_load.assert_called_once_with(mock_app_config) # This depends on exact execution order
    mock_save.assert_not_called() # Save should not happen if parser fails
    mock_notify.assert_not_called() # Should not notify if error occurred
    # Use the actual message from main.py
    mock_alert.assert_called_once_with(
        "run_check: An unexpected error occurred.",
        error=test_exception,
        config=mock_app_config
    )

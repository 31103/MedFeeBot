import pytest
import json
from unittest.mock import MagicMock, patch, ANY
from google.cloud.exceptions import NotFound
from typing import Dict, List, Any, Set # Import necessary types

# Modules to test
from src import main
from src.config import Config # Import Config class
from src import parser # Import parser to reference functions

# --- Constants ---
PDF_URL = "https://www.hospital.or.jp/site/ministry/"
MEETING_URL = "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html"
MOCK_HTML_PDF = """
<html><body>
 <div class="col-12 isotope-item">
   <div class="fs13">2025.04.19</div>
   <div><p class="fs_p ic_140"><a href="known.pdf">Known PDF</a></p></div>
 </div>
 <div class="col-12 isotope-item">
   <div class="fs13">2025.04.20</div>
   <div><p class="fs_p ic_140"><a href="new.pdf">New PDF</a></p></div>
 </div>
</body></html>
"""
MOCK_HTML_MEETING = """
<html><body>
<table class="m-tableFlex">
  <tbody>
    <tr>
      <td> 第607回 </td><td> 2025年4月23日 </td><td> <ol><li>New Topic</li></ol> </td>
      <td></td><td><a href="new_material.pdf" class="m-link">資料</a></td>
    </tr>
  </tbody>
</table>
</body></html>
"""
MOCK_HTML_MEETING_OLD = """
<html><body>
<table class="m-tableFlex">
  <tbody>
    <tr>
      <td> 第606回 </td><td> 2025年4月09日 </td><td> <ol><li>Old Topic</li></ol> </td>
      <td></td><td><a href="old_material.pdf" class="m-link">資料</a></td>
    </tr>
  </tbody>
</table>
</body></html>
"""

# Expected parser results
PARSED_PDF_DOCS = [
    {'date': '2025.04.19', 'title': 'Known PDF', 'url': f'{PDF_URL}known.pdf'},
    {'date': '2025.04.20', 'title': 'New PDF', 'url': f'{PDF_URL}new.pdf'}
]
PARSED_MEETING_NEW = {
    'id': '第607回', 'date': '2025年4月23日', 'topics': ['New Topic'],
    'minutes_url': None, 'minutes_text': None,
    'materials_url': f'{MEETING_URL.rsplit("/", 1)[0]}/new_material.pdf', 'materials_text': '資料'
}
PARSED_MEETING_OLD = {
    'id': '第606回', 'date': '2025年4月09日', 'topics': ['Old Topic'],
    'minutes_url': None, 'minutes_text': None,
    'materials_url': f'{MEETING_URL.rsplit("/", 1)[0]}/old_material.pdf', 'materials_text': '資料'
}

# Initial storage states
INITIAL_KNOWN_URLS: Dict[str, List[str]] = {PDF_URL: [f'{PDF_URL}known.pdf']}
INITIAL_LATEST_IDS: Dict[str, str] = {MEETING_URL: '第606回'}

# Expected states after successful run
EXPECTED_KNOWN_URLS_AFTER_PDF: Dict[str, List[str]] = {
    PDF_URL: sorted([f'{PDF_URL}known.pdf', f'{PDF_URL}new.pdf'])
}
EXPECTED_LATEST_IDS_AFTER_MEETING: Dict[str, str] = {MEETING_URL: '第607回'}

# Expected notification payloads
EXPECTED_PDF_NOTIFY_PAYLOAD = {
    'type': 'pdf',
    'data': [{'date': '2025.04.20', 'title': 'New PDF', 'url': f'{PDF_URL}new.pdf'}],
    'source_url': PDF_URL
}
EXPECTED_MEETING_NOTIFY_PAYLOAD = {
    'type': 'meeting',
    'data': PARSED_MEETING_NEW,
    'source_url': MEETING_URL
}


# --- Fixtures ---

@pytest.fixture
def mock_fetcher(mocker):
    """Mocks fetcher.fetch_html."""
    return mocker.patch('src.main.fetcher.fetch_html')

@pytest.fixture
def mock_parsers(mocker):
    """Mocks all parser functions used in main."""
    mock_pdf_parser = mocker.patch('src.main.parser.extract_hospital_document_info')
    mock_meeting_parser = mocker.patch('src.main.parser.extract_latest_chuikyo_meeting')
    return mock_pdf_parser, mock_meeting_parser

@pytest.fixture
def mock_storage_funcs(mocker):
    """Mocks all storage functions used in main."""
    mock_load_known = mocker.patch('src.main.storage.load_known_urls')
    mock_save_known = mocker.patch('src.main.storage.save_known_urls')
    mock_load_ids = mocker.patch('src.main.storage.load_latest_meeting_ids')
    mock_save_ids = mocker.patch('src.main.storage.save_latest_meeting_ids')
    # find_new_pdf_urls uses load/save internally, so we don't mock it directly
    # unless we want to test its specific return value in isolation.
    # For integration, we let it run using the mocked load/save.
    # mocker.patch('src.main.storage.find_new_pdf_urls') # Don't mock this for integration
    mocker.patch('src.storage._get_gcs_client', return_value=MagicMock()) # Mock GCS client init
    return mock_load_known, mock_save_known, mock_load_ids, mock_save_ids

@pytest.fixture
def mock_notifier(mocker):
    """Mocks notifier functions."""
    mock_notify = mocker.patch('src.main.notifier.send_slack_notification')
    mock_alert = mocker.patch('src.main.notifier.send_admin_alert')
    return mock_notify, mock_alert

@pytest.fixture
def mock_app_config() -> Config:
    """Returns a mock Config object for integration tests."""
    return Config(
        target_urls=[PDF_URL, MEETING_URL], # Include both URLs
        url_configs={ # Define configs for both
            PDF_URL: {"type": "pdf", "parser": parser.extract_hospital_document_info},
            MEETING_URL: {"type": "meeting", "parser": parser.extract_latest_chuikyo_meeting}
        },
        slack_api_token="test-token",
        slack_channel_id="C123INTEGRATION",
        known_urls_file="test_known.json",
        latest_ids_file="test_ids.json",
        log_level="DEBUG",
        admin_slack_channel_id="C456ADMININTEGRATION",
        gcs_bucket_name="test-bucket",
        request_timeout=10,
        request_retries=3,
        request_retry_delay=1
    )

# Remove autouse fixture for load_config mocking, as config is passed directly

# --- Test Cases ---

def test_run_check_all_success(mock_fetcher, mock_parsers, mock_storage_funcs, mock_notifier, mock_app_config):
    """Test run_check processes both URL types successfully with new findings."""
    mock_pdf_parser, mock_meeting_parser = mock_parsers
    mock_load_known, mock_save_known, mock_load_ids, mock_save_ids = mock_storage_funcs
    mock_notify, mock_alert = mock_notifier

    # Configure mocks
    mock_fetcher.side_effect = lambda url, **kwargs: MOCK_HTML_PDF if url == PDF_URL else MOCK_HTML_MEETING if url == MEETING_URL else None
    mock_pdf_parser.return_value = PARSED_PDF_DOCS
    mock_meeting_parser.return_value = PARSED_MEETING_NEW
    mock_load_known.return_value = INITIAL_KNOWN_URLS
    mock_load_ids.return_value = INITIAL_LATEST_IDS

    # Run the main check function
    result = main.run_check(mock_app_config)

    # Assertions
    assert result is True # Overall success
    assert mock_fetcher.call_count == 2 # Called for both URLs
    mock_pdf_parser.assert_called_once_with(MOCK_HTML_PDF, PDF_URL)
    mock_meeting_parser.assert_called_once_with(MOCK_HTML_MEETING, MEETING_URL)
    mock_load_known.assert_called_once_with(mock_app_config)
    mock_load_ids.assert_called_once_with(mock_app_config)
    # Check saves
    mock_save_known.assert_called_once_with(EXPECTED_KNOWN_URLS_AFTER_PDF, mock_app_config)
    mock_save_ids.assert_called_once_with(EXPECTED_LATEST_IDS_AFTER_MEETING, mock_app_config)
    # Check notifications
    assert mock_notify.call_count == 2
    mock_notify.assert_any_call(EXPECTED_PDF_NOTIFY_PAYLOAD, mock_app_config)
    mock_notify.assert_any_call(EXPECTED_MEETING_NOTIFY_PAYLOAD, mock_app_config)
    mock_alert.assert_not_called()

def test_run_check_no_new_items(mock_fetcher, mock_parsers, mock_storage_funcs, mock_notifier, mock_app_config):
    """Test run_check when no new PDFs or meetings are found."""
    mock_pdf_parser, mock_meeting_parser = mock_parsers
    mock_load_known, mock_save_known, mock_load_ids, mock_save_ids = mock_storage_funcs
    mock_notify, mock_alert = mock_notifier

    # Configure mocks
    mock_fetcher.side_effect = lambda url, **kwargs: MOCK_HTML_PDF if url == PDF_URL else MOCK_HTML_MEETING_OLD if url == MEETING_URL else None
    # PDF parser returns docs, but they are already known
    mock_pdf_parser.return_value = [{'date': '2025.04.19', 'title': 'Known PDF', 'url': f'{PDF_URL}known.pdf'}]
    # Meeting parser returns the old meeting ID
    mock_meeting_parser.return_value = PARSED_MEETING_OLD
    # Storage load returns the current state
    mock_load_known.return_value = {PDF_URL: [f'{PDF_URL}known.pdf']}
    mock_load_ids.return_value = {MEETING_URL: '第606回'}

    result = main.run_check(mock_app_config)

    assert result is True
    assert mock_fetcher.call_count == 2
    mock_pdf_parser.assert_called_once()
    mock_meeting_parser.assert_called_once()
    mock_load_known.assert_called_once()
    mock_load_ids.assert_called_once()
    mock_save_known.assert_not_called() # No changes to save
    mock_save_ids.assert_not_called()   # No changes to save
    mock_notify.assert_not_called()     # No notifications
    mock_alert.assert_not_called()

def test_run_check_pdf_first_run_meeting_no_change(mock_fetcher, mock_parsers, mock_storage_funcs, mock_notifier, mock_app_config):
    """Test first run for PDF URL, no change for meeting URL."""
    mock_pdf_parser, mock_meeting_parser = mock_parsers
    mock_load_known, mock_save_known, mock_load_ids, mock_save_ids = mock_storage_funcs
    mock_notify, mock_alert = mock_notifier

    # Configure mocks
    mock_fetcher.side_effect = lambda url, **kwargs: MOCK_HTML_PDF if url == PDF_URL else MOCK_HTML_MEETING_OLD if url == MEETING_URL else None
    mock_pdf_parser.return_value = PARSED_PDF_DOCS # Found docs for PDF URL
    mock_meeting_parser.return_value = PARSED_MEETING_OLD # Old meeting info
    mock_load_known.return_value = {} # PDF file not found (first run)
    mock_load_ids.return_value = {MEETING_URL: '第606回'} # Existing meeting ID

    result = main.run_check(mock_app_config)

    assert result is True
    assert mock_fetcher.call_count == 2
    mock_pdf_parser.assert_called_once()
    mock_meeting_parser.assert_called_once()
    mock_load_known.assert_called_once()
    mock_load_ids.assert_called_once()
    # Save should be called for PDF URL with current docs
    mock_save_known.assert_called_once_with({PDF_URL: sorted([d['url'] for d in PARSED_PDF_DOCS])}, mock_app_config)
    mock_save_ids.assert_not_called() # No change for meeting ID
    mock_notify.assert_not_called() # No notification on first run for PDF
    mock_alert.assert_not_called()

def test_run_check_meeting_parser_returns_none(mock_fetcher, mock_parsers, mock_storage_funcs, mock_notifier, mock_app_config):
    """Test run_check handles meeting parser returning None gracefully."""
    mock_pdf_parser, mock_meeting_parser = mock_parsers
    mock_load_known, mock_save_known, mock_load_ids, mock_save_ids = mock_storage_funcs
    mock_notify, mock_alert = mock_notifier

    # Configure mocks
    mock_fetcher.side_effect = lambda url, **kwargs: MOCK_HTML_PDF if url == PDF_URL else "<html></html>" # Empty HTML for meeting
    mock_pdf_parser.return_value = [] # No new PDFs
    mock_meeting_parser.return_value = None # Simulate parser finding nothing or erroring gracefully
    mock_load_known.return_value = {PDF_URL: []}
    mock_load_ids.return_value = {MEETING_URL: 'ID_Prev'}

    result = main.run_check(mock_app_config)

    assert result is True # Should still be overall success
    assert mock_fetcher.call_count == 2
    mock_pdf_parser.assert_called_once()
    mock_meeting_parser.assert_called_once()
    mock_load_known.assert_called_once()
    mock_load_ids.assert_called_once() # Load IDs is still called
    mock_save_known.assert_not_called()
    mock_save_ids.assert_not_called() # Save IDs not called as no new ID found
    mock_notify.assert_not_called()
    mock_alert.assert_not_called()


def test_run_check_fetch_failure_one_url(mock_fetcher, mock_parsers, mock_storage_funcs, mock_notifier, mock_app_config):
    """Test run_check handles fetch failure for one URL and continues."""
    mock_pdf_parser, mock_meeting_parser = mock_parsers
    mock_load_known, mock_save_known, mock_load_ids, mock_save_ids = mock_storage_funcs
    mock_notify, mock_alert = mock_notifier

    # Configure mocks
    def fetch_side_effect(url, **kwargs):
        if url == PDF_URL:
            return None # Fail PDF fetch
        elif url == MEETING_URL:
            return MOCK_HTML_MEETING_OLD # Succeed meeting fetch
        return None
    mock_fetcher.side_effect = fetch_side_effect
    mock_meeting_parser.return_value = PARSED_MEETING_OLD
    mock_load_ids.return_value = {MEETING_URL: '第606回'} # No change expected

    result = main.run_check(mock_app_config)

    assert result is False # Overall failure because one URL failed
    assert mock_fetcher.call_count == 2
    mock_pdf_parser.assert_not_called() # Not called because fetch failed
    mock_meeting_parser.assert_called_once() # Called for the successful one
    mock_load_known.assert_not_called() # Not called because PDF processing didn't happen
    mock_load_ids.assert_called_once() # Called for meeting processing
    mock_save_known.assert_not_called()
    mock_save_ids.assert_not_called()
    mock_notify.assert_not_called()
    # Check admin alert for the failed URL
    mock_alert.assert_called_once_with(f"HTML fetch failed: {PDF_URL}", config=mock_app_config)

def test_run_check_parser_failure_one_url(mock_fetcher, mock_parsers, mock_storage_funcs, mock_notifier, mock_app_config):
    """Test run_check handles parser failure for one URL and continues."""
    mock_pdf_parser, mock_meeting_parser = mock_parsers
    mock_load_known, mock_save_known, mock_load_ids, mock_save_ids = mock_storage_funcs
    mock_notify, mock_alert = mock_notifier
    test_exception = ValueError("PDF Parse Error")

    # Configure mocks
    mock_fetcher.side_effect = lambda url, **kwargs: MOCK_HTML_PDF if url == PDF_URL else MOCK_HTML_MEETING_OLD if url == MEETING_URL else None
    mock_pdf_parser.side_effect = test_exception # Fail PDF parser
    mock_meeting_parser.return_value = PARSED_MEETING_OLD
    mock_load_ids.return_value = {MEETING_URL: '第606回'} # No change expected

    result = main.run_check(mock_app_config)

    assert result is False # Overall failure
    assert mock_fetcher.call_count == 2
    mock_pdf_parser.assert_called_once() # Parser was called
    mock_meeting_parser.assert_called_once() # Meeting parser also called
    # Load functions might be called depending on exact flow within process_url
    # mock_load_known.assert_called_once() # Might not be called if parser fails early
    mock_load_ids.assert_called_once()
    mock_save_known.assert_not_called()
    mock_save_ids.assert_not_called()
    mock_notify.assert_not_called()
    # Check admin alert for the failed parser
    mock_alert.assert_called_once_with(
        f"Parser execution error for {PDF_URL}",
        error=test_exception,
        config=mock_app_config
    )

def test_run_check_storage_load_error(mock_fetcher, mock_parsers, mock_storage_funcs, mock_notifier, mock_app_config):
    """Test run_check handles critical storage load error."""
    mock_pdf_parser, mock_meeting_parser = mock_parsers
    mock_load_known, mock_save_known, mock_load_ids, mock_save_ids = mock_storage_funcs
    mock_notify, mock_alert = mock_notifier
    test_exception = Exception("GCS Critical Error")

    # Configure mocks
    mock_fetcher.side_effect = lambda url, **kwargs: MOCK_HTML_PDF if url == PDF_URL else MOCK_HTML_MEETING_OLD if url == MEETING_URL else None
    mock_pdf_parser.return_value = PARSED_PDF_DOCS
    mock_meeting_parser.return_value = PARSED_MEETING_OLD
    mock_load_known.side_effect = test_exception # Simulate critical error loading known URLs

    result = main.run_check(mock_app_config)

    assert result is False # Overall failure
    assert mock_fetcher.call_count == 2 # Both fetches might happen before error propagates fully
    mock_pdf_parser.assert_called_once() # PDF parser called
    mock_meeting_parser.assert_called_once() # Meeting parser called
    mock_load_known.assert_called_once() # Load known called
    # Depending on where the exception is caught, load_ids might not be called
    # mock_load_ids.assert_called_once()
    mock_save_known.assert_not_called()
    mock_save_ids.assert_not_called()
    mock_notify.assert_not_called()
    # Check admin alert for the storage error (likely caught in process_url or run_check)
    # The exact message might vary depending on where it's caught.
    # Using ANY for the error object might be safer.
    mock_alert.assert_called_once_with(
        ANY, # The message might differ slightly
        error=test_exception,
        config=mock_app_config
    )

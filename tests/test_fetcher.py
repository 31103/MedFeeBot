import pytest
import requests
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
from unittest.mock import MagicMock, patch

from src.fetcher import fetch_html, HEADERS
from src.config import Config # Import Config class (still needed for mock_config fixture)

TEST_URL = "http://test.com"
MOCK_HTML_CONTENT = "<html><body>Test HTML</body></html>"

# --- Fixtures ---

@pytest.fixture
def mock_requests_get(mocker):
    """Fixture to mock requests.get."""
    return mocker.patch('requests.get')

@pytest.fixture
def mock_time_sleep(mocker):
    """Fixture to mock time.sleep."""
    return mocker.patch('time.sleep')

@pytest.fixture
def mock_config() -> Config:
    """Returns a mock Config object for fetcher tests."""
    # Create a Config instance with specific values for testing fetcher
    return Config(
        target_url="dummy", # Not directly used by fetch_html
        slack_api_token="dummy",
        slack_channel_id="dummy",
        known_urls_file_path="dummy",
        log_level="DEBUG",
        request_timeout=10, # Mocked value
        request_retries=3,  # Mocked value
        request_retry_delay=1 # Mocked value
    )

# Remove the autouse fixture for load_config as fetch_html no longer calls it
# @pytest.fixture(autouse=True)
# def mock_load_config_in_fetcher(mocker, mock_config):
#     """Fixture to automatically mock load_config within src.fetcher."""
#     mocker.patch('src.fetcher.load_config', return_value=mock_config)

# --- Test Cases ---

# Pass timeout, retries, delay explicitly
def test_fetch_html_success(mock_requests_get, mock_time_sleep):
    """Test fetch_html successfully retrieves HTML on the first attempt."""
    # Configure the mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = MOCK_HTML_CONTENT
    mock_response.apparent_encoding = 'utf-8' # Mock apparent encoding
    mock_response.raise_for_status.return_value = None # No exception for 200
    mock_requests_get.return_value = mock_response

    # Call fetch_html with explicit arguments
    html = fetch_html(TEST_URL, timeout=10, retries=3, delay=1)

    assert html == MOCK_HTML_CONTENT
    # Assert requests.get was called with the passed arguments
    mock_requests_get.assert_called_once_with(
        TEST_URL,
        headers=HEADERS,
        timeout=10 # Assert against the passed value
    )
    # Ensure encoding was set based on apparent_encoding
    assert mock_response.encoding == 'utf-8'
    mock_time_sleep.assert_not_called() # No retries needed

# Pass timeout, retries, delay explicitly
def test_fetch_html_http_error_retry_and_fail(mock_requests_get, mock_time_sleep):
    """Test fetch_html retries on HTTPError and fails after max retries."""
    # Configure the mock response to raise HTTPError
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = HTTPError("Not Found")
    mock_requests_get.return_value = mock_response

    # Call fetch_html with explicit arguments
    html = fetch_html(TEST_URL, timeout=10, retries=3, delay=1)

    assert html is None
    # Assert requests.get was called the correct number of times
    assert mock_requests_get.call_count == 3 # Assert against the passed retries
    # Assert time.sleep was called the correct number of times with the correct delay
    assert mock_time_sleep.call_count == 3 - 1 # Assert against the passed retries
    mock_time_sleep.assert_called_with(1) # Assert against the passed delay

# Pass timeout, retries, delay explicitly
def test_fetch_html_connection_error_retry_and_fail(mock_requests_get, mock_time_sleep):
    """Test fetch_html retries on ConnectionError and fails after max retries."""
    mock_requests_get.side_effect = ConnectionError("Cannot connect")

    # Call fetch_html with explicit arguments
    html = fetch_html(TEST_URL, timeout=10, retries=3, delay=1)

    assert html is None
    assert mock_requests_get.call_count == 3
    assert mock_time_sleep.call_count == 3 - 1
    mock_time_sleep.assert_called_with(1)

# Pass timeout, retries, delay explicitly
def test_fetch_html_timeout_retry_and_fail(mock_requests_get, mock_time_sleep):
    """Test fetch_html retries on Timeout and fails after max retries."""
    mock_requests_get.side_effect = Timeout("Request timed out")

    # Call fetch_html with explicit arguments
    html = fetch_html(TEST_URL, timeout=10, retries=3, delay=1)

    assert html is None
    assert mock_requests_get.call_count == 3
    assert mock_time_sleep.call_count == 3 - 1
    mock_time_sleep.assert_called_with(1)

# Pass timeout, retries, delay explicitly
def test_fetch_html_generic_request_exception_retry_and_fail(mock_requests_get, mock_time_sleep):
    """Test fetch_html retries on a generic RequestException."""
    mock_requests_get.side_effect = RequestException("Some request error")

    # Call fetch_html with explicit arguments
    html = fetch_html(TEST_URL, timeout=10, retries=3, delay=1)

    assert html is None
    assert mock_requests_get.call_count == 3
    assert mock_time_sleep.call_count == 3 - 1
    mock_time_sleep.assert_called_with(1)

# Pass timeout, retries, delay explicitly
def test_fetch_html_unexpected_exception_retry_and_fail(mock_requests_get, mock_time_sleep):
    """Test fetch_html retries on an unexpected non-RequestException."""
    mock_requests_get.side_effect = ValueError("Unexpected error during request")

    # Call fetch_html with explicit arguments
    html = fetch_html(TEST_URL, timeout=10, retries=3, delay=1)

    assert html is None
    assert mock_requests_get.call_count == 3
    assert mock_time_sleep.call_count == 3 - 1
    mock_time_sleep.assert_called_with(1)

# Pass timeout, retries, delay explicitly
def test_fetch_html_success_on_retry(mock_requests_get, mock_time_sleep):
    """Test fetch_html succeeds on the second attempt."""
    # First call raises error, second call succeeds
    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    mock_error_response.raise_for_status.side_effect = HTTPError("Server Error")

    mock_success_response = MagicMock()
    mock_success_response.status_code = 200
    mock_success_response.text = MOCK_HTML_CONTENT
    mock_success_response.apparent_encoding = 'shift_jis'
    mock_success_response.raise_for_status.return_value = None

    mock_requests_get.side_effect = [mock_error_response, mock_success_response]

    # Call fetch_html with explicit arguments
    html = fetch_html(TEST_URL, timeout=10, retries=3, delay=1)

    assert html == MOCK_HTML_CONTENT
    assert mock_requests_get.call_count == 2 # Failed once, succeeded once
    mock_time_sleep.assert_called_once_with(1) # Assert against the passed delay
    # Ensure encoding was set correctly on the successful response
    assert mock_success_response.encoding == 'shift_jis'

# Consider adding tests for logging output if necessary, using caplog fixture.

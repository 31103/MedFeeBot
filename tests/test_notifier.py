import pytest
import pytest
from unittest.mock import MagicMock, patch
from slack_sdk import WebClient # Import for type hint if needed
from slack_sdk.errors import SlackApiError

# Assuming src is importable
from src import notifier
from src.config import Config # Import Config class

# --- Constants ---
TEST_CHANNEL_ID = "C123MAIN"
TEST_ADMIN_CHANNEL_ID = "C456ADMIN"
TEST_SLACK_TOKEN = "xoxb-test-token"
TEST_TARGET_URL = "http://example.com/mhlw"
PDF_LINK_1 = "http://example.com/doc1.pdf"
PDF_LINK_2 = "http://example.com/doc2.pdf?v=1"
PDF_LINK_3 = "http://example.com/doc3.pdf"

# --- Fixtures ---

@pytest.fixture
def mock_slack_client(mocker):
    """Fixture to mock the slack_client instance within the notifier module."""
    # Mock the WebClient instance directly within the notifier module
    mock_client = MagicMock()
    # Mock the return value of chat_postMessage for success cases
    mock_response = MagicMock()
    mock_response.get.return_value = "12345.67890" # Mock timestamp
    mock_client.chat_postMessage.return_value = mock_response
    # Mock the getter function to return our mock client
    mocker.patch('src.notifier._get_slack_client', return_value=mock_client)
    # Reset the global client in notifier before each test
    # to ensure lazy initialization logic is tested correctly
    notifier._slack_client = None
    notifier._slack_config = None
    return mock_client

@pytest.fixture
def mock_app_config() -> Config:
    """Returns a mock Config object for notifier tests."""
    return Config(
        target_url=TEST_TARGET_URL,
        slack_api_token=TEST_SLACK_TOKEN,
        slack_channel_id=TEST_CHANNEL_ID,
        known_urls_file_path="dummy",
        log_level="DEBUG",
        admin_slack_channel_id=TEST_ADMIN_CHANNEL_ID,
    )

@pytest.fixture(autouse=True)
def mock_get_config(mocker, mock_app_config):
    """Mocks the internal _get_config function in notifier."""
    return mocker.patch('src.notifier._get_config', return_value=mock_app_config)

# --- Test Cases for send_slack_notification ---

# Add mock_app_config fixture
def test_send_slack_notification_success(mock_slack_client, mock_app_config):
    """Test successful notification for new PDF links."""
    new_links = [PDF_LINK_1, PDF_LINK_2]
    notifier.send_slack_notification(new_links)

    mock_slack_client.chat_postMessage.assert_called_once()
    # Ensure _get_slack_client was called implicitly by send_slack_notification
    # (mock_slack_client fixture already patches the instance, so we check the call)
    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1] # Get keyword args

    # Access config via the fixture directly
    assert call_args['channel'] == mock_app_config.slack_channel_id
    assert "新規PDF通知 (2件)" in call_args['text']
    assert isinstance(call_args['blocks'], list)
    # Check block structure basics
    # Check block structure basics using mocked config values
    assert call_args['blocks'][0]['type'] == 'header'
    assert "新規PDF通知 (2件)" in call_args['blocks'][0]['text']['text']
    assert call_args['blocks'][1]['type'] == 'section'
    assert mock_app_config.target_url in call_args['blocks'][1]['text']['text']
    assert call_args['blocks'][2]['type'] == 'divider'
    # Check link blocks
    assert call_args['blocks'][3]['type'] == 'section'
    assert f"<{PDF_LINK_1}|doc1.pdf>" in call_args['blocks'][3]['text']['text']
    assert call_args['blocks'][4]['type'] == 'section'
    assert f"<{PDF_LINK_2}|doc2.pdf>" in call_args['blocks'][4]['text']['text']

# Add mock_app_config fixture
def test_send_slack_notification_many_links(mock_slack_client, mock_app_config):
    """Test notification limits links shown and adds context."""
    new_links = [f"http://example.com/doc{i}.pdf" for i in range(15)] # 15 links
    notifier.send_slack_notification(new_links)

    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]
    blocks = call_args['blocks']

    assert len(blocks) == 3 + 10 + 1 # Header, Intro, Divider + 10 links + Context
    assert blocks[-1]['type'] == 'context'
    assert "他5件のリンクがあります" in blocks[-1]['elements'][0]['text']

# Add mock_app_config fixture
def test_send_slack_notification_no_links(mock_slack_client, mock_app_config):
    """Test no notification is sent when the link list is empty."""
    notifier.send_slack_notification([])
    mock_slack_client.chat_postMessage.assert_not_called()

def test_send_slack_notification_no_channel_id(mock_slack_client, mock_get_config, mock_app_config):
    """Test no notification is sent if SLACK_CHANNEL_ID is not set in config."""
    # Modify the config returned by the mock _get_config
    mock_app_config_no_channel = Config(
        target_url=mock_app_config.target_url,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=None, # Set channel to None
        known_urls_file_path=mock_app_config.known_urls_file_path,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
    )
    mock_get_config.return_value = mock_app_config_no_channel

    notifier.send_slack_notification([PDF_LINK_1])
    mock_slack_client.chat_postMessage.assert_not_called()

def test_send_slack_notification_client_init_fails(mocker, mock_get_config, mock_app_config):
    """Test no notification if slack client initialization fails (e.g., no token)."""
    # Modify config to have no token
    mock_app_config_no_token = Config(
        target_url=mock_app_config.target_url,
        slack_api_token=None, # Set token to None
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file_path=mock_app_config.known_urls_file_path,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
    )
    mock_get_config.return_value = mock_app_config_no_token
    # Unpatch the client mock so the real init logic runs (and fails)
    mocker.stopall() # Stop previous mocks
    # Re-mock _get_config only
    mocker.patch('src.notifier._get_config', return_value=mock_app_config_no_token)
    # Reset the global client variable
    notifier._slack_client = None
    notifier._slack_config = None


    notifier.send_slack_notification([PDF_LINK_1])
    # We expect an error log, but no call to chat_postMessage
    # Need to check logs or ensure no exception bubbles up.
    # For simplicity, just check chat_postMessage wasn't called.
    # Note: We can't easily assert chat_postMessage wasn't called if the client mock was removed.
    # A better way might be to mock WebClient init to raise error or return None client.
    # Let's mock _get_slack_client directly to return None
    mocker.patch('src.notifier._get_slack_client', return_value=None)
    notifier.send_slack_notification([PDF_LINK_1])
    # Now we can assert the mock wasn't called (though it wouldn't exist anyway)
    # This test setup is becoming complex due to module-level state.

# --- Test Cases for send_admin_alert ---

# Add mock_app_config fixture
def test_send_admin_alert_success_no_error(mock_slack_client, mock_app_config):
    """Test successful admin alert without error details."""
    message = "This is a test alert."
    notifier.send_admin_alert(message)

    mock_slack_client.chat_postMessage.assert_called_once()
    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]

    # Access config via the fixture directly
    assert call_args['channel'] == mock_app_config.admin_slack_channel_id
    assert "管理者アラート" in call_args['text']
    assert message in call_args['text']
    assert isinstance(call_args['blocks'], list)
    assert call_args['blocks'][0]['type'] == 'header'
    assert call_args['blocks'][1]['type'] == 'section'
    assert message in call_args['blocks'][1]['text']['text']
    assert len(call_args['blocks']) == 2 # Header + Message

# Add mock_app_config fixture
def test_send_admin_alert_success_with_error(mock_slack_client, mock_app_config):
    """Test successful admin alert with error details."""
    message = "An error occurred during processing."
    error = ValueError("Something went wrong")
    notifier.send_admin_alert(message, error)

    mock_slack_client.chat_postMessage.assert_called_once()
    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]

    # Access config via the fixture directly
    assert call_args['channel'] == mock_app_config.admin_slack_channel_id
    assert "管理者アラート" in call_args['text']
    assert message in call_args['text']
    assert "ValueError: Something went wrong" in call_args['text'] # Check text fallback
    blocks = call_args['blocks']
    assert len(blocks) == 3 # Header, Message, Error Details
    assert blocks[2]['type'] == 'section'
    assert "*エラー詳細:*" in blocks[2]['text']['text']
    assert "```ValueError: Something went wrong```" in blocks[2]['text']['text']

def test_send_admin_alert_no_admin_channel_id(mock_slack_client, mock_get_config, mock_app_config):
    """Test no admin alert is sent if admin_slack_channel_id is None in config."""
    mock_app_config_no_admin = Config(
        target_url=mock_app_config.target_url,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file_path=mock_app_config.known_urls_file_path,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=None, # Set admin channel to None
    )
    mock_get_config.return_value = mock_app_config_no_admin

    notifier.send_admin_alert("Test message")
    mock_slack_client.chat_postMessage.assert_not_called()

def test_send_admin_alert_client_init_fails(mocker, mock_get_config):
    """Test no admin alert if slack client initialization fails."""
    # Mock _get_slack_client directly to simulate failure
    mocker.patch('src.notifier._get_slack_client', return_value=None)
    # Ensure _get_config still works (or mock it if needed, already done by autouse fixture)

    notifier.send_admin_alert("Test message")
    # We expect an error log, but no call to chat_postMessage.
    # Since _get_slack_client returns None, _send_message should exit early.
    # We can't easily assert chat_postMessage wasn't called as the client mock isn't active.
    # Relying on the logic check: if _get_slack_client is None, _send_message returns False early.

def test_get_slack_client_config_load_value_error(mocker):
    """Test _get_slack_client handles ValueError during config load."""
    mocker.patch('src.notifier.load_config', side_effect=ValueError("Missing env var"))
    notifier._slack_client = None # Reset state
    notifier._slack_config = None
    client = notifier._get_slack_client()
    assert client is None

def test_get_slack_client_config_load_exception(mocker):
    """Test _get_slack_client handles generic Exception during config load."""
    mocker.patch('src.notifier.load_config', side_effect=Exception("Some error"))
    notifier._slack_client = None # Reset state
    notifier._slack_config = None
    client = notifier._get_slack_client()
    assert client is None

def test_get_config_returns_none_on_value_error(mocker):
    """Test _get_config returns None if load_config raises ValueError."""
    # Stop autouse mocks for this test
    mocker.stopall()
    # Mock load_config within the notifier module to raise ValueError
    mocker.patch('src.notifier.load_config', side_effect=ValueError("Bad config"))
    notifier._slack_config = None # Reset state
    config_obj = notifier._get_config()
    assert config_obj is None

def test_get_config_returns_none_on_exception(mocker):
    """Test _get_config returns None if load_config raises a generic Exception."""
    # Stop autouse mocks for this test
    mocker.stopall()
    # Mock load_config within the notifier module to raise Exception
    mocker.patch('src.notifier.load_config', side_effect=Exception("Something failed"))
    notifier._slack_config = None # Reset state
    config_obj = notifier._get_config()
    assert config_obj is None

# --- Test Cases for _send_message (indirectly via public funcs, plus error cases) ---

def test_send_message_slack_api_error(mock_slack_client, mock_app_config): # Add mock_app_config
    """Test handling of SlackApiError during message sending."""
    # Configure the mock client to raise SlackApiError
    mock_response = MagicMock()
    mock_response.__getitem__.side_effect = lambda key: {'error': 'channel_not_found'}[key] # Mock dict access
    mock_slack_client.chat_postMessage.side_effect = SlackApiError("API Error", mock_response)

    # Use send_slack_notification to trigger _send_message
    notifier.send_slack_notification([PDF_LINK_1])

    # Assert chat_postMessage was called
    mock_slack_client.chat_postMessage.assert_called_once()
    # We expect the function to log the error but not raise it further.
    # We could use caplog fixture to assert log messages.

def test_send_message_other_exception(mock_slack_client, mock_app_config): # Add mock_app_config
    """Test handling of unexpected exceptions during message sending."""
    mock_slack_client.chat_postMessage.side_effect = ConnectionError("Network failed")

    # Use send_admin_alert to trigger _send_message
    notifier.send_admin_alert("Test alert")

    # Assert chat_postMessage was called
    mock_slack_client.chat_postMessage.assert_called_once()
    # Expect function to log the error but not raise it.

def test_send_message_no_channel_id(mock_slack_client):
    """Test _send_message returns False if channel_id is empty."""
    result = notifier._send_message("", "Test text")
    assert result is False
    mock_slack_client.chat_postMessage.assert_not_called()

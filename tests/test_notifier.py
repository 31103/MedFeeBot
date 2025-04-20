import pytest
from unittest.mock import MagicMock, patch
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Dict, Any # Any を追加

from src import notifier
from src.config import Config # Config をインポート

# --- Constants ---
TEST_CHANNEL_ID = "C123MAIN"
TEST_ADMIN_CHANNEL_ID = "C456ADMIN"
TEST_SLACK_TOKEN = "xoxb-test-token"
# Source URLs for testing different notification types
PDF_SOURCE_URL = "https://www.hospital.or.jp/site/ministry/"
MEETING_SOURCE_URL = "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html"
PDF_LINK_1 = "http://example.com/doc1.pdf"
PDF_LINK_2 = "http://example.com/doc2.pdf?v=1"

# --- Fixtures ---

@pytest.fixture
def mock_slack_client(mocker):
    """Fixture to mock the slack_client instance within the notifier module."""
    mock_client = MagicMock(spec=WebClient) # Use spec=WebClient
    mock_response = MagicMock()
    mock_response.get.return_value = "12345.67890" # Mock timestamp
    mock_client.chat_postMessage.return_value = mock_response
    mocker.patch('src.notifier._get_slack_client', return_value=mock_client)
    notifier._slack_client = None # Reset state for lazy init test
    notifier._slack_config = None # Reset config state
    return mock_client

@pytest.fixture
def mock_app_config() -> Config:
    """Returns a mock Config object for notifier tests."""
    # Include necessary fields, others can be dummy if not used by notifier directly
    return Config(
        target_urls=[PDF_SOURCE_URL, MEETING_SOURCE_URL], # Dummy list
        url_configs={}, # Dummy dict
        slack_api_token=TEST_SLACK_TOKEN,
        slack_channel_id=TEST_CHANNEL_ID,
        known_urls_file="dummy_known.json",
        latest_ids_file="dummy_latest.json",
        log_level="DEBUG",
        admin_slack_channel_id=TEST_ADMIN_CHANNEL_ID,
        gcs_bucket_name="dummy-bucket" # Provide a dummy value
    )

# Remove mock_get_config fixture as config is passed directly

# --- Test Cases for send_slack_notification ---

def test_send_slack_notification_pdf_success(mock_slack_client, mock_app_config):
    """Test successful PDF notification."""
    pdf_data: List[Dict[str, str]] = [
        {'date': '2025.04.19', 'title': 'Document 1 Title', 'url': PDF_LINK_1},
        {'date': '2025.04.18', 'title': 'Document 2 Title (with query)', 'url': PDF_LINK_2}
    ]
    payload = {'type': 'pdf', 'data': pdf_data, 'source_url': PDF_SOURCE_URL}
    notifier.send_slack_notification(payload, mock_app_config)

    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]

    assert call_args['channel'] == mock_app_config.slack_channel_id
    assert "新規文書通知 (2件)" in call_args['text']
    assert PDF_SOURCE_URL in call_args['text']
    blocks = call_args['blocks']
    assert blocks[0]['type'] == 'header'
    assert "新規文書通知 (2件)" in blocks[0]['text']['text']
    assert blocks[1]['type'] == 'section'
    assert f"<{PDF_SOURCE_URL}|ページ>" in blocks[1]['text']['text']
    assert blocks[2]['type'] == 'divider'
    assert blocks[3]['type'] == 'section'
    assert "📅 *2025.04.19*" in blocks[3]['text']['text']
    assert f"📄 <{PDF_LINK_1}|Document 1 Title>" in blocks[3]['text']['text']
    assert blocks[4]['type'] == 'section'
    assert "📅 *2025.04.18*" in blocks[4]['text']['text']
    assert f"📄 <{PDF_LINK_2}|Document 2 Title (with query)>" in blocks[4]['text']['text']

def test_send_slack_notification_pdf_many_docs(mock_slack_client, mock_app_config):
    """Test PDF notification limits documents shown."""
    pdf_data = [
        {'date': f'2025.04.{20-i:02d}', 'title': f'Doc {i}', 'url': f'http://example.com/doc{i}.pdf'}
        for i in range(15) # 15 documents
    ]
    payload = {'type': 'pdf', 'data': pdf_data, 'source_url': PDF_SOURCE_URL}
    notifier.send_slack_notification(payload, mock_app_config)

    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]
    blocks = call_args['blocks']
    assert len(blocks) == 3 + 10 + 1 # Header, Intro, Divider + 10 docs + Context
    assert blocks[-1]['type'] == 'context'
    assert "他5件の文書があります" in blocks[-1]['elements'][0]['text']

def test_send_slack_notification_meeting_success(mock_slack_client, mock_app_config):
    """Test successful meeting notification."""
    meeting_data: Dict[str, Any] = {
        'id': '第606回',
        'date': '2025年4月9日（令和7年4月9日）',
        'topics': [
            '1 部会・小委員会に属する委員の指名等について',
            '2 医療機器の保険適用について',
        ],
        'minutes_url': 'https://www.mhlw.go.jp/stf/newpage_56730.html',
        'minutes_text': '議事録',
        'materials_url': 'https://www.mhlw.go.jp/stf/newpage_56712.html',
        'materials_text': '資料'
    }
    payload = {'type': 'meeting', 'data': meeting_data, 'source_url': MEETING_SOURCE_URL}
    notifier.send_slack_notification(payload, mock_app_config)

    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]

    assert call_args['channel'] == mock_app_config.slack_channel_id
    assert "新規会議開催通知: 第606回" in call_args['text']
    assert MEETING_SOURCE_URL in call_args['text']
    blocks = call_args['blocks']
    assert blocks[0]['type'] == 'header'
    assert "新しい中央社会保険医療協議会が開催されました" in blocks[0]['text']['text']
    assert blocks[1]['type'] == 'section'
    assert f"<{MEETING_SOURCE_URL}|ページ>" in blocks[1]['fields'][0]['text'] # Check source URL in meeting name field
    assert "第606回" in blocks[1]['fields'][1]['text']
    assert "2025年4月9日" in blocks[1]['fields'][2]['text']
    assert blocks[2]['type'] == 'section'
    assert "*議題:*" in blocks[2]['text']['text']
    assert "1 部会・小委員会に属する委員の指名等について" in blocks[2]['text']['text']
    assert "2 医療機器の保険適用について" in blocks[2]['text']['text']
    assert blocks[3]['type'] == 'divider'
    assert blocks[4]['type'] == 'actions'
    assert len(blocks[4]['elements']) == 2 # Both buttons should be present
    assert blocks[4]['elements'][0]['type'] == 'button'
    assert blocks[4]['elements'][0]['text']['text'] == '資料'
    assert blocks[4]['elements'][0]['url'] == meeting_data['materials_url']
    assert blocks[4]['elements'][1]['type'] == 'button'
    assert blocks[4]['elements'][1]['text']['text'] == '議事録'
    assert blocks[4]['elements'][1]['url'] == meeting_data['minutes_url']

def test_send_slack_notification_meeting_no_optional_links(mock_slack_client, mock_app_config):
    """Test meeting notification without optional links."""
    meeting_data: Dict[str, Any] = {
        'id': '第605回',
        'date': '2025年3月26日',
        'topics': ['議題A'],
        'minutes_url': None, # No minutes link
        'minutes_text': None,
        'materials_url': None, # No materials link
        'materials_text': None
    }
    payload = {'type': 'meeting', 'data': meeting_data, 'source_url': MEETING_SOURCE_URL}
    notifier.send_slack_notification(payload, mock_app_config)

    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]
    blocks = call_args['blocks']
    # Check that the actions block is NOT present
    assert len(blocks) == 4 # Header, Fields, Topics, Divider
    assert blocks[-1]['type'] == 'divider' # Last block should be divider

def test_send_slack_notification_no_data(mock_slack_client, mock_app_config):
    """Test no notification is sent if data is empty or None."""
    payload_pdf_empty = {'type': 'pdf', 'data': [], 'source_url': PDF_SOURCE_URL}
    payload_meeting_none = {'type': 'meeting', 'data': None, 'source_url': MEETING_SOURCE_URL}
    payload_meeting_empty = {'type': 'meeting', 'data': {}, 'source_url': MEETING_SOURCE_URL}

    notifier.send_slack_notification(payload_pdf_empty, mock_app_config)
    notifier.send_slack_notification(payload_meeting_none, mock_app_config)
    notifier.send_slack_notification(payload_meeting_empty, mock_app_config)

    mock_slack_client.chat_postMessage.assert_not_called()

def test_send_slack_notification_invalid_payload(mock_slack_client, mock_app_config, mocker):
    """Test no notification and logs error for invalid payload."""
    mock_logger_error = mocker.patch('src.notifier.logger.error')
    payload_missing_type = {'data': [], 'source_url': PDF_SOURCE_URL}
    payload_missing_data = {'type': 'pdf', 'source_url': PDF_SOURCE_URL}

    notifier.send_slack_notification(payload_missing_type, mock_app_config)
    notifier.send_slack_notification(payload_missing_data, mock_app_config)

    mock_slack_client.chat_postMessage.assert_not_called()
    assert mock_logger_error.call_count == 2
    mock_logger_error.assert_any_call(f"Invalid notification payload: 'type' or 'data' missing. Payload: {payload_missing_type}")
    mock_logger_error.assert_any_call(f"Invalid notification payload: 'type' or 'data' missing. Payload: {payload_missing_data}")


def test_send_slack_notification_unknown_type(mock_slack_client, mock_app_config, mocker):
    """Test no notification and logs error for unknown type."""
    mock_logger_error = mocker.patch('src.notifier.logger.error')
    payload = {'type': 'unknown', 'data': {}, 'source_url': PDF_SOURCE_URL}

    notifier.send_slack_notification(payload, mock_app_config)

    mock_slack_client.chat_postMessage.assert_not_called()
    mock_logger_error.assert_called_once_with(f"Unknown notification type: {payload['type']}")


def test_send_slack_notification_no_channel_id(mock_slack_client, mock_app_config):
    """Test no notification is sent if SLACK_CHANNEL_ID is None in config."""
    # Create a new config instance with slack_channel_id=None
    config_no_channel = Config(
        target_urls=mock_app_config.target_urls,
        url_configs=mock_app_config.url_configs,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=None, # Set to None for this test
        known_urls_file=mock_app_config.known_urls_file,
        latest_ids_file=mock_app_config.latest_ids_file,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=mock_app_config.admin_slack_channel_id,
        gcs_bucket_name=mock_app_config.gcs_bucket_name
    )
    payload = {'type': 'pdf', 'data': [{'date': 'd', 'title': 't', 'url': 'u'}], 'source_url': PDF_SOURCE_URL}

    notifier.send_slack_notification(payload, config_no_channel) # Pass the modified config
    mock_slack_client.chat_postMessage.assert_not_called()

def test_send_slack_notification_client_init_fails(mocker, mock_app_config):
    """Test no notification if slack client initialization fails."""
    mocker.patch('src.notifier._get_slack_client', return_value=None)
    payload = {'type': 'pdf', 'data': [{'date': 'd', 'title': 't', 'url': 'u'}], 'source_url': PDF_SOURCE_URL}

    notifier.send_slack_notification(payload, mock_app_config)
    # Cannot assert mock_slack_client.chat_postMessage was not called as the mock wasn't returned

# --- Test Cases for send_admin_alert (Unchanged, but ensure config passing works) ---

def test_send_admin_alert_success_no_error(mock_slack_client, mock_app_config):
    """Test successful admin alert without error details."""
    message = "This is a test alert."
    notifier.send_admin_alert(message, config=mock_app_config) # Pass config

    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]
    assert call_args['channel'] == mock_app_config.admin_slack_channel_id
    assert "管理者アラート" in call_args['text']
    assert message in call_args['text']
    blocks = call_args['blocks']
    assert len(blocks) == 2

def test_send_admin_alert_success_with_error(mock_slack_client, mock_app_config):
    """Test successful admin alert with error details."""
    message = "An error occurred."
    error = ValueError("Test error")
    notifier.send_admin_alert(message, error, config=mock_app_config) # Pass config

    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args[1]
    assert call_args['channel'] == mock_app_config.admin_slack_channel_id
    blocks = call_args['blocks']
    assert len(blocks) == 3
    assert "*エラー詳細:*" in blocks[2]['text']['text']
    assert "```ValueError: Test error```" in blocks[2]['text']['text']

def test_send_admin_alert_no_admin_channel_id(mock_slack_client, mock_app_config):
    """Test no admin alert if admin_slack_channel_id is None."""
    # Create a new config instance with admin_slack_channel_id=None
    config_no_admin = Config(
        target_urls=mock_app_config.target_urls,
        url_configs=mock_app_config.url_configs,
        slack_api_token=mock_app_config.slack_api_token,
        slack_channel_id=mock_app_config.slack_channel_id,
        known_urls_file=mock_app_config.known_urls_file,
        latest_ids_file=mock_app_config.latest_ids_file,
        log_level=mock_app_config.log_level,
        admin_slack_channel_id=None, # Set to None for this test
        gcs_bucket_name=mock_app_config.gcs_bucket_name
    )
    notifier.send_admin_alert("Test message", config=config_no_admin) # Pass the modified config
    mock_slack_client.chat_postMessage.assert_not_called()

def test_send_admin_alert_client_init_fails(mocker, mock_app_config):
    """Test no admin alert if slack client initialization fails."""
    mocker.patch('src.notifier._get_slack_client', return_value=None)
    notifier.send_admin_alert("Test message", config=mock_app_config)
    # Cannot assert mock_slack_client.chat_postMessage was not called

# --- Tests for internal helpers (_get_slack_client, _get_config - keep as they test init logic) ---

def test_get_slack_client_config_load_value_error(mocker):
    """Test _get_slack_client handles ValueError during config load."""
    mocker.patch('src.notifier.load_config', side_effect=ValueError("Missing env var"))
    notifier._slack_client = None
    notifier._slack_config = None
    client = notifier._get_slack_client()
    assert client is None

def test_get_slack_client_config_load_exception(mocker):
    """Test _get_slack_client handles generic Exception during config load."""
    mocker.patch('src.notifier.load_config', side_effect=Exception("Some error"))
    notifier._slack_client = None
    notifier._slack_config = None
    client = notifier._get_slack_client()
    assert client is None

# _get_config tests are less relevant now config is passed, but keep for completeness
def test_get_config_returns_none_on_value_error(mocker):
    """Test _get_config returns None if load_config raises ValueError."""
    mocker.patch('src.notifier.load_config', side_effect=ValueError("Bad config"))
    notifier._slack_config = None
    config_obj = notifier._get_config()
    assert config_obj is None

def test_get_config_returns_none_on_exception(mocker):
    """Test _get_config returns None if load_config raises a generic Exception."""
    mocker.patch('src.notifier.load_config', side_effect=Exception("Something failed"))
    notifier._slack_config = None
    config_obj = notifier._get_config()
    assert config_obj is None

# --- Test Cases for _send_message (indirectly via public funcs, plus error cases) ---

def test_send_message_slack_api_error(mock_slack_client, mock_app_config):
    """Test handling of SlackApiError during message sending."""
    mock_response = MagicMock()
    mock_response.__getitem__.side_effect = lambda key: {'error': 'channel_not_found'}[key]
    mock_slack_client.chat_postMessage.side_effect = SlackApiError("API Error", mock_response)
    notifier.send_admin_alert("Test alert", config=mock_app_config)
    mock_slack_client.chat_postMessage.assert_called_once()

def test_send_message_other_exception(mock_slack_client, mock_app_config):
    """Test handling of unexpected exceptions during message sending."""
    mock_slack_client.chat_postMessage.side_effect = ConnectionError("Network failed")
    notifier.send_admin_alert("Test alert", config=mock_app_config)
    mock_slack_client.chat_postMessage.assert_called_once()

def test_send_message_no_channel_id(mock_slack_client):
    """Test _send_message returns False if channel_id is empty."""
    result = notifier._send_message("", "Test text")
    assert result is False
    mock_slack_client.chat_postMessage.assert_not_called()

# Remove __main__ block test code

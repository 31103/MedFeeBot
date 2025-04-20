import pytest
from src.config import Config
from src import parser # Import parser for function references

# Define constants used in the fixture
PDF_URL = "https://www.hospital.or.jp/site/ministry/"
MEETING_URL = "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html"
TEST_CHANNEL_ID = "C123INTEGRATION"
TEST_ADMIN_CHANNEL_ID = "C456ADMININTEGRATION"
TEST_SLACK_TOKEN = "test-token"
TEST_BUCKET_NAME = "test-bucket"
TEST_KNOWN_URLS_FILE = "test_known.json"
TEST_LATEST_IDS_FILE = "test_ids.json"

@pytest.fixture
def mock_app_config() -> Config:
    """Provides a mock Config object shared across test files."""
    return Config(
        # Required fields first
        slack_api_token=TEST_SLACK_TOKEN,
        slack_channel_id=TEST_CHANNEL_ID,
        # Fields with defaults
        target_urls=[PDF_URL, MEETING_URL],
        url_configs={
            PDF_URL: {"type": "pdf", "parser": parser.extract_hospital_document_info},
            MEETING_URL: {"type": "meeting", "parser": parser.extract_latest_chuikyo_meeting}
        },
        known_urls_file=TEST_KNOWN_URLS_FILE,
        latest_ids_file=TEST_LATEST_IDS_FILE,
        log_level="DEBUG",
        admin_slack_channel_id=TEST_ADMIN_CHANNEL_ID,
        gcs_bucket_name=TEST_BUCKET_NAME,
        request_timeout=10,
        request_retries=3,
        request_retry_delay=1
    )

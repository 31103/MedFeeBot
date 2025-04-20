import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Any # List, Dict, Callable, Any を追加
from dotenv import load_dotenv
from google.cloud import secretmanager as sm # Correct import
from src import parser # parser モジュールをインポート

# .env file loading is now done inside load_config()

@dataclass(frozen=True) # frozen=True makes instances immutable
class Config:
    """Application configuration."""
    # --- Core Settings (Required fields first) ---
    slack_api_token: str
    slack_channel_id: str

    # --- Core Settings (Fields with defaults) ---
    target_urls: List[str] = field(default_factory=list) # 監視対象URLのリスト
    url_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict) # URLごとの設定

    # --- Storage Settings (Fields with defaults) ---
    gcs_bucket_name: str | None = None # GCSバケット名 (オプション)
    known_urls_file: str = "known_urls.json" # PDF状態ファイル名 (デフォルト値)
    latest_ids_file: str = "latest_ids.json" # 会議ID状態ファイル名 (デフォルト値)

    # --- Optional Settings ---
    log_level: str = "INFO"
    admin_slack_channel_id: str | None = None

    # --- Request Settings ---
    request_timeout: int = 30
    request_retries: int = 3
    request_retry_delay: int = 5

    # --- Deprecated (for reference, will be removed later) ---
    # target_url: str (replaced by target_urls)
    # known_urls_file_path: str (replaced by known_urls_file)
    # gcs_object_name: str (replaced by known_urls_file/latest_ids_file)


def access_secret_version(project_id: str, secret_id: str, version_id: str = "latest") -> str:
    """
    Access the payload for the given secret version.
    """
    client = sm.SecretManagerServiceClient() # Use the aliased import
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def load_config() -> Config:
    """
    Loads configuration from environment variables and Secret Manager,
    returning a Config object.
    Prioritizes Secret Manager for SLACK_API_TOKEN if SLACK_SECRET_ID is set.
    """
    load_dotenv() # Load .env for local development primarily

    # --- Target URLs ---
    target_urls_str = os.getenv('TARGET_URLS', '')
    target_urls_list: List[str] = [url.strip() for url in target_urls_str.split(',') if url.strip()]
    if not target_urls_list:
        raise ValueError("Environment variable 'TARGET_URLS' is not set or empty.")
    logging.info(f"Loaded TARGET_URLS: {target_urls_list}")

    # --- URL Configurations (Hardcoded for now based on plan) ---
    # TODO: Consider loading this from a separate config file or env var if it grows
    url_configs_dict: Dict[str, Dict[str, Any]] = {
        "https://www.hospital.or.jp/site/ministry/": {
            "type": "pdf",
            "parser": parser.extract_hospital_document_info # PDF情報リストを返す関数
        },
        "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html": {
            "type": "meeting",
            "parser": parser.extract_latest_chuikyo_meeting # 会議情報辞書 or None を返す関数
        }
        # Add other URLs here if needed
    }

    # --- Validate TARGET_URLS against URL_CONFIGS ---
    configured_urls = list(url_configs_dict.keys())
    valid_target_urls: List[str] = []
    for url in target_urls_list:
        if url in configured_urls:
            valid_target_urls.append(url)
        else:
            logging.warning(f"URL '{url}' is in TARGET_URLS but not configured in URL_CONFIGS. It will be ignored.")
    if not valid_target_urls:
         raise ValueError("No valid and configured URLs found in TARGET_URLS.")
    logging.info(f"Using configured URLs: {valid_target_urls}")


    # --- Slack API Token Handling ---
    slack_secret_id = os.getenv("SLACK_SECRET_ID")
    if slack_secret_id:
        logging.info(f"Attempting to load Slack token from Secret Manager: {slack_secret_id}")
        slack_api_token = access_secret_version(slack_secret_id)
    else:
        logging.info("SLACK_SECRET_ID not set, attempting to load SLACK_API_TOKEN from environment.")
        slack_api_token = os.getenv("SLACK_API_TOKEN", "")

    if not slack_api_token:
        # This error occurs if neither SLACK_SECRET_ID nor SLACK_API_TOKEN yields a value
        raise ValueError("Slack API token could not be loaded. Set SLACK_SECRET_ID (GCP) or SLACK_API_TOKEN (local).")

    # --- Other Configurations ---
    slack_channel_id = os.getenv("SLACK_CHANNEL_ID", "")
    if not slack_channel_id:
        raise ValueError("Environment variable 'SLACK_CHANNEL_ID' is not set.")

    # --- Storage File Names ---
    known_urls_file = os.getenv("KNOWN_URLS_FILE", "known_urls.json")
    latest_ids_file = os.getenv("LATEST_IDS_FILE", "latest_ids.json")

    # --- Log Level ---
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level_str not in valid_log_levels:
        logging.warning(
            f"Invalid log level '{log_level_str}' specified. Using 'INFO'."
        )
        log_level_str = "INFO"

    # Get optional values, treat empty string as None
    admin_slack_channel_id_env = os.getenv("ADMIN_SLACK_CHANNEL_ID")
    admin_slack_channel_id = admin_slack_channel_id_env if admin_slack_channel_id_env else None

    gcs_bucket_name_env = os.getenv("GCS_BUCKET_NAME")
    gcs_bucket_name = gcs_bucket_name_env if gcs_bucket_name_env else None

    # gcs_object_name is deprecated

    # --- Request Settings ---
    request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
    request_retries = int(os.getenv("REQUEST_RETRIES", "3"))
    request_retry_delay = int(os.getenv("REQUEST_RETRY_DELAY", "5"))


    # Filter url_configs_dict to only include valid target URLs
    final_url_configs = {url: config for url, config in url_configs_dict.items() if url in valid_target_urls}

    return Config(
        target_urls=valid_target_urls, # Use the validated list
        url_configs=final_url_configs, # Use the filtered configs
        slack_api_token=slack_api_token,
        slack_channel_id=slack_channel_id,
        known_urls_file=known_urls_file,
        latest_ids_file=latest_ids_file,
        log_level=log_level_str,
        admin_slack_channel_id=admin_slack_channel_id,
        gcs_bucket_name=gcs_bucket_name,
        # gcs_object_name is removed
        request_timeout=request_timeout,
        request_retries=request_retries,
        request_retry_delay=request_retry_delay,
    )

# --- Example Usage ---
if __name__ == "__main__":
    try:
        config_instance = load_config()
        print("Configuration loaded successfully:")
        print("Configuration loaded successfully:")
        print(f"  Target URLs: {config_instance.target_urls}")
        # print(f"  URL Configs: {config_instance.url_configs}") # Might be too verbose
        print(f"  Slack Token: {'*' * 8 if config_instance.slack_api_token else 'Not Set'}")
        print(f"  Slack Channel ID: {config_instance.slack_channel_id}")
        print(f"  Admin Channel ID: {config_instance.admin_slack_channel_id or 'Not Set'}")
        print(f"  Known URLs File: {config_instance.known_urls_file}")
        print(f"  Latest IDs File: {config_instance.latest_ids_file}")
        print(f"  Log Level: {config_instance.log_level}")
        print(f"  GCS Bucket: {config_instance.gcs_bucket_name or 'Not Set'}")
        # print(f"  GCS Object: (removed)")
        print(f"  Request Timeout: {config_instance.request_timeout}")
        print(f"  Request Retries: {config_instance.request_retries}")
        print(f"  Request Retry Delay: {config_instance.request_retry_delay}")

    except ValueError as e:
        print(f"Error loading configuration: {e}")

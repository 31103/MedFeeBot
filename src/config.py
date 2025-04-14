import os
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

# .env file loading is now done inside load_config()

@dataclass(frozen=True) # frozen=True makes instances immutable
class Config:
    """Application configuration."""
    target_url: str
    slack_api_token: str
    slack_channel_id: str
    known_urls_file_path: str # Path for local storage
    log_level: str = "INFO"
    admin_slack_channel_id: str | None = None
    gcs_bucket_name: str | None = None # For cloud phase
    gcs_object_name: str | None = None # For cloud phase

    # Other settings not directly from env vars
    request_timeout: int = 30
    request_retries: int = 3
    request_retry_delay: int = 5

    # __post_init__ removed as validation is now done in load_config

def load_config() -> Config:
    """Loads configuration from environment variables and returns a Config object."""
    load_dotenv() # Ensure .env is loaded whenever config is requested

    target_url = os.getenv("TARGET_URL", "")
    if not target_url:
        raise ValueError("Environment variable 'TARGET_URL' is not set.")

    slack_api_token = os.getenv("SLACK_API_TOKEN", "")
    if not slack_api_token:
        raise ValueError("Environment variable 'SLACK_API_TOKEN' is not set.")

    slack_channel_id = os.getenv("SLACK_CHANNEL_ID", "")
    if not slack_channel_id:
        raise ValueError("Environment variable 'SLACK_CHANNEL_ID' is not set.")

    # Default local storage path if not set via env var
    known_urls_file_path = os.getenv("KNOWN_URLS_FILE_PATH", "known_urls.json")

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

    gcs_object_name_env = os.getenv("GCS_OBJECT_NAME")
    gcs_object_name = gcs_object_name_env if gcs_object_name_env else None

    # Other settings (could be env vars too if needed)
    request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
    request_retries = int(os.getenv("REQUEST_RETRIES", "3"))
    request_retry_delay = int(os.getenv("REQUEST_RETRY_DELAY", "5"))


    return Config(
        target_url=target_url,
        slack_api_token=slack_api_token,
        slack_channel_id=slack_channel_id,
        known_urls_file_path=known_urls_file_path,
        log_level=log_level_str,
        admin_slack_channel_id=admin_slack_channel_id,
        gcs_bucket_name=gcs_bucket_name,
        gcs_object_name=gcs_object_name,
        request_timeout=request_timeout,
        request_retries=request_retries,
        request_retry_delay=request_retry_delay,
    )

# --- Example Usage ---
if __name__ == "__main__":
    try:
        config_instance = load_config()
        print("Configuration loaded successfully:")
        print(f"  Target URL: {config_instance.target_url}")
        print(f"  Slack Token: {'*' * 8 if config_instance.slack_api_token else 'Not Set'}")
        print(f"  Slack Channel ID: {config_instance.slack_channel_id}")
        print(f"  Admin Channel ID: {config_instance.admin_slack_channel_id or 'Not Set'}")
        print(f"  Known URLs Path: {config_instance.known_urls_file_path}")
        print(f"  Log Level: {config_instance.log_level}")
        print(f"  GCS Bucket: {config_instance.gcs_bucket_name or 'Not Set'}")
        print(f"  GCS Object: {config_instance.gcs_object_name or 'Not Set'}")
        print(f"  Request Timeout: {config_instance.request_timeout}")
        print(f"  Request Retries: {config_instance.request_retries}")
        print(f"  Request Retry Delay: {config_instance.request_retry_delay}")

    except ValueError as e:
        print(f"Error loading configuration: {e}")

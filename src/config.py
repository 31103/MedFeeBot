import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv
from google.cloud import secretmanager

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


def _get_secret(secret_id: str) -> str:
    """Retrieves a secret value from Google Cloud Secret Manager."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(name=secret_id)
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logging.error(f"Failed to access secret: {secret_id}. Error: {e}")
        raise ValueError(f"Failed to access secret: {secret_id}") from e


def load_config() -> Config:
    """
    Loads configuration from environment variables and Secret Manager,
    returning a Config object.
    Prioritizes Secret Manager for SLACK_API_TOKEN if SLACK_SECRET_ID is set.
    """
    load_dotenv() # Load .env for local development primarily

    target_url = os.getenv("TARGET_URL", "")
    if not target_url:
        raise ValueError("Environment variable 'TARGET_URL' is not set.")

    # --- Slack API Token Handling ---
    slack_secret_id = os.getenv("SLACK_SECRET_ID")
    if slack_secret_id:
        logging.info(f"Attempting to load Slack token from Secret Manager: {slack_secret_id}")
        slack_api_token = _get_secret(slack_secret_id)
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

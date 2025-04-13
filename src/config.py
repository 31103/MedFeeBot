import os
from dotenv import load_dotenv
import logging

# .envファイルから環境変数を読み込む (存在する場合)
# Cloud Functions環境など、.envがない場合は無視される
load_dotenv()

# --- 環境変数から設定値を取得 ---

# 監視対象のURL (必須)
TARGET_URL: str = os.getenv("TARGET_URL", "")
if not TARGET_URL:
    raise ValueError("環境変数 'TARGET_URL' が設定されていません。")

# Slack Bot Token (必須)
SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
if not SLACK_BOT_TOKEN:
    raise ValueError("環境変数 'SLACK_BOT_TOKEN' が設定されていません。")

# Slack通知先チャンネルID (必須)
SLACK_CHANNEL_ID: str = os.getenv("SLACK_CHANNEL_ID", "")
if not SLACK_CHANNEL_ID:
    raise ValueError("環境変数 'SLACK_CHANNEL_ID' が設定されていません。")

# Slack管理者通知用チャンネルID (オプション)
# 設定されていない場合は、管理者通知は行わない
SLACK_ADMIN_CHANNEL_ID: str | None = os.getenv("SLACK_ADMIN_CHANNEL_ID")

# GCSバケット名 (将来のフェーズで使用)
GCS_BUCKET_NAME: str | None = os.getenv("GCS_BUCKET_NAME")

# GCSファイルパス (将来のフェーズで使用)
GCS_FILE_PATH: str | None = os.getenv("GCS_FILE_PATH")

# ログレベル (デフォルト: INFO)
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
# 有効なログレベルか確認 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
if LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    logging.warning(f"無効なログレベル '{LOG_LEVEL}' が指定されました。INFOレベルを使用します。")
    LOG_LEVEL = "INFO"

# --- その他の設定 ---
# HTTPリクエストのタイムアウト秒数
REQUEST_TIMEOUT: int = 30
# HTTPリクエストのリトライ回数
REQUEST_RETRIES: int = 3
# HTTPリクエストのリトライ間隔 (秒)
REQUEST_RETRY_DELAY: int = 5

# 初回実行フラグ (環境変数で制御可能にするか検討)
# IS_FIRST_RUN: bool = os.getenv("IS_FIRST_RUN", "false").lower() == "true"

if __name__ == "__main__":
    # モジュールとして実行された場合、読み込まれた設定を表示 (デバッグ用)
    print(f"TARGET_URL: {TARGET_URL}")
    print(f"SLACK_BOT_TOKEN: {'*' * 8 if SLACK_BOT_TOKEN else 'Not Set'}")
    print(f"SLACK_CHANNEL_ID: {SLACK_CHANNEL_ID}")
    print(f"SLACK_ADMIN_CHANNEL_ID: {SLACK_ADMIN_CHANNEL_ID or 'Not Set'}")
    print(f"GCS_BUCKET_NAME: {GCS_BUCKET_NAME or 'Not Set'}")
    print(f"GCS_FILE_PATH: {GCS_FILE_PATH or 'Not Set'}")
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print(f"REQUEST_TIMEOUT: {REQUEST_TIMEOUT}")
    print(f"REQUEST_RETRIES: {REQUEST_RETRIES}")
    print(f"REQUEST_RETRY_DELAY: {REQUEST_RETRY_DELAY}")

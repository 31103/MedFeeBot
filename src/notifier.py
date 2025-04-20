from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from .config import load_config, Config # Import load_config
from .logger import logger

# Global variable to hold the client instance (lazy initialized)
_slack_client: WebClient | None = None
_slack_config: Config | None = None # To store loaded config

def _get_slack_client() -> WebClient | None:
    """Initializes and returns the Slack client instance."""
    global _slack_client, _slack_config
    if _slack_client is None:
        try:
            # Load config if not already loaded by this module
            if _slack_config is None:
                 _slack_config = load_config()

            if _slack_config.slack_api_token:
                _slack_client = WebClient(token=_slack_config.slack_api_token)
                logger.info("Slack client initialized.")
            else:
                logger.warning("SLACK_API_TOKEN is not set. Slack notifications disabled.")
                # Keep _slack_client as None
        except ValueError as e:
            logger.error(f"Failed to load config for Slack client: {e}. Slack notifications disabled.")
            # Keep _slack_client as None
        except Exception as e:
             logger.exception(f"Unexpected error initializing Slack client: {e}. Slack notifications disabled.")
             # Keep _slack_client as None
    return _slack_client

def _get_config() -> Config | None:
    """Loads and returns the config, storing it globally."""
    global _slack_config
    if _slack_config is None:
        try:
            _slack_config = load_config()
        except ValueError as e:
            logger.error(f"Failed to load config: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error loading config: {e}")
            return None
    return _slack_config


def _send_message(channel_id: str, text: str, blocks: list | None = None) -> bool:
    """
    指定されたチャンネルにメッセージを送信する内部関数。
    Slackクライアントを必要に応じて初期化する。

    Args:
        channel_id (str): 送信先のチャンネルID。
        text (str): 通知などに表示されるプレーンテキスト。
        blocks (list | None): Slack Block Kit形式のメッセージペイロード。

    Returns:
        bool: 送信に成功した場合はTrue、失敗した場合はFalse。
    """
    client = _get_slack_client()
    if not client:
        logger.error("Slack client is not available. Cannot send message.")
        return False
    if not channel_id:
        logger.error("Destination channel ID is not specified.")
        return False

    try:
        logger.debug(f"Sending Slack message (Channel: {channel_id})")
        response = client.chat_postMessage(
            channel=channel_id,
            text=text, # Fallback text for notifications
            blocks=blocks # Block Kit payload
        )
        logger.info(f"Slack message sent successfully (Channel: {channel_id}, ts: {response.get('ts')})")
        return True
    except SlackApiError as e:
        logger.error(f"Slack API error occurred (Channel: {channel_id}): {e.response['error']}")
        logger.debug(f"Slack API error details: {e.response}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error sending Slack message (Channel: {channel_id}): {e}")
        return False

from typing import List, Dict, Any # Add Any for type hinting

# ... (rest of the imports and _get_slack_client, _get_config) ...

def _build_pdf_notification_blocks(data: List[Dict[str, str]], source_url: str) -> List[Dict[str, Any]]:
    """Helper function to build Block Kit for PDF notifications."""
    num_documents = len(data)
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📄 新規文書通知 ({num_documents}件)", "emoji": True}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"監視対象サイト (<{source_url}|ページ>) で新しい文書が検出されました。"}
        },
        {"type": "divider"}
    ]

    link_limit = 10 # Limit the number of detailed links shown
    for i, doc in enumerate(data):
        if i < link_limit:
            date_str = doc.get('date', '日付不明')
            title_str = doc.get('title', 'タイトル不明')
            url_str = doc.get('url', '#')
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"📅 *{date_str}*\n📄 <{url_str}|{title_str}>"}
            })
        elif i == link_limit:
             blocks.append({
                "type": "context",
                "elements": [{"type": "plain_text", "text": f"...他{num_documents - link_limit}件の文書があります。", "emoji": True}]
            })
             break
    return blocks

def _build_meeting_notification_blocks(data: Dict[str, Any], source_url: str) -> List[Dict[str, Any]]:
    """Helper function to build Block Kit for meeting notifications."""
    meeting_id = data.get('id', '不明')
    meeting_date = data.get('date', '不明')
    topics = data.get('topics', [])
    minutes_url = data.get('minutes_url')
    minutes_text = data.get('minutes_text', '議事録') # Default text
    materials_url = data.get('materials_url')
    materials_text = data.get('materials_text', '資料') # Default text

    # Format topics list
    topics_str = "\n".join(f"- {topic}" for topic in topics) if topics else "議題情報なし"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":mega: 新しい中央社会保険医療協議会が開催されました",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                # Assuming the meeting name is fixed for this source URL
                {"type": "mrkdwn", "text": f"*会議名:*\n中央社会保険医療協議会 (<{source_url}|ページ>)"},
                {"type": "mrkdwn", "text": f"*回数:*\n{meeting_id}"},
                {"type": "mrkdwn", "text": f"*開催日:*\n{meeting_date}"}
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*議題:*\n```\n{topics_str}\n```"
            }
        },
        {"type": "divider"}
    ]

    # Action buttons for links (only if URL exists)
    action_elements = []
    if materials_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": materials_text, "emoji": True},
            "url": materials_url
        })
    if minutes_url:
         action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": minutes_text, "emoji": True},
            "url": minutes_url
        })

    if action_elements:
        blocks.append({
            "type": "actions",
            "elements": action_elements
        })

    return blocks


def send_slack_notification(payload: Dict[str, Any], cfg: Config):
    """
    新規検知情報（PDFまたは会議）を整形してSlackのメインチャンネルに通知する。

    Args:
        payload (Dict[str, Any]): 通知内容。以下のキーを含む:
            - 'type' (str): 'pdf' または 'meeting'
            - 'data' (Any): 通知するデータ本体 (pdfの場合はList[Dict], meetingの場合はDict)
            - 'source_url' (str): 検知元のURL
        cfg (Config): アプリケーション設定。
    """
    if not _get_slack_client():
        logger.error("Slack client not available. Cannot send notification.")
        return
    if not cfg.slack_channel_id:
        logger.error("SLACK_CHANNEL_ID is not configured. Cannot send notification.")
        return

    notification_type = payload.get('type')
    notification_data = payload.get('data')
    source_url = payload.get('source_url', '不明なソース') # Default source URL

    if not notification_type or notification_data is None:
         logger.error(f"Invalid notification payload: 'type' or 'data' missing. Payload: {payload}")
         return

    text = "" # Fallback text
    blocks = []

    try:
        if notification_type == 'pdf':
            if isinstance(notification_data, list) and notification_data:
                num_docs = len(notification_data)
                text = f"📄 新規文書通知 ({num_docs}件) - {source_url}"
                blocks = _build_pdf_notification_blocks(notification_data, source_url)
            else:
                 logger.warning(f"Received 'pdf' notification type but data is empty or not a list: {notification_data}")
                 return # Don't send empty/invalid PDF notifications
        elif notification_type == 'meeting':
             if isinstance(notification_data, dict) and notification_data.get('id'):
                 meeting_id = notification_data.get('id')
                 text = f"📣 新規会議開催通知: {meeting_id} - {source_url}"
                 blocks = _build_meeting_notification_blocks(notification_data, source_url)
             else:
                 logger.warning(f"Received 'meeting' notification type but data is empty, not a dict, or missing 'id': {notification_data}")
                 return # Don't send invalid meeting notifications
        else:
            logger.error(f"Unknown notification type: {notification_type}")
            return

        if blocks: # Only send if blocks were generated
            _send_message(cfg.slack_channel_id, text, blocks)
        else:
             logger.warning(f"No message blocks generated for notification type '{notification_type}'. Payload: {payload}")

    except Exception as e:
        logger.exception(f"Error building notification message for type '{notification_type}': {e}")
        # Send a simple admin alert if block building fails
        send_admin_alert(f"Failed to build Slack message for {notification_type} notification from {source_url}", error=e, config=cfg)


# Pass config object to send_admin_alert as well
def send_admin_alert(message: str, error: Exception | None = None, config: Config | None = None):
    """
    管理者向けチャンネルにアラートメッセージを送信する。

    Args:
        message (str): 送信するアラートメッセージ。
        error (Exception | None): 関連する例外オブジェクト (オプション)。
    """
    # Use passed config or try to load it
    cfg = config if config else _get_config()
    if not cfg:
        logger.error("Configuration not available. Cannot send admin alert.")
        return
    if not _get_slack_client(): # Ensure client can be initialized
        logger.error("Slack client not available. Cannot send admin alert.")
        return

    admin_channel_id = cfg.admin_slack_channel_id
    if not admin_channel_id:
        logger.debug("Admin Slack channel ID not configured. Skipping admin alert.")
        return

    text = f"🚨 MedFeeBot 管理者アラート\n{message}"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🚨 MedFeeBot 管理者アラート", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": message}}
    ]
    if error:
        error_details = f"```{type(error).__name__}: {str(error)}```"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*エラー詳細:*\n{error_details}"}
        })
        text += f"\nエラー詳細:\n{error_details}"

    _send_message(admin_channel_id, text, blocks)


# --- 例: 実行テスト ---
# Note: The __main__ block is less useful now as send_slack_notification expects a specific payload structure.
# Consider creating dedicated test scripts or using pytest fixtures for testing notifications.
# if __name__ == "__main__":
#     # ... (Example usage would need significant updates) ...
#     pass

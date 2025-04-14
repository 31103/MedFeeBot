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

def send_slack_notification(new_pdf_links: list[str]):
    """
    新規PDFリンクのリストを整形してSlackのメインチャンネルに通知する。

    Args:
        new_pdf_links (list[str]): 新しく発見されたPDFファイルのURLリスト。
    """
    cfg = _get_config()
    if not cfg:
        logger.error("Configuration not loaded. Cannot send Slack notification.")
        return
    if not _get_slack_client(): # Ensure client can be initialized
        logger.error("Slack client not available. Cannot send notification.")
        return

    if not new_pdf_links:
        logger.info("No new PDF links found, skipping Slack notification.")
        return

    if not cfg.slack_channel_id:
        logger.error("SLACK_CHANNEL_ID is not configured. Cannot send notification.")
        return

    num_links = len(new_pdf_links)
    text = f"📄 新規PDF通知 ({num_links}件)\n厚生労働省サイトで新しいPDFファイルが検出されました。"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📄 新規PDF通知 ({num_links}件)", "emoji": True}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"厚生労働省サイト (<{cfg.target_url}|監視対象ページ>) で新しいPDFファイルが検出されました。"}
        },
        {"type": "divider"}
    ]

    link_limit = 10
    for i, link in enumerate(new_pdf_links):
        if i < link_limit:
            filename = link.split('/')[-1].split('?')[0]
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"• <{link}|{filename}>"}
            })
        elif i == link_limit:
             blocks.append({
                "type": "context",
                "elements": [{"type": "plain_text", "text": f"...他{num_links - link_limit}件のリンクがあります。", "emoji": True}]
            })
             break

    _send_message(cfg.slack_channel_id, text, blocks)

def send_admin_alert(message: str, error: Exception | None = None):
    """
    管理者向けチャンネルにアラートメッセージを送信する。

    Args:
        message (str): 送信するアラートメッセージ。
        error (Exception | None): 関連する例外オブジェクト (オプション)。
    """
    cfg = _get_config()
    if not cfg:
        logger.error("Configuration not loaded. Cannot send admin alert.")
        return
    if not _get_slack_client(): # Ensure client can be initialized
        logger.error("Slack client not available. Cannot send admin alert.")
        return

    if not cfg.admin_slack_channel_id:
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

    _send_message(cfg.admin_slack_channel_id, text, blocks)


# --- 例: 実行テスト ---
if __name__ == "__main__":
    # Load config explicitly for the example run
    main_config = _get_config()
    slack_client_instance = _get_slack_client()

    if not slack_client_instance or not main_config:
        logger.error("Slack client or config could not be initialized. Cannot run tests.")
    else:
        logger.info("Slack notification test starting...")

        # 1. Normal notification test
        test_links = [
            "https://www.mhlw.go.jp/stf/newpage_example1.pdf",
            "https://www.mhlw.go.jp/stf/shingi/other/dl/example_document_ver2.pdf?download",
            "https://www.mhlw.go.jp/content/12401000/000987654.pdf"
        ]
        if main_config.slack_channel_id:
            logger.info(f"Testing normal notification (Channel: {main_config.slack_channel_id})")
            send_slack_notification(test_links)
        else:
            logger.warning("SLACK_CHANNEL_ID not set, skipping normal notification test.")

        # 2. Admin alert test
        if main_config.admin_slack_channel_id:
            logger.info(f"Testing admin alert (Channel: {main_config.admin_slack_channel_id})")
            try:
                1 / 0
            except ZeroDivisionError as e:
                send_admin_alert("Error occurred during testing.", e)
        else:
            logger.info("Admin channel ID not set, skipping admin alert test.")

        logger.info("Slack notification test finished.")

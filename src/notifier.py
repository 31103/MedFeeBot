from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from . import config
from .logger import logger

# Slackクライアントの初期化
# トークンが設定されていない場合は初期化しない (エラーを防ぐ)
slack_client: WebClient | None = None
if config.SLACK_BOT_TOKEN:
    slack_client = WebClient(token=config.SLACK_BOT_TOKEN)
else:
    logger.warning("SLACK_BOT_TOKENが設定されていないため、Slack通知機能は無効です。")

def _send_message(channel_id: str, text: str, blocks: list | None = None) -> bool:
    """
    指定されたチャンネルにメッセージを送信する内部関数。

    Args:
        channel_id (str): 送信先のチャンネルID。
        text (str): 通知などに表示されるプレーンテキスト。
        blocks (list | None): Slack Block Kit形式のメッセージペイロード。

    Returns:
        bool: 送信に成功した場合はTrue、失敗した場合はFalse。
    """
    if not slack_client:
        logger.error("Slackクライアントが初期化されていません。メッセージを送信できません。")
        return False
    if not channel_id:
        logger.error("送信先のチャンネルIDが指定されていません。")
        return False

    try:
        logger.debug(f"Slackへメッセージ送信開始 (チャンネル: {channel_id})")
        response = slack_client.chat_postMessage(
            channel=channel_id,
            text=text, # 通知用のフォールバックテキスト
            blocks=blocks # Block Kitを使う場合
        )
        logger.info(f"Slackメッセージ送信成功 (チャンネル: {channel_id}, ts: {response.get('ts')})")
        return True
    except SlackApiError as e:
        logger.error(f"Slack APIエラーが発生しました (チャンネル: {channel_id}): {e.response['error']}")
        # エラーの詳細 (例: 'channel_not_found', 'invalid_auth') をログに出力
        logger.debug(f"Slack APIエラー詳細: {e.response}")
        return False
    except Exception as e:
        logger.exception(f"Slackメッセージ送信中に予期せぬエラーが発生しました (チャンネル: {channel_id}): {e}")
        return False

def send_slack_notification(new_pdf_links: list[str]):
    """
    新規PDFリンクのリストを整形してSlackのメインチャンネルに通知する。

    Args:
        new_pdf_links (list[str]): 新しく発見されたPDFファイルのURLリスト。
    """
    if not new_pdf_links:
        logger.info("新規PDFリンクがないため、Slack通知は送信しません。")
        return

    if not config.SLACK_CHANNEL_ID:
        logger.error("通知先のSLACK_CHANNEL_IDが設定されていません。")
        return

    num_links = len(new_pdf_links)
    # メッセージのプレーンテキスト版 (通知用)
    text = f"📄 新規PDF通知 ({num_links}件)\n厚生労働省サイトで新しいPDFファイルが検出されました。"

    # Block Kitを使ったメッセージ本体
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📄 新規PDF通知 ({num_links}件)",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"厚生労働省サイト (<{config.TARGET_URL}|監視対象ページ>) で新しいPDFファイルが検出されました。"
            }
        },
        {"type": "divider"}
    ]

    # 各PDFリンクをリスト表示 (最大10件程度に制限した方が良い場合も)
    # Slackのメッセージ長制限にも注意
    link_limit = 10
    for i, link in enumerate(new_pdf_links):
        if i < link_limit:
            # URLからファイル名を抽出試行 (単純な方法)
            filename = link.split('/')[-1].split('?')[0] # クエリパラメータ除去
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• <{link}|{filename}>"
                }
            })
        elif i == link_limit:
             blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"...他{num_links - link_limit}件のリンクがあります。",
                        "emoji": True
                    }
                ]
            })
             break # 上限に達したらループ終了

    _send_message(config.SLACK_CHANNEL_ID, text, blocks)

def send_admin_alert(message: str, error: Exception | None = None):
    """
    管理者向けチャンネルにアラートメッセージを送信する。

    Args:
        message (str): 送信するアラートメッセージ。
        error (Exception | None): 関連する例外オブジェクト (オプション)。
    """
    if not config.SLACK_ADMIN_CHANNEL_ID:
        logger.debug("管理者通知用チャンネルIDが設定されていないため、管理者アラートは送信しません。")
        return

    text = f"🚨 MedFeeBot 管理者アラート\n{message}"
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 MedFeeBot 管理者アラート",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": message
            }
        }
    ]
    if error:
        error_details = f"```{type(error).__name__}: {str(error)}```"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*エラー詳細:*\n{error_details}"
            }
        })
        text += f"\nエラー詳細:\n{error_details}" # textにも追加

    _send_message(config.SLACK_ADMIN_CHANNEL_ID, text, blocks)


# --- 例: 実行テスト ---
if __name__ == "__main__":
    if not slack_client:
        logger.error("Slackクライアントが初期化されていないため、テストを実行できません。")
    else:
        logger.info("Slack通知テスト開始...")

        # 1. 通常通知テスト
        test_links = [
            "https://www.mhlw.go.jp/stf/newpage_example1.pdf",
            "https://www.mhlw.go.jp/stf/shingi/other/dl/example_document_ver2.pdf?download",
            "https://www.mhlw.go.jp/content/12401000/000987654.pdf"
        ]
        logger.info(f"通常通知テスト (チャンネル: {config.SLACK_CHANNEL_ID})")
        send_slack_notification(test_links)

        # 2. 管理者アラートテスト
        if config.SLACK_ADMIN_CHANNEL_ID:
            logger.info(f"管理者アラートテスト (チャンネル: {config.SLACK_ADMIN_CHANNEL_ID})")
            try:
                # ダミーのエラーを発生させる
                1 / 0
            except ZeroDivisionError as e:
                send_admin_alert("テスト中にエラーが発生しました。", e)
        else:
            logger.info("管理者通知用チャンネルが設定されていないため、管理者アラートテストはスキップします。")

        logger.info("Slack通知テスト完了。")

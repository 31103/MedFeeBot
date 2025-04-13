import os
import sys
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_TEST_CHANNEL_ID = os.environ.get("SLACK_TEST_CHANNEL_ID")

def send_slack_message(channel_id: str, message: str):
    """指定されたチャンネルIDにメッセージを送信する"""
    if not SLACK_BOT_TOKEN:
        print("Error: SLACK_BOT_TOKEN is not set in .env file.", file=sys.stderr)
        return False
    if not channel_id:
        print("Error: Channel ID is not provided.", file=sys.stderr)
        return False

    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        print(f"Sending message to channel {channel_id}...")
        response = client.chat_postMessage(channel=channel_id, text=message)
        print("Message sent successfully!")
        return True
    except SlackApiError as e:
        print(f"Error sending message to Slack: {e.response['error']}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    print("--- Starting Slack Notification PoC ---")

    if not SLACK_TEST_CHANNEL_ID:
        print("Error: SLACK_TEST_CHANNEL_ID is not set in .env file.", file=sys.stderr)
    else:
        test_message = "This is a test message from the MedFeeBot PoC script! 🤖"
        success = send_slack_message(SLACK_TEST_CHANNEL_ID, test_message)
        if success:
            print(f"Test message sent to channel ID: {SLACK_TEST_CHANNEL_ID}")
        else:
            print("Failed to send test message.")

    print("\n--- PoC Script Finished ---")

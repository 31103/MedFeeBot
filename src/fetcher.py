import time
import requests
from requests.exceptions import RequestException
from . import config
from .logger import logger

# 標準的なブラウザを模倣するUser-Agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_html(url: str) -> str | None:
    """
    指定されたURLからHTMLコンテンツを取得する。
    設定に基づいてリトライ処理を行う。

    Args:
        url (str): 取得対象のURL。

    Returns:
        str | None: 取得したHTMLコンテンツ。取得失敗時はNone。
    """
    logger.info(f"HTML取得開始: {url}")
    attempts = 0
    while attempts < config.REQUEST_RETRIES:
        attempts += 1
        logger.debug(f"試行 {attempts}/{config.REQUEST_RETRIES} 回目...")
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()  # ステータスコードが200番台以外なら例外を発生させる
            logger.info(f"HTML取得成功 (ステータスコード: {response.status_code})")
            # エンコーディングを正しく処理する (多くの日本語サイトは 'utf-8' または 'shift_jis', 'euc-jp')
            # requestsは賢く推測してくれるが、明示的に指定した方が確実な場合もある
            response.encoding = response.apparent_encoding # コンテンツからエンコーディングを推測
            return response.text

        except RequestException as e:
            logger.warning(f"HTML取得中にエラー発生 (試行 {attempts}/{config.REQUEST_RETRIES}): {e}")
            if attempts < config.REQUEST_RETRIES:
                logger.info(f"{config.REQUEST_RETRY_DELAY}秒待機してリトライします...")
                time.sleep(config.REQUEST_RETRY_DELAY)
            else:
                logger.error(f"リトライ上限 ({config.REQUEST_RETRIES}回) に達しました。HTML取得失敗: {url}")
                return None
        except Exception as e:
            # 予期せぬエラー
            logger.exception(f"予期せぬエラーが発生しました (試行 {attempts}/{config.REQUEST_RETRIES}): {e}")
            # 予期せぬエラーでもリトライする（場合によるが、一時的な問題の可能性も考慮）
            if attempts < config.REQUEST_RETRIES:
                 time.sleep(config.REQUEST_RETRY_DELAY)
            else:
                logger.error(f"リトライ上限 ({config.REQUEST_RETRIES}回) に達しました。HTML取得失敗: {url}")
                return None

    return None # ここには到達しないはずだが、念のため

# --- 例: 実行テスト ---
if __name__ == "__main__":
    test_url = config.TARGET_URL # 設定ファイルからURLを取得
    if not test_url:
        logger.error("テスト用のTARGET_URLが設定されていません。")
    else:
        html_content = fetch_html(test_url)
        if html_content:
            logger.info(f"{test_url} からHTMLを取得しました (最初の500文字):")
            print(html_content[:500] + "...")
        else:
            logger.error(f"{test_url} からHTMLを取得できませんでした。")

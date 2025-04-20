import time
import requests
import logging # Import logging
from requests.exceptions import RequestException
# from .config import load_config, Config # No longer needed here
# from .logger import logger # REMOVE direct logger import

# Get logger instance for this module
logger = logging.getLogger(__name__)

# 標準的なブラウザを模倣するUser-Agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_html(url: str, timeout: int = 30, retries: int = 3, delay: int = 5) -> str | None:
    """
    指定されたURLからHTMLコンテンツを取得する。
    引数に基づいてリトライ処理を行う。

    Args:
        url (str): 取得対象のURL。
        timeout (int): リクエストのタイムアウト秒数。
        retries (int): 失敗時のリトライ回数。
        delay (int): リトライ時の待機秒数。

    Returns:
        str | None: 取得したHTMLコンテンツ。取得失敗時はNone。
    """
    # Configuration is now passed via arguments with defaults

    logger.info(f"HTML取得開始: {url} (timeout={timeout}, retries={retries}, delay={delay})")
    attempts = 0
    while attempts < retries:
        attempts += 1
        logger.debug(f"試行 {attempts}/{retries} 回目...")
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=timeout
            )
            response.raise_for_status()  # ステータスコードが200番台以外なら例外を発生させる
            logger.info(f"HTML取得成功 (ステータスコード: {response.status_code})")
            # エンコーディングを正しく処理する (多くの日本語サイトは 'utf-8' または 'shift_jis', 'euc-jp')
            # requestsは賢く推測してくれるが、明示的に指定した方が確実な場合もある
            response.encoding = response.apparent_encoding # コンテンツからエンコーディングを推測
            return response.text

        except RequestException as e:
            logger.warning(f"HTML取得中にエラー発生 (試行 {attempts}/{retries}): {e}")
            if attempts < retries:
                logger.info(f"{delay}秒待機してリトライします...")
                time.sleep(delay)
            else:
                logger.error(f"リトライ上限 ({retries}回) に達しました。HTML取得失敗: {url}")
                return None
        except Exception as e:
            # 予期せぬエラー
            logger.exception(f"予期せぬエラーが発生しました (試行 {attempts}/{retries}): {e}")
            # 予期せぬエラーでもリトライする（場合によるが、一時的な問題の可能性も考慮）
            if attempts < retries:
                 time.sleep(delay)
            else:
                logger.error(f"リトライ上限 ({retries}回) に達しました。HTML取得失敗: {url}")
                return None

    return None # Should not be reached, but just in case

# --- 例: 実行テスト ---
if __name__ == "__main__":
    # Example usage requires setting up logger and getting URL differently now
    # Setup logger for direct execution test
    from logger import setup_logger # Import locally for example
    setup_logger(level_str="INFO") # Setup with default level

    # Example URL (replace with a real one for testing)
    test_url_example = "https://www.mhlw.go.jp/stf/newpage_21484.html" # Example URL

    if not test_url_example:
        logger.error("テスト用のURLが設定されていません。")
    else:
        # Call fetch_html with default timeout/retries or specify them
        html_content = fetch_html(test_url_example)
        if html_content:
            logger.info(f"{test_url_example} からHTMLを取得しました (最初の500文字):")
            print(html_content[:500] + "...")
        else:
            logger.error(f"{test_url_example} からHTMLを取得できませんでした。")

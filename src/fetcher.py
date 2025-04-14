import time
import requests
from requests.exceptions import RequestException
from .config import load_config, Config # Import load_config and Config
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
    # Load config inside the function or pass it as an argument
    # Let's load it inside for now, though passing might be cleaner
    try:
        cfg = load_config()
    except ValueError as e:
        logger.error(f"Configuration error in fetch_html: {e}")
        return None

    logger.info(f"HTML取得開始: {url}")
    attempts = 0
    while attempts < cfg.request_retries:
        attempts += 1
        logger.debug(f"試行 {attempts}/{cfg.request_retries} 回目...")
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=cfg.request_timeout
            )
            response.raise_for_status()  # ステータスコードが200番台以外なら例外を発生させる
            logger.info(f"HTML取得成功 (ステータスコード: {response.status_code})")
            # エンコーディングを正しく処理する (多くの日本語サイトは 'utf-8' または 'shift_jis', 'euc-jp')
            # requestsは賢く推測してくれるが、明示的に指定した方が確実な場合もある
            response.encoding = response.apparent_encoding # コンテンツからエンコーディングを推測
            return response.text

        except RequestException as e:
            logger.warning(f"HTML取得中にエラー発生 (試行 {attempts}/{cfg.request_retries}): {e}")
            if attempts < cfg.request_retries:
                logger.info(f"{cfg.request_retry_delay}秒待機してリトライします...")
                time.sleep(cfg.request_retry_delay)
            else:
                logger.error(f"リトライ上限 ({cfg.request_retries}回) に達しました。HTML取得失敗: {url}")
                return None
        except Exception as e:
            # 予期せぬエラー
            logger.exception(f"予期せぬエラーが発生しました (試行 {attempts}/{cfg.request_retries}): {e}")
            # 予期せぬエラーでもリトライする（場合によるが、一時的な問題の可能性も考慮）
            if attempts < cfg.request_retries:
                 time.sleep(cfg.request_retry_delay)
            else:
                logger.error(f"リトライ上限 ({cfg.request_retries}回) に達しました。HTML取得失敗: {url}")
                return None

    return None # ここには到達しないはずだが、念のため

# --- 例: 実行テスト ---
if __name__ == "__main__":
    try:
        cfg_main = load_config()
        test_url = cfg_main.target_url # 設定オブジェクトからURLを取得
    except ValueError as e:
        logger.error(f"設定の読み込みに失敗しました: {e}")
        test_url = None

    if not test_url:
        logger.error("テスト用のURLが設定されていません。")
    else:
        html_content = fetch_html(test_url)
        if html_content:
            logger.info(f"{test_url} からHTMLを取得しました (最初の500文字):")
            print(html_content[:500] + "...")
        else:
            logger.error(f"{test_url} からHTMLを取得できませんでした。")

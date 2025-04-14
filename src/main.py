from .config import load_config # Import load_config
from .logger import logger
from . import fetcher
from . import parser
from . import storage
from . import notifier

def run_check():
    """
    メインの処理フローを実行する。
    HTML取得 -> PDFリンク抽出 -> 新規URL判定 -> Slack通知
    """
    logger.info("処理開始: 診療報酬改定通知の確認を開始します。")

    try:
        # Load configuration at the start of the run
        cfg = load_config()

        # 1. HTMLコンテンツを取得
        html_content = fetcher.fetch_html(cfg.target_url) # Use cfg object
        if not html_content:
            # fetch_html内でエラーログは出力済みのはず
            # 必要であれば管理者通知
            notifier.send_admin_alert(f"HTML取得失敗: {cfg.target_url}") # Use cfg object
            logger.error("HTML取得に失敗したため、処理を中断します。")
            return # 処理中断

        # 2. HTMLからPDFリンクを抽出
        current_pdf_links = parser.extract_pdf_links(html_content, cfg.target_url) # Use cfg object
        # extract_pdf_links内でエラーログは出力されるが、念のためチェック
        # (現実装ではエラー時空セットが返る)

        # 3. 新規PDFリンクを特定
        # find_new_urls内で既知URLの読み込み、比較、新規URLの保存が行われる
        # 初回実行時は空セットが返り、通知は行われない
        new_urls = storage.find_new_urls(current_pdf_links)

        # 4. 新規リンクがあればSlack通知
        if new_urls:
            # セットをリストに変換して通知関数へ渡す
            notifier.send_slack_notification(sorted(list(new_urls)))
        else:
            # new_urlsが空でも、初回実行かどうかのログはstorage側で出力される
            logger.info("新規PDFは見つかりませんでした。Slack通知は行いません。")

        logger.info("処理正常終了。")

    except Exception as e:
        # 予期せぬエラーをキャッチ
        logger.exception(f"メイン処理中に予期せぬエラーが発生しました: {e}")
        # 管理者通知
        notifier.send_admin_alert(f"メイン処理中に予期せぬエラーが発生しました。", error=e)

if __name__ == "__main__":
    # スクリプトとして直接実行された場合に処理を開始
    run_check()

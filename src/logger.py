import logging
import sys
from . import config  # configモジュールからLOG_LEVELをインポート

# ルートロガーを取得
logger = logging.getLogger(__name__.split('.')[0]) # プロジェクトのルートロガー名を取得

# 既存のハンドラをクリア (重複設定を防ぐため)
if logger.hasHandlers():
    logger.handlers.clear()

# ログレベルを設定
log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
logger.setLevel(log_level)

# ログフォーマットを設定
# Cloud Functions環境では、標準のログフォーマットが適用されることが多いが、
# ローカル実行や他の環境での可読性を考慮して設定する。
log_format = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 標準出力へのハンドラを作成
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(log_format)
logger.addHandler(stdout_handler)

# 必要に応じてファイルハンドラも追加可能
# file_handler = logging.FileHandler('app.log')
# file_handler.setFormatter(log_format)
# logger.addHandler(file_handler)

# --- 例: ログ出力テスト ---
if __name__ == "__main__":
    logger.debug("これはデバッグメッセージです。")
    logger.info("これは情報メッセージです。")
    logger.warning("これは警告メッセージです。")
    logger.error("これはエラーメッセージです。")
    logger.critical("これは致命的なエラーメッセージです。")
    print(f"ロガー '{logger.name}' がレベル '{logging.getLevelName(logger.level)}' で設定されました。")

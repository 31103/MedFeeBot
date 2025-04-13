import json
import os
from typing import Set
from .logger import logger
# from . import config # 将来的にGCSのパスなどをconfigから読む

# ローカル開発用の既知URLリスト保存ファイル
# TODO: クラウド実装フェーズでGCSパスをconfigから読むように変更
LOCAL_STORAGE_PATH = "known_urls.json"

def load_known_urls() -> Set[str]:
    """
    ローカルのJSONファイルから既知のPDF URLリストを読み込む。

    Returns:
        Set[str]: 既知のURLのセット。ファイルが存在しない、または読み込みエラー時は空のセット。
    """
    known_urls: Set[str] = set()
    if not os.path.exists(LOCAL_STORAGE_PATH):
        logger.info(f"既知URLファイル '{LOCAL_STORAGE_PATH}' が存在しません。初回実行として扱います。")
        return known_urls

    try:
        with open(LOCAL_STORAGE_PATH, 'r', encoding='utf-8') as f:
            urls_list = json.load(f)
            if isinstance(urls_list, list):
                known_urls = set(urls_list)
                logger.info(f"既知URLファイル '{LOCAL_STORAGE_PATH}' から {len(known_urls)} 件のURLを読み込みました。")
            else:
                logger.warning(f"既知URLファイル '{LOCAL_STORAGE_PATH}' の形式が不正です (リスト形式ではありません)。空のリストとして扱います。")
                # 不正なファイルをリネームまたは削除する処理を追加しても良い
    except json.JSONDecodeError:
        logger.error(f"既知URLファイル '{LOCAL_STORAGE_PATH}' のJSONデコードに失敗しました。空のリストとして扱います。")
        # 不正なファイルをリネームまたは削除する処理を追加しても良い
    except Exception as e:
        logger.exception(f"既知URLファイル '{LOCAL_STORAGE_PATH}' の読み込み中に予期せぬエラーが発生しました: {e}")

    return known_urls

def save_known_urls(urls_to_save: Set[str]):
    """
    既知のPDF URLリストをローカルのJSONファイルに保存する。

    Args:
        urls_to_save (Set[str]): 保存するURLのセット。
    """
    try:
        # セットをリストに変換してJSONシリアライズ可能にする
        urls_list = sorted(list(urls_to_save))
        with open(LOCAL_STORAGE_PATH, 'w', encoding='utf-8') as f:
            json.dump(urls_list, f, ensure_ascii=False, indent=2)
        logger.info(f"既知URLファイル '{LOCAL_STORAGE_PATH}' に {len(urls_list)} 件のURLを保存しました。")
    except Exception as e:
        logger.exception(f"既知URLファイル '{LOCAL_STORAGE_PATH}' の保存中に予期せぬエラーが発生しました: {e}")
        # TODO: 管理者への通知を検討 (notifier.send_admin_alert)

def find_new_urls(current_urls: Set[str]) -> Set[str]:
    """
    現在のURLリストと既知のURLリストを比較し、新規URLを特定する。

    Args:
        current_urls (Set[str]): 今回ウェブサイトから取得したURLのセット。

    Returns:
        Set[str]: 新規に発見されたURLのセット。
    """
    known_urls = load_known_urls()
    new_urls = current_urls - known_urls

    if not known_urls and current_urls:
        logger.info("初回実行のため、検出された全てのURLを既知として保存し、通知は行いません。")
        save_known_urls(current_urls) # 初回は検出したURLを保存
        return set() # 初回は新規URLなしとして扱う
    elif new_urls:
        logger.info(f"{len(new_urls)} 件の新規URLを発見しました。")
        # 新しいURLが見つかった場合、現在の全URLリストで既知リストを更新する
        updated_known_urls = known_urls.union(new_urls)
        save_known_urls(updated_known_urls)
    else:
        logger.info("新規URLは見つかりませんでした。")

    return new_urls

# --- 例: 実行テスト ---
if __name__ == "__main__":
    # テスト用のダミーURL
    urls1 = {"http://example.com/a.pdf", "http://example.com/b.pdf"}
    urls2 = {"http://example.com/b.pdf", "http://example.com/c.pdf"}
    urls3 = {"http://example.com/c.pdf", "http://example.com/d.pdf"}

    # 既存ファイルを削除して初期状態にする
    if os.path.exists(LOCAL_STORAGE_PATH):
        os.remove(LOCAL_STORAGE_PATH)
        logger.info(f"テスト用に既存ファイル '{LOCAL_STORAGE_PATH}' を削除しました。")

    # 1回目の実行 (初回)
    logger.info("\n--- 1回目のテスト実行 (初回) ---")
    new_found1 = find_new_urls(urls1)
    print(f"新規URL (1回目): {new_found1}") # -> set()のはず
    print(f"保存されたURL (1回目): {load_known_urls()}") # -> urls1 のはず

    # 2回目の実行
    logger.info("\n--- 2回目のテスト実行 ---")
    new_found2 = find_new_urls(urls2)
    print(f"新規URL (2回目): {new_found2}") # -> {'http://example.com/c.pdf'} のはず
    print(f"保存されたURL (2回目): {load_known_urls()}") # -> urls1 と urls2 の和集合のはず

    # 3回目の実行
    logger.info("\n--- 3回目のテスト実行 ---")
    new_found3 = find_new_urls(urls3)
    print(f"新規URL (3回目): {new_found3}") # -> {'http://example.com/d.pdf'} のはず
    print(f"保存されたURL (3回目): {load_known_urls()}") # -> urls1, urls2, urls3 の和集合のはず

    # 4回目の実行 (変更なし)
    logger.info("\n--- 4回目のテスト実行 (変更なし) ---")
    new_found4 = find_new_urls(urls3)
    print(f"新規URL (4回目): {new_found4}") # -> set() のはず
    print(f"保存されたURL (4回目): {load_known_urls()}") # -> 変化なしのはず

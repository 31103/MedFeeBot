import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup, SoupStrainer
from .logger import logger

# PDFリンクを検出するための正規表現 (末尾のクエリパラメータも許容)
PDF_LINK_PATTERN = re.compile(r"\.pdf(\?.*)?$", re.IGNORECASE)

def extract_pdf_links(html_content: str, base_url: str) -> set[str]:
    """
    HTMLコンテンツからPDFファイルへの絶対URLリンクを抽出する。

    Args:
        html_content (str): 解析対象のHTMLコンテンツ。
        base_url (str): HTMLコンテンツが取得された元のページのURL。相対パスを解決するために使用。

    Returns:
        set[str]: 抽出されたPDFファイルの絶対URLのセット。
    """
    logger.info(f"HTML解析開始: {base_url} からPDFリンクを抽出します。")
    pdf_links: set[str] = set()

    try:
        # <a> タグのみを解析対象とする (効率化)
        only_a_tags = SoupStrainer("a")
        soup = BeautifulSoup(html_content, 'html.parser', parse_only=only_a_tags)

        for a_tag in soup.find_all('a', href=True): # href属性を持つ<a>タグのみを対象
            href = a_tag['href'].strip()
            if href: # 空のhrefは無視
                # PDFリンクかどうかを正規表現で判定
                if PDF_LINK_PATTERN.search(href):
                    # 相対URLを絶対URLに変換
                    absolute_url = urljoin(base_url, href)
                    if absolute_url not in pdf_links:
                         logger.debug(f"PDFリンク発見: {absolute_url} (元: {href})")
                         pdf_links.add(absolute_url)

        logger.info(f"HTML解析完了: {len(pdf_links)} 件のユニークなPDFリンクを発見しました。")
        return pdf_links

    except Exception as e:
        logger.exception(f"HTML解析中に予期せぬエラーが発生しました: {e}")
        return set() # エラー時は空のセットを返す

# --- 例: 実行テスト ---
if __name__ == "__main__":
    from . import fetcher
    from . import config

    test_url = config.TARGET_URL
    if not test_url:
        logger.error("テスト用のTARGET_URLが設定されていません。")
    else:
        logger.info(f"テスト実行: {test_url} からHTMLを取得してPDFリンクを抽出します。")
        html = fetcher.fetch_html(test_url)
        if html:
            extracted_links = extract_pdf_links(html, test_url)
            if extracted_links:
                print("\n--- 抽出されたPDFリンク ---")
                for link in sorted(list(extracted_links)):
                    print(link)
                print("--------------------------")
            else:
                logger.info("PDFリンクは見つかりませんでした。")
        else:
            logger.error("HTMLの取得に失敗したため、解析テストを実行できませんでした。")

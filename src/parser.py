import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup, SoupStrainer, Tag # Import Tag
import re # 正規表現モジュールを追加
from typing import List, Dict # 型ヒント用
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

        for a_tag in soup.find_all('a', href=True): # href=True should yield Tags
            # Explicit check for mypy
            if isinstance(a_tag, Tag):
                href_value = a_tag.get('href') # Use .get() for safer access
                # Ensure href_value is a string and strip it
                if isinstance(href_value, str):
                    href = href_value.strip()
                elif isinstance(href_value, list): # Handle case where href might be a list (less common)
                    href = href_value[0].strip() if href_value else ""
                else:
                    href = "" # Skip if href is not a string or list

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


def extract_hospital_document_info(html_content: str, base_url: str) -> List[Dict[str, str]]:
    """
    hospital.or.jp/site/ministry/ のHTML構造から文書情報を抽出する。
    日付、タイトル、PDFの絶対URLを含む辞書のリストを返す。

    Args:
        html_content (str): 解析対象のHTMLコンテンツ。
        base_url (str): HTMLコンテンツが取得された元のページのURL。

    Returns:
        List[Dict[str, str]]: 抽出された文書情報のリスト。各辞書は 'date', 'title', 'url' キーを持つ。
    """
    logger.info(f"HTML解析開始 (Hospital Site): {base_url} から文書情報を抽出します。")
    documents: List[Dict[str, str]] = []

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # '.col-12.isotope-item' クラスを持つ div をすべて検索
        items = soup.find_all('div', class_='col-12 isotope-item') # Use class_

        for item in items:
            date_str: str | None = None
            title: str | None = None
            pdf_url: str | None = None

            # 1. 日付の抽出 (fs13クラスのdiv)
            date_div = item.find('div', class_='fs13')
            if date_div:
                # .text で取得し、内部の span タグなどを無視し、前後の空白を削除
                raw_date_text = date_div.get_text(strip=True)
                # 日付形式 "YYYY.MM.DD" を正規表現で抽出
                match = re.search(r'(\d{4}\.\d{2}\.\d{2})', raw_date_text)
                if match:
                    date_str = match.group(1)
                else:
                    logger.warning(f"日付形式が見つかりません: '{raw_date_text}' in item: {str(item)[:100]}...")

            # 2. PDFリンクとタイトルの抽出 (p.fs_p > a)
            #    <p class="fs_p ic_140"> の中の <a> タグを探す
            link_container = item.find('p', class_='fs_p')
            if link_container:
                link_tag = link_container.find('a', href=True)
                if link_tag and isinstance(link_tag, Tag):
                    href_value = link_tag.get('href')
                    link_text = link_tag.get_text(strip=True) # <a> タグのテキストを取得

                    if isinstance(href_value, str):
                        href = href_value.strip()
                        # PDFリンクかどうかを確認 (既存のパターンを使用)
                        if PDF_LINK_PATTERN.search(href):
                            pdf_url = urljoin(base_url, href) # 絶対URLに変換
                            title = link_text # 抽出したテキストをタイトルとする
                        else:
                            logger.debug(f"PDFではないリンクをスキップ: {href}")
                    else:
                        # href が文字列でない場合は警告 (通常は文字列のはず)
                        logger.warning(f"不正な href 属性値が見つかりました: {href_value} in item: {str(item)[:100]}...")
                else:
                     logger.debug(f"リンクタグ(a)が見つかりません in p.fs_p: {str(link_container)[:100]}...")
            else:
                logger.debug(f"リンクコンテナ(p.fs_p)が見つかりません in item: {str(item)[:100]}...")


            # 3. 日付、タイトル、URLがすべて取得できた場合のみリストに追加
            if date_str and title and pdf_url:
                documents.append({
                    'date': date_str,
                    'title': title,
                    'url': pdf_url
                })
                logger.debug(f"文書情報発見: Date={date_str}, Title={title[:30]}..., URL={pdf_url}")
            else:
                 # 何かが見つからなかった場合、デバッグ用にログ出力
                 missing_parts = []
                 if not date_str: missing_parts.append("日付")
                 if not title: missing_parts.append("タイトル")
                 if not pdf_url: missing_parts.append("URL")
                 # アイテム内に p.fs_p や a タグが存在しない場合などはログを出さないようにする
                 if link_container and link_tag and missing_parts:
                    logger.debug(f"文書情報の一部が見つかりませんでした ({', '.join(missing_parts)}が見つかりません): Item HTML (partial) = {str(item)[:200]}...")


        logger.info(f"HTML解析完了 (Hospital Site): {len(documents)} 件の文書情報を抽出しました。")
        return documents

    except Exception as e:
        logger.exception(f"HTML解析中に予期せぬエラーが発生しました (Hospital Site): {e}")
        return [] # エラー時は空のリストを返す


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

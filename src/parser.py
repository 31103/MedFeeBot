import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup, SoupStrainer, Tag # Import Tag
import re # 正規表現モジュールを追加
import logging # Import logging
from typing import List, Dict, Optional, Any # 型ヒント用 (Optional, Any を追加)
# from .logger import logger # REMOVE direct logger import

# Get logger instance for this module
logger = logging.getLogger(__name__)

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


def extract_latest_chuikyo_meeting(html_content: str, base_url: str) -> Optional[Dict[str, Any]]:
    """
    中医協総会ページ (mhlw.go.jp) のHTMLから最新の会議情報を抽出する (アドホック実装)。

    Args:
        html_content (str): 解析対象のHTMLコンテンツ。
        base_url (str): HTMLコンテンツが取得された元のページのURL。相対パス解決用。

    Returns:
        Optional[Dict[str, Any]]: 抽出された最新会議情報の辞書、または見つからない/必須情報欠落の場合は None。
            辞書のキー: 'id', 'date', 'topics', 'minutes_url', 'minutes_text', 'materials_url', 'materials_text'
    """
    logger.info(f"HTML解析開始 (Chukyo Meeting): {base_url} から最新会議情報を抽出します。")
    meeting_info: Dict[str, Any] = {}

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # <table class="m-tableFlex"> を探す
        table = soup.find('table', class_='m-tableFlex')
        if not table or not isinstance(table, Tag):
            logger.warning("会議情報テーブル (<table class='m-tableFlex'>) が見つかりません。")
            return None

        # 最初の <tr> (最新会議の行) を探す
        first_row = table.find('tr')
        if not first_row or not isinstance(first_row, Tag):
            logger.warning("会議情報テーブル内に最初の行 (<tr>) が見つかりません。")
            return None

        # <td> 要素を取得
        tds = first_row.find_all('td', recursive=False) # 直接の子要素のみ取得

        if len(tds) < 3: # 必須項目 (回数, 日付, 議題) が含まれる最低限のtd数
            logger.warning(f"会議情報テーブルの最初の行に必要なtd要素が不足しています (検出数: {len(tds)})。")
            return None

        # 1. 会議回数 (識別子)
        # 計画では td.m-table__highlight だが、実際のHTML(docs/shingi-chuo_128154.html)を見ると
        # 最初のtd自体がハイライトクラスを持っているわけではなく、中の要素が持っている可能性がある。
        # より堅牢にするため、最初のtdのテキストを直接取得する。
        meeting_info['id'] = tds[0].get_text(strip=True) if len(tds) > 0 and isinstance(tds[0], Tag) else None
        if not meeting_info['id']:
            logger.error("必須情報「会議回数」が取得できませんでした。")
            return None


        # 2. 開催日
        # 計画では td.m-table__highlight.m-table__nowrap だが、実際のHTMLを見ると2番目のtdが該当
        date_tag = tds[1] if len(tds) > 1 and isinstance(tds[1], Tag) else None
        if date_tag:
            meeting_info['date'] = date_tag.get_text(strip=True)
        else:
            logger.error("必須情報「開催日」が取得できませんでした。")
            return None

        # 3. 議題リスト
        topics_list: List[str] = []
        topics_container = tds[2] if len(tds) > 2 and isinstance(tds[2], Tag) else None
        if topics_container:
            # ol.m-listMarker > li を探す
            topic_items = topics_container.select('ol.m-listMarker > li')
            if topic_items:
                 for item in topic_items:
                     if isinstance(item, Tag):
                         topics_list.append(item.get_text(strip=True))
            else:
                 # ol がない場合、td 直下のテキストを議題とみなす（構造変化への備え）
                 topics_text = topics_container.get_text(strip=True)
                 if topics_text:
                     topics_list.append(topics_text) # 単一の議題として追加

        if not topics_list: # 議題が一つも取得できなかった場合
            logger.error("必須情報「議題」が取得できませんでした。")
            return None
        meeting_info['topics'] = topics_list

        # 4. 議事録/要旨リンク (オプション)
        meeting_info['minutes_url'] = None
        meeting_info['minutes_text'] = None
        minutes_container = tds[3] if len(tds) > 3 and isinstance(tds[3], Tag) else None
        if minutes_container:
            link_tag = minutes_container.find('a', class_='m-link', href=True)
            if link_tag and isinstance(link_tag, Tag):
                href_value = link_tag.get('href')
                if isinstance(href_value, str):
                    meeting_info['minutes_url'] = urljoin(base_url, href_value.strip())
                    meeting_info['minutes_text'] = link_tag.get_text(strip=True)

        # 5. 資料リンク (オプション)
        meeting_info['materials_url'] = None
        meeting_info['materials_text'] = None
        materials_container = tds[4] if len(tds) > 4 and isinstance(tds[4], Tag) else None
        if materials_container:
            link_tag = materials_container.find('a', class_='m-link', href=True)
            if link_tag and isinstance(link_tag, Tag):
                href_value = link_tag.get('href')
                if isinstance(href_value, str):
                    meeting_info['materials_url'] = urljoin(base_url, href_value.strip())
                    meeting_info['materials_text'] = link_tag.get_text(strip=True)

        # 必須情報が揃っているか最終確認 (id, date, topics)
        if not all(k in meeting_info and meeting_info[k] for k in ['id', 'date', 'topics']):
             logger.error(f"必須情報が不足しているため、会議情報を返せません: {meeting_info}")
             return None

        logger.info(f"HTML解析完了 (Chukyo Meeting): 最新会議情報 ID={meeting_info.get('id')} を抽出しました。")
        return meeting_info

    except Exception as e:
        logger.exception(f"HTML解析中に予期せぬエラーが発生しました (Chukyo Meeting): {e}")
        return None


# --- 例: 実行テスト ---
if __name__ == "__main__":
    # Example usage requires setting up logger and getting URL differently now
    from fetcher import fetch_html # Import locally for example
    from logger import setup_logger # Import locally for example
    setup_logger(level_str="INFO") # Setup with default level

    # Example URLs for testing different parsers
    test_url_pdf = "https://www.hospital.or.jp/site/ministry/"
    test_url_meeting = "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_128154.html"

    # --- Test PDF Parser ---
    logger.info(f"テスト実行 (PDF): {test_url_pdf}")
    html_pdf = fetch_html(test_url_pdf)
    if html_pdf:
        # Test extract_pdf_links (original function)
        extracted_links = extract_pdf_links(html_pdf, test_url_pdf)
        if extracted_links:
            print(f"\n--- extract_pdf_links ({len(extracted_links)} links) ---")
            # for link in sorted(list(extracted_links))[:5]: # Print first 5
            #     print(link)
            # print("...")
        else:
            logger.info("extract_pdf_links: PDFリンクは見つかりませんでした。")

        # Test extract_hospital_document_info
        doc_infos = extract_hospital_document_info(html_pdf, test_url_pdf)
        if doc_infos:
             print(f"\n--- extract_hospital_document_info ({len(doc_infos)} docs) ---")
             # for doc in doc_infos[:2]: # Print first 2
             #     print(f"  Date: {doc.get('date')}, Title: {doc.get('title', '')[:20]}..., URL: {doc.get('url')}")
             # print("...")
        else:
             logger.info("extract_hospital_document_info: 文書情報は見つかりませんでした。")
    else:
        logger.error(f"{test_url_pdf} からHTMLを取得できませんでした。")

    # --- Test Meeting Parser ---
    logger.info(f"\nテスト実行 (Meeting): {test_url_meeting}")
    html_meeting = fetch_html(test_url_meeting)
    if html_meeting:
        meeting_info = extract_latest_chuikyo_meeting(html_meeting, test_url_meeting)
        if meeting_info:
            print("\n--- extract_latest_chuikyo_meeting ---")
            print(f"  ID: {meeting_info.get('id')}")
            print(f"  Date: {meeting_info.get('date')}")
            print(f"  Topics: {len(meeting_info.get('topics', []))} items")
            print(f"  Minutes URL: {meeting_info.get('minutes_url')}")
            print(f"  Materials URL: {meeting_info.get('materials_url')}")
            print("------------------------------------")
        else:
            logger.info("extract_latest_chuikyo_meeting: 会議情報は見つかりませんでした。")
    else:
        logger.error(f"{test_url_meeting} からHTMLを取得できませんでした。")

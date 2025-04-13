import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import sys

# 監視対象URL (ユーザー確認済み)
TARGET_URL = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000188411_00040.html"

# PDFリンクを判定する正規表現 (クエリパラメータも考慮)
PDF_PATTERN = re.compile(r"\.pdf(\?.*)?$", re.IGNORECASE)

def fetch_and_extract_pdf_links(url: str) -> list[str]:
    """指定されたURLからHTMLを取得し、PDFリンクを抽出する"""
    pdf_links = []
    try:
        print(f"Fetching HTML from: {url}")
        response = requests.get(url, timeout=30) # タイムアウトを設定
        response.raise_for_status() # ステータスコードが200以外の場合は例外を発生
        response.encoding = response.apparent_encoding # 文字化け対策

        print("Parsing HTML...")
        soup = BeautifulSoup(response.text, 'html.parser')

        print("Finding PDF links...")
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # hrefがPDFファイルへのリンクか判定
            if PDF_PATTERN.search(href):
                # 相対URLを絶対URLに変換
                absolute_url = urljoin(url, href)
                pdf_links.append(absolute_url)

        # 重複を除去して返す
        return sorted(list(set(pdf_links)))

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return []

if __name__ == "__main__":
    print(f"--- Starting PDF Link Extraction PoC for {TARGET_URL} ---")
    extracted_links = fetch_and_extract_pdf_links(TARGET_URL)

    if extracted_links:
        print("\n--- Found PDF Links: ---")
        for link in extracted_links:
            print(link)
        print(f"\nTotal unique PDF links found: {len(extracted_links)}")
    else:
        print("\nNo PDF links found or an error occurred.")

    print("\n--- PoC Script Finished ---")

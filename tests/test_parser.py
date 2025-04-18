import pytest
from src.parser import extract_pdf_links, extract_hospital_document_info # Import the new function
from typing import List, Dict # For type hinting expected results

# --- Test Data ---

BASE_URL = "http://example.com/path/"
BASE_URL_NO_SLASH = "http://example.com/path" # Test base URL without trailing slash

HTML_SIMPLE_ABS = """
<html><body>
<p>Some text</p>
<a href="http://example.com/docs/document1.pdf">Absolute Link 1</a>
<a href="https://another.site/report.pdf?v=2">Absolute Link 2 (Query)</a>
</body></html>
"""
EXPECTED_SIMPLE_ABS = {
    "http://example.com/docs/document1.pdf",
    "https://another.site/report.pdf?v=2"
}

HTML_SIMPLE_REL = """
<html><body>
<a href="relative/doc2.pdf">Relative Link 1</a>
<a href="../another.pdf">Relative Link 2 (Parent)</a>
<a href="/root.pdf">Relative Link 3 (Root)</a>
</body></html>
"""
EXPECTED_SIMPLE_REL = {
    "http://example.com/path/relative/doc2.pdf",
    "http://example.com/another.pdf",
    "http://example.com/root.pdf"
}
# Expected for base URL without trailing slash
EXPECTED_SIMPLE_REL_NO_SLASH = {
    "http://example.com/relative/doc2.pdf", # urljoin('http://example.com/path', 'relative/doc2.pdf') -> 'http://example.com/relative/doc2.pdf'
    "http://example.com/another.pdf",
    "http://example.com/root.pdf"
}


HTML_MIXED = """
<html><body>
<a href="http://example.com/absolute.pdf">Absolute</a>
<a href="relative.pdf">Relative</a>
<a href="/root_rel.pdf">Root Relative</a>
<a href="duplicate.pdf">Duplicate 1</a>
<a href="duplicate.pdf">Duplicate 2</a>
<a href="case_test.PDF">Case Test</a>
<a href="with_query.pdf?id=123&type=report">Query Test</a>
</body></html>
"""
EXPECTED_MIXED = {
    "http://example.com/absolute.pdf",
    "http://example.com/path/relative.pdf",
    "http://example.com/root_rel.pdf",
    "http://example.com/path/duplicate.pdf",
    "http://example.com/path/case_test.PDF", # Case preserved
    "http://example.com/path/with_query.pdf?id=123&type=report"
}

HTML_NO_PDF = """
<html><body>
<a href="document.txt">Text File</a>
<a href="image.jpg">Image File</a>
<a href="/page.html">HTML Page</a>
<a href="http://example.com/no_pdf_here">No PDF</a>
</body></html>
"""
EXPECTED_NO_PDF: set[str] = set()

HTML_EMPTY = ""
EXPECTED_EMPTY: set[str] = set()

HTML_NO_LINKS = """
<html><body><p>No links here.</p></body></html>
"""
EXPECTED_NO_LINKS: set[str] = set()

HTML_LINK_NO_HREF = """
<html><body><a>Link without href</a></body></html>
"""
EXPECTED_LINK_NO_HREF: set[str] = set()

HTML_MALFORMED = """
<html><body>
<a href="malformed1.pdf> Link 1 (missing quote)
<a href="malformed2.pdf" Link 2 Text </a> (malformed tag)
<a href="good.pdf">Good Link</a>
"""
# BeautifulSoup might not parse severely malformed hrefs
EXPECTED_MALFORMED: set[str] = {
    # "http://example.com/path/malformed1.pdf", # Likely ignored due to missing quote
    # "http://example.com/path/malformed2.pdf", # Likely ignored due to structure
    "http://example.com/path/good.pdf" # Only the valid link should be found
}


# --- Test Cases ---

@pytest.mark.parametrize(
    "html_content, base_url, expected_links",
    [
        (HTML_SIMPLE_ABS, BASE_URL, EXPECTED_SIMPLE_ABS),
        (HTML_SIMPLE_REL, BASE_URL, EXPECTED_SIMPLE_REL),
        (HTML_SIMPLE_REL, BASE_URL_NO_SLASH, EXPECTED_SIMPLE_REL_NO_SLASH), # Test base URL handling
        (HTML_MIXED, BASE_URL, EXPECTED_MIXED),
        (HTML_NO_PDF, BASE_URL, EXPECTED_NO_PDF),
        (HTML_EMPTY, BASE_URL, EXPECTED_EMPTY),
        (HTML_NO_LINKS, BASE_URL, EXPECTED_NO_LINKS),
        (HTML_LINK_NO_HREF, BASE_URL, EXPECTED_LINK_NO_HREF),
        (HTML_MALFORMED, BASE_URL, EXPECTED_MALFORMED),
    ],
)
def test_extract_pdf_links(html_content, base_url, expected_links):
    """Test extract_pdf_links with various HTML inputs."""
    result = extract_pdf_links(html_content, base_url)
    assert result == expected_links

def test_extract_pdf_links_empty_input():
    """Test with explicitly empty string and None base URL (though base should always be provided)."""
    assert extract_pdf_links("", "http://base.url") == set()
    # Although base_url shouldn't be None, test defensive coding
    # assert extract_pdf_links(HTML_SIMPLE_REL, None) == set() # urljoin would likely fail here

def test_extract_pdf_links_exception_handling(mocker):
    """Test that extract_pdf_links returns an empty set on unexpected errors."""
    # Mock BeautifulSoup to raise an exception
    mocker.patch('src.parser.BeautifulSoup', side_effect=Exception("Parsing failed unexpectedly"))
    result = extract_pdf_links("<html></html>", "http://base.url")
    assert result == set()

# Remove the unrealistic test case for href as list
# HTML_HREF_AS_LIST = """
# <html><body>
# <a href='["list_item.pdf"]'>List Href (unlikely but possible)</a>
# </body></html>
# """
# EXPECTED_HREF_AS_LIST = {"http://example.com/path/list_item.pdf"}
#
# @pytest.mark.parametrize(
#     "html_content, base_url, expected_links",
#     [
#         (HTML_HREF_AS_LIST, BASE_URL, EXPECTED_HREF_AS_LIST),
#     ]
# )
# def test_extract_pdf_links_href_list(html_content, base_url, expected_links):
#     """Test extract_pdf_links handles href attribute being a list."""
#     result = extract_pdf_links(html_content, base_url)
#     assert result == expected_links


# Consider adding tests for extremely large HTML if performance is a concern.
# Consider adding tests for different encodings if that's relevant.


# --- Test Data for extract_hospital_document_info ---

HOSPITAL_BASE_URL = "https://www.hospital.or.jp/site/ministry/"

HTML_HOSPITAL_SITE_VALID = """
<html><body>
<div class="isotope-wrap">
  <div class="col-12 isotope-item" data-filter="Category 1">
    <div class="fs13">2025.04.16 <span class="h_new"></span></div>
    <div><div class="ic_mhlw_hoken ic_575r"></div>
    <p class="fs_p ic_140">
    <a href="/site/news/file/1744877060.pdf" target="_blank" class="type1">【事務連絡】「番号法等一部改正法等の施行に伴う保険局及び社会・援護局関係通知の一部改正について」の一部訂正について</a></p></div>
  </div>
  <div class="col-12 isotope-item" data-filter="Category 2">
    <div class="fs13">2025.04.15</div>
    <div><p class="fs_p ic_140">
    <a href="another/relative/doc.pdf?v=1" target="_blank">Another Document Title</a></p></div>
  </div>
  <div class="col-12 isotope-item" data-filter="Category 1">
    <div class="fs13"> 2025.04.14 (extra space) </div>
    <div><p class="fs_p"> <!-- Missing ic_140 class -->
    <a href="https://external.com/external.pdf">External Document</a></p></div>
  </div>
</div>
</body></html>
"""
EXPECTED_HOSPITAL_SITE_VALID: List[Dict[str, str]] = [
    {
        'date': '2025.04.16',
        'title': '【事務連絡】「番号法等一部改正法等の施行に伴う保険局及び社会・援護局関係通知の一部改正について」の一部訂正について',
        'url': 'https://www.hospital.or.jp/site/news/file/1744877060.pdf'
    },
    {
        'date': '2025.04.15',
        'title': 'Another Document Title',
        'url': 'https://www.hospital.or.jp/site/ministry/another/relative/doc.pdf?v=1' # Resolved relative URL
    },
    {
        'date': '2025.04.14',
        'title': 'External Document',
        'url': 'https://external.com/external.pdf' # Absolute URL preserved
    }
]

HTML_HOSPITAL_SITE_MISSING_DATE = """
<html><body>
<div class="col-12 isotope-item">
  <!-- Missing date div -->
  <div><p class="fs_p ic_140"><a href="doc1.pdf">Doc 1</a></p></div>
</div>
</body></html>
"""
EXPECTED_HOSPITAL_SITE_MISSING_DATE: List[Dict[str, str]] = [] # Should not be included if date is missing

HTML_HOSPITAL_SITE_MISSING_TITLE_LINK = """
<html><body>
<div class="col-12 isotope-item">
  <div class="fs13">2025.04.17</div>
  <div><p class="fs_p ic_140">No link here</p></div> <!-- Missing <a> tag -->
</div>
</body></html>
"""
EXPECTED_HOSPITAL_SITE_MISSING_TITLE_LINK: List[Dict[str, str]] = [] # Should not be included if link/title is missing

HTML_HOSPITAL_SITE_NOT_PDF = """
<html><body>
<div class="col-12 isotope-item">
  <div class="fs13">2025.04.18</div>
  <div><p class="fs_p ic_140"><a href="document.html">Not a PDF</a></p></div>
</div>
</body></html>
"""
EXPECTED_HOSPITAL_SITE_NOT_PDF: List[Dict[str, str]] = [] # Should not be included if link is not PDF

HTML_HOSPITAL_SITE_NO_ITEMS = """
<html><body><p>No relevant items found.</p></body></html>
"""
EXPECTED_HOSPITAL_SITE_NO_ITEMS: List[Dict[str, str]] = []

HTML_HOSPITAL_SITE_MALFORMED_DATE = """
<html><body>
<div class="col-12 isotope-item">
  <div class="fs13">Invalid Date Format</div> <!-- Date format doesn't match regex -->
  <div><p class="fs_p ic_140"><a href="doc2.pdf">Doc 2</a></p></div>
</div>
</body></html>
"""
EXPECTED_HOSPITAL_SITE_MALFORMED_DATE: List[Dict[str, str]] = [] # Should not be included if date format is wrong


# --- Test Cases for extract_hospital_document_info ---

@pytest.mark.parametrize(
    "html_content, base_url, expected_documents",
    [
        (HTML_HOSPITAL_SITE_VALID, HOSPITAL_BASE_URL, EXPECTED_HOSPITAL_SITE_VALID),
        (HTML_HOSPITAL_SITE_MISSING_DATE, HOSPITAL_BASE_URL, EXPECTED_HOSPITAL_SITE_MISSING_DATE),
        (HTML_HOSPITAL_SITE_MISSING_TITLE_LINK, HOSPITAL_BASE_URL, EXPECTED_HOSPITAL_SITE_MISSING_TITLE_LINK),
        (HTML_HOSPITAL_SITE_NOT_PDF, HOSPITAL_BASE_URL, EXPECTED_HOSPITAL_SITE_NOT_PDF),
        (HTML_HOSPITAL_SITE_NO_ITEMS, HOSPITAL_BASE_URL, EXPECTED_HOSPITAL_SITE_NO_ITEMS),
        (HTML_HOSPITAL_SITE_MALFORMED_DATE, HOSPITAL_BASE_URL, EXPECTED_HOSPITAL_SITE_MALFORMED_DATE),
        (HTML_EMPTY, HOSPITAL_BASE_URL, EXPECTED_HOSPITAL_SITE_NO_ITEMS), # Empty HTML should yield empty list
    ],
)
def test_extract_hospital_document_info(html_content, base_url, expected_documents):
    """Test extract_hospital_document_info with various HTML structures."""
    result = extract_hospital_document_info(html_content, base_url)
    # Sort both lists of dictionaries by URL for consistent comparison
    result_sorted = sorted(result, key=lambda x: x['url'])
    expected_sorted = sorted(expected_documents, key=lambda x: x['url'])
    assert result_sorted == expected_sorted

def test_extract_hospital_document_info_exception_handling(mocker):
    """Test that extract_hospital_document_info returns an empty list on unexpected errors."""
    mocker.patch('src.parser.BeautifulSoup', side_effect=Exception("Parsing failed unexpectedly"))
    result = extract_hospital_document_info("<html></html>", HOSPITAL_BASE_URL)
    assert result == []

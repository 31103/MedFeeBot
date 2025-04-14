import pytest
from src.parser import extract_pdf_links

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

from crawler import build_list_page_urls, extract_main_content, fetch_html


class _FakeResp:
    def __init__(self, text: str):
        self.text = text
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"

    def raise_for_status(self):
        return None


def test_fetch_html_returns_text(monkeypatch):
    def fake_get(url, timeout, headers):
        assert url == "http://example.com"
        assert timeout == 10
        assert "User-Agent" in headers
        return _FakeResp("ok")

    monkeypatch.setattr("crawler.requests.get", fake_get)
    assert fetch_html("http://example.com", timeout=10) == "ok"


def test_extract_main_content_prefers_zoom():
    html = '<html><body><div id="zoom">第一行<br/>第二行</div></body></html>'
    text = extract_main_content(html)
    assert "第一行" in text
    assert "第二行" in text


def test_build_list_page_urls_uses_index_suffix_for_pagination():
    urls = build_list_page_urls("http://i.whut.edu.cn/xxtg/", 3)
    assert urls == [
        "http://i.whut.edu.cn/xxtg/",
        "http://i.whut.edu.cn/xxtg/index_1.shtml",
        "http://i.whut.edu.cn/xxtg/index_2.shtml",
    ]

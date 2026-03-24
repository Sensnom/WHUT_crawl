import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


def build_list_page_urls(list_url: str, max_pages: int) -> list[str]:
    urls = [list_url]
    for page in range(1, max_pages):
        urls.append(urljoin(list_url, f"index_{page}.shtml"))
    return urls


def fetch_html(url: str, timeout: int = 20, retries: int = 2) -> str:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=HEADERS)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def extract_main_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    candidates = [
        "#zoom",
        ".TRS_Editor",
        ".article",
        ".content",
        ".detail",
    ]
    node = None
    for selector in candidates:
        node = soup.select_one(selector)
        if node:
            break
    if not node:
        node = soup.body or soup

    text = node.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

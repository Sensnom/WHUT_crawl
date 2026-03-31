from unittest.mock import MagicMock
from pathlib import Path

from config import Settings
from chaoxing_client import ChaoxingClient, _PlaywrightBrowser


def test_chaoxing_client_has_auth_state_path(tmp_path):
    settings = MagicMock(spec=Settings)
    settings.output_dir = str(tmp_path)
    client = ChaoxingClient(settings)
    path = client._get_auth_state_path()
    assert path == tmp_path / "chaoxing_auth_state.json"


def test_chaoxing_client_uses_provided_browser_factory():
    factory = MagicMock()
    settings = MagicMock(spec=Settings)
    settings.output_dir = "/tmp"
    client = ChaoxingClient(settings, browser_factory=factory)
    assert client.browser_factory is factory


def test_playwright_browser_class_exists():
    assert hasattr(_PlaywrightBrowser, "new_page")
    assert hasattr(_PlaywrightBrowser, "close")


def test_chaoxing_client_default_browser_is_playwright():
    settings = MagicMock(spec=Settings)
    settings.output_dir = "/tmp"
    client = ChaoxingClient(settings)
    assert client.browser_factory is _PlaywrightBrowser

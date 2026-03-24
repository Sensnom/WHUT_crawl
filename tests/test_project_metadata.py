from pathlib import Path
import tomllib


def test_pyproject_declares_uv_managed_dependencies():
    pyproject = Path("pyproject.toml")

    assert pyproject.exists()

    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert data["project"]["name"] == "network-crawl"
    assert data["project"]["requires-python"] == ">=3.10"
    assert "beautifulsoup4>=4.12.0" in data["project"]["dependencies"]
    assert "python-dotenv>=1.0.0" in data["project"]["dependencies"]
    assert "requests>=2.31.0" in data["project"]["dependencies"]
    assert "pytest>=8.0.0" in data["dependency-groups"]["dev"]


def test_uv_lock_exists():
    assert Path("uv.lock").exists()


def test_project_declares_playwright_dependency():
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "playwright>=" in text

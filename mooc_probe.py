"""
MOOC探针脚本 - 分析MOOC主页结构
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

MOOC_LOGIN_URL = "https://www.icourse163.org/member/login.htm"
MOOC_HOME_URL = "https://www.icourse163.org/learn/myhome"

# 存储认证状态
AUTH_STATE_PATH = Path(__file__).parent / "output" / "mooc_auth_state.json"


def setup_browser():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="zh-CN",
    )
    # 注入反检测脚本
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    """)
    return playwright, browser, context


def login_if_needed(page, timeout_ms: int):
    """登录MOOC"""
    page.goto(MOOC_LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    print(f"当前URL: {page.url}")

    if "login" in page.url.lower():
        print("需要登录...")

        # 尝试切换到手机号登录标签
        try:
            phone_tab_selectors = [
                "li:has-text('手机号登录')",
                "li:has-text('手机登录')",
                ".last-login-holder:has-text('手机')",
                "li.last-login-holder:first-child",
            ]
            for selector in phone_tab_selectors:
                try:
                    tab = page.locator(selector).first
                    if tab.is_visible():
                        print(f"找到手机号登录标签: {selector}")
                        tab.click()
                        break
                except Exception:
                    pass
        except Exception as e:
            print(f"切换手机号登录标签失败: {e}")

        # 等待iframe加载
        page.wait_for_timeout(3000)

        # 查找登录iframe
        frame = find_login_frame(page)

        # 填写登录信息 (需要从.env或环境变量获取)
        import os

        email = os.getenv("MOOC_EMAIL", "")
        password = os.getenv("MOOC_PASSWORD", "")

        if not email or not password:
            print("错误: 请设置 MOOC_EMAIL 和 MOOC_PASSWORD 环境变量")
            return False

        print(f"填写手机号/邮箱: {email}")
        email_input = find_email_input(frame)
        email_input.fill(email)

        import random
        import time

        time.sleep(random.uniform(0.3, 0.6))

        print("填写密码")
        password_input = find_password_input(frame)
        password_input.fill(password)

        time.sleep(random.uniform(0.3, 0.6))

        print("点击登录按钮")
        login_button = find_login_button(frame)
        login_button.click()

        # 等待登录完成
        try:
            page.wait_for_url("**/myhome**", timeout=15000)
            print("登录成功!")
        except Exception as e:
            print(f"等待URL跳转失败: {e}")
            # 检查是否还有登录框
            if "login" in page.url.lower():
                print("可能登录失败")
                save_screenshot(page, "login_failed")
                return False

        page.wait_for_timeout(3000)

        # 保存认证状态
        AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        page.context.storage_state(path=str(AUTH_STATE_PATH))
        print(f"认证状态已保存到: {AUTH_STATE_PATH}")

    return True


def find_login_frame(page):
    """查找登录iframe"""
    print("查找登录iframe...")

    # 尝试多种iframe选择器
    frame_selectors = [
        "#j-ursContainer-1 iframe",
        "iframe[id*='URS-iframe'][src*='index_dl2_new']",
        "iframe[id*='URS-iframe']",
        "iframe[src*='reg.icourse163.org']",
        "iframe[src*='index_dl2']",
    ]

    for selector in frame_selectors:
        try:
            print(f"尝试iframe选择器: {selector}")
            frames = page.frame_locator(selector)
            # 验证iframe中是否有登录表单
            test_locator = frames.locator("input[type='password']").first
            test_locator.wait_for(timeout=2000)
            if test_locator.is_visible():
                print(f"找到登录iframe: {selector}")
                return frames
        except Exception:
            pass

    # 如果精确选择器都失败，遍历所有iframe
    print("遍历所有iframe...")
    try:
        iframe_count = page.locator("iframe").count()
        print(f"页面共有 {iframe_count} 个iframe")
        for i in range(iframe_count):
            try:
                frame = page.frame_locator("iframe").nth(i)
                test_locator = frame.locator(
                    "input[type='tel'], input[type='password']"
                ).first
                test_locator.wait_for(timeout=1000)
                if test_locator.is_visible():
                    print(f"找到登录iframe: 第 {i + 1} 个iframe")
                    return frame
            except Exception:
                pass
    except Exception as e:
        print(f"遍历iframe失败: {e}")

    raise RuntimeException("未找到登录iframe")


def find_email_input(frame):
    """查找手机号/邮箱输入框"""
    selectors = [
        "input[type='tel']",  # 手机号输入框
        "input.dlemail.j-nameforslide",  # 邮箱输入框
        "input[name='email']",
        "input[type='email']",
        "input[placeholder*='手机']",
        "input[placeholder*='邮箱']",
    ]
    for selector in selectors:
        try:
            locator = frame.locator(selector).first
            locator.wait_for(timeout=2000)
            if locator.is_visible():
                return locator
        except Exception:
            pass
    raise RuntimeException("未找到邮箱输入框")


def find_password_input(frame):
    """查找密码输入框"""
    selectors = [
        "input.dlpwd",
        "input.j-inputtext.dlpwd",
        "input[type='password']",
    ]
    for selector in selectors:
        try:
            locator = frame.locator(selector).first
            locator.wait_for(timeout=2000)
            if locator.is_visible():
                return locator
        except Exception:
            pass
    raise RuntimeException("未找到密码输入框")


def find_login_button(frame):
    """查找登录按钮"""
    selectors = [
        "a#dologin",
        "a.u-loginbtn",
        "a:has-text('登录')",
        "button[type='submit']",
    ]
    for selector in selectors:
        try:
            locator = frame.locator(selector).first
            locator.wait_for(timeout=2000)
            if locator.is_visible():
                return locator
        except Exception:
            pass
    raise RuntimeException("未找到登录按钮")


def analyze_myhome_page(page):
    """分析课程主页结构"""
    print("\n" + "=" * 60)
    print("开始分析课程主页...")
    print("=" * 60)

    page.goto(MOOC_HOME_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)

    print(f"当前URL: {page.url}")

    # 保存截图
    save_screenshot(page, "mooc_myhome")

    # 列出所有iframe
    print("\n--- 页面iframes ---")
    try:
        iframe_count = page.locator("iframe").count()
        print(f"共有 {iframe_count} 个iframe")
        for i in range(iframe_count):
            try:
                iframe = page.locator("iframe").nth(i)
                src = iframe.get_attribute("src") or "无src"
                print(f"  iframe[{i}]: {src[:100]}...")
            except Exception as e:
                print(f"  iframe[{i}]: 获取失败 - {e}")
    except Exception as e:
        print(f"获取iframe失败: {e}")

    # 尝试在主文档中查找课程链接
    print("\n--- 主文档中的课程链接 ---")
    soup = BeautifulSoup(page.content(), "html.parser")

    # 查找包含课程名称的链接
    course_links = soup.select("a[href*='course'], a[href*='learn']")
    print(f"找到 {len(course_links)} 个可能的相关链接")

    for link in course_links[:20]:
        href = link.get("href", "")
        text = link.get_text(strip=True)
        if text and href:
            print(f"  文本: {text[:30]}... | href: {href[:80]}")

    # 尝试在iframe中查找
    print("\n--- 在iframe中查找课程 ---")
    try:
        for i in range(min(5, page.locator("iframe").count())):
            try:
                frame = page.frame_locator("iframe").nth(i)
                frame_soup = BeautifulSoup(frame.content(), "html.parser")
                frame_links = frame_soup.select("a[href*='tid='], a[href*='course']")
                if frame_links:
                    print(f"\n  iframe[{i}] 中的课程链接:")
                    for link in frame_links[:10]:
                        href = link.get("href", "")
                        text = link.get_text(strip=True)
                        if text:
                            print(f"    {text[:30]}... | {href[:80]}")
            except Exception as e:
                print(f"  iframe[{i}] 分析失败: {e}")
    except Exception as e:
        print(f"iframe遍历失败: {e}")

    # 尝试获取API数据
    print("\n--- 尝试获取课程数据 ---")
    try:
        # 查找包含termId信息的script或变量
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.get_text()
            if "termId" in text or "courseId" in text:
                print(f"找到包含termId的script标签，内容片段: {text[:200]}...")
    except Exception as e:
        print(f"查找script失败: {e}")

    # 保存页面源码
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "mooc_myhome.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page.content())
    print(f"\n页面源码已保存到: {html_path}")

    return True


def save_screenshot(page, name: str):
    """保存截图"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"截图已保存到: {path}")


def main():
    print("=" * 60)
    print("MOOC探针脚本 - 分析MOOC主页结构")
    print("=" * 60)

    # 检查环境变量
    import os

    if not os.getenv("MOOC_EMAIL") or not os.getenv("MOOC_PASSWORD"):
        print("\n请设置以下环境变量:")
        print("  export MOOC_EMAIL=your_email@example.com")
        print("  export MOOC_PASSWORD=your_password")
        print("\n或者在.env文件中设置:")
        print("  MOOC_EMAIL=your_email@example.com")
        print("  MOOC_PASSWORD=your_password")
        return

    playwright, browser, context = setup_browser()

    try:
        # 尝试加载已保存的认证状态
        page = context.new_page()
        timeout_ms = 60000

        if AUTH_STATE_PATH.exists():
            print(f"\n发现已保存的认证状态: {AUTH_STATE_PATH}")
            page = context.new_page(storage_state=str(AUTH_STATE_PATH))

        # 访问主页检查是否已登录
        page.goto(MOOC_HOME_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        if "login" in page.url.lower():
            print("认证状态已过期，需要重新登录")
            page.close()
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                locale="zh-CN",
            )
            page = context.new_page()
            if not login_if_needed(page, timeout_ms):
                return
        else:
            print("使用已保存的认证状态访问主页")

        # 分析主页结构
        analyze_myhome_page(page)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
    finally:
        browser.close()
        playwright.stop()


if __name__ == "__main__":
    main()

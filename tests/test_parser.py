from datetime import datetime

from parser import filter_recent_notices, filter_source_notices, parse_list_page


def test_filter_recent_notices_keeps_only_last_72_hours():
    now = datetime(2026, 3, 18, 12, 0, 0)
    html = """
    <ul>
      <li><a href="./dept/">【部门】</a><a href="./a.shtml">通知A</a> 2026-03-18</li>
      <li><a href="./dept/">【部门】</a><a href="./b.shtml">通知B</a> 2026-03-14</li>
    </ul>
    """
    notices = parse_list_page(html, "http://i.whut.edu.cn/xxtg/")
    result = filter_recent_notices(notices, now)
    assert [item.title for item in result] == ["通知A"]


def test_parse_list_page_builds_absolute_url():
    html = """
    <ul>
      <li><a href="./dept/">【本科生院】</a><a href="./znbm/jwc/202603/t1.shtml">标题1</a> 2026-03-18</li>
    </ul>
    """
    notices = parse_list_page(html, "http://i.whut.edu.cn/xxtg/")
    assert len(notices) == 1
    assert notices[0].url == "http://i.whut.edu.cn/xxtg/znbm/jwc/202603/t1.shtml"
    assert notices[0].source == "本科生院"


def test_filter_source_notices_keeps_undergraduate_office_only():
    html = """
    <ul>
      <li><a href="./dept/">【本科生院】</a><a href="./a.shtml">通知A</a> 2026-03-18</li>
      <li><a href="./dept/">【团委】</a><a href="./b.shtml">通知B</a> 2026-03-18</li>
    </ul>
    """
    notices = parse_list_page(html, "http://i.whut.edu.cn/xxtg/")
    result = filter_source_notices(notices, "本科生院")
    assert [item.title for item in result] == ["通知A"]

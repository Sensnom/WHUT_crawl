"""
MOOC服务 - 中国大学MOOC课程任务抓取服务
"""

from config import Settings
from course_parser import CourseTask

try:
    from mooc_client import MoocClient
except ImportError:
    MoocClient = None


def fetch_mooc_tasks(
    settings: Settings,
    mooc_client_factory: callable | None = None,
) -> tuple[list[CourseTask], list[str]]:
    """
    获取MOOC课程任务

    Args:
        settings: 配置对象
        mooc_client_factory: 可选的客户端工厂函数

    Returns:
        (任务列表, 警告列表)
    """
    if (
        not settings.enable_mooc_service
        or not settings.mooc_email
        or not settings.mooc_password
    ):
        return [], []

    if mooc_client_factory is None:
        if MoocClient is None:
            return [], ["MOOC客户端未安装，请检查依赖"]
        mooc_client_factory = MoocClient

    try:
        client = mooc_client_factory(settings)
        return client.fetch_pending_tasks()
    except Exception as exc:
        return [], [f"MOOC课程任务爬取失败: {exc}"]

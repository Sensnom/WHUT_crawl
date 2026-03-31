from datetime import datetime

from chaoxing_parser import parse_chaoxing_items, parse_deadline


def test_parse_chaoxing_items_keeps_unfinished_items_within_30_days():
    raw_items = [
        {
            "course_name": "高数",
            "title": "作业1",
            "status": "unfinished",
            "task_type": "assignment",
            "deadline": "2026-04-10 23:59",
        },
        {
            "course_name": "高数",
            "title": "期中考试",
            "status": "unfinished",
            "task_type": "exam",
            "deadline": "2026-05-30 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert [(task.title, task.task_type) for task in tasks] == [("作业1", "assignment")]


def test_parse_chaoxing_items_filters_finished_items():
    raw_items = [
        {
            "course_name": "高数",
            "title": "已完成作业",
            "status": "已完成",
            "task_type": "assignment",
            "deadline": "2026-04-10 23:59",
        },
        {
            "course_name": "高数",
            "title": "未完成作业",
            "status": "未完成",
            "task_type": "assignment",
            "deadline": "2026-04-10 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert [t.title for t in tasks] == ["未完成作业"]


def test_parse_chaoxing_items_filters_items_without_parseable_deadline():
    raw_items = [
        {
            "course_name": "高数",
            "title": "无截止日期任务",
            "status": "unfinished",
            "task_type": "assignment",
            "deadline": "",
        },
        {
            "course_name": "高数",
            "title": "正常任务",
            "status": "unfinished",
            "task_type": "assignment",
            "deadline": "2026-04-10 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert [t.title for t in tasks] == ["正常任务"]


def test_parse_chaoxing_items_filters_by_target_course_names():
    raw_items = [
        {
            "course_name": "高数",
            "title": "高数作业",
            "status": "unfinished",
            "task_type": "assignment",
            "deadline": "2026-04-10 23:59",
        },
        {
            "course_name": "大物",
            "title": "大物作业",
            "status": "unfinished",
            "task_type": "assignment",
            "deadline": "2026-04-10 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert [t.title for t in tasks] == ["高数作业"]


def test_parse_chaoxing_items_source_platform_is_chaoxing():
    raw_items = [
        {
            "course_name": "高数",
            "title": "作业1",
            "status": "unfinished",
            "task_type": "assignment",
            "deadline": "2026-04-10 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert all(t.source_platform == "chaoxing" for t in tasks)


def test_parse_deadline_handles_isoformat_with_z():
    text, dt = parse_deadline("2026-04-10T23:59Z", datetime(2026, 3, 24))
    assert text == "2026-04-10 23:59"
    assert dt is not None


def test_parse_deadline_handles_plain_datetime_format():
    text, dt = parse_deadline("2026-04-10 23:59", datetime(2026, 3, 24))
    assert text == "2026-04-10 23:59"
    assert dt is not None


def test_parse_chaoxing_items_keeps_unfinished_exam_within_30_days():
    raw_items = [
        {
            "course_name": "高数",
            "title": "期末考试",
            "status": "unfinished",
            "task_type": "exam",
            "deadline": "2026-04-20 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert len(tasks) == 1
    assert tasks[0].title == "期末考试"
    assert tasks[0].task_type == "exam"


def test_parse_chaoxing_items_filters_finished_exam():
    raw_items = [
        {
            "course_name": "高数",
            "title": "期末考试",
            "status": "已完成",
            "task_type": "exam",
            "deadline": "2026-04-20 23:59",
        },
        {
            "course_name": "高数",
            "title": "补考",
            "status": "已结束",
            "task_type": "exam",
            "deadline": "2026-04-20 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert [t.title for t in tasks] == []


def test_parse_chaoxing_items_filters_exam_outside_30_days():
    raw_items = [
        {
            "course_name": "高数",
            "title": "期末考试",
            "status": "unfinished",
            "task_type": "exam",
            "deadline": "2026-05-01 23:59",
        },
    ]

    tasks = parse_chaoxing_items(
        raw_items, now=datetime(2026, 3, 24, 12, 0), target_course_names=["高数"]
    )

    assert [t.title for t in tasks] == []


def test_parse_deadline_returns_original_on_failure():
    text, dt = parse_deadline("some invalid date", datetime(2026, 3, 24))
    assert text == "some invalid date"
    assert dt is None

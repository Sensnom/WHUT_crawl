from course_parser import parse_pending_course_tasks


def test_parse_pending_course_tasks_extracts_title_course_and_deadline():
    html = """
    <div class="task-item">
      <div class="course-name">高等数学</div>
      <div class="task-title">作业 3</div>
      <div class="deadline">截止时间：2026-03-21 23:59</div>
    </div>
    """

    tasks = parse_pending_course_tasks(html)

    assert len(tasks) == 1
    assert tasks[0].course_name == "高等数学"
    assert tasks[0].title == "作业 3"
    assert tasks[0].deadline_text == "2026-03-21 23:59"

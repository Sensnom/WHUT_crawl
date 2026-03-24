# 课程任务 Playwright 抓取设计

## 1. 背景

当前课程任务分支通过 `requests.Session` 访问 Smart WHUT 的 `mycourse` 页面。实测返回的是前端壳页面，正文包含“您需要启用 JavaScript 才能运行此应用程序”，说明课程任务列表依赖浏览器执行脚本后再渲染到 DOM。

因此，继续沿用纯 HTTP 登录和抓取方案，无法稳定拿到“待完成任务”数据。

## 2. 目标

将课程任务抓取从纯 HTTP 方案切换为浏览器自动化方案，在保留现有新闻邮件管线和课程邮件输出格式的前提下，可靠抓取 Smart WHUT `mycourse` 页面中的待完成任务列表。

完成后应满足：
- 能自动登录 Smart WHUT 统一认证。
- 能等待课程页面渲染完成后抓取待完成任务。
- 能继续复用现有 `course_parser.py` 输出 `CourseTask` 列表。
- 课程任务分支失败时，仍不影响新闻邮件分支。

## 3. 方案选择

### 方案 A：Playwright 浏览器自动化（采用）

做法：
- 使用 Playwright 启动无头浏览器。
- 打开 `COURSE_PAGE_URL`。
- 自动填写统一认证账号密码并提交。
- 等待 `mycourse` 页面完成前端渲染。
- 获取最终页面 HTML，再交给 `parse_pending_course_tasks()`。

优点：
- 最贴合当前站点的 JS 渲染特征。
- 能处理跳转、Cookie、前端渲染和延迟加载。
- 对现有业务层侵入较小，只替换课程抓取实现。

缺点：
- 新增浏览器依赖，运行环境要安装 Playwright 浏览器。
- 比 `requests` 更重，定时任务耗时略高。

### 方案 B：继续反向接口

做法：抓浏览器请求，推断课程任务接口，再直接调接口。

优点：运行轻、速度快。

缺点：前期不确定性高，可能涉及动态鉴权、签名或复杂请求链路；在当前缺少接口信息的情况下，不是最快落地路径。

## 4. 架构调整

保留当前双管线结构：
- 新闻摘要邮件管线保持不变。
- 课程任务邮件管线继续独立发送、独立记录状态。

仅替换课程抓取实现：
- `course_client.py` 从 `requests` 客户端调整为 Playwright 客户端。
- `main.py` 仍通过 `fetch_course_tasks()` 获取课程任务列表。
- `course_parser.py` 保持统一解析职责，不直接感知浏览器实现细节。

## 5. 组件设计

### `course_client.py`

职责：
- 启动 Playwright 浏览器和页面。
- 打开 `COURSE_PAGE_URL`。
- 判断是否进入统一认证页。
- 填写 `SMART_WHUT_USERNAME` / `SMART_WHUT_PASSWORD`。
- 提交表单并等待课程页渲染。
- 返回最终 HTML。

建议接口保持简单：

```python
class CourseClient:
    def __init__(self, settings: Settings, browser_factory: Callable | None = None):
        ...

    def fetch_course_page_html(self) -> str:
        ...
```

其中 `browser_factory` 只用于测试注入，生产路径默认使用 Playwright。

### `course_parser.py`

继续负责：
- 从渲染后 HTML 中提取任务块。
- 解析课程名、任务名、截止时间。

必要时可扩展选择器兼容当前页面真实 DOM，但不在浏览器客户端中混入解析逻辑。

### `main.py`

继续负责：
- 调用 `fetch_course_tasks()`。
- 调用课程任务邮件构建函数。
- 发送课程任务邮件。
- 写课程任务分支状态记录。

不把浏览器细节泄漏到调度逻辑里。

## 6. 数据流

课程分支的新数据流：

1. `run()` 进入 noon/evening 发送窗口。
2. `process_course_task_delivery()` 调用 `fetch_course_tasks()`。
3. `fetch_course_tasks()` 创建 `CourseClient`。
4. `CourseClient.fetch_course_page_html()` 用 Playwright 登录并等待课程页渲染。
5. 返回最终 HTML。
6. `parse_pending_course_tasks()` 输出 `list[CourseTask]`。
7. `email_sender.py` 构建课程任务邮件正文和 HTML。
8. 发送邮件并写入 `course_tasks_noon` / `course_tasks_evening` 状态。

## 7. 错误处理

需要覆盖三类失败：

### 登录失败
- 表现：账号密码提交后仍停留在登录页，或出现错误提示。
- 处理：抛出明确异常，例如“课程系统登录失败”。
- 结果：仅课程任务分支记录失败，不阻断新闻邮件分支。

### 页面渲染超时
- 表现：成功跳转但在限定时间内未出现任务区域。
- 处理：抛出超时异常，并标记课程任务邮件失败。

### DOM 结构变化
- 表现：页面已加载，但任务列表选择器失效。
- 处理：`course_parser.py` 返回空列表或抛出解析异常；短期先保守返回空列表并结合页面标记判断，避免把结构变更误判为“无任务”。

## 8. 测试策略

采用最小可维护测试集：

### 单测
- 为 `course_client.py` 增加浏览器页面对象的假实现，验证：
  - 会打开课程页。
  - 会填写用户名密码。
  - 会等待目标页面或任务区域。
  - 会返回渲染后的 HTML。

### 解析测试
- 继续用 `course_parser.py` 的 HTML fixture 测试任务提取。
- 若真实页面结构与现有 fixture 不同，补一组更贴近 Playwright 抓到的 HTML 片段。

### 调度回归
- 保留 `tests/test_main.py` 中双邮件发送、空任务发送、失败隔离、状态隔离测试。

## 9. 配置与依赖

新增依赖：
- `playwright`

环境配置：
- 继续使用现有 `COURSE_PAGE_URL`
- 继续使用现有 `SMART_WHUT_USERNAME`
- 继续使用现有 `SMART_WHUT_PASSWORD`

文档需要补充：
- 安装 Playwright Python 包后，首次需要执行浏览器安装命令。
- 定时任务机器上也要具备对应浏览器运行环境。

## 10. 实施边界

本次只做“最小可用浏览器抓取”：
- 不做截图归档。
- 不做多页面兼容层。
- 不做接口逆向。
- 不做复杂重试策略。

优先目标是先让课程任务邮件稳定拿到真实任务数据。

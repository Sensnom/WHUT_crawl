# WHUT 通知抓取与总结

抓取 `http://i.whut.edu.cn/xxtg/` 最近三天通知，默认聚焦 `本科生院` 消息，提取正文后调用 DeepSeek 生成中文简明要点，并可通过 Gmail 每天自动发送到你的邮箱。

## 1. 安装

```bash
uv sync
```

课程任务抓取现在依赖 Playwright 浏览器自动化。首次在新机器上完成依赖同步后，还需要安装浏览器运行时：

```bash
uv run playwright install chromium
```

如果你是手动维护依赖，也可以使用 `uv add playwright` 后再执行上面的浏览器安装命令。

如果还没安装 `uv`，先执行：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
REQUEST_TIMEOUT=60
TARGET_SOURCE=本科生院
MAX_PAGES=3
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail@gmail.com
SMTP_APP_PASSWORD=your_gmail_app_password
EMAIL_TO=your_gmail@gmail.com
COURSE_PAGE_URL=https://whut.ai-augmented.com/app/jx-web/mycourse
SMART_WHUT_USERNAME=your_student_id
SMART_WHUT_PASSWORD=your_password
SCHEDULE_TIMEZONE=Asia/Shanghai
SCHEDULE_HOUR=12
SCHEDULE_MINUTE=0
EVENING_SCHEDULE_HOUR=18
EVENING_SCHEDULE_MINUTE=0
BACKFILL_MAX_DAYS=7
STATE_RETENTION_DAYS=15
ENABLE_NEWS_SERVICE=true
ENABLE_COURSE_SERVICE=true
CHAOXING_USERNAME=your_chaoxing_phone_or_id
CHAOXING_PASSWORD=your_chaoxing_password
CHAOXING_TARGET_COURSE_NAMES=高数,大学物理
ENABLE_CHAOXING_SERVICE=true
```

如果你以后想改成别的发布单位，可以修改 `TARGET_SOURCE`。
如果通知较多、最近三天内容可能跨分页，可以把 `MAX_PAGES` 调大。
`SMTP_USER` 建议与 Gmail 发件账号一致，`EMAIL_TO` 可以填你自己的 Gmail。
`COURSE_PAGE_URL` 默认指向 Smart WHUT 的 `mycourse` 页面，`SMART_WHUT_USERNAME` 和 `SMART_WHUT_PASSWORD` 用于统一登录后抓取课程待办。
`SCHEDULE_TIMEZONE`、`SCHEDULE_HOUR`、`SCHEDULE_MINUTE`、`EVENING_SCHEDULE_HOUR`、`EVENING_SCHEDULE_MINUTE` 用来生成每天两次自动发送的定时任务。
`BACKFILL_MAX_DAYS` 控制最多补发多少天，`STATE_RETENTION_DAYS` 控制状态文件和日志清理周期。
`ENABLE_NEWS_SERVICE` 用来控制新闻服务总开关；设为 `false` 时会一起关闭新闻发送、失败重试和补发。
`ENABLE_COURSE_SERVICE` 用来控制课程任务服务总开关；设为 `false` 时不会发送课程任务邮件。
`CHAOXING_USERNAME` 和 `CHAOXING_PASSWORD` 用于登录超星学习通平台（`https://i.chaoxing.com/base?ws=1`）。
`CHAOXING_TARGET_COURSE_NAMES` 为逗号分隔的课程名称列表，只爬取这些课程的未完成作业和未完成考试；留空则跳过超星爬取。
`ENABLE_CHAOXING_SERVICE` 设为 `false` 可完全关闭超星学习通任务爬取。

### Gmail App Password

发送邮件时不要使用 Gmail 登录密码，而是使用 App Password：

1. 给 Gmail 账号开启两步验证
2. 在 Google 账号安全设置中创建 App Password
3. 把生成的 16 位密码填入 `SMTP_APP_PASSWORD`

## 3. 运行

```bash
uv run python main.py
```

运行后会：
- 在终端打印总结
- 写入 `output/summary_YYYYMMDD.md`
- 尝试把摘要发送到 `EMAIL_TO`
- 在发送窗口内额外发送一封课程任务邮件

脚本的发送行为：
- `12:00` 固定发送当天通知摘要，并发送一封课程任务邮件
- `18:00` 在有新增通知时发送晚间更新，同时发送一封课程任务邮件
- 若最近最多 `7` 天存在漏发，会聚合成一封补发邮件

课程任务邮件说明：
- 第二封邮件合并了 Smart WHUT 待完成任务和小雅作业（来自小雅课程平台），以及超星学习通的未完成作业和未完成考试（仅限 30 天内截止）
- 邮件正文按来源平台分组展示：小雅课程任务、超星学习通 / 作业、超星学习通 / 考试
- 邮件会尽量展示课程名、任务标题和截止时间
- 即使当天没有任务，也会发送一封写明"今日没有待完成任务"的课程任务邮件
- 新闻摘要邮件与课程任务邮件会分别记录发送状态，互不影响重试和去重
- 首次部署到 cron 或服务器机器时，也要先执行 `uv run playwright install chromium`，否则课程任务分支无法启动浏览器

状态文件：
- `output/email_delivery_state.json` 记录日期、槽位、是否发送成功、告警状态、通知链接集合
- 新闻邮件使用 `noon` / `evening` 槽位，课程任务邮件使用 `course_tasks_noon` / `course_tasks_evening` 槽位
- 发送失败会记录 `email_sent = false`，后续仍可继续重试或补发

补发规则：
- 最多追最近 `BACKFILL_MAX_DAYS` 天
- 所有缺失日期聚合到一个补发 Markdown 和一封补发邮件
- 补发文件名包含“补发”，例如 `output/补发_summary_20260312_20260318.md`
- 补发内容按对应日期生成，不使用当天新闻回填过去日期

清理规则：
- 每 `STATE_RETENTION_DAYS` 天清理过旧状态记录
- 不再额外维护独立日志文件，Linux 部署统一通过 `journalctl -u network-crawl.service` 查看运行日志

## 4. 定时任务

Linux 部署统一使用 `systemd`，把仓库里的 `scheduler/network-crawl.service` 和 `scheduler/network-crawl.timer` 当作生成模板，日常部署优先使用 `scheduler/manage_systemd.py` 自动渲染和安装。

### 4.1 systemd（Linux 首选）

1. 先完成依赖安装、`.env` 配置，以及 `uv run playwright install chromium`
2. 先渲染本机可用的 unit 预览文件，生成结果位于 `output/systemd/`
3. 确认生成结果后，用一条 root 命令安装到 `/etc/systemd/system/`
4. 如需排查，可重新渲染并检查 `output/systemd/` 里的最终内容

其中 `scheduler/network-crawl.service` 仍然保留 `WorkingDirectory=<PROJECT_ROOT>` 和 `ExecStart="<PYTHON_BIN>" "<PROJECT_ROOT>/main.py"` 这种占位格式，作为仓库内模板来源；自动化脚本会按当前机器路径、Python 解释器、运行账号和 `.env` 里的 `SCHEDULE_TIMEZONE` 生成可安装文件。

```bash
uv run python scheduler/manage_systemd.py --render
sudo uv run python scheduler/manage_systemd.py --install
sudo uv run python scheduler/manage_systemd.py --uninstall
```

常用检查命令：

```bash
sudo systemctl status network-crawl.timer
sudo systemctl list-timers network-crawl.timer
sudo systemctl start network-crawl.service
journalctl -u network-crawl.service -n 100 --no-pager
```

- `network-crawl.timer` 默认在每天 `12:00` 和 `18:00` 触发 `network-crawl.service`
- `scheduler/manage_systemd.py --render` 会把预览文件写到 `output/systemd/`
- `scheduler/manage_systemd.py --install` 只允许 root 执行，内部会复制生成后的 unit 到 `/etc/systemd/system/`，再执行 `systemctl daemon-reload` 和 `systemctl enable --now network-crawl.timer`
- `scheduler/manage_systemd.py --uninstall` 只允许 root 执行，会停掉并禁用 `network-crawl.timer`，删除已安装的 unit，然后重新加载 systemd
- `scheduler/network-crawl.timer` 里的 `Timezone=` 必须和 `.env` 里的 `SCHEDULE_TIMEZONE` 保持一致，否则 systemd 触发时间和应用判定窗口会错位
- `network-crawl.service` 会在项目根目录运行 `main.py`，并确保 `output/` 目录存在
- `scheduler/network-crawl.timer` 里的 `Persistent=true` 表示：如果机器在计划时间关机，错过的触发会在机器恢复后尽快补跑一次

## 5. 测试

```bash
uv run pytest -v
```

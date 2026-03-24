# WHUT 通知每日邮件发送设计

## 1. 目标

在现有“抓取武汉理工大学本科生院近三天通知并调用 DeepSeek 总结”的基础上，增加每日定时邮件发送能力。

目标行为：
- 每天北京时间 08:00 自动执行一次。
- 抓取并总结本科生院最近三天通知。
- 将“AI 总结 + 原始通知链接列表”发送到 `y2902341094@gmail.com`。
- 本地仍保留 `output/summary_YYYYMMDD.md`。

## 2. 方案选择

采用方案 A：在现有 Python 脚本中增加 Gmail SMTP 发信模块，并继续通过 cron 调度。

选择理由：
- 复用现有项目结构，改动最小。
- Gmail SMTP + App Password 配置简单。
- 适合个人每日通知场景。

## 3. 系统结构

新增模块：
- `email_sender.py`：负责构造邮件主题、正文、SMTP 发送。

调整模块：
- `config.py`：增加 SMTP 配置与收件人配置。
- `main.py`：在生成摘要文件后调用邮件发送逻辑。
- `README.md`：增加 Gmail App Password 配置说明和定时任务说明。
- `scheduler/cron.example`：更新为每日 08:00 运行的真实模板说明。

## 4. 配置设计

`.env` 增加以下变量：
- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USER=y2902341094@gmail.com`
- `SMTP_APP_PASSWORD=...`
- `EMAIL_TO=y2902341094@gmail.com`

保留已有变量：
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `REQUEST_TIMEOUT`
- `TARGET_SOURCE`
- `MAX_PAGES`

## 5. 邮件内容设计

邮件主题：
- `WHUT 本科生院通知摘要 YYYY-MM-DD`

邮件正文结构：
- 标题
- AI 总结
- 原始通知链接列表
- 生成时间

正文优先用纯文本，保证 SMTP 兼容性和可读性。必要时可扩展 HTML 版本，但当前不是必需项。

## 6. 运行流程

1. 读取配置。
2. 抓取本科生院近三天通知。
3. 抓取详情页正文。
4. 调用 DeepSeek 生成摘要。
5. 生成 Markdown 文件。
6. 组装邮件正文。
7. 通过 Gmail SMTP 发送给指定邮箱。

## 7. 错误处理

- 抓取失败：脚本退出并打印错误；不发送空邮件。
- DeepSeek 失败：发送降级版邮件（原始通知简表）。
- SMTP 失败：保留本地摘要文件，并在终端/日志输出失败原因。
- 配置缺失：明确指出缺失的 SMTP 或 DeepSeek 配置项。

## 8. 测试策略

- `config` 测试：验证 SMTP 配置读取。
- `email_sender` 测试：验证邮件主题和正文拼装。
- SMTP 测试：mock `smtplib.SMTP`，验证 TLS、登录、发送动作。
- `main` 流程测试：验证摘要文件仍会写入，即使发信失败。

## 9. 定时任务

cron 每天 08:00 运行：
- 调用 Python 脚本
- 将 stdout/stderr 追加到日志文件

如系统时区非中国时区，需额外设置 `TZ=Asia/Shanghai` 或在服务器上调整系统时区。

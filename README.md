# WHUT 通知抓取与总结

定时抓取武汉理工大学官网通知，AI 生成摘要后通过邮件推送。同时整合课程任务（Smart WHUT、小雅、超星学习通），每天 12:00 和 18:00 各发送一封。

---

## 功能概览

| 模块 | 说明 |
|------|------|
| **通知抓取** | 抓取 i.whut.edu.cn 最近三天通知，默认聚焦本科生院 |
| **AI 摘要** | 调用 DeepSeek 提取每条通知的要点 |
| **邮件推送** | 通过任意 SMTP 邮件服务发送，每天两档（12:00 / 18:00） |
| **补发机制** | 漏发日期自动聚合补发，最多追 7 天 |
| **课程任务** | 合并 Smart WHUT + 小雅 + 超星学习通的未完成作业/考试 |
| **发送状态** | JSON 状态文件记录每天发送结果，失败自动重试 |

---

## 安装

```bash
# 安装 uv（如果没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync

# 安装 Playwright 浏览器（课程任务爬取需要）
uv run playwright install chromium
```

---

## 配置

```bash
cp .env.example .env
vim .env
```

---

### 完整配置参数说明

```env
# ========== DeepSeek 摘要 ==========
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
REQUEST_TIMEOUT=60                    # 抓取单页超时（秒）

# ========== 通知来源 ==========
TARGET_SOURCE=本科生院                # 目标发布单位，可改成其他部门
MAX_PAGES=3                          # 最多抓取几页列表

# ========== 邮件推送 ==========
SMTP_HOST=smtp.gmail.com             # SMTP 服务器地址（支持任意邮件服务商）
SMTP_PORT=587                        # SMTP 端口（TLS：587，SSL：465）
SMTP_USER=your_email@example.com     # 发件邮箱
SMTP_APP_PASSWORD=your_app_password  # 邮箱授权码（不是登录密码）
EMAIL_TO=target@example.com           # 收件邮箱

# ========== 课程任务 — Smart WHUT ==========
COURSE_PAGE_URL=https://whut.ai-augmented.com/app/jx-web/mycourse
SMART_WHUT_USERNAME=your_student_id
SMART_WHUT_PASSWORD=your_password

# ========== 课程任务 — 小雅 ==========
MOOC_EMAIL=your_phone_or_email
MOOC_PASSWORD=your_password
MOOC_TARGET_COURSE_NAMES=数据库系统原理,计算机网络   # 逗号分隔，留空则跳过
ENABLE_MOOC_SERVICE=true

# ========== 课程任务 — 超星学习通 ==========
CHAOXING_USERNAME=your_phone_or_id
CHAOXING_PASSWORD=your_password
CHAOXING_TARGET_COURSE_NAMES=高数,大学物理            # 逗号分隔，留空则跳过
ENABLE_CHAOXING_SERVICE=true

# ========== 定时发送 ==========
SCHEDULE_TIMEZONE=Asia/Shanghai
SCHEDULE_HOUR=12
SCHEDULE_MINUTE=0
EVENING_SCHEDULE_HOUR=18
EVENING_SCHEDULE_MINUTE=0

# ========== 补发与清理 ==========
BACKFILL_MAX_DAYS=7       # 最多补发几天内的通知
STATE_RETENTION_DAYS=15  # 状态文件保留天数，过期自动清理

# ========== 服务总开关 ==========
ENABLE_NEWS_SERVICE=true     # 通知摘要（开/关）
ENABLE_COURSE_SERVICE=true  # 课程任务邮件（开/关）

# ========== NapCat QQ 晚间推送 ==========
ENABLE_NAPCAT_SERVICE=false
NAPCAT_BASE_URL=http://localhost:3000
NAPCAT_ACCESS_TOKEN=your_token
NAPCAT_TARGETS=group:123456789,private:987654321
```

---

### 邮件服务说明

不限于 Gmail，任意支持 SMTP 的邮箱均可使用：

| 邮箱 | SMTP_HOST | SMTP_PORT | 授权码说明 |
|------|-----------|-----------|------------|
| Gmail | `smtp.gmail.com` | 587 (TLS) | Google 账号 → 安全 → App Password |
| QQ 邮箱 | `smtp.qq.com` | 587 (TLS) | 邮箱设置 → 账户 → POP3/IMAP → 生成授权码 |
| 163 邮箱 | `smtp.163.com` | 465 (SSL) | 邮箱设置 → POP3/SMTP/IMAP → 客户端授权密码 |
| 企业邮箱 | `smtp.exmail.qq.com` | 465 (SSL) | 管理员开通或自设授权码 |

### NapCat QQ 晚间推送

晚间新闻摘要可选接入 NapCat 推送到 QQ。该配置只用于 `18:00` 的本科生院新闻摘要，不影响中午新闻邮件、补发邮件或课程任务邮件。`NAPCAT_TARGETS` 需使用 `group:<id>` 或 `private:<id>` 语法，多个目标用逗号分隔。

---

## 运行

```bash
# 手动运行一次（完整流程：抓取→摘要→发送）
uv run python main.py

# 仅运行健康检查（验证基础配置与本地运行前提）
uv run python main.py --mode healthcheck
```

**发送逻辑**
- `12:00` — 固定发送当天通知摘要 + 课程任务邮件
- `18:00` — 有新增通知时发送晚间更新 + 课程任务邮件
- 漏发日期自动补发（最多追 7 天）
- 新闻和课程任务邮件**分别记录状态**，互不影响

---

## 定时任务（systemd）

项目使用 systemd 定时器，不依赖 cron。

```bash
# 渲染生成可安装的 unit 文件（预览）
uv run python scheduler/manage_systemd.py --render

# 安装定时器（需要 root）
sudo uv run python scheduler/manage_systemd.py --install

# 卸载
sudo uv run python scheduler/manage_systemd.py --uninstall
```

**常用命令**

```bash
# 查看定时器状态
sudo systemctl status network-crawl.timer

# 查看最近运行日志
journalctl -u network-crawl.service -n 50 --no-pager

# 手动触发一次
sudo systemctl start network-crawl.service
```

---

## 输出文件

| 文件 | 说明 |
|------|------|
| `output/summary_YYYYMMDD.md` | 当天摘要 Markdown |
| `output/summary_YYYYMMDD_evening.md` | 晚间更新摘要 |
| `output/补发_summary_YYYYMMDD_YYYYMMDD.md` | 补发摘要 |
| `output/email_delivery_state.json` | 发送状态记录 |
| `output/email_diagnostics.log` | 邮件发送诊断日志 |

---

## 测试

```bash
uv run pytest -v
```

---

## 项目结构

```
WHUT_crawl/
├── main.py                  # 入口
├── crawler.py               # 通知列表抓取
├── parser.py                # 页面解析
├── summarizer.py            # DeepSeek 摘要
├── email_sender.py          # 邮件发送
├── course_client.py         # Smart WHUT 课程
├── mooc_client.py           # 小雅课程平台
├── chaoxing_client.py       # 超星学习通
├── app/
│   ├── runtime.py           # 运行时上下文
│   ├── workflows.py         # 工作流编排
│   └── healthcheck.py       # 健康检查
├── services/
│   ├── news_service.py      # 新闻发送逻辑
│   ├── course_service.py     # 课程任务逻辑
│   ├── backfill_service.py  # 补发逻辑
│   └── cleanup_service.py    # 状态清理
└── scheduler/
    └── manage_systemd.py     # systemd 安装脚本
```

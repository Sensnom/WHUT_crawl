# 每日邮件定时安装设计

## 1. 目标

在现有“抓取通知 + 生成摘要 + 发送邮件”的基础上，补齐一个可重复执行、可测试、可直接落地的定时安装能力，让用户不必手写 `crontab`。

目标行为：
- 继续复用 `main.py` 作为唯一执行入口。
- 新增一个命令行安装器，把每日定时任务写入当前用户的 `crontab`。
- 默认每天北京时间 08:00 执行一次。
- 允许通过环境变量调整时区、小时、分钟。
- 重复安装时保持幂等，不生成重复任务。

## 2. 方案选择

采用方案 A：增加项目内 `cron` 安装器，仍然使用系统 `cron` 调度。

选择理由：
- 保持现有运行链路不变，风险最低。
- 比让用户手工编辑 `crontab` 更易用，也更不容易配错路径。
- 比内置常驻调度器更适合个人 Linux 主机上的“每天一次”场景。

未采用方案：
- 在 Python 进程内引入 APScheduler：需要常驻进程，部署复杂度更高。
- 直接由我修改系统 `crontab`：依赖运行环境与用户偏好，不适合作为仓库内通用实现。

## 3. 系统结构

新增模块：
- `scheduler/manage_cron.py`：生成、安装、移除、打印受管 `cron` 配置。

调整模块：
- `config.py`：增加定时配置读取。
- `.env.example`：补充定时相关变量示例。
- `README.md`：增加安装定时任务的命令说明。
- `tests/test_scheduler.py`：覆盖 cron 文本生成与幂等替换行为。

## 4. 配置设计

`.env` 新增以下变量：
- `SCHEDULE_TIMEZONE=Asia/Shanghai`
- `SCHEDULE_HOUR=8`
- `SCHEDULE_MINUTE=0`

这些变量只影响安装出来的 `cron` 规则，不影响 `main.py` 的业务逻辑。

## 5. Cron 管理设计

安装器输出一个带标记的受管块：
- 起始标记：`# BEGIN network_crawl daily email`
- 结束标记：`# END network_crawl daily email`

块内包含：
- `TZ=Asia/Shanghai`
- 每日执行 `main.py` 的一条 `cron` 表达式
- 输出重定向到 `output/cron.log`

幂等规则：
- 若当前 `crontab` 不含受管块，则追加。
- 若已存在受管块，则整块替换。
- 移除时仅删除受管块，不影响其他已有定时任务。

## 6. 命令设计

提供以下命令：
- `python scheduler/manage_cron.py --print`：打印将要安装的 cron 块
- `python scheduler/manage_cron.py --install`：写入当前用户 crontab
- `python scheduler/manage_cron.py --remove`：移除当前项目的受管 cron 块

默认使用当前 Python 解释器路径，避免写死 `/usr/bin/python3`。

## 7. 错误处理

- 时间配置非法：抛出明确 `ValueError`。
- 未安装 `crontab` 命令：打印清晰错误并返回非 0。
- 读取或写入 `crontab` 失败：透出 stderr，便于排查。
- 安装器不读取邮件密钥，也不触碰 `.env` 中的敏感值。

## 8. 测试策略

- 配置测试：验证定时环境变量读取与默认值。
- 调度测试：验证 cron 块文本生成正确。
- 幂等测试：验证重复安装会替换旧块而不是追加重复块。
- 移除测试：验证仅删除受管块，保留其他 cron 内容。

## 9. 交付结果

完成后，用户只需要：
- 配好 `.env`
- 先手动运行 `python main.py` 验证发信
- 再执行 `python scheduler/manage_cron.py --install`

之后系统会每天自动发送邮件，无需再手工编辑 `crontab`。

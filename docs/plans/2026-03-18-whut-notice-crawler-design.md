# WHUT 通知站近三天抓取与 DeepSeek 总结设计

## 1. 目标与范围

目标：抓取 `http://i.whut.edu.cn/xxtg/` 最近三天内发布的通知，提取页面正文内容，并调用 DeepSeek API 生成中文简明要点总结。

范围：
- 支持手动运行一次。
- 支持定时自动运行（通过 cron）。
- 输出同时包含终端打印和本地 Markdown 文件。
- API Key 通过 `.env` 提供。

非目标：
- 不构建 Web UI。
- 不做多站点通用爬虫框架。
- 不做数据库持久化（先以文件输出为主）。

## 2. 方案选择

采用方案 A：Python + requests + BeautifulSoup + DeepSeek API。

选择理由：
- 项目目标单一，依赖轻，落地快。
- 维护成本低，适合校园通知站点结构化页面抓取。
- 后续可平滑升级为 Playwright（若页面改为强动态加载）。

## 3. 运行流程

1. 拉取列表页 HTML。
2. 解析通知条目：标题、详情链接、发布时间。
3. 将发布时间与“当前时间 - 72 小时”比较，筛选最近三天条目。
4. 逐条抓取详情页，提取正文并清洗文本。
5. 组织输入内容并调用 DeepSeek 生成中文简明要点。
6. 输出结果到终端和 `output/summary_YYYYMMDD.md`。

## 4. 模块与目录设计

建议目录：

```text
network_crawl/
  main.py
  crawler.py
  parser.py
  summarizer.py
  config.py
  models.py
  scheduler/
    cron.example
  output/
  .env.example
  requirements.txt
  README.md
```

模块职责：
- `config.py`: 读取环境变量和运行参数（DeepSeek Key、模型名、超时、输出路径）。
- `models.py`: 定义数据结构（通知项、抓取结果）。
- `crawler.py`: 网络请求、重试、详情页抓取。
- `parser.py`: 列表/详情页 HTML 解析与时间过滤。
- `summarizer.py`: DeepSeek 调用与提示词构建。
- `main.py`: 编排全流程，输出日志与文件。
- `scheduler/cron.example`: 提供定时任务模板。

## 5. 数据与提示词策略

输入给总结模型的数据格式：
- 每条通知包含：`标题`、`发布时间`、`链接`、`正文（截断到合理长度）`。

提示词约束：
- 输出中文。
- 输出 3-8 条要点。
- 每条尽量包含“事项 + 对象 + 时间/要求（若有）”。
- 避免复述无效前言。

为控制 token：
- 单条正文设最大长度（例如 1200-2000 字符）。
- 总条目过多时按发布时间排序后截取最近若干条。

## 6. 时间过滤规则

规则定义：
- 以程序运行时刻为 `now`。
- 仅保留 `publish_time >= now - 72h` 的通知。

实现注意：
- 使用站点发布时间字段做过滤，不按列表顺序假设。
- 发布时间解析失败时记录警告并跳过该条，避免污染结果。

## 7. 错误处理与稳健性

- 网络请求失败：有限次重试（指数退避），最终失败则记录并继续处理其他条目。
- 页面结构变化：解析不到关键字段时输出结构告警并跳过。
- DeepSeek 调用失败：
  - 第一次失败重试一次；
  - 仍失败时输出“原始通知简表”作为降级结果，保证任务有产出。
- 空结果场景（最近三天无通知）：输出明确提示并写入文件。

## 8. 配置与安全

`.env` 变量建议：
- `DEEPSEEK_API_KEY=...`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-chat`
- `REQUEST_TIMEOUT=20`

安全要求：
- `.env` 加入忽略文件，不提交到仓库。
- 日志中不打印完整密钥。

## 9. 运行与调度

手动运行：
- `python main.py`

cron 示例（每天 08:00）：
- `0 8 * * * /usr/bin/python3 /path/to/network_crawl/main.py >> /path/to/network_crawl/output/cron.log 2>&1`

## 10. 验证与测试策略

最小验证：
- 能成功抓取列表页并解析出通知数量。
- 时间过滤后仅包含最近三天条目。
- 至少一条详情页正文提取成功。
- DeepSeek 成功返回摘要并写入文件。

建议测试：
- 时间解析单元测试（不同日期格式）。
- 解析器单元测试（使用本地 HTML 样例）。
- 无数据、网络失败、API 失败的异常路径测试。

## 11. 里程碑

1. 搭建项目骨架与配置读取。
2. 完成列表页/详情页抓取与解析。
3. 完成 72 小时过滤和文本清洗。
4. 接入 DeepSeek 总结。
5. 完成终端+文件输出与 cron 模板。
6. 进行端到端验证并补充 README。

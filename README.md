# novel-spider

一个面向静态小说站的通用采集工具骨架。它通过“站点配置 + 通用抓取引擎”的方式工作：同一套命令行程序负责请求、限速、断点记录、清洗和导出；不同网站只需要单独维护配置文件。

请只采集你拥有授权、公共领域、自己维护的网站或个人备份范围内的内容，并遵守目标网站的服务条款和 robots.txt。

## 功能

- 从目录页提取章节链接
- 抓取章节标题和正文
- 自动处理相对链接、页面编码、简单正文清洗
- 支持断点续爬和跳过已抓章节
- 导出为 TXT 或 Markdown
- 默认尊重 robots.txt，并带有请求间隔
- 支持 dry-run 预览章节链接

## 安装

```powershell
cd E:\code\tools\novel-spider
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## 快速使用

单本下载：

```powershell
novel-spider --config jinyong-net --id yitiantulongji
```

先预览章节：

```powershell
novel-spider --config jinyong-net --id yitiantulongji --dry-run
```

限制只抓前 3 章测试：

```powershell
novel-spider --config jinyong-net --id yitiantulongji --limit 3
```

手动指定书名或输出文件：

```powershell
novel-spider --config jinyong-net --id yitiantulongji --name 倚天屠龙记 --output .\downloads\book.txt
```

导出 Markdown：

```powershell
novel-spider --config jinyong-net --id yitiantulongji --format md
```

忽略断点记录并重新抓：

```powershell
novel-spider --config jinyong-net --id yitiantulongji --force
```

## 批量下载

批量配置只引用站点配置，然后在 `books` 里放多本书的 ID：

```json
{
  "config": "jinyong-net",
  "books": [
    {"name": "", "id": "yitiantulongji"},
    {"name": "手动书名", "id": "shediaoyingxiongzhuan"}
  ]
}
```

运行：

```powershell
novel-spider --config jinyong-net-batch --batch
```

每本书默认导出到 `downloads\<书名>.txt`。也可以指定目录：

```powershell
novel-spider --config jinyong-net-batch --batch --output-dir .\downloads
```

批量预览章节：

```powershell
novel-spider --config jinyong-net-batch --batch --dry-run
```

## 配置说明

配置文件使用 JSON，示例见 `configs/site.template.json`。

常用字段：

- `site_name`: 站点名称，仅用于日志和进度文件
- `book_url_template`: 目录页 URL 模板。`{id}` 会被命令里的 `--id` 或批量书单里的 `id` 替换
- `book_url`: 固定目录页 URL，可选。适合只抓一本的配置
- `book_name`: 书名，可选。不填时会从目录页自动读取
- `book_name_regex`: 可选。对自动读取到的书名再做一次正则提取
- `encoding`: 可选。目标站编码，如 `utf-8`、`gbk`。不填则自动猜测
- `request.delay_seconds`: 每次请求之间的等待秒数
- `request.timeout_seconds`: 请求超时时间
- `request.user_agent`: User-Agent
- `request.respect_robots`: 是否尊重 robots.txt，默认 true
- `selectors.chapter_links`: 章节链接选择器
- `selectors.book_name`: 书名选择器
- `selectors.chapter_title`: 章节标题选择器
- `selectors.chapter_content`: 正文选择器
- `selectors.remove`: 正文中需要移除的元素选择器列表
- `filters.include_url_regex`: 只保留匹配的章节 URL
- `filters.exclude_url_regex`: 排除匹配的章节 URL
- `content_filters.stop_before_text_regex`: 正文行匹配这些正则时，从该行开始丢弃后续内容，适合清掉正文末尾推广
- `content_filters.drop_line_regex`: 丢弃匹配这些正则的单行内容

例如正文末尾有“相关推荐”“展开阅读”之类的广告段，可以这样配置：

```json
"content_filters": {
  "stop_before_text_regex": ["相关推荐", "展开阅读"],
  "drop_line_regex": ["^\\s*更多\\s*$"]
}
```

## 针对 jinyong.net.cn 这类老站

这类页面通常是静态 HTML，章节目录和正文都可以通过 CSS 选择器解析。因为页面结构可能会变，建议先用浏览器打开目录页，右键检查章节链接和正文容器，再填入配置。

现有的 `configs/jinyong-net.json` 是站点规则，`configs/jinyong-net-batch.json` 是书单示例。

## 项目结构

```text
novel_spider/
  cli.py          命令行入口
  config.py       配置读取与校验
  crawler.py      抓取流程
  fetcher.py      HTTP 请求、限速、robots
  parser.py       目录和章节解析
  exporters.py    TXT/Markdown 导出
  progress.py     断点进度
```

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

批量配置也是 Python。只需要引用站点配置，然后在 `BOOKS` 里放多本书的 ID：

```python
SITE_CONFIG = "jinyong-net"

BOOKS = [
    "yitiantulongji",
    {"id": "shediaoyingxiongzhuan", "name": "射雕英雄传"},
]
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

配置文件只支持 Python，示例见 `configs/site-template.py`。省略后缀时会自动在 `configs/` 下查找同名 `.py` 文件。

Python 配置会执行本地代码，只运行你信任的配置文件。

最小站点配置：

```python
CONFIG = {
    "site": {
        "name": "example",
        "home": "https://example.com/",
        "desc": "",
    },
    "book": {
        "url_template": "https://example.com/{id}/",
        "name_selector": ".book-title, h1, title",
        "chapters": {
            "selector": ".chapter-list li",
            "url_selector": "a[href]",
            "name_selector": "a",
        },
    },
    "chapter": {
        "content_selector": ".chapter-content p",
    },
}
```

常用字段：

- `site.name`: 站点名称，仅用于日志和进度文件
- `site.home`: 站点首页，可选
- `site.desc`: 站点描述，可选
- `book.url_template`: 目录页 URL 模板。`{id}` 会被命令里的 `--id` 或批量书单里的 `id` 替换
- `book.url`: 固定目录页 URL，可选。适合只抓一本的配置
- `book.name`: 书名，可选。不填时会从目录页自动读取
- `book.name_regex`: 可选。对自动读取到的书名再做一次正则提取
- `book.name_selector`: 书名选择器，可选
- `book.chapters.selector`: 目录页里每一个章节条目的选择器
- `book.chapters.url_selector`: 从章节条目里获取链接的选择器
- `book.chapters.name_selector`: 从章节条目里获取标题的选择器，优先读取 `title` 属性，其次读取文本
- `chapter.content_selector`: 章节页正文容器选择器
- `encoding`: 可选。目标站编码，如 `utf-8`、`gbk`。不填则自动猜测

请求参数也可以按需覆盖；不写就使用默认值：

- `delay_seconds`: 每次请求之间的等待秒数，默认 1.0
- `timeout_seconds`: 请求超时时间，默认 20.0
- `retries`: 请求失败后的重试次数，默认 2
- `user_agent`: User-Agent，默认使用工具自己的标识
- `respect_robots`: 是否尊重 robots.txt，默认 true

### Hook 特殊适配

还可以按需导出这些 hook：

- `parse_book_name(url, html, config) -> str | None`
- `format_book_name(name, config) -> str | None`
- `parse_book_chapters(url, html, config) -> list[ChapterLink] | None`
- `format_book_chapters(chapters, config) -> list[ChapterLink] | None`
- `parse_chapter_content(url, html, config) -> str | None`
- `format_chapter_content(content, config) -> str | None`

`parse_*` hook 返回 `None` 时会回退到默认解析逻辑；`format_*` hook 返回 `None` 时会保留当前解析结果。

例如只对正文做额外清洗：

```python
CONFIG = {
    "site": {"name": "example"},
    "book": {
        "url_template": "https://example.com/{id}/",
        "chapters": {
            "selector": ".chapter-list li",
            "url_selector": "a[href]",
            "name_selector": "a",
        },
    },
    "chapter": {
        "content_selector": ".chapter-content p",
    },
}


def format_chapter_content(content, config):
    lines = [line for line in content.splitlines() if "广告" not in line]
    return "\n\n".join(lines)
```

如果目录里混入了非章节链接，也不要再加通用 `include/exclude` 配置，直接写 `format_book_chapters`：

```python
def format_book_chapters(chapters, config):
    return [chapter for chapter in chapters if chapter.url.endswith(".html")]
```

## 针对 jinyong.net.cn 这类老站

这类页面通常是静态 HTML，章节目录和正文都可以通过 CSS 选择器解析。因为页面结构可能会变，建议先用浏览器打开目录页，右键检查章节链接和正文容器，再填入配置。

现有的 `configs/jinyong-net.py` 是站点规则，`configs/jinyong-net-batch.py` 是书单示例。

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

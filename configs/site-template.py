from __future__ import annotations

# Python 配置会执行本地代码，只使用你信任的配置文件。
# 简单站点通常只需要 CONFIG；特殊站点再按需补下面的 hook。

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
            # 先选中目录里的每一个“章节条目”。
            "selector": ".chapter-list li",
            # 再从章节条目里找链接元素，读取 href。
            "url_selector": "a[href]",
            # 再从章节条目里找标题元素，优先读取 title 属性，其次读取文本。
            "name_selector": "a",
        },
    },
    "chapter": {
        # 章节页正文容器。默认解析会把这些节点里的文本按段落导出。
        "content_selector": ".chapter-content p",
    },
}


# 可选 hook。parse_* 负责特殊解析；返回 None 表示交回默认解析逻辑处理。
# format_* 负责后置整理；返回 None 表示保留当前解析结果。
#
# def parse_book_name(url: str, html: str, config):
#     return None
#
#
# def format_book_name(name: str, config):
#     return name
#
#
# def parse_book_chapters(url: str, html: str, config):
#     from novel_spider.parser import default_parse_book_chapters
#
#     return default_parse_book_chapters(url, html, config)
#
#
# def format_book_chapters(chapters: list, config):
#     return chapters
#
#
# def parse_chapter_content(url: str, html: str, config):
#     from novel_spider.parser import default_parse_chapter_content
#
#     return default_parse_chapter_content(url, html, config)
#
#
# def format_chapter_content(content: str, config):
#     return content

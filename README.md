# AI、Rust、HFT基础宝典

这是一套面向零基础求职者的中文 `mdBook`。当前版本优先完善 HFT 与低延迟工程：从市场微观结构、订单撮合和交易生命周期，一直讲到 Rust 成本模型、网络、风控、性能验证与系统设计面试。

## 阅读原则

- 先解释“它解决什么问题”，再引入术语和实现细节。
- 核心章节尽量包含直觉、原理、图表、算例、代码、面试追问、易错点和练习。
- 不把经验规则写成绝对定律；性能数字必须说明硬件、负载和测量方法。
- 先保证行情、订单、持仓和风控正确，再优化延迟。
- 内容仅用于工程与面试学习，不构成投资建议。

## 本地预览

需要 `mdbook` 与 `mdbook-mermaid`：

```bash
cargo install --locked --version 0.5.2 mdbook
cargo install --locked --version 0.17.0 mdbook-mermaid
python3 scripts/check_book.py
mdbook serve --open
```

构建后的静态文件位于 `book/`。

## 内容质量检查

```bash
python3 scripts/check_book.py
mdbook test
mdbook build
```

检查脚本会发现目录中的失效链接、未进入目录的孤立章节、过短占位页、重复一级标题和常见草稿标记。`mdbook test` 还会编译所有标为可独立运行的 Rust 示例。GitHub Actions 也会执行同一组检查。

## 搜索引擎设置

本书要求不被搜索引擎收录，因此每个 HTML 页面的 `<head>` 都包含 `noindex` 元信息。`robots.txt` **有意允许抓取 HTML**，让搜索引擎能够读取并执行 `noindex`；不要把这些页面 `Disallow`，否则已知 URL 可能因为爬虫看不到 `noindex` 而继续留在索引中。这只能约束遵守规范的爬虫；如果内容必须严格保密，应使用私有仓库、身份认证或受访问控制的托管。

## 目录

全书目录由 [src/SUMMARY.md](src/SUMMARY.md) 管理。新增章节后必须把它加入目录，并保证相对链接可用。

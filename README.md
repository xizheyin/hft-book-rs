# AI、Rust、C++、HFT基础宝典

这是一个面向零基础求职者的中文知识库。仓库中包含两本独立的 `mdBook`，但共用同一套主题、质量检查和 GitHub Pages 部署流程：

- **《Rust、C++ 与 HFT 基础宝典》**：市场微观结构、订单撮合、Rust/C++ 成本模型、网络、风控、性能验证和系统设计面试。
- **《DeepSeek AI Agent Infra 面试宝典》**：从 AI/LLM 地基、DeepSeek 架构与 Agent Harness，一直覆盖沙箱、虚拟化、存储、网络、调度、可靠性和个性化面试实战。

## 仓库结构

```text
books/
├── rust-hft/          # Rust/C++/HFT 独立 mdBook（沿用既有部署路径）
│   ├── book.toml
│   └── src/
└── ai/                # AI 独立 mdBook
    ├── book.toml
    └── src/
shared/theme/           # 两本书共用的主题和 noindex 模板
portal/                 # 部署后的总入口
scripts/                # 结构检查与兼容跳转工具
site/                   # 本地统一构建产物（不提交）
```

部署后的路径是：

- `/hft-book-rs/`：两本书的总入口；
- `/hft-book-rs/rust-hft/`：Rust/C++/HFT 书；
- `/hft-book-rs/ai/`：AI 书。

## 阅读与贡献原则

- 先解释“它解决什么问题”，再引入术语和实现细节。
- 核心章节尽量包含直觉、原理、图表、算例、代码、面试追问、易错点和练习。
- 性能数字必须说明硬件、负载和测量方法；不把经验规则写成绝对定律。
- 先保证数据、状态、风控和评测正确，再谈延迟或模型优化。
- 内容仅用于工程与面试学习，不构成投资建议。

## 本地检查

需要 `mdbook`、`mdbook-mermaid`，以及支持 C++20 的 GCC 或 Clang：

```bash
cargo install --locked --version 0.5.2 mdbook
cargo install --locked --version 0.17.0 mdbook-mermaid

python3 scripts/check_book.py
python3 scripts/check_cpp_examples.py
mdbook test books/rust-hft
mdbook test books/ai
```

## 构建统一站点

```bash
BOOK_SITE_ROOT="$(pwd)/site"
mkdir -p "$BOOK_SITE_ROOT"
cp -R portal/. "$BOOK_SITE_ROOT/"
mdbook build books/rust-hft -d "$BOOK_SITE_ROOT/rust-hft"
mdbook build books/ai -d "$BOOK_SITE_ROOT/ai"
python3 scripts/create_legacy_redirects.py "$BOOK_SITE_ROOT"
python3 scripts/check_site.py "$BOOK_SITE_ROOT"
python3 -m http.server --directory "$BOOK_SITE_ROOT" 8000
```

GitHub Actions 会执行同样的双书检查和构建，然后把整个 `site/` 作为一个 Pages artifact 发布。

## 搜索引擎设置

总入口和两本书的每个 HTML 页面都包含 `noindex`。`robots.txt` **有意允许抓取 HTML**，让搜索引擎能读取并执行 `noindex`。这不是权限控制；若内容必须保密，仍应使用私有仓库、身份认证或受访问控制的托管。

## 内容入口

- Rust/C++/HFT 目录：[`books/rust-hft/src/SUMMARY.md`](books/rust-hft/src/SUMMARY.md)
- AI 目录：[`books/ai/src/SUMMARY.md`](books/ai/src/SUMMARY.md)
- 贡献规范：[`CONTRIBUTING.md`](CONTRIBUTING.md)

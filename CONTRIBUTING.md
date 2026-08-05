# 内容贡献规范

这套书面向第一次接触项目细节的读者。新增或修改章节时，不要默认读者已经懂金融、Rust、Linux、低延迟或 AI 术语。

## 两本书放在哪里

仓库使用同一套 mdBook 工具链，但内容分成两本可以独立阅读的书：

- `books/rust-hft/`：Rust、C++ 与 HFT；章节放入 `books/rust-hft/src/`，目录维护在 `books/rust-hft/src/SUMMARY.md`。
- `books/ai/`：AI；章节放入 `books/ai/src/`，目录维护在 `books/ai/src/SUMMARY.md`。
- `shared/theme/`：两本书共用的样式、交互和 `noindex` 页面头。
- `portal/`：部署后的总入口，只负责把读者带到两本子书。

不要把一本书的 Markdown 文件复制到另一本书。跨书引用应链接部署后的 HTML 页面，例如 AI 首页引用 Rust 生命周期章节时使用 `../rust-hft/rust_advanced/lifetimes.html`。

## 一章的推荐结构

不要求机械套模板，但核心章节应尽量覆盖：

```markdown
# 清楚、可搜索的章节标题

用 2–3 句话说明“它解决什么问题”。

> 本章目标：读完能解释、推演和选择什么。

## 直觉模型
## 工作原理
## 带数字的算例或状态机
## Rust / 伪代码 / 架构图
## 工程权衡与故障模式
## 面试追问与参考答法
## 易错点
## 练习与参考答案
## 小结
```

## 事实与措辞

- 不写“终极方案”“严禁”“必然更快”“固定快 N 倍”，除非它是有明确定义的安全/协议约束。
- 市场、订单和协议规则要注明适用场所；实现前指向当前官方规范。
- 性能数字必须说明硬件、软件、负载、样本和计时边界；教学数字要标成“教学算例”。
- 区分语言保证、库实现、当前编译器行为和经验观察。
- 区分提交、完成、缓冲区可复用、网卡发出和业务确认。
- 不承诺收益，不把可能违法或操纵市场的行为包装成技巧。

## 代码示例

- 优先给安全、短小、能解释的不变量；`unsafe` 必须写 `SAFETY` 理由。
- 解析器先检查长度、类型、字节序和溢出，不对任意字节直接 `transmute`。
- 价格、数量、名义金额用明确单位与 checked 运算。
- 并发示例说明生产者/消费者数量、所有权、满/空语义和内存顺序。
- 标准库且声称完整的示例使用 `rust` 围栏，必须通过 `mdbook test`。
- 依赖外部 crate、操作系统、硬件或多文件工程的示例使用 `rust,ignore`，并在正文说明依赖和单独验证方式。
- 单文件、只依赖标准库的完整 C++20 程序使用 `cpp` 围栏，必须包含 `main` 并通过 `scripts/check_cpp_examples.py`。
- C++ 教学片段、多文件工程、平台专属代码和故意展示错误的代码使用 `cpp,ignore`，正文必须说明为什么不能独立编译。
- 真正的伪代码要明确写出省略的类型或步骤，不能伪装成可直接运行的程序。

## 展现形式

根据知识关系选择最小有效形式：

- 状态变化：Mermaid `stateDiagram` / `sequenceDiagram`；
- 组件链路：`flowchart`；
- 概念对比、字段映射：表格；
- 手算过程：公式 + 逐步计算；
- 参考答案：`<details>` 折叠块；
- 风险提醒、面试骨架：Markdown 引用块。

图和表必须在移动端仍可理解；很宽的图允许横向滚动。

## 提交前检查

```bash
python3 scripts/check_book.py
python3 scripts/check_cpp_examples.py
mdbook test books/rust-hft
mdbook test books/ai

BOOK_SITE_ROOT="$(pwd)/site"
mkdir -p "$BOOK_SITE_ROOT"
cp -R portal/. "$BOOK_SITE_ROOT/"
mdbook build books/rust-hft -d "$BOOK_SITE_ROOT/rust-hft"
mdbook build books/ai -d "$BOOK_SITE_ROOT/ai"
python3 scripts/create_legacy_redirects.py "$BOOK_SITE_ROOT"
python3 scripts/check_site.py "$BOOK_SITE_ROOT"

git diff --check
```

还要人工确认：

- 新章节已加入对应子书的 `src/SUMMARY.md`；
- 每章只有一个一级标题；
- 书内链接、跨书链接和折叠块完整；
- 深色/浅色、桌面/移动端无明显布局问题；
- 总入口和两本书构建出的每个 HTML 页面都保留 `<meta name="robots" content="noindex, ...">`。

`noindex` 不是权限控制。若内容必须保密，应使用认证或私有托管。

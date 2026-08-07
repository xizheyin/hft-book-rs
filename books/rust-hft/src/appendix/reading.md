# 推荐阅读 (Recommended Reading)

HFT 开发涉及 Rust、计算机体系结构、操作系统、网络协议和市场微结构。下面的资料适合按当前短板选读，不是一份必须从头到尾完成的权威清单。书籍和演讲提供思维模型；实现细节、协议字段与交易规则仍要回到当前的一手文档。

推荐顺序不是“全部读完”，而是：先用一本系统教材补当前基础，再读与你项目直接相关的一份官方规范，最后才用论文、博客或演讲扩展视角。每读一项都应能回答“它解决了我的哪个问题”；没有问题驱动的长书单不会自动提高面试表现。

## 1. 分主题书籍

### 系统编程与性能优化
*   **《Systems Performance: Enterprise and the Cloud》 (Brendan Gregg)**
    *   介绍从问题陈述、指标到工具验证的性能分析方法，并覆盖 `perf`、eBPF（Linux 内核的可观测与可编程机制）和火焰图等工具。命令和内核能力会随版本变化，实践时配合当前官方文档。
*   **《Computer Systems: A Programmer's Perspective》 (CSAPP，常见中文名《深入理解计算机系统》)**
    *   用程序员视角建立流水线、缓存、虚拟内存和链接等基础模型。其示例环境与具体硬件不是所有生产系统的通用规格。
*   **《Rust for Rustaceans》 (Jon Gjengset)**
    *   面向已经掌握所有权、借用和 trait 基础的进阶读者，讨论 API 设计、类型系统、异步与 unsafe 等主题；零基础读者可在完成 Rust 基础材料后阅读。

### 金融与算法交易
*   **《Algorithmic Trading & DMA》 (Barry Johnson)**
    *   提供 DMA（Direct Market Access，直接市场接入）、订单类型、执行算法和市场微结构的系统性背景。具体监管、场所规则和技术接入细节可能已经变化，需要与当前官方规则交叉核对。
*   **《Trading and Exchanges》 (Larry Harris)**
    *   用经济学视角解释流动性、交易者动机和价格形成，适合建立概念框架；它不是某个交易所当前撮合规则的实现规范。

## 2. 经典论文与博客

*   **[The LMAX Architecture](https://martinfowler.com/articles/lmax.html)** (Martin Fowler)
    *   介绍 LMAX 当时的事件处理与单线程业务逻辑设计，可作为系统案例研究，不应直接视为所有低延迟系统的模板。
*   **[Mechanical Sympathy](https://mechanical-sympathy.blogspot.com/)** (Martin Thompson)
    *   包含硬件亲和性、并发和内存顺序方面的工程文章。博客跨越多年，代码与性能结论要结合发布日期、目标 CPU 和当前语言内存模型复核。
*   **[Ulrich Drepper's "What Every Programmer Should Know About Memory"](https://people.freebsd.org/~lstewart/articles/cpumemory.pdf)**
    *   一篇有影响力的历史性内存系统长文，适合学习缓存与 NUMA 的分析视角。文中的硬件代际、延迟数字、Linux 机制和调优建议已有年代，不应概括为“原理都未改变”；请与处理器手册、内核文档和实测结果对照。

## 3. 官方规范：实现前必须回到一手资料

二手文章适合建立直觉，协议和交易规则却必须以目标场所的当前官方文档为准。下面不是“读完就通用”的规则，而是学习怎样阅读规范的入口：

* **[Nasdaq TotalView-ITCH 5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf)**
  * 观察逐订单行情如何用消息类型、订单引用号和时间戳表达事件。不要把其中字段直接套到其他交易所。
* **[CME Globex Matching Algorithm Overview](https://www.cmegroup.com/education/matching-algorithm-overview)**
  * 对比 FIFO（First In, First Out，同价先到先成交）、Pro-Rata 及其变体，理解“撮合算法不是所有市场都只有价格时间优先”。
* **[FIX Trading Community：FIX Standards](https://www.fixtrading.org/standards/)**
  * 从应用层语义、会话层、编码和 FIXP 等不同标准理解 FIX（Financial Information eXchange）不是单一报文格式。
* **[FIX Order State Changes](https://www.fixtrading.org/online-specification/order-state-changes/)**
  * 学习 `ExecType` 与 `OrdStatus` 的区别，以及成交、撤单、替换、拒绝等状态转换。
* **[SEC Trading Basics](https://www.sec.gov/file/trading101basicspdf)**
  * 用监管机构的投资者教育材料核对市价单和限价单的基本语义；实际可用订单类型仍以经纪商和场所规则为准。
* **[Rust Reference：Type Layout](https://doc.rust-lang.org/stable/reference/type-layout.html)**
  * 核对 `repr(Rust)`、`repr(C)`、对齐和 packed 的语言保证，避免把编译器当前行为当成稳定协议。

### 阅读一份交易所规范时记录什么

| 类别 | 要提取的信息 |
|---|---|
| 传输 | TCP/UDP、组播通道、会话、心跳、重传 |
| 帧与字段 | 长度、类型、字节序、精度、版本、保留值 |
| 顺序 | 序号作用域、日切重置、乱序/重复/缺口规则 |
| 状态 | 订单、交易阶段、熔断、恢复状态机 |
| 边界 | 最大消息、最大批次、非法输入、兼容策略 |
| 验证 | 官方样例、认证测试、回放数据、变更日志 |

## 4. 视频资源

*   **Carl Cook: "When a Microsecond Is an Eternity" (CppCon 2017)**
    *   一场以 C++ 低延迟实践为背景的演讲。适合观察问题分解方式，但其中工具链、硬件与公司架构背景不能直接等同于今天的 Rust 项目。
*   **Jon Gjengset's YouTube Channel**
    *   长篇 Rust 编程与源码阅读视频，覆盖 `Pin`、`Future` 和 unsafe 等主题。建议先选与当前章节对应的视频，并核对录制时使用的 Rust 版本。

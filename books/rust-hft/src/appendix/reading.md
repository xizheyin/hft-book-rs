# 参考教材、课程与官方规范

## 1. 计算机基础的覆盖依据

| 学科 | 范围基线 | 机制与例题参考 |
|---|---|---|
| 计算机组成原理 | [高校公开的 2025 年 408 考试大纲 PDF](https://www.uwh.edu.cn/uploads/article/20250609/660428d58334252302af691bf99e064e.pdf) | Patterson/Hennessy《Computer Organization and Design》、[CSAPP 官方课程资源](https://csapp.cs.cmu.edu/) |
| 操作系统 | 同一 408 大纲中的进程、内存、文件与 I/O 范围 | [Operating Systems: Three Easy Pieces（OSTEP）官方免费版](https://pages.cs.wisc.edu/~remzi/OSTEP/)、Silberschatz《Operating System Concepts》、Linux 内核文档与 man-pages |
| 数据结构与算法 | 同一 408 大纲中的线性表、树、图、查找与排序范围 | 严蔚敏《数据结构》、CLRS《Introduction to Algorithms》、[MIT 6.006](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/)、[Princeton Algorithms](https://algs4.cs.princeton.edu/home/) |
| 计算机网络 | 同一 408 大纲中的物理、链路、网络、传输与应用层范围 | Kurose/Ross《Computer Networking: A Top-Down Approach》及其[官方目录与资源](https://gaia.cs.umass.edu/kurose_ross/)、相关 IEEE 标准与 IETF RFC |

408 大纲用于检查“基础主干有没有缺块”，经典教材用于核对概念依赖、公式和推演，Linux/Rust/RFC/交易场所文档用于核对会随实现和版本变化的事实。正文均为重新组织的原创解释，不复刻教材段落。

## 2. 公开面经怎样参与选题

公开面经只能说明“某位候选人在某次面试中遇到了什么”，不能证明某个答案正确，也不能代表一家公司所有团队。编写时先从多份面经中提取反复出现的追问，再回到上表中的教材、标准和官方文档核对技术内容。

| 面经样本 | 反复出现的追问 | 本书怎样承接 |
|---|---|---|
| [LinkedIn Systems & Infrastructure](https://leetcode.com/discuss/post/2214902/linkedin-interview-experience-bangalore-rhxe5/)、[Aruba 系统软件工程师](https://leetcode.com/discuss/interview-experience/1874093/aruba-networks-an-hpe-company-system-software-engineer-2-banglore-selected/) | 进程线程、分页、同步、网络、图与项目深挖 | 操作系统和网络先讲完整机制；算法章要求复杂度、边界和测试 |
| [Rubrik System Coding](https://leetcode.com/discuss/post/6730864/swe-l4-interview-experience-at-rubrik-20-gxtp/) | 多线程、同步、任务依赖、饥饿与系统编码 | 同步、死锁、队列和图基础各自只维护一套定义，再在综合题组合 |
| [量化公司面经](https://www.nowcoder.com/discuss/473626483991281664)、[量化/HFT 技术面试经验](https://www.nowcoder.com/discuss/353155100422119424) | C++、操作系统、共享内存、网络与交易系统背景 | 共同基础放在 HFT 之前；交易章节只补市场、行情、订单和风控语义 |

这种做法避免两种偏差：只照考纲会缺少工程追问，只照面经又容易背到过时、偶然或错误的结论。

## 3. 系统编程与性能

*   **《Systems Performance: Enterprise and the Cloud》 (Brendan Gregg)**
    *   介绍从问题陈述、指标到工具验证的性能分析方法，并覆盖 `perf`、eBPF（Linux 内核的可观测与可编程机制）和火焰图等工具。命令和内核能力会随版本变化，实践时配合当前官方文档。
*   **《Computer Systems: A Programmer's Perspective》 (CSAPP，常见中文名《深入理解计算机系统》)**
    *   用程序员视角建立流水线、缓存、虚拟内存和链接等基础模型。其示例环境与具体硬件不是所有生产系统的通用规格。
*   **《Rust for Rustaceans》 (Jon Gjengset)**
    *   面向已经掌握所有权、借用和 trait 基础的进阶读者，讨论 API 设计、类型系统、异步与 unsafe 等主题；零基础读者可在完成 Rust 基础材料后阅读。

## 4. 数据库与分布式系统

| 资料 | 主要用途 |
|---|---|
| [CMU 15-445/645 Database Systems](https://15445.courses.cs.cmu.edu/spring2026/) 与《Database System Concepts》 | 关系模型、SQL、存储、索引、查询执行、并发控制与恢复的完整课程主线 |
| [PostgreSQL 并发控制](https://www.postgresql.org/docs/current/mvcc.html)与[WAL](https://www.postgresql.org/docs/current/wal-intro.html) | 核对一个真实数据库的隔离、MVCC 和恢复语义；正文会明确哪些是 PostgreSQL 实现选择 |
| [MIT 6.5840 Distributed Systems](https://pdos.csail.mit.edu/6.5840/) | 容错、复制、一致性和分布式系统案例的课程主线 |
| [Raft 原始论文](https://raft.github.io/raft.pdf) | 领导者选举、日志复制、提交规则与安全性 |
| 《Designing Data-Intensive Applications》 | 把复制、分片、事务、批处理和流处理放进工程场景；具体协议结论仍回到论文与产品文档 |

数据库和分布式系统尤其需要区分“抽象保证”与“某个产品的默认行为”。隔离级别、同步复制确认点、缓存一致性和故障切换都必须绑定实际数据库、协议、版本与部署配置。

## 5. 金融与算法交易
*   **《Algorithmic Trading & DMA》 (Barry Johnson)**
    *   提供 DMA（Direct Market Access，直接市场接入）、订单类型、执行算法和市场微结构的系统性背景。具体监管、场所规则和技术接入细节可能已经变化，需要与当前官方规则交叉核对。
*   **《Trading and Exchanges》 (Larry Harris)**
    *   用经济学视角解释流动性、交易者动机和价格形成，适合建立概念框架；它不是某个交易所当前撮合规则的实现规范。

## 6. 经典论文与博客

*   **[The LMAX Architecture](https://martinfowler.com/articles/lmax.html)** (Martin Fowler)
    *   介绍 LMAX 当时的事件处理与单线程业务逻辑设计，可作为系统案例研究，不应直接视为所有低延迟系统的模板。
*   **[Mechanical Sympathy](https://mechanical-sympathy.blogspot.com/)** (Martin Thompson)
    *   包含硬件亲和性、并发和内存顺序方面的工程文章。博客跨越多年，代码与性能结论要结合发布日期、目标 CPU 和当前语言内存模型复核。
*   **[Ulrich Drepper's "What Every Programmer Should Know About Memory"](https://people.freebsd.org/~lstewart/articles/cpumemory.pdf)**
    *   一篇有影响力的历史性内存系统长文，适合学习缓存与 NUMA 的分析视角。文中的硬件代际、延迟数字、Linux 机制和调优建议已有年代，不应概括为“原理都未改变”；请与处理器手册、内核文档和实测结果对照。

## 7. 官方规范：实现前必须回到一手资料

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

## 8. 视频资源

*   **Carl Cook: "When a Microsecond Is an Eternity" (CppCon 2017)**
    *   一场以 C++ 低延迟实践为背景的演讲。适合观察问题分解方式，但其中工具链、硬件与公司架构背景不能直接等同于今天的 Rust 项目。
*   **Jon Gjengset's YouTube Channel**
    *   长篇 Rust 编程与源码阅读视频，覆盖 `Pin`、`Future` 和 unsafe 等主题。建议先选与当前章节对应的视频，并核对录制时使用的 Rust 版本。

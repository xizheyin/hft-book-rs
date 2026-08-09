# 量化开发岗位考点矩阵

量化公司的“Software Engineer”并不都写交易策略。通用开发、核心交易系统、低延迟网络、Linux 基础设施和研究平台会共享编程与计算机基础，但深挖方向不同。公开校招信息也反复说明：多数通用软件岗位不要求入职前掌握金融知识；能否清楚编程、分析问题和学习，比背交易术语更重要。

## 1. 共同考点

| 能力 | 会怎样被考 | 本书主讲 |
|---|---|---|
| 现场编码 | 从需求写出正确代码，解释复杂度、边界和测试 | [算法与数据结构](../algorithms/index.html)、[C++](../cpp/index.html)、[Python](../python/core_engineering.html) |
| 语言与对象生命周期 | 值/引用、内存、容器、异常、并发和资源释放 | [现代 C++](../cpp/minimal_syntax.html)、[Rust](../introduction/rust_basics.html) |
| 计算机系统 | 指令、Cache、虚拟内存、进程、文件、I/O | [程序执行总览](../foundations/computer_execution.html)及其后续章节 |
| 并发 | mutex/condition variable、atomic、内存序、队列 | [C++ 线程同步](../cpp/threads_sync.html)、[并发基础](../foundations/concurrency.html)、[原子操作](../infrastructure/atomics.html) |
| 网络 | TCP/UDP、Socket、协议 framing、故障与背压 | [网络知识地图](../network/index.html) |
| 概率与统计 | 组合计数、条件概率、期望方差、简单随机过程直觉 | [概率、组合与统计](../algorithms/probability_statistics.html) |
| 调试与性能 | core、strace、perf、Sanitizer、可复现实验 | [Linux 排障](../optimization/linux_debugging.html)、[性能分析](../optimization/profiling.html) |
| 设计与可靠性 | 数据所有权、过载、失败恢复、测试和发布 | [数据库/分布式](../distributed/index.html)、[HFT 系统设计](system_design_interview.md) |

共同考点不表示每场面试逐项覆盖。它表示这些知识可以迁移到多数开发岗，缺一块会让候选人在不同轮次反复遇到盲区。

## 2. 四条开发轨道

### 2.1 通用 Software Engineer

这类岗位可能开发研究平台、数据服务、内部工具或交易系统的非极致关键路径。优先级通常是：

1. 一门主力语言能写可维护代码；
2. 数据结构、算法、复杂度和测试；
3. 操作系统、网络、数据库和分布式基础；
4. 能讨论项目中的设计选择、失败和个人贡献；
5. 概率/统计基础，尤其是明确写入岗位要求的公司。

不要因为公司做 HFT，就把所有编码题都强行写成无锁或 busy polling。开放式题更看重需求澄清、接口、正确性和代码演进。

### 2.2 Core / Low-Latency Engineer

在共同核心之上继续深挖：

- CPU pipeline、Cache、分支、内存布局和 NUMA；
- C++ 对象布局、分配、原子内存模型和 SPSC/MPMC 所有权；
- Linux 调度、中断、网络收发、Socket 与性能计数器；
- UDP 行情、TCP/FIX/二进制协议和连接恢复；
- 基准、profiling、可证伪优化与回滚；
- 岗位确实需要时再读 kernel bypass、FPGA 接口等专项。

“低延迟”不能替代正确性。现场回答仍先写不变量、生命周期和错误路径，再讨论是否值得减少分配、锁、系统调用或数据搬运。

### 2.3 Linux / Infrastructure Engineer

这一轨更关注服务和机器为什么能持续运行：

- 进程、线程、fd、pipe、signal、虚拟内存和文件系统；
- TCP/IP、DNS、路由、Socket、抓包与网络排障；
- 配置、日志、指标、trace、部署与权限；
- 容量、队列、背压、数据库、复制和故障恢复；
- GDB/core、strace、perf、`/proc` 与系统事件证据链。

它与低延迟轨共享 Linux，但目标不同：前者更强调可运营和跨层诊断，后者会进一步追问关键路径与硬件行为。

### 2.4 Market Connectivity / Trading Systems Engineer

这类开发把系统基础接到市场规则：

- 市场微观结构、订单类型与撮合优先级；
- 行情序号、A/B feed、gap、快照和订单簿；
- 订单状态机、ACK/Fill/Cancel 竞态和 Unknown 状态；
- 预交易风控、持仓、幂等、drop copy 与对账；
- 回放、模拟时钟、故障演练和发布门禁。

规则必须以目标交易场所和协议版本为准。本书提供通用机制与可推演案例，不把某一交易所字段当成全球标准。

## 3. 三种编码面试要分别准备

### 3.1 定型算法题

输入输出和目标明确。回答顺序是澄清边界、给暴力基线、选择数据结构、证明不变量、编码、测空/一/极值和复杂度。

### 3.2 开放式协作编码

题目可能先让实现一个小 API，再增加撤销、并发、缓存或测试要求。旧需求不应被悄悄破坏。重点是：

- 接口怎样容纳变化；
- 状态由谁拥有；
- 怎样保留简单正确基线；
- 新约束加入后哪些测试必须继续通过；
- 何时重构，而不是不断加特殊分支。

[追加盲测与协作编码](../algorithms/mock_exams_extra.html)包含需求逐轮变化和代码评审题。

### 3.3 系统组件题

例如有界队列、限流器、订单状态机或版本化 KV。代码之外还要说明并发语义、容量满、超时、关闭、持久化和测试。若题目没有要求无锁，先给可以证明的同步版本，再讨论为何以及如何优化。

## 4. 哪些内容不是通用开发硬门槛

- 期权定价、Greeks、随机微积分和 alpha 研究属于特定量化研究/策略轨道；
- 某家公司的内部语言可入职后学习，公开岗位通常更看重已有语言中的编程能力；
- DPDK、OpenOnload、FPGA 等只在相关低延迟/硬件岗位深入；
- 交易协议字段与场所规则按目标团队补充，不能代替计算机基础。

这不是删掉专业知识，而是防止通用 SWE 候选人把时间花在不会被该岗位考察的细枝末节。选择专项前先读职位责任和面试流程。

## 5. 掌握程度怎样验证

“看过”不等于能回答。对目标轨道，至少独立完成以下输出：

1. 在编辑器中实现并测试一个中等算法题，能应对一次需求变化；
2. 画出一个请求/行情/订单的数据流和状态机；
3. 从 crash、hang 或 slow 现象选对证据工具并形成可证伪假设；
4. 手算一题概率/期望和一题容量/带宽；
5. 对一段 C++ 并发代码指出所有权、等待谓词、关闭和竞态；
6. 设计一次故障恢复与测试计划，而不只画正常架构；
7. 对自己的项目说清目标、个人改动、失败、证据与取舍。

最后一项由个人项目决定，本书无法替你生成真实经历；前六项都能在正文、练习、模拟卷和完整题解中反复验证。

## 一手岗位依据

- [Jane Street Software Engineer](https://www.janestreet.com/join-jane-street/position/8140274002/)与[Low-Latency Engineer](https://www.janestreet.com/join-jane-street/position/6254435002/)：通用编程能力与低层系统专项的区别。
- [Hudson River Trading 2027 Graduate Software Engineer](https://www.hudsonrivertrading.com/hrt-job/software-engineer-c-or-python-2027-grads/)与[HRT 技术团队](https://www.hudsonrivertrading.com/work-at-hrt/)：C++/Python、OS、CPU 和网络方向。
- [Citadel Securities University Graduate Software Engineer](https://www.citadelsecurities.com/careers/details/software-engineer-university-graduate-us/)：编程、设计、分析与概率统计要求。
- [IMC Graduate Software Engineer](https://www.imc.com/in/careers/jobs/4818790101)：数据结构、算法和 C++/Java 等编程能力；公开职位说明不要求既有金融经验。
- [Optiver Graduate Software Engineer](https://www.optiver.com/join-us/jobs/technology/chicago/graduate-software-engineer-2027-start/)：计算机基础、代码质量和系统设计。
- [Jump Technology](https://www.jumptrading.com/technology)：从高性能语言、网络、存储到硬件的技术范围。

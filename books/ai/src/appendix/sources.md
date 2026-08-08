# 资料来源与核验说明

本书优先使用原始论文、标准规范、项目官方文档和模型官方技术报告。协议行为以对应版本的规范为准，软件行为以目标版本文档和实测为准，论文中的实验结果只适用于论文声明的数据、硬件与配置。

## 1. DeepSeek 模型与公开基础设施

| 一手资料 | 本书主要使用点 |
|---|---|
| [DeepSeek-V2 Technical Report](https://arxiv.org/abs/2405.04434) | MLA、DeepSeekMoE 的原理背景 |
| [DeepSeek-V3 Technical Report](https://arxiv.org/abs/2412.19437) | MoE、MLA、MTP、训练与系统协同 |
| [DeepSeek-R1 Technical Report](https://arxiv.org/abs/2501.12948) | cold start、强化学习、GRPO 与推理模型 |
| [DeepSeek-V3 官方仓库](https://github.com/deepseek-ai/DeepSeek-V3) | 模型配置、公开代码与报告链接 |
| [DeepSeek-R1 官方仓库](https://github.com/deepseek-ai/DeepSeek-R1) | R1 模型说明与评测设置 |
| [3FS 官方仓库](https://github.com/deepseek-ai/3fs) | AI 存储、强一致性、元数据与高带宽案例 |
| [DeepEP 官方仓库](https://github.com/deepseek-ai/DeepEP) | MoE 专家并行通信案例 |
| [EPLB 官方仓库](https://github.com/deepseek-ai/EPLB) | 专家并行负载均衡案例 |
| [FlashMLA 官方仓库](https://github.com/deepseek-ai/FlashMLA) | MLA 高性能 kernel 案例 |

公开项目只说明对应仓库和报告公开了这些技术，不能推出其他未公开系统采用相同架构。

## 2. LLM 与推理基础

| 一手资料 | 主题 |
|---|---|
| [Attention Is All You Need](https://arxiv.org/abs/1706.03762) | Transformer 与多头注意力 |
| [FlashAttention](https://arxiv.org/abs/2205.14135) | IO-aware exact attention |
| [vLLM / PagedAttention 论文](https://arxiv.org/abs/2309.06180) | KV Cache 分页与推理服务 |
| [vLLM 官方文档](https://docs.vllm.ai/) | continuous batching、服务与指标的工程参考 |
| [LoRA](https://arxiv.org/abs/2106.09685) | 参数高效微调 |
| [PPO](https://arxiv.org/abs/1707.06347) | 策略优化基础 |
| [DPO](https://arxiv.org/abs/2305.18290) | 直接偏好优化 |
| [PyTorch Automatic Mixed Precision](https://docs.pytorch.org/docs/stable/amp.html) | 混合精度、autocast 与梯度缩放的官方接口语义 |
| [PyTorch Distributed Overview](https://docs.pytorch.org/docs/stable/distributed.html) | 数据并行通信与分布式训练接口 |
| [PyTorch FSDP](https://docs.pytorch.org/docs/stable/fsdp.html) | 参数、梯度和优化器状态分片的工程参考 |
| [CUDA C++ Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/) | 内存带宽、数据搬运、kernel 与 GPU 性能测量 |
| [Mixed Precision Training](https://arxiv.org/abs/1710.03740) | 低精度计算与高精度累加/权重的训练方法 |
| [Knowledge Distillation](https://arxiv.org/abs/1503.02531) | 教师—学生能力迁移的经典方法 |

论文中的实验数字只在原设定下成立。本书主要提取机制与取舍，不把单个基准结果推广成普遍性能承诺。

## 3. Agent、工具与评测

| 一手资料 | 主题 |
|---|---|
| [ReAct](https://arxiv.org/abs/2210.03629) | 推理与行动交错的 Agent 范式 |
| [Toolformer](https://arxiv.org/abs/2302.04761) | 模型学习使用工具 |
| [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/) | MCP 的角色、消息与安全边界 |
| [JSON Schema Specification](https://json-schema.org/specification) | 工具参数与模型输出的结构约束 |
| [SWE-bench](https://www.swebench.com/) | 真实仓库软件工程任务评测案例 |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) | Coding Agent 接口与执行案例 |
| [AgentBench](https://arxiv.org/abs/2308.03688) | 多环境 Agent 评测案例 |
| [On Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599) | 预测置信度与真实正确率的校准 |
| [Dense Passage Retrieval](https://aclanthology.org/2020.emnlp-main.550/) | 稠密检索与双编码器召回 |
| [Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) | 检索结果参与生成的经典范式 |
| [HNSW](https://arxiv.org/abs/1603.09320) | 图式近似最近邻索引 |
| [Product Quantization](https://doi.org/10.1109/TPAMI.2010.57) | 向量压缩与近似距离计算 |
| [Faiss 官方索引说明](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes) | 精确、IVF、PQ 与组合索引的工程接口 |

Benchmark 分数依赖数据版本、模型、采样、Harness、工具、预算和评测器。比较时必须一起报告这些条件。

## 4. OS、沙箱、网络与存储

| 一手资料 | 主题 |
|---|---|
| [Linux cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html) | CPU、内存、I/O 等资源控制 |
| [Linux namespaces](https://www.kernel.org/doc/html/latest/admin-guide/namespaces/index.html) | 进程视图隔离 |
| [Linux seccomp](https://docs.kernel.org/userspace-api/seccomp_filter.html) | 系统调用过滤 |
| [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec) | 容器运行时接口 |
| [gVisor Architecture and Security](https://gvisor.dev/docs/architecture_guide/intro/) | 用户态内核与威胁模型案例 |
| [gVisor Production Guide](https://gvisor.dev/docs/user_guide/production/) | 生产负载兼容性与性能取舍 |
| [Firecracker 官方仓库](https://github.com/firecracker-microvm/firecracker) | microVM 与精简 VMM 案例 |
| [Linux KVM API](https://docs.kernel.org/virt/kvm/api.html) | VM/vCPU、`KVM_RUN`、中断与 dirty log 的官方接口语义 |
| [QEMU Device Emulation](https://www.qemu.org/docs/master/system/device-emulation.html) | 虚拟设备前后端、模拟与直通的公开实现参考 |
| [OASIS Virtio 1.3](https://docs.oasis-open.org/virtio/virtio/v1.3/virtio-v1.3.html) | virtqueue、通知与标准虚拟设备接口 |
| [CNI Specification](https://www.cni.dev/docs/spec/) | 容器/VM 网络接入接口 |
| [Linux block layer](https://docs.kernel.org/block/index.html) | 文件写入到底层设备的关键层次 |
| [Linux 内存管理概念](https://docs.kernel.org/admin-guide/mm/concepts.html) | 虚拟内存、页表、页缓存、匿名内存与回收 |
| [Linux Page Tables](https://docs.kernel.org/mm/page_tables.html) | 分层页表、MMU、TLB、缺页与大页 |
| [Linux Process Addresses](https://docs.kernel.org/mm/process_addrs.html) | VMA、进程地址空间与页表关系 |
| [Linux `fork(2)`](https://man7.org/linux/man-pages/man2/fork.2.html) | 进程创建、写时复制与继承语义 |
| [Linux `futex(2)`](https://man7.org/linux/man-pages/man2/futex.2.html) | 用户态同步与争用时内核等待/唤醒 |
| [Linux `epoll(7)`](https://man7.org/linux/man-pages/man7/epoll.7.html) | 文件描述符就绪通知语义 |
| [Linux `io_uring(7)`](https://man7.org/linux/man-pages/man7/io_uring.7.html) | 提交/完成队列式异步 I/O 接口 |
| [Rust 原子类型与内存序](https://doc.rust-lang.org/std/sync/atomic/) | Rust 原子操作和 ordering 的官方语义 |
| [Tokio Graceful Shutdown](https://tokio.rs/tokio/topics/shutdown) | 异步取消传播、任务等待与优雅关闭 |
| [gRPC Cancellation](https://grpc.io/docs/guides/cancellation/) | RPC 取消传播及应用自行停止工作的责任 |

gVisor、Firecracker、Kubernetes、CNI 等是典型技术案例，不代表任何未公开平台的实际选型。

## 5. 网络协议、文件系统与数据库

| 一手资料 | 主题 |
|---|---|
| [RFC 8200](https://www.rfc-editor.org/rfc/rfc8200.html) | IPv6 与 IP 层基本语义 |
| [RFC 826](https://www.rfc-editor.org/rfc/rfc826.html) | IPv4 地址到链路层地址的 ARP 解析 |
| [RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html) | TCP 连接、序号、可靠字节流与重传 |
| [RFC 5681](https://www.rfc-editor.org/rfc/rfc5681.html) | TCP 拥塞控制的基本算法 |
| [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034.html) / [RFC 1035](https://www.rfc-editor.org/rfc/rfc1035.html) | DNS 概念、名称解析与消息格式 |
| [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html) | TLS 1.3 握手、身份、机密性与完整性 |
| [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html) / [RFC 9113](https://www.rfc-editor.org/rfc/rfc9113.html) | HTTP/1.1 与 HTTP/2 |
| [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html) / [RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html) | QUIC 与 HTTP/3；用于说明 HTTPS 不只存在 TCP + TLS 路径 |
| [gRPC Core Concepts](https://grpc.io/docs/what-is-grpc/core-concepts/) | unary/streaming RPC、deadline 与 metadata |
| [Linux VFS](https://docs.kernel.org/filesystems/vfs.html) | inode、dentry、file object 与文件系统接口 |
| [Linux Pathname Lookup](https://docs.kernel.org/filesystems/path-lookup.html) | 路径组件解析与 dentry cache |
| [ext4 Journal](https://docs.kernel.org/filesystems/ext4/journal.html) | 文件系统 journal 与崩溃恢复 |
| [PostgreSQL WAL](https://www.postgresql.org/docs/current/wal-intro.html) | Write-Ahead Logging 与数据库恢复 |
| [PostgreSQL MVCC](https://www.postgresql.org/docs/current/mvcc-intro.html) | 多版本并发控制与事务隔离入口 |
| [RocksDB Wiki](https://github.com/facebook/rocksdb/wiki/RocksDB-Overview) | LSM-tree、memtable、SST 与 compaction 工程案例 |
| [The Log-Structured Merge-Tree](https://doi.org/10.1007/s002360050048) | LSM-tree 的原始设计 |

这里的 RFC 是协议规范，Linux/PostgreSQL/RocksDB 文档描述各自实现。书中会明确区分“协议必须如此”和“某个实现选择如此”，不会把一个实现细节推广成所有系统的共同保证。

## 6. 分布式系统、可观测性与 SRE

| 一手资料 | 主题 |
|---|---|
| [Raft](https://raft.github.io/raft.pdf) | 共识与复制日志 |
| [Dynamo](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf) | 可用性、最终一致与 quorum 取舍 |
| [Spanner](https://research.google/pubs/spanner-googles-globally-distributed-database/) | 全球分布式事务与时间 |
| [Google SRE Books](https://sre.google/books/) | SLO、过载、事故、发布与运维 |
| [Google SRE Workbook：Canarying Releases](https://sre.google/workbook/canarying-releases/) | 影子/灰度、指标门槛与渐进放量 |
| [OpenTelemetry Specifications](https://opentelemetry.io/docs/specs/) | trace、metric、log 与语义约定 |
| [OpenTelemetry GenAI Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) | 生成式 AI 遥测字段参考 |
| [Time, Clocks, and the Ordering of Events](https://lamport.azurewebsites.net/pubs/time-clocks.pdf) | happens-before 与逻辑时钟 |
| [Linearizability](https://cs.brown.edu/~mph/HerlihyW90/p463-herlihy.pdf) | 并发对象线性一致性的原始定义 |
| [CAP 形式化论文](https://groups.csail.mit.edu/tds/papers/Gilbert/Brewer2.pdf) | 分区下原子一致性与可用性的边界 |
| [Sagas](https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf) | 长事务拆分与补偿事务 |
| [Little's Law 原始证明](https://doi.org/10.1287/opre.9.3.383) | 平均在途量、到达率和停留时间的关系 |
| [Linux PSI](https://docs.kernel.org/accounting/psi.html) | CPU、内存与 I/O 压力造成的等待 |
| [`perf` 官方 Wiki](https://perfwiki.github.io/main/) | CPU profiling、采样与事件分析 |
| [HdrHistogram Coordinated Omission](https://github.com/HdrHistogram/HdrHistogram#the-coordinated-omission-problem) | 压测漏记等待时间的问题与校正思路 |

OpenTelemetry 的 GenAI/Agent 约定仍会演进，生产系统应固定自己采用的版本，并在业务层保留稳定 schema。

## 7. 安全与治理

| 一手资料 | 主题 |
|---|---|
| [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | 注入、工具滥用、Memory、预算与测试 |
| [OWASP Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) | Agent 威胁建模 |
| [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) | AI 风险治理框架 |
| [SLSA Specification](https://slsa.dev/spec/) | 软件供应链 provenance 与构建完整性 |

安全清单是起点，不是合规证明。具体系统还需根据资产、攻击者能力、地区与组织要求完成威胁建模和验证。

## 8. 公开面经怎样校准问题频率

匿名面经不能证明技术结论，也不能代表一家公司的固定流程；它只用于发现反复出现的追问。技术答案仍由本页的论文、规范和官方文档核对。

| 公开样本 | 反复出现的组合 | 本书对应内容 |
|---|---|---|
| [AI 平台研发面经](https://www.nowcoder.com/feed/main/detail/7fa8ae2f1c2e42909e664dce6cbc8190) | LLM 选择与后端、数据库、API 基础一起追问 | 模型基础与共享系统基础分开主讲，再在系统设计中组合 |
| [包含 AI 概念轮的软件工程面经](https://leetcode.com/discuss/post/7313117/intuit-interview-experience-for-swe-2-se-6t8a/) | RAG、system prompt、temperature、API 测试与生产指标 | 生成、检索、评测和可观测性各自解释机制与失败 |
| [RAG / Agent 项目追问经验](https://ac.nowcoder.com/discuss/1649000?type=0) | 业务目标、技术链路、效果评估、优化与故障 | 问题库要求从定义、过程、证据和边界回答，不只列框架名 |

## 9. 证据怎样支撑技术主张

使用下面的四级标签：

1. **标准或接口事实**：由版本明确的规范和官方文档直接支持。
2. **论文结论**：只在论文声明的数据、模型、硬件和实验设置内成立。
3. **工程推断**：根据机制提出的候选方案，例如 microVM、CNI、fencing；必须写明成立条件和验证方法。
4. **教学假设**：为容量计算构造的数字；不能冒充生产测量。

二手材料可以帮助定位原文，但不能替代规范、论文或项目文档。任何会变化的结论都要绑定版本或日期。

## 10. 本版基础知识的来源核验结果

来源要与主张类型匹配：协议语义以 RFC 为主；Linux 实现语义以对应内核文档和 Linux man-pages 为主；数据库实现以官方文档为主；算法与分布式概念回到原始论文；具体模型架构使用对应官方报告和仓库。

| 主张类别 | 主要证据 | 核验结果 | 仍需保留的限制 |
|---|---|---|---|
| 进程、虚拟内存、并发与 I/O | kernel.org、man7、Rust/Tokio 官方文档 | 机制与接口来源可追溯 | 内核版本、架构和配置会改变具体行为 |
| TCP、DNS、TLS、HTTP | IETF RFC | 规范层主张可追溯 | 实现、代理和部署拓扑仍可能不同 |
| 文件系统与数据库 | Linux、PostgreSQL、RocksDB 官方文档及原始论文 | 已区分通用思想与实现选择 | 持久化保证必须绑定文件系统、设备和数据库配置 |
| 时间、一致性、共识与排队 | Lamport、Linearizability、CAP、Raft、Little 等原始论文 | 定义与推理链可追溯 | 教学简化不替代生产协议证明 |
| 神经网络、GPU、量化与训练 | 原始论文、CUDA/PyTorch 官方文档、DeepSeek 官方报告 | 核心机制和公开案例可追溯 | 性能与质量数字不能跨硬件、模型和数据外推 |

核验覆盖来源存在性、标题/作者或官方归属、链接目标与所支撑主张是否相符；没有把无法确认的二手材料升级为事实。它不等于复现每篇论文的实验，也不等于在所有内核和 GPU 上执行了书中的每条命令。凡涉及性能、兼容性和故障恢复，正文仍要求在明确版本与 workload 下重新测量。

## 11. 编写与核验说明

本书由 AI 辅助完成资料检索、结构设计和初稿撰写。技术结论按本页及各章所列一手资料核验，目录、Markdown 结构与本地链接经过自动检查；书中的教学数字必须与真实生产测量区分，软件接口也应按实际使用版本再次核对。

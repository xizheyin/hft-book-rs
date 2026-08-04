# 资料来源与核验说明

本书把来源分为三类：DeepSeek 官方招聘与技术材料、论文/规范、工程项目官方文档。招聘状态和 API 行为会变化，书中凡使用“当前”“在招”等词，均绑定到明确核验日期。

## 1. DeepSeek 招聘来源

截至 **2026-08-04（Asia/Shanghai）**，本书通过以下官方链路核验岗位：

| 来源 | 用途 | 备注 |
|---|---|---|
| [DeepSeek 招聘官网](https://talent.deepseek.com/) | 当前岗位列表与完整 JD | 站点首页标注构建时间；动态页面会更新 |
| [Agent Infra 研发工程师 Moka 单岗页](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/bae809fb-1978-4401-b209-34067b26569d) | 主岗职责、要求、地点与类型 | Moka 为官方招聘页跳转目标 |
| [Agent Infra Moka 公共职位查询](https://api.mokahr.com/api-platform/v1/jobs/high-flyer?mode=social&keyword=Agent%20Infra&limit=30&siteId=140576) | 核验 open/时间等结构化元数据 | 字段可能随招聘系统变更 |
| [Agent Harness 团队](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/8d40c764-d2b2-49b1-826c-e3f2adb75c01) | 相邻岗明确列出的 Agent AI 知识 | 不能冒充主岗逐条要求 |
| [AI 搜索算法/架构工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/1df4597d-6039-4392-9954-0df72510f415) | 检索、RAG、成本/延迟/效果边界 | 属于相邻岗位证据 |
| [超算集群研发工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/cdccf456-207f-4ea0-9fdd-c30a5ce42d5b) | cgroup、namespace、Kubernetes、调度等相邻证据 | 不代表 DSec 必然采用同一技术栈 |

网上转载的早期 JD 只能作为线索；本书没有把无法在当前官方列表核验的内容写成当前硬要求。

## 2. DeepSeek 模型与公开基础设施

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

公开项目能证明某种技术存在于 DeepSeek 的开放技术生态，不能单独证明未公开的 DSec 内部架构。

## 3. LLM 与推理基础

| 一手资料 | 主题 |
|---|---|
| [Attention Is All You Need](https://arxiv.org/abs/1706.03762) | Transformer 与多头注意力 |
| [FlashAttention](https://arxiv.org/abs/2205.14135) | IO-aware exact attention |
| [vLLM / PagedAttention 论文](https://arxiv.org/abs/2309.06180) | KV Cache 分页与推理服务 |
| [vLLM 官方文档](https://docs.vllm.ai/) | continuous batching、服务与指标的工程参考 |
| [LoRA](https://arxiv.org/abs/2106.09685) | 参数高效微调 |
| [PPO](https://arxiv.org/abs/1707.06347) | 策略优化基础 |
| [DPO](https://arxiv.org/abs/2305.18290) | 直接偏好优化 |

论文中的实验数字只在原设定下成立。本书主要提取机制与取舍，不把单个基准结果推广成普遍性能承诺。

## 4. Agent、工具与评测

| 一手资料 | 主题 |
|---|---|
| [ReAct](https://arxiv.org/abs/2210.03629) | 推理与行动交错的 Agent 范式 |
| [Toolformer](https://arxiv.org/abs/2302.04761) | 模型学习使用工具 |
| [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/) | MCP 的角色、消息与安全边界 |
| [SWE-bench](https://www.swebench.com/) | 真实仓库软件工程任务评测案例 |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) | Coding Agent 接口与执行案例 |

Benchmark 分数依赖数据版本、模型、采样、Harness、工具、预算和评测器。比较时必须一起报告这些条件。

## 5. OS、沙箱、网络与存储

| 一手资料 | 主题 |
|---|---|
| [Linux cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html) | CPU、内存、I/O 等资源控制 |
| [Linux namespaces](https://www.kernel.org/doc/html/latest/admin-guide/namespaces/index.html) | 进程视图隔离 |
| [Linux seccomp](https://docs.kernel.org/userspace-api/seccomp_filter.html) | 系统调用过滤 |
| [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec) | 容器运行时接口 |
| [gVisor Architecture and Security](https://gvisor.dev/docs/architecture_guide/intro/) | 用户态内核与威胁模型案例 |
| [gVisor Production Guide](https://gvisor.dev/docs/user_guide/production/) | 生产负载兼容性与性能取舍 |
| [Firecracker 官方仓库](https://github.com/firecracker-microvm/firecracker) | microVM 与精简 VMM 案例 |
| [CNI Specification](https://www.cni.dev/docs/spec/) | 容器/VM 网络接入接口 |
| [Linux block layer](https://docs.kernel.org/block/index.html) | 文件写入到底层设备的关键层次 |

gVisor、Firecracker、Kubernetes、CNI 等是典型技术案例；除非 JD 原文明确出现，本书均把它们标为方案推断而非 DeepSeek 内部事实。

## 6. 分布式系统、可观测性与 SRE

| 一手资料 | 主题 |
|---|---|
| [Raft](https://raft.github.io/raft.pdf) | 共识与复制日志 |
| [Dynamo](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf) | 可用性、最终一致与 quorum 取舍 |
| [Spanner](https://research.google/pubs/spanner-googles-globally-distributed-database/) | 全球分布式事务与时间 |
| [Google SRE Books](https://sre.google/books/) | SLO、过载、事故、发布与运维 |
| [OpenTelemetry Specifications](https://opentelemetry.io/docs/specs/) | trace、metric、log 与语义约定 |
| [OpenTelemetry GenAI Attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) | 生成式 AI 遥测字段参考 |

OpenTelemetry 的 GenAI/Agent 约定仍会演进，生产系统应固定自己采用的版本，并在业务层保留稳定 schema。

## 7. 安全与治理

| 一手资料 | 主题 |
|---|---|
| [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | 注入、工具滥用、Memory、预算与测试 |
| [OWASP Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) | Agent 威胁建模 |
| [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) | AI 风险治理框架 |
| [SLSA Specification](https://slsa.dev/spec/) | 软件供应链 provenance 与构建完整性 |

安全清单是起点，不是合规证明。具体系统还需根据资产、攻击者能力、地区与组织要求完成威胁建模和验证。

## 8. 如何判断一句话能不能写进书

使用下面的四级标签：

1. **官方事实**：DeepSeek 当前 JD、论文或仓库直接写出。
2. **相邻岗位证据**：同一招聘站的其他岗位明确写出，说明值得准备，但不是主岗硬要求。
3. **工程推断**：从职责推导出的典型方案，例如 microVM、CNI、fencing；必须显式标“可能/可选”。
4. **教学假设**：为容量计算构造的数字；必须写明不是生产数据。

任何来源若只能从二手转载找到，就不能升级为“官方事实”。任何会变化的结论都要标日期或版本。

## 9. 编写与核验说明

本书由 AI 辅助完成资料检索、结构设计和初稿撰写。招聘事实与技术结论按本页所列一手资料核验，目录、Markdown 结构与本地链接经过自动检查；书中的伪代码和命令片段不是一套可执行实验课程。招聘信息、软件版本和行业实践仍会变化，请在面试前再次打开官方页面确认。

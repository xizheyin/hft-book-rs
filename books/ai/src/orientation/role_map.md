# 从招聘启事读懂岗位：DeepSeek Agent Infra 能力地图

想象一座只给 AI Agent 居住的“云上城市”。模型像居民的大脑，Agent 会写代码、运行程序、访问工具，甚至彼此协作；Agent Infra 则负责房屋、道路、水电、门禁、消防和城市调度。居民越自主，城市越不能靠“大家应该不会乱来”维持秩序：每个动作都要被隔离、计量、观察，并能在故障后恢复。

这正是理解岗位的第一把钥匙：**DeepSeek 当前的 Agent Infra 研发工程师首先是系统基础设施岗位，不是单纯调用大模型 API 的应用开发岗位。** 但它服务的是 Agent 执行、评测和模型迭代，因此还需要懂模型周围的 Harness 怎样使用这些基础设施。

本章只把招聘页明确公开的内容当作 DeepSeek 的事实。Kubernetes、Firecracker、eBPF 等业界常见技术会作为学习建议出现，但不会被写成 DeepSeek 内部实现。

## 1. 来源如何核验

截至 **2026-08-04**，来源链如下：

1. [DeepSeek 官方网站](https://www.deepseek.com/)直接链接到 [DeepSeek 招聘官网](https://talent.deepseek.com/)。
2. 招聘官网展示完整职位卡片，并跳转到公司使用的 Moka 招聘系统。
3. [Agent Infra 单岗页](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/bae809fb-1978-4401-b209-34067b26569d)和 [Moka 公共职位查询](https://api.mokahr.com/api-platform/v1/jobs/high-flyer?mode=social&keyword=Agent%20Infra&limit=30&siteId=140576)均能定位到同一个职位 ID。

核验时，Moka 记录为：

| 字段 | 结果 | 怎样理解 |
|---|---|---|
| 岗位 | Agent Infra 研发工程师 | 当前官方名称 |
| 状态 | `open` | 仍在开放投递 |
| 开始招聘 | 2026-06-25（北京时间） | 由 `openedAt` 换算；不等于团队成立时间 |
| 最近元数据更新 | 2026-08-03 10:14（北京时间） | 说明记录被刷新，不代表当天改过 JD 文案 |
| 地点 | 北京市海淀区、杭州市拱墅区 | 官方列出的两个地点 |
| 岗位类别 | JD 正文写“实习/全职” | Moka 结构化字段只显示“全职”，两者有差异时不擅自猜测招聘流程 |

招聘页面随时可能变化。准备投递时应再次打开官方页面确认，而不是把本书当作永久有效的招聘通知。

## 2. 主岗位明确写了什么

下面内容是对官方 JD 的忠实归纳，不是内部架构爆料。

### 2.1 平台定位

官方把 DSec 描述为面向 Agent 的云平台，托管成千上万个沙箱环境，用于推进下一代模型迭代。JD 明确把系统范围从操作系统、虚拟机、网络、存储，一直延伸到应用层调度和控制面服务。

这意味着面试官可能沿着一条请求向下追问：

```text
Agent 任务
  → 调度与控制面
  → 沙箱/容器/虚拟机
  → 虚拟网络与临时存储
  → Linux 内核和硬件
```

### 2.2 六类职责

JD 明确列出以下方向，候选人不一定全部负责，但应知道它们怎样连接：

1. **虚拟化环境**：托管大规模 VM 集群，支持不同操作系统配置和硬件方案。
2. **容器化**：加强隔离、缩小逃逸面、降低沙箱资源占用，并适应多样任务需求。
3. **临时存储**：为沙箱设计块设备和共享卷。
4. **虚拟化网络**：部署超大规模虚拟网络，让 Agent 在不越过物理边界的前提下通信。
5. **云服务**：设计混合云架构，开发可观测平台、日志和控制面。
6. **可观测性与高可用**：监控、节点自动上下线、应急响应和稳定运行。

JD 还特别指出，无监管自动运行的 Agent 会带来新的安全挑战，传统的负载模式、数据隔离、资源用量和平台安全假设可能不再成立。

### 2.3 基础能力与“五选一”

基础要求包括相关专业本科及以上、系统编程能力（倾向 Rust、C、Python）、可维护代码、底层好奇心、中文沟通与协作。

官方要求候选人在下列方向中至少有一项突出能力：

- 能讲清一次文件写入从调用到落盘的全过程及瓶颈。
- 深入理解大规模分布式系统和架构 trade-off。
- 会用压测与可观测工具定位跨层复杂问题。
- 理解可靠系统设计，并把事故教训固化为防复发机制。
- 有大型系统自动化运维或应急响应经验。

“满足任意一条”不代表其他内容完全不用学。它更像 T 型能力：一根竖线足够深，横向还能与相邻系统对话。

## 3. 三种证据等级：不要把推断讲成内幕

面试表达可采用下面的三级标签。

| 等级 | 可以说什么 | 例子 |
|---|---|---|
| A：主岗明确要求 | 可以直接说“JD 写明” | VM、容器隔离、临时块设备、虚拟网络、控制面、可观测性、HA、文件写入链路 |
| B：相邻官方岗位明确、对主岗合理相关 | 应说“相邻岗表明需要理解” | LLM API、KV Cache、Agent Loop、Tool Use、MCP、Memory、Multi-Agent、Agent RL、评测 |
| C：业界典型方案推断 | 只能说“我会把它作为候选方案比较” | KVM、Firecracker、Kata、gVisor、Kubernetes、eBPF、CNI、OVS、VXLAN、Cilium |

例如，正确说法是：

> JD 要求容器隔离和缩小逃逸面。我会比较 namespace/cgroup、系统调用过滤、用户态内核或轻量 VM 等方案，但公开信息不足以判断 DeepSeek 实际采用哪一种。

错误说法是：

> DeepSeek 的 DSec 一定基于 Kubernetes 和 Firecracker。

后一句把可能方案伪装成内部事实，会暴露证据意识薄弱。

## 4. 相邻官方岗位透露的 AI 边界

主岗没有逐项要求 Agent 算法名词，但 DeepSeek 同期的相邻官方岗位给出了清晰边界。

### 4.1 Agent Harness 团队

[Agent Harness 团队](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/8d40c764-d2b2-49b1-826c-e3f2adb75c01)用“Model + Harness = Agent”概括职责，并明确列出：

- LLM API、KV Cache、Agent Loop、Tool Use；
- Reasoning、Planning、Skills、MCP；
- Memory、Subagent、Multi-Agent；
- Prompt Engineering、Context Engineering、Harness Engineering；
- 上下文管理、长期记忆、自进化 Agent、超长程任务和评测。

这些不是 Agent Infra 主 JD 的逐项硬门槛，却解释了沙箱的上层使用者是谁。基础设施工程师至少要能听懂 Harness 团队的需求，例如“恢复一个长任务时要保留哪些状态”“工具调用怎样审计”“多 Agent 是否需要网络互通”。

### 4.2 Agent 后端、训练与数据

其他直接相关岗位包括：

- [服务端开发工程师（Agent 后端方向）](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/2eb2e75d-29f3-47b5-bb10-39f12547d398)：执行环境快照、接入 Agent 框架、稳定评测和 Agent 数据生产。
- [大模型训练/推理框架工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/43f8551a-4235-4d5e-a9a7-44386cd79795)：异步 RL、Agent RL、KV Cache 磁盘缓存和负载均衡。
- [Code Agent 数据工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/a4ad8628-286e-4395-ac3e-b8117ac695c6)：把真实代码、安全或科研场景变成可训练的 RL 环境，并设计奖励和评测任务。
- [后训练研究员](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/5d75f4cd-f626-4f73-80c1-e53b2073de76)：RLHF、RLVR、PPO、GRPO、数据合成与 Agent 评测。
- [AI 搜索算法/架构工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/1df4597d-6039-4392-9954-0df72510f415)：查询理解、召回、排序、索引、RAG 与 Agent 检索工具。
- [高性能分布式存储工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/a7355097-fd57-4219-99a5-8963745d362f)：KV Cache 存储、分布式一致性、RDMA、`io_uring`、SPDK 和 Linux I/O。

因此，本书会讲 Agent 的 AI 机制，但始终标明：**这是为了理解上下游和应对系统设计追问，不等于主岗已经变成算法研究岗。**

## 5. 一个带数字的系统题

假设平台同时运行 10,000 个沙箱，每个沙箱平均占用 0.4 个 CPU 核、1.5 GiB 内存、2 GiB 临时盘；峰值到达率为每秒 200 个任务，平均运行 50 秒。

先做三个粗算：

1. Little 定律给出的平均并发约为 `200 × 50 = 10,000`，与题设一致。
2. 平均资源需求约为 4,000 核 CPU、15 TiB 内存、20 TiB 临时盘。
3. 若冷启动需要 8 秒，仅启动等待就占平均任务时长的 `8 / 50 = 16%`。

这还不是容量结论，因为平均数会隐藏长尾。继续追问至少包括：

- 任务时长和内存是否呈重尾分布？
- 共享卷是吞吐瓶颈还是元数据瓶颈？
- 同一租户能否瞬间提交 5,000 个任务？
- 沙箱失败后重试会不会形成重试风暴？
- 允许外网访问时，如何控制数据泄露和扫描行为？

面试官想看的通常不是心算速度，而是你会先写假设、再估算、最后指出平均值的局限。

## 6. 失败路径：城市会怎样失火

一个 Agent 沙箱平台至少要面对以下失败链：

```text
节点磁盘变慢
  → checkpoint 延迟上升
  → 任务超时并同时重试
  → 调度队列激增
  → 新节点被快速拉起
  → 镜像仓库和网络进一步过载
```

只修“磁盘慢”不够。完整方案还应包含限速与带抖动退避、重试预算、熔断、队列背压、分层告警、故障域隔离和恢复演练。安全侧也不能只防恶意用户：模型可能因为误解指令而重复删除文件、无限生成进程或访问不应访问的服务。

## 7. DeepSeek Agent Infra 面试怎么问

### 典型问题

> 这个岗位明明叫 Agent Infra，为什么既要学 Linux，又要懂 Agent Loop？

### 30 秒答法

> 主岗直接负责的是 Agent 的安全执行底座，包括 VM、容器隔离、网络、存储、调度、控制面和可靠性，所以 Linux 与分布式系统是核心。Agent Loop、工具、记忆和多 Agent 是相邻 Harness 岗明确要求的上层机制。理解它们能帮助我设计正确的快照、权限、审计和恢复语义，但我不会把这些相邻要求说成主 JD 的算法硬门槛，也不会猜测 DeepSeek 未公开的内部技术栈。

### 常见追问

- 一次 `write()` 到落盘经过哪些层？页缓存、文件系统、块层和设备缓存分别可能怎样失败？
- 容器与 VM 的隔离边界有什么差别？面对不可信代码如何取舍冷启动、密度与安全？
- 10,000 个沙箱如何调度？公平性、优先级、抢占和拓扑感知怎样冲突？
- Agent 重试工具调用时，怎样避免重复付款或重复写数据？
- 你引用某项技术时，证据来自主 JD、相邻 JD，还是业界经验？

## 8. 本章速记

- Agent Infra 是 Agent 的“云上城市”，主线是系统而不是只接模型 API。
- 官方主岗明确覆盖 VM、容器、临时存储、虚拟网络、混合云、控制面、可观测性与 HA。
- 文件写入全链路、分布式 trade-off、跨层诊断、可靠性、自动化运维是官方“五选一”。
- Harness JD 明确列出完整 Agent AI 知识，但对主岗属于相邻边界。
- 面试表达要区分：主岗事实、相邻岗事实、典型方案推断。
- 公开信息没有说明 DSec 的具体开源组件，不要把 Kubernetes、Firecracker 等说成内部事实。

## 9. 一手资料

- [DeepSeek 官方招聘](https://talent.deepseek.com/)
- [Agent Infra 研发工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/bae809fb-1978-4401-b209-34067b26569d)
- [Agent Harness 团队](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/8d40c764-d2b2-49b1-826c-e3f2adb75c01)
- [服务端开发工程师（含 Agent 后端）](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/2eb2e75d-29f3-47b5-bb10-39f12547d398)
- [大模型训练/推理框架工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/43f8551a-4235-4d5e-a9a7-44386cd79795)
- [Code Agent 数据工程师](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/a4ad8628-286e-4395-ac3e-b8117ac695c6)

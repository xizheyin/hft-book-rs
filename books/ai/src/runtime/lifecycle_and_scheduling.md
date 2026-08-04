# 沙箱生命周期与调度：把“一次运行”做成可恢复状态机

> 难度：必会。官方职责包含大规模 VM 集群、应用层调度、节点自动上下线和稳定运行。

调度器不是“找一台 CPU 还空着的机器”。它像机场塔台：要检查机型与跑道是否兼容，安排时隙，处理取消与迫降，还要防止某家航空公司占满所有资源。

## 1. 先定义生命周期

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Admitted: 配额与策略通过
    Pending --> Rejected: 超预算或无权限
    Admitted --> Assigned: 调度并签发租约
    Assigned --> Starting: 节点拉取/恢复环境
    Starting --> Running: 健康检查通过
    Running --> Succeeded: 结果提交
    Running --> Failed: 执行失败
    Running --> Lost: 节点失联/租约失效
    Assigned --> Lost: 租约失效
    Starting --> Lost: 节点失联
    Lost --> Admitted: 满足安全重试条件
    Pending --> Cancelling: 用户取消
    Admitted --> Cancelling: 用户取消
    Assigned --> Cancelling: 用户取消
    Starting --> Cancelling: 用户取消
    Running --> Cancelling: 用户取消/预算耗尽
    Lost --> Cancelling: 用户取消
    Succeeded --> Cleaning
    Failed --> Cleaning
    Cancelling --> Cleaning
    Cleaning --> [*]
```

每次状态转移都要有：唯一 run ID、期望状态、实际状态、幂等操作、超时、审计事件和负责人。控制面可以重复下发“清理”，节点执行两次也不应误删其他 run 的卷。

## 2. 请求值、上限值与实际用量

- request 是调度器预留资源时相信的估计。
- limit 是运行时强制的安全上限。
- usage 是观测到的真实消耗。

只看 request 会被低报资源的任务挤爆；只按 limit 装箱会浪费大量资源；只看历史平均值又会忽略长尾。实用方案会为不同 workload class 建模，并持续比较 request/usage 偏差。

## 3. 一个容量算例

有 100 台节点，每台可分配 64 vCPU 和 256 GiB。预留 10% 给系统后，总预算约为：

```text
CPU = 100 × 64 × 0.9 = 5,760 vCPU
内存 = 100 × 256 × 0.9 = 23,040 GiB
```

若平均运行沙箱申请 2 vCPU、4 GiB，只按总量可容纳 `min(5760/2, 23040/4) = 2880` 个。但这仍忽略每节点碎片、镜像盘、网络、启动并发、NUMA、GPU、故障域和 oversubscription 风险。

当到达率为每秒 400 个任务、平均服务时间 30 秒，理论在运行数约 `400 × 30 = 12,000`。这已经远超 2,880 个名义槽位，系统必须排队、扩容、降级或拒绝；“让队列无限长”只会把失败变成超时。

## 4. 调度决策分成过滤与打分

先过滤不能运行的节点：

- CPU、内存、磁盘、设备和运行时是否满足；
- OS、架构、内核能力或镜像是否兼容；
- 安全等级、租户与专用节点策略是否允许；
- 节点是否健康、是否正在下线；
- 数据位置、区域和合规边界是否允许。

再对候选节点打分：资源碎片、镜像命中、数据局部性、拓扑分散、启动队列、能耗和成本。打分函数不能只在模拟器上漂亮，还要能解释为何某次任务被放到某节点。

## 5. 公平、优先级与背压

多租户平台至少需要：每租户并发配额、队列配额、加权公平、优先级和全局准入控制。高优先级不应等于可以无限抢占；抢占会浪费已完成工作并形成重启风暴。

背压信号应从节点逐层返回：节点启动槽位已满，调度器减少派发，队列限制接收，API 给出明确的排队或拒绝响应。隐藏过载只会让各层独立重试。

## 6. 租约、心跳与脑裂

控制面给节点的不是永久所有权，而是带 epoch 的租约。节点只有在租约有效且 epoch 匹配时才能提交结果或续写卷。

如果控制面因网络分区认定节点失联并重新调度，旧节点可能仍在运行。此时 fence token 能让存储或结果服务拒绝旧 epoch 的写入，避免两个实例同时成为“当前任务”。

## 7. 节点安全上下线

上线不是进程启动就接流量：要验证运行时版本、内核配置、时钟、磁盘健康、网络连通、镜像签名与最小自检。下线也不是直接断电：先停止新分配，等待或迁移任务，清理秘密和临时卷，最后从服务发现移除。

自动化需要失败上限。若新版本节点连续出现同类启动失败，控制器应停止扩大故障，而不是忠实地把整个集群升级坏。

## 8. 典型失败路径

心跳超时被设为 5 秒，存储偶发长尾让大批节点同时错过心跳。控制面把任务全部重排，新旧实例并存并争抢共享卷，启动流量又击穿镜像仓库。

改进包括：心跳与业务 I/O 隔离；基于多信号判定节点；带抖动的分批恢复；全局重排速率上限；租约与 fencing；镜像预热；先验证小比例节点再扩大动作。

## 9. DeepSeek Agent Infra 面试怎么问

**题目：设计一个支持成千上万沙箱的调度器。**

**30 秒答法：**我会把 run 建成持久状态机，API 先做身份、配额和预算准入；调度先按 OS、架构、运行时、安全等级、资源和故障域过滤，再按碎片、镜像/数据局部性、负载和公平性打分。节点通过带 epoch 的租约获得执行权，心跳丢失后用 fencing 防止旧实例写入。控制面需要有界队列、分层背压、每租户公平、自动上下线和恢复速率限制；最后用排队时间、启动延迟、利用率、失败率和重调度风暴指标验证。

常见追问：

1. request 经常不准时怎样避免过度预留或节点 OOM？
2. 何时值得抢占？被抢占任务从哪里恢复？
3. 控制面宕机时，已运行沙箱继续还是停止？
4. 怎样防止热点镜像、热点租户和热点故障域？

## 10. 本章速记

- 先有持久状态机，后有调度算法。
- request 用于规划，limit 用于强制，usage 用于校准。
- 过滤保证可行，打分优化目标；决策应可解释。
- 租约解决暂时所有权，fencing 阻止旧主人继续写。
- 队列必须有界，恢复和自动化也必须限速。

## 一手资料

- [Kubernetes Scheduling, Preemption and Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/)
- [Kubernetes Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [The Datacenter as a Computer（Google 公开专著）](https://research.google/pubs/the-datacenter-as-a-computer-an-introduction-to-the-design-of-warehouse-scale-machines-second-edition/)

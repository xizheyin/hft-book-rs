# 并发模型选择 (Async vs Thread vs Actor)

在很多 Web 项目中，Rust 并发首先让人想到 `async/await`。但在高频交易 (HFT) 中，我们有不同的优先级：**确定性 (Determinism)** 和 **低延迟 (Low Latency)**。吞吐量 (Throughput) 也很重要，但它必须建立在不牺牲尾部延迟 (P99) 的基础上。

本章将深入操作系统的调度原理，剖析不同并发模型的底层开销，并解释为什么 HFT 系统往往选择看似原始的 "Thread per Core" 模型。

## 1. 理论背景：操作系统调度的代价

要理解并发模型的选择，首先必须理解操作系统内核在做什么。

### 1.1 上下文切换 (Context Switch) 的解剖
上下文切换没有一个放之四海而皆准的“固定微秒数”。同进程线程切换、跨进程切换、是否命中缓存、是否启用 PCID、机器是否过载，结果都不同。HFT 更在意的往往不是保存寄存器本身，而是**线程排队多久才重新获得 CPU，以及回来后工作集是否还在缓存中**。

一次切换可能涉及：

1. **进入内核并保存执行现场**：保存必要寄存器与线程状态；
2. **调度决策**：调度器从可运行任务中选择下一个；具体数据结构会随内核版本变化，不应把某个实现细节当成永久事实；
3. **地址空间处理**：跨进程时可能切换页表。现代 CPU 的 PCID 等机制可保留部分 TLB 项；**TLB shootdown 是页表映射变更时通知其他核心失效，并非每次上下文切换都发生**；
4. **微架构状态受扰**：新任务会竞争前端、执行单元、分支预测器和缓存，原任务恢复时可能遭遇更多 miss。

> **工程原则**：尽量减少关键线程的非自愿切换，并用 `perf sched`、调度 trace 和延迟直方图验证。Core pinning 降低迁移概率，但它本身不等于“操作系统再也不会打断”。

### 1.2 忙轮询 (Busy Polling) vs 系统通知 (Epoll/Kqueue)

| 策略 | 优点 | 代价 | 适合场景 |
| :--- | :--- | :--- | :--- |
| `epoll`/park 等通知 | 空闲时让出 CPU，连接数扩展性好 | 唤醒和重新调度增加尾延迟 | 网关、控制面、低消息率连接 |
| 忙轮询 | 数据一旦可见即可继续处理，避免 park/wakeup | 占满核心、功耗与热量高，还可能挤压同机任务 | 有独占核心、等待很短的关键数据面 |
| 自适应等待 | 先短暂自旋，超时后 park | 参数需要按负载调优 | 消息率会明显变化的系统 |

唤醒或轮询的实际延迟取决于内核、网卡路径、CPU 电源状态与负载，不能写死为某个纳秒/微秒数字。忙轮询也只消除了“睡眠再唤醒”这一段，并没有消除网络栈、缓存 miss 或排队。

## 2. 核心实现：HFT 的并发架构

### 2.1 为什么核心路径常不用 Async/Await?
Rust 的 `async/await` 基于状态机 (State Machine) 和协作式调度 (Cooperative Scheduling)。虽然它比 OS 线程轻量，但在 HFT 中仍有隐患：

1. **调度可控性较弱**：多线程 runtime 可以在两次 `poll` 之间迁移任务；单次 `poll` 不会被 Tokio 从任意指令处强行抢占，但长时间不 `.await` 会阻塞同一 worker 的其他任务；
2. **状态机大小需关注**：跨越 `.await` 的局部变量会进入 Future。大缓冲区或层层组合会增大 task 工作集；
3. **生态层开销**：语言并不强制每个 Future 分配，但 `spawn` 的 task、装箱、共享所有权和调度队列可能引入分配、原子操作与队列流量；
4. **公平性与尾延迟**：通用 runtime 要服务许多任务，其公平性目标不一定等于某条订单路径的截止时间目标。

**结论**：Async 常适合网关、控制面和大量并发 I/O；thread-per-core 常适合有专用核心、状态单写者且尾延迟优先的数据面。这是延迟预算下的工程选择，不是“Async 天生慢”。单线程 runtime 能避免 task 跨 worker 迁移，却仍有协作式调度和任务互相拖延的问题。

### 2.2 线程绑定 (Core Pinning / Affinity)

一种常见模型是 **Thread per Core**：把每个关键线程限制在指定 CPU 上，使其状态长期由同一个核心处理。注意 affinity 只是限制“允许在哪些 CPU 运行”，不会自动独占核心；SMT sibling、IRQ、内核线程和定时器仍可能造成干扰。

#### 实现代码 (使用 `core_affinity` 库)

下面是 thread-per-core 的 **架构骨架**：它依赖第三方 `core_affinity` crate，并把 `receive_packet`、`process` 留给具体行情接入实现。由于还涉及核心数量和持续运行的忙轮询，mdBook 不执行该片段。

```rust,ignore
use std::thread;
use core_affinity;

fn main() {
    let core_ids = core_affinity::get_core_ids().unwrap();

    // 假设核心 2 用于接收行情
    let market_data_core = core_ids[2];
    
    let handle = thread::spawn(move || {
        // 1. 绑定当前线程到指定核心
        if !core_affinity::set_for_current(market_data_core) {
            eprintln!("Failed to pin thread to core!");
        }
        
        // 2. 若业务确实需要，再单独评估实时调度策略。
        // SCHED_FIFO 需要相应权限，并可能饿死系统线程，不能只凭“更快”就开启。
        
        // 3. 忙轮询循环
        loop {
            if let Some(packet) = receive_packet() {
                process(packet);
            } else {
                // 给处理器“正在自旋”的提示；它不是内存屏障，也不会让出线程。
                std::hint::spin_loop();
            }
        }
    });

    handle.join().unwrap();
}
```

### 2.3 隔离核心 (Isolcpus)
仅仅在代码里绑定是不够的。操作系统仍然可能在这个核心上调度一些杂务（如 SSH 守护进程、cron 任务、RCU 回调）。

`isolcpus=2-5` 只能解决隔离问题的一部分，不能让内核“完全忽略”这些 CPU。完整方案通常还要规划：

- 用 cgroup v2 的 isolated cpuset 或相应 scheduler-domain 隔离放置任务；
- 用 `nohz_full` 尽可能停止调度 tick，并把 RCU 回调交给 housekeeping CPU；
- 设置 IRQ/managed IRQ affinity，避免中断落在关键核心；
- 检查 watchdog、workqueue、内核线程与 SMT sibling；
- 至少保留 housekeeping CPU 处理系统杂务。

这些选项依赖内核版本与部署环境，不能复制一串启动参数就宣称完成。应以 [Linux CPU Isolation 官方文档](https://docs.kernel.org/admin-guide/cpu-isolation.html) 为准，并用 trace 验证关键 CPU 上实际发生了什么。

### 2.4 NUMA 架构感知 (NUMA Awareness)

现代高性能服务器通常是双路（Dual Socket）甚至四路的。这就引入了 **NUMA (Non-Uniform Memory Access)** 问题。

- **Local Access**：访问当前 NUMA 节点连接的内存，通常更快；
- **Remote Access**：经 socket 间互连访问另一个节点，通常延迟更高且会消耗互连带宽。

具体差异取决于 CPU 拓扑、内存频率和负载，不应背固定数字。目标是让关键线程、热内存与 NIC 的 PCIe locality 尽量处在同一 NUMA 节点。

在 Rust 中，这通常意味着：
1. **线程绑定**：确保线程固定在某个 NUMA 节点的核心上；
2. **内存放置**：Linux 常按 first-touch 放置物理页；关键是哪个 CPU 第一次触碰并造成缺页，单纯在哪个线程调用 `malloc` 并不总能决定物理页位置；
3. **预触页与验证**：在线程绑定后初始化大块内存，并通过 NUMA 工具/计数器确认 local 与 remote 访问；必要时使用显式 NUMA policy。

下面是用于表达“先查拓扑、再决定放置”的 **伪代码骨架**。它依赖具体版本的 `hwloc` 绑定，类型名和返回值还会随 crate API 变化，不能作为独立 Rust 程序执行。

```rust,ignore
// 伪代码骨架：检查 NUMA 拓扑
let topology = hwloc::Topology::new();
let core = topology.objects_with_type(ObjectType::Core)[0];
// 确保网卡、CPU 核心、内存都在同一个 NUMA 节点！
```

### 2.5 Actor 不是第四种线程，而是一种所有权模型

Actor 的核心是：每份可变状态只由一个 actor 拥有，其他组件通过消息请求它做事。它与执行方式是两个维度：

- actor 可以运行在 Tokio task 上，得到 async actor；
- actor 也可以固定在独占线程上，得到 thread-per-core actor；
- 一个核心还可按 symbol/account 分片持有多个逻辑 actor，但要避免不可控 mailbox 排队。

HFT 常用的“行情线程 → 策略线程 → 下单线程”其实已经具有 actor 风格：单写者状态、SPSC 消息传递、明确交接所有权。Actor 的好处是减少共享锁；代价是消息排队、序列化/拷贝、邮箱满时的背压策略，以及跨 actor 事务更难表达。

| 问题特征 | 更自然的起点 |
| :--- | :--- |
| 海量连接、等待 I/O 为主 | Async runtime |
| 固定流水线、专用核心、极低尾延迟 | Thread-per-core + SPSC |
| 状态需要单写者隔离、命令式交互 | Actor 所有权模型（再选择 async 或线程承载） |
| 大块 CPU 计算、可拆分任务 | 有界 worker pool / 数据并行 |

## 3. 性能分析：跨核通信 (Cross-Core Communication)

即便每个线程独占核心，它们之间仍需通信（如行情线程 -> 策略线程 -> 下单线程）。跨核通信的延迟由 CPU 的互连架构（如 Intel Mesh 或 AMD Infinity Fabric）决定。

### 3.1 缓存一致性协议 (MESI) 的影响
当核心 A 写入一条缓存行、核心 B 随后读取它时，一致性协议必须转移或共享该缓存行的有效副本。具体路径可能经过目录、共享缓存或 cache-to-cache transfer，取决于微架构，不能把某个 MESI 教科书步骤当作所有 CPU 的实际数据通路。

端到端消息延迟还包含生产者发布、消费者多久轮询到、屏障、队列代码和缓存命中情况。因此不存在一个统一的“40–100ns 物理极限”；应在目标 CPU、目标核距和目标负载上测量。更重要的设计原则是**每条缓存行尽量只有一个高频写者**。

### 3.2 内存屏障 (Memory Barriers)
为了给跨线程发布建立可证明的 happens-before，需要原子操作与合适的 `Ordering`。Ordering 同时约束编译器和目标硬件，并不总是一条单独的“屏障指令”。

- `Relaxed`: 只保证当前原子操作的原子性，不发布旁边的数据。
- `Release` / `Acquire`: 典型的生产者-消费者同步。
- `SeqCst`: 在 Acq/Rel 基础上，为所有 SeqCst 操作增加全局一致顺序；具体额外成本取决于操作和架构。

```rust
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;

fn main() {
    // 用两个原子变量模拟一个槽位和“槽位已发布”的 head 游标。
    let slot = Arc::new(AtomicU64::new(0));
    let head = Arc::new(AtomicU64::new(0));

    let producer_slot = Arc::clone(&slot);
    let producer_head = Arc::clone(&head);
    let producer = thread::spawn(move || {
        producer_slot.store(42, Ordering::Relaxed); // 先写 payload
        producer_head.store(1, Ordering::Release);  // 再发布游标
    });

    let consumer_slot = Arc::clone(&slot);
    let consumer_head = Arc::clone(&head);
    let consumer = thread::spawn(move || {
        while consumer_head.load(Ordering::Acquire) == 0 {
            std::hint::spin_loop();
        }
        // Acquire 读到了 Release 发布的 1，因此能看到此前写入的 payload。
        consumer_slot.load(Ordering::Relaxed)
    });

    producer.join().unwrap();
    assert_eq!(consumer.join().unwrap(), 42);
}
```

只有当 Acquire load 实际读到相应 Release 发布的值时，两边才“接上”。x86 上原子 load/store 的 Acquire/Release 常与 Relaxed 生成相同指令，但源码语义仍不可省；原子 RMW、SeqCst store、ARM 以及争用场景的代价又不同。完整推导见 [原子操作与内存顺序](../infrastructure/atomics.md)。

## 4. 常见陷阱 (Pitfalls)

1.  **超线程 (Hyper-Threading)**:
    Intel 的超线程技术让一个物理核心模拟两个逻辑核心。它们共享 L1/L2 Cache 和执行单元。
    关键线程通常不与繁忙任务共用 SMT sibling；是否全局关闭 SMT 要依据容量需求、安全策略和实测结果，而不是绝对口号。

2.  **中断风暴 (IRQ Storm)**:
    网卡中断如果打在你的关键核心上，会强制打断你的线程。
    **解决**: 配置 `/proc/irq/N/smp_affinity`，将网卡中断绑定到专门的 IO 核心，或者使用 DPDK 的轮询模式驱动 (PMD) 完全接管网卡，屏蔽中断。

3.  **False Sharing (伪共享)**:
    并发队列的头尾指针若位于同一缓存行，两个写者会让整行来回迁移。用带对齐的包装类型隔离热字段，并在目标机器验证布局；`align(128)` 不是所有硬件上的魔法常量。

4. **实时优先级失控**：
    `SCHED_FIFO` 线程若不阻塞且没有预算，可能饿死监控、网络或系统维护线程。实时策略需要明确优先级层次、housekeeping CPU、watchdog 与故障降级。

## 5. 面试快问快答

### Q1：线程绑定后，为什么还会出现延迟尖刺？

Affinity 不会驱逐 SMT sibling，也不会自动迁走 IRQ、RCU、内核线程和定时器；此外还有 page fault、缓存/TLB miss、NUMA 远端访问和电源状态变化。要用 trace 找出尖刺时 CPU 实际执行了什么。

### Q2：Actor、线程和 Async 的关系是什么？

Actor 描述状态所有权与消息交互；线程/Async 描述 actor 如何被执行。一个 actor 可以独占线程，也可以是 runtime 上的 task。面试中应先讲所有权拓扑，再讲调度载体。

### Q3：忙轮询一定比 `epoll` 快吗？

在有独占核心且事件即将到来时，它通常省去 park/wakeup；长期空闲、CPU 降频、同机争用或完整 I/O 路径不同，都可能改变结果。更完整的答案还要包含 CPU 预算和自适应退避。

### Q4：为什么 thread-per-core 常与 SPSC 一起出现？

每个阶段单写自己的状态，相邻阶段用一对一队列交接消息，可以避免共享锁和多生产者 CAS 热点，也让缓存行的写者关系更清晰。

## 6. 本章小结

- 优化目标应是尾延迟分布和可控调度，而不是“线程数量越少越好”；
- affinity、CPU isolation、IRQ、SMT、NUMA 和内存预触页需要作为一个整体设计；
- Actor 是所有权模型，可由 thread-per-core 或 async runtime 承载；
- 所有硬件纳秒数都应在目标拓扑实测，避免把经验值包装成定律。

## 7. 延伸阅读

- [The Linux Scheduler: a Decade of Wasted Cores](https://www.ece.ubc.ca/~sasha/papers/eurosys16-final29.pdf) - 深入了解调度器的问题。
- [Intel 64 and IA-32 Architectures Optimization Reference Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) - 权威的硬件优化指南。
- [rigtorp/MPMCQueue](https://github.com/rigtorp/MPMCQueue) - C++ 实现的极致性能队列，Rust 实现可参考其原理。

---
延伸阅读：进入基础设施部分，继续学习 HFT 系统的事件通道 —— [无锁数据结构与 Ring Buffer](../infrastructure/ring_buffer.md)。

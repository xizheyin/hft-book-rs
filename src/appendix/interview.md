# HFT 随手记：核心法则与优化经验

> "Talk is cheap. Show me the code." —— Linus Torvalds
> "But in HFT, even the code is too slow. Show me the assembly." —— Me

本文记录了在开发 HFT 系统过程中总结的一些核心优化原则与经验。这些内容是基于生产环境的实践得出的，旨在为解决系统延迟和抖动问题提供参考。

## 1. 关于 CPU：核心资源的精细化管理

CPU 是系统中最宝贵的资源，对其管理需要极度精细。

首先，**独占是基础 (One Core, One Task)**。通用操作系统的调度器虽然智能，但在微秒级的低延迟场景下，频繁的上下文切换 (Context Switch) 是不可接受的。通过配置 **Isolcpus** 和 **Taskset**，我们可以将关键线程绑定到特定的物理核心上，避免操作系统干扰。这确保了每个核心各司其职，维持 L1/L2 缓存的热度，从而消除调度带来的延迟抖动。

其次，**缓存 (Cache) 优化至关重要**。对于 I-Cache (指令缓存)，应保持热路径代码短小精悍，过度内联 (`#[inline(always)]`) 有时反而会增加代码体积导致缓存溢出。对于 D-Cache (数据缓存)，最常见的问题是 **False Sharing (伪共享)**。当多核频繁修改处于同一缓存行 (Cache Line, 通常 64 字节) 的不同变量时，会导致严重的性能下降。解决方法是对竞争变量使用 `#[repr(align(64))]` 进行对齐。此外，结构体的 **数据局部性 (Locality)** 也不容忽视，应将热数据紧凑排列，冷数据置于末尾。

最后，**分支预测 (Branch Prediction)** 的影响不容小觑。CPU 的流水线非常依赖分支预测，无法预测的分支会导致流水线冲刷。在可能的情况下，使用位运算替代分支逻辑 (Branchless programming) 是更优的选择。虽然编译器提供了 `likely`/`unlikely` 指令，但在现代 CPU 强大的预测能力下，仅应在概率极端偏斜的场景下使用。

## 2. 关于内存：TLB 与缺页处理

内存优化的核心目标是**提高 TLB 命中率并消除缺页中断**。

最基本的原则是 **热路径零分配 (No Allocation on Hot Path)**。动态内存分配 (`malloc`/`free` 或 Rust 的 `Box::new`) 涉及复杂的分配器逻辑甚至系统调用，严禁在交易主循环中使用。应采用 **对象池 (Object Pool)** 和 **Ring Buffer**，在系统启动阶段完成所有必要的内存预分配。

关于 **TLB 与缺页**，默认的 4KB 页面在大内存场景下容易导致 TLB Miss。启用 **Hugepages (2MB/1GB)** 可以显著减少页表项，提高查找效率。**Page Fault** 是导致长尾延迟的主要原因之一。程序启动后，应遍历所有分配的内存进行预读 (Pre-fault)，并使用 `mlockall` 锁定物理内存，防止操作系统将其交换 (Swap) 出去。

此外，**NUMA (非一致性内存访问)** 架构下的内存布局直接影响延迟。跨 Socket 访问内存会带来显著的延迟增加。应确保线程与其访问的内存位于同一个 NUMA 节点上。

## 3. 关于网络：内核旁路与中断控制

网络 I/O 是 HFT 系统的命脉，核心策略是 **Kernel Bypass** 和 **避免中断**。

传统的 Socket 通信 (`sys_recv`/`sys_send`) 涉及用户态与内核态的切换以及数据拷贝，开销巨大。因此，**Kernel Bypass** 技术 (如 DPDK, OpenOnload, AF_XDP) 是必选项。通过直接在用户态轮询网卡的 Ring Buffer，可以实现零拷贝和低延迟的数据收发。

关于中断，它是 CPU 流水线的大敌。在交易高峰期，频繁的中断会打断处理逻辑。**Busy Polling (忙轮询)** 是更合适的模式，虽然 CPU 占用率会达到 100%，但它消除了中断带来的抖动。如果必须保留中断，应将其亲和性 (Affinity) 设置到非交易核心上。

## 4. 架构设计：减少共享，强化通信

在架构层面，**锁 (Lock)** 是延迟的主要来源。`Mutex` 会导致线程挂起和调度器介入，`Spinlock` 虽然避免了挂起，但也存在死锁和优先级反转的风险。**SPSC (Single Producer Single Consumer) Ring Buffer** 是理想的替代方案，它实现了无锁、无竞争的线程间通信。

这自然引出了 **流水线 (Pipelining)** 的设计模式。与其让一个核心处理所有逻辑，不如将任务分解为 Network -> Decode -> Strategy -> Encode -> Network 等阶段。每个核心只负责单一任务，既提高了指令缓存的命中率，也使系统逻辑更加清晰。

## 5. 关于 Rust：安全性与性能的平衡

选择 Rust 的主要原因在于其**内存安全**和**零成本抽象**。相比 C++，Rust 在编译期杜绝了内存安全问题，且 `&mut T` 的独占性允许编译器进行激进的优化 (如 `noalias`)。

但在使用 Rust 时也需注意陷阱。**Async/Await** 运行时 (如 Tokio) 的工作窃取 (Work Stealing) 调度器可能会破坏缓存亲和性。在 HFT 场景下，手写 `epoll` 或 `io_uring` 的 Polling Loop 往往更可控。此外，Rust 的 **Drop 机制** 虽然保证了资源释放的确定性，但应避免在 `Drop` 中执行耗时操作，以免影响关键路径的延迟。

---

> **后记**: 优化是没有尽头的。不要为了优化而优化，**Benchmark Everything**。数据不会骗人，直觉通常会。

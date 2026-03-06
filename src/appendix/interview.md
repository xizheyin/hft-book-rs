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

---

## 6. HFT 面试技能矩阵 (The Skill Matrix)

为了满足 "95% 头部高频量化" 的面试要求，除了操作系统、网络和并发基础（前三章）之外，你必须掌握以下进阶领域：

### 6.1 计算机体系结构 (Computer Architecture)
这是区分初级和高级开发者的分水岭。
- **Cache Coherency**: MESI 协议，False Sharing 的底层原理，Store Buffer 与 Load Buffer 的作用。
- **Memory Ordering**: 为什么需要 `std::sync::atomic::Ordering`？Acquire/Release 语义到底在 CPU 层面做了什么（内存屏障）？
- **Branch Prediction**: 静态预测 vs 动态预测，如何写出对分支预测器友好的代码 (`if (unlikely(...))`)。

### 6.2 交易协议与市场微结构 (Protocols & Microstructure)
不懂业务的技术在 HFT 只是通用组件开发。
- **交易所协议**:
    - **文本协议**: FIX (Financial Information Exchange) —— 慢，由于 Tag=Value 解析开销。
    - **二进制协议**: SBE (Simple Binary Encoding), OUCH, ITCH (纳斯达克数据协议)。
    - **核心考点**: 如何编写零拷贝、零分配的协议解析器？(Rust `nom` vs 手写状态机)。
- **订单簿 (Order Book)**:
    - **L2 vs L3 数据**: 什么是快照 (Snapshot)？什么是增量 (Incremental)？
    - **设计题**: 如何设计一个支持 O(1) 插入/取消/修改的 Limit Order Book？(通常使用 HashMap + Doubly Linked List)。

### 6.3 低延迟编码实战 (Low Latency Coding)
面试官通常会让你手写代码（白板或 CoderPad）。
- **无锁队列 (Lock-free Queue)**:
    - SPSC (Single Producer Single Consumer) Ring Buffer —— HFT 的基石。
    - MPMC (Bounded Blocking Queue) —— 为什么 HFT 很少用 MPMC？(竞争太激烈)。
- **内存管理**:
    - **Object Pool**: 避免 `malloc`/`free`。
    - **Arena Allocator**: 区域内存分配。
- **热路径优化**:
    - 如何消除虚函数调用 (Devirtualization)？(Rust `enum` vs `dyn Trait`)。
    - SIMD 优化 (AVX2/AVX-512) 在行情处理中的应用。

### 6.4 硬件与系统边界 (Hardware & System Boundaries)
- **Kernel Bypass**: Userspace Networking (DPDK/Solarflare OpenOnload) 的原理。哪怕你不写，也要懂它为什么快（TLB Miss, Context Switch, Interrupts）。
- **FPGA**: 只要了解它在 HFT 中的位置（行情解码、风控网关），知道软件与硬件的延迟数量级差异 (Software ~2-5us vs FPGA ~100-800ns)。
- **Switching**: Cut-through vs Store-and-forward 交换机。

### 6.5 C++ vs Rust (The Elephant in the Room)
绝大多数 HFT 存量代码是 C++。
- **对比**: Rust 的 Move Semantics 对应 C++ 的 `std::move`。
- **内存模型**: Rust `Box` vs C++ `std::unique_ptr`。
- **虚表**: Trait Objects vs Virtual Functions (vtable layout)。
- **FFI**: 如何低开销地在 Rust 中调用 C++ 遗留库。

---

## 7. 核心面试题详解 (Deep Dive Q&A)

这里挑选了 3 个最常考的 HFT 编码/设计题进行详解。

### 7.1 设计一个 L3 Order Book (Limit Order Book)

**题目**: 请设计一个支持 O(1) `Add`, `Cancel`, `Execute` 的限价订单簿。

**分析**:
- 仅仅使用 `Vec` 或 `BTreeMap` 是不够的。`BTreeMap` 查找是 O(log N)，而在 HFT 中我们需要 O(1)。
- **标准解法**: `HashMap<OrderId, OrderNode>` + `BTreeMap<Price, LevelNode>` (或固定价格数组) + `Doubly Linked List` (在每个价格档位内)。

**Rust 实现思路 (伪代码)**:

```rust
struct Order {
    id: u64,
    price: u64,
    qty: u32,
    // prev/next 指针用于链表
    prev: Option<NonNull<Order>>,
    next: Option<NonNull<Order>>,
}

struct PriceLevel {
    price: u64,
    head: Option<NonNull<Order>>,
    tail: Option<NonNull<Order>>,
}

struct OrderBook {
    // 快速查找订单，O(1) Cancel/Modify
    orders: HashMap<u64, NonNull<Order>>,
    // 维护价格优先，BTreeMap 或者对于固定价格步长用 Vec
    levels: BTreeMap<u64, PriceLevel>,
}

impl OrderBook {
    fn add_order(&mut self, order: Order) {
        // 1. 插入 HashMap
        // 2. 找到对应的 PriceLevel
        // 3. 插入 PriceLevel 的链表尾部 (时间优先)
    }

    fn cancel_order(&mut self, order_id: u64) {
        // 1. 从 HashMap 找到 Order 指针
        // 2. 从链表中 O(1) 断开连接 (Unlink)
        // 3. 如果 PriceLevel 空了，移除 PriceLevel
        // 4. 移除 HashMap 条目
    }
}
```

> **面试加分项**: 提到使用 `Arena` 或 `Object Pool` 来分配 `Order` 节点，避免 `Box::new` 带来的内存碎片和分配开销。

### 7.2 实现一个无锁 SPSC 队列

**题目**: 手写一个单生产者单消费者 (Single Producer Single Consumer) 的 Ring Buffer。

**关键点**:
- 缓存行填充 (Padding) 避免 False Sharing。
- `Acquire` / `Release` 内存序。
- 只有 Producer 修改 `head`，只有 Consumer 修改 `tail`。

**代码片段**:

```rust
use std::sync::atomic::{AtomicUsize, Ordering};

const CACHE_LINE: usize = 64;

struct SpscRingBuffer<T, const N: usize> {
    buffer: [Option<T>; N], // 实际应该用 UnsafeCell<MaybeUninit<T>>
    
    #[repr(align(64))] // 避免 head 和 tail 在同一缓存行
    head: AtomicUsize, 
    
    #[repr(align(64))]
    tail: AtomicUsize,
}

impl<T, const N: usize> SpscRingBuffer<T, N> {
    pub fn push(&self, item: T) -> Result<(), T> {
        let head = self.head.load(Ordering::Relaxed);
        let tail = self.tail.load(Ordering::Acquire); // 同步 Consumer 的修改
        
        if head.wrapping_sub(tail) >= N {
            return Err(item); // Full
        }
        
        // 写入数据 (伪代码，需 unsafe)
        // self.buffer[head % N] = Some(item);
        
        // Release 语义保证 Consumer 能看到数据写入
        self.head.store(head.wrapping_add(1), Ordering::Release);
        Ok(())
    }

    pub fn pop(&self) -> Option<T> {
        let tail = self.tail.load(Ordering::Relaxed);
        let head = self.head.load(Ordering::Acquire); // 同步 Producer 的修改
        
        if tail == head {
            return None; // Empty
        }
        
        // 读取数据
        // let item = self.buffer[tail % N].take();
        
        // Release 语义保证 Producer 能看到 slot 被释放
        self.tail.store(tail.wrapping_add(1), Ordering::Release);
        // return item
        None 
    }
}
```

### 7.3 解释 False Sharing 及其修复

**题目**: 什么是 False Sharing？在 Rust 中如何修复？

**回答**:
- **现象**: 两个线程分别修改两个独立的变量 `A` 和 `B`，但这俩变量恰好位于同一个 Cache Line (64字节) 中。
- **后果**: Core 1 修改 `A` 会导致 Core 2 的 Cache Line 失效 (Invalidate)，Core 2 修改 `B` 又会导致 Core 1 失效。这种“乒乓效应”会导致严重的性能下降（可能慢 10-100 倍）。
- **修复**: 使用 `#[repr(align(64))]` 强制对齐，或者在变量之间插入 Padding。

```rust
#[repr(align(64))]
struct AlignedCounter {
    value: AtomicUsize,
}

// 这样数组中的每个计数器都会独占一个 Cache Line
let counters: Vec<AlignedCounter> = Vec::with_capacity(10);
```



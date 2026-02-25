# 并发模型选择 (Async vs Thread vs Actor)

在 Web 开发中，Rust 的并发几乎等同于 `async/await`。但在高频交易 (HFT) 中，我们有完全不同的优先级：**确定性 (Determinism)** 和 **低延迟 (Low Latency)**。吞吐量 (Throughput) 也很重要，但它必须建立在不牺牲尾部延迟 (P99) 的基础上。

本章将深入操作系统的调度原理，剖析不同并发模型的底层开销，并解释为什么 HFT 系统往往选择看似原始的 "Thread per Core" 模型。

## 1. 理论背景：操作系统调度的代价

要理解并发模型的选择，首先必须理解操作系统内核在做什么。

### 1.1 上下文切换 (Context Switch) 的解剖
当 Linux 内核决定暂停当前线程并运行另一个线程时，并非仅仅是保存几个寄存器那么简单。这是一个昂贵的操作，通常耗时 **1-5 微秒 (µs)**。在 HFT 中，5µs 可能意味着价格已经变动了。

一次上下文切换包含以下步骤：
1.  **用户态 -> 内核态切换**: 涉及特权级转换，CPU 流水线刷新。
2.  **保存寄存器状态**: 将通用寄存器、浮点寄存器 (AVX/SSE) 保存到内核栈。
3.  **调度器决策 (Scheduler Logic)**: CFS (Completely Fair Scheduler) 算法运行，计算红黑树节点，决定下一个运行的任务。
4.  **切换页表 (TLB Shootdown/Flush)**: 如果切换到不同进程，CR3 寄存器更新，导致 TLB (Translation Lookaside Buffer) 失效。内存访问延迟瞬间飙升。
5.  **缓存污染 (Cache Pollution)**: 最致命的一点。新线程的代码和数据会通过 L1/L2 Cache 加载，驱逐掉之前热乎的数据。当原线程切回来时，它面临的是一个冰冷的 Cache，必须重新从 RAM 读取数据。

> **HFT 铁律**: 永远不要让操作系统调度你的关键线程。一旦被调度出去，你的延迟就不可控了。

### 1.2 忙轮询 (Busy Polling) vs 系统通知 (Epoll/Kqueue)
- **系统通知 (Epoll)**: 线程挂起 (`park`)，等待内核唤醒。
    - *优点*: 省电，不占用 CPU。
    - *缺点*: 唤醒延迟 (Wakeup Latency) 高达 3-10µs。数据到达网卡 -> 中断 -> 内核处理 -> 唤醒线程 -> 调度执行。
- **忙轮询 (Busy Polling)**: 线程死循环检查标志位。
    - *优点*: 延迟极低 (纳秒级)。数据到达内存 -> CPU 立即读到。
    - *缺点*: 烧 CPU (100% Usage)，发热。

HFT 核心线程几乎总是使用忙轮询。

## 2. 核心实现：HFT 的并发架构

### 2.1 为什么不用 Async/Await?
Rust 的 `async/await` 基于状态机 (State Machine) 和协作式调度 (Cooperative Scheduling)。虽然它比 OS 线程轻量，但在 HFT 中仍有隐患：

1.  **不可预测的调度**: Tokio 的调度器不仅有任务窃取 (Work Stealing)，还有防止饿死的抢占机制。你无法确信你的 `Future` 是否会在同一个核心上连续执行。跨核迁移会导致 L1/L2 Cache 失效。
2.  **内存布局不透明**: `async` 块生成的 Future 结构体布局由编译器决定，可能包含大量填充，导致 Cache 密度低。
3.  **动态分配**: 虽然 Future 本身可以在栈上，但复杂的异步生态往往依赖 `Box<dyn Future>` 或 `Arc<Mutex<..>>`，引入堆分配和锁竞争。

**结论**: Async 适合网关、数据库连接池等 IO 密集型边缘组件。**核心交易逻辑应避免使用 Async。**

### 2.2 线程绑定 (Core Pinning / Affinity)

最稳健的模型是 **Thread per Core**。我们将每个关键线程“钉”在一个物理核心上，独占该核心的 L1/L2 Cache。

#### 实现代码 (使用 `core_affinity` 库)

```rust
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
        
        // 2. 提高线程优先级 (需要 root 权限或 CAP_SYS_NICE)
        // 这一步告诉 OS：除非机器要爆炸，否则别打断我
        // 设置 SCHED_FIFO 策略
        
        // 3. 忙轮询循环
        loop {
            // 接收数据
                    if let Some(packet) = receive_packet() {
                        process(packet);
                    } else {
                        // 关键优化：PAUSE 指令
                        // 1. 节能：让流水线暂停，降低功耗。
                        // 2. 避免内存顺序冲突：在退出自旋循环时，防止流水线清空带来的巨大惩罚 (Memory Order Violation)。
                        // Intel 推荐在 Skylake 架构上使用 `_mm_pause()` (大约 140 周期)。
                        std::hint::spin_loop(); 
                    }
        }
    });

    handle.join().unwrap();
}
```

### 2.3 隔离核心 (Isolcpus)
仅仅在代码里绑定是不够的。操作系统仍然可能在这个核心上调度一些杂务（如 SSH 守护进程、cron 任务、RCU 回调）。

我们需要在 Linux 启动参数中将这些核心隔离：
`isolcpus=2,3,4,5`

这样，Linux 调度器会完全忽略这些核心。除非你显式地将线程绑定上去，否则这些核心上不会运行任何用户态进程。这是 HFT 服务器的标准配置。

### 2.4 NUMA 架构感知 (NUMA Awareness)

现代高性能服务器通常是双路（Dual Socket）甚至四路的。这就引入了 **NUMA (Non-Uniform Memory Access)** 问题。

- **Local Access**: CPU 访问自己插槽上的内存，延迟低 (~60ns)。
- **Remote Access**: CPU 访问另一个插槽上的内存（通过 QPI/UPI 总线），延迟高 (~100ns+)。

**HFT 铁律**: 你的线程在哪颗 CPU 上跑，你的内存就必须在哪颗 CPU 上分配。

在 Rust 中，这通常意味着：
1.  **线程绑定**: 确保线程固定在某个 NUMA 节点的核心上。
2.  **内存分配**: 在该线程中进行内存分配（Linux 的 `first-touch` 策略通常保证了这一点）。或者使用 `libnuma` 显式绑定内存。

```rust
// 伪代码：检查 NUMA 拓扑
let topology = hwloc::Topology::new();
let core = topology.objects_with_type(ObjectType::Core)[0];
// 确保网卡、CPU 核心、内存都在同一个 NUMA 节点！
```

## 3. 性能分析：跨核通信 (Cross-Core Communication)

即便每个线程独占核心，它们之间仍需通信（如行情线程 -> 策略线程 -> 下单线程）。跨核通信的延迟由 CPU 的互连架构（如 Intel Mesh 或 AMD Infinity Fabric）决定。

### 3.1 缓存一致性协议 (MESI) 的影响
当核心 A 写入一个变量，核心 B 读取它时，硬件必须保证一致性。
1.  Core A 修改变量，其 L1 Cache Line 状态变为 `Modified`。
2.  Core B 尝试读取，发生 L1 Miss。
3.  Core B 向总线发出读请求。
4.  Core A 监听到请求 (Snoop)，将数据写回 L3 或直接传输给 Core B。
5.  Core A 的 Cache Line 变为 `Shared`，Core B 获得数据。

这个过程大约耗时 **40-100ns**。这是线程间传递消息的物理极限。

### 3.2 内存屏障 (Memory Barriers)
为了保证指令不被 CPU 乱序执行，我们需要内存屏障。在 Rust 中，这对应 `std::sync::atomic::Ordering`。

- `Relaxed`: 无屏障，只保证原子性。最快。
- `Release` / `Acquire`: 典型的生产者-消费者同步。
- `SeqCst`: 全局顺序一致性。最慢，会清空 CPU 流水线，**HFT 中应极力避免**。

```rust
use std::sync::atomic::{AtomicU64, Ordering};

// SPSC (Single Producer Single Consumer) 队列的指针更新
// 生产者
head.store(new_head, Ordering::Release); 
// 保证在此之前的所有写操作（写入队列数据）对消费者可见

// 消费者
let h = head.load(Ordering::Acquire);
// 保证在此之后的所有读操作（读取队列数据）能看到生产者写入的内容
```

如果使用 `SeqCst`，可能会导致 10-20ns 的额外开销。而在 x86 架构上，`Acquire`/`Release` 通常是零开销的（因为 x86 的内存模型本身就是强一致的 TSO），但在 ARM 上差异巨大。

## 4. 常见陷阱 (Pitfalls)

1.  **超线程 (Hyper-Threading)**:
    Intel 的超线程技术让一个物理核心模拟两个逻辑核心。它们共享 L1/L2 Cache 和执行单元。
    **HFT 必须关闭超线程**（或在 BIOS 中禁用，或只绑定物理核心的第一个逻辑核）。因为如果另一个逻辑核上的线程在争抢 ALU 或 L1 Cache，你的延迟会剧烈抖动。

2.  **中断风暴 (IRQ Storm)**:
    网卡中断如果打在你的关键核心上，会强制打断你的线程。
    **解决**: 配置 `/proc/irq/N/smp_affinity`，将网卡中断绑定到专门的 IO 核心，或者使用 DPDK 的轮询模式驱动 (PMD) 完全接管网卡，屏蔽中断。

3.  **False Sharing (伪共享)**:
    前文已述，并发队列的头尾指针如果位于同一 Cache Line，会导致生产者和消费者互相 invalid 对方的 Cache，导致性能从纳秒级跌落到微秒级。务必使用 `#[repr(align(128))]` (为了保险，有时设为 128 字节以防预取器读取相邻行)。

## 5. 延伸阅读

- [The Linux Scheduler: a Decade of Wasted Cores](https://www.ece.ubc.ca/~sasha/papers/eurosys16-final29.pdf) - 深入了解调度器的问题。
- [Intel 64 and IA-32 Architectures Optimization Reference Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) - 权威的硬件优化指南。
- [rigtorp/MPMCQueue](https://github.com/rigtorp/MPMCQueue) - C++ 实现的极致性能队列，Rust 实现可参考其原理。

---
下一章：我们将进入 **第二部分：核心基础设施**，首先构建 HFT 系统的血管 —— [无锁数据结构与 Ring Buffer](../infrastructure/ring_buffer.md)。

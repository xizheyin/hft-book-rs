# 操作系统原理回顾 (OS Internals)

在 HFT 面试中，除了 CPU 微架构，操作系统（OS）的底层原理是另一大重灾区。面试官通常会考察你对**虚拟内存**、**内存锁定**、**系统调用**和**中断**的理解，因为这些机制直接决定了系统的抖动（Jitter）。

本章将回顾那些对低延迟编程至关重要的 OS 概念。

## 1. 虚拟内存：宏观视角 (Virtual Memory: The Big Picture)

你程序中看到的指针地址（如 `0x7ffe...`）都是**虚拟地址**。硬件中的 DRAM 存储使用的是**物理地址**。
这两者之间有一层复杂的映射关系，由硬件单元 **MMU (Memory Management Unit)** 和操作系统共同管理。

### 1.1 映射过程与页表
Linux 默认将内存划分为 **4KB** 大小的“页 (Page)”。
为了记录 "虚拟页 X -> 物理页 Y" 的映射，OS 维护了一个**多级页表 (Multi-level Page Table)** 结构（通常是 4 级）。

每次 CPU 访问内存（例如 `mov rax, [ptr]`）：
1.  **查 TLB**: MMU 首先查询 **TLB (Translation Lookaside Buffer)**，这是一个极快的硬件缓存。
2.  **TLB Hit**: 如果找到了，直接得到物理地址。耗时 ~0 周期。
3.  **TLB Miss**: 如果没找到，MMU 必须遍历内存中的 4 级页表（Page Walk）。这涉及 4 次串行的内存访问！耗时可能高达 100+ 周期。

### 1.2 物理内存不仅是物理内存
你以为你分配了内存，实际上你只得到了一段虚拟地址空间（VMA）。只有当你**真正写入**数据时，OS 才会触发 **缺页异常 (Page Fault)**，分配物理页，并建立映射。

更糟糕的是，物理内存不足时，OS 会将不常用的物理页写入磁盘（**Swap**），并将页表项标记为“无效”。下次你访问时，再次触发 Page Fault，从磁盘读回。这对 HFT 来说是**绝对禁止**的（毫秒级延迟）。

## 2. 内存管理的 HFT 实践

为了消灭上述的不确定性，HFT 系统必须采取以下措施。

### 2.1 预故障 (Pre-faulting)
既然分配内存时不分配物理页，那我们就强制分配。
在交易开始前（初始化阶段），我们遍历所有分配的内存，对每一页写入一个字节。

```rust
// 预热内存，防止运行时 Page Fault
let mut buffer = vec![0u8; 1024 * 1024];
for i in (0..buffer.len()).step_by(4096) {
    // 写入导致 OS 必须分配物理页并建立页表映射
    // 使用 volatile 写入防止编译器优化掉这个循环
    unsafe { std::ptr::write_volatile(&mut buffer[i], 0); }
}
```

### 2.2 内存锁定 (Memory Locking)
**Pre-fault 还不够！** 就算你现在分配了物理页，OS 还是可能因为内存压力把它 Swap 出去。
你必须告诉内核：“这块内存非常重要，**永远不要换出**”。

在 Linux 中，这通过 `mlock` 或 `mlockall` 系统调用实现。

```rust
use libc::{mlockall, MCL_CURRENT, MCL_FUTURE};

pub fn lock_memory() -> std::io::Result<()> {
    unsafe {
        // MCL_CURRENT: 锁定当前已分配的所有内存
        // MCL_FUTURE: 锁定未来分配的所有内存
        if mlockall(MCL_CURRENT | MCL_FUTURE) != 0 {
            return Err(std::io::Error::last_os_error());
        }
    }
    Ok(())
}
```
**注意**: 这通常需要 `CAP_IPC_LOCK` 权限或调整 `ulimit -l`。

### 2.3 大页内存 (Hugepages)
为什么默认的 4KB 页不够好？

1.  **TLB 覆盖范围 (TLB Reach)**:
    假设 CPU 的 L1 TLB 有 64 个条目。
    - 使用 4KB 页：覆盖 $64 \times 4KB = 256KB$ 内存。
    - 使用 2MB 页：覆盖 $64 \times 2MB = 128MB$ 内存。
    如果你的订单簿有 1GB，使用 4KB 页会导致频繁的 TLB Miss。而使用 2MB/1GB 页可以显著提高 TLB 命中率。这就是 "Huge" 的意义——它极大地扩展了 TLB 的视野。

2.  **减少页表层级**:
    - 4KB 页：4 级页表。
    - 2MB 页：3 级页表（省去 1 次内存访问）。
    - 1GB 页：2 级页表（省去 2 次内存访问）。

**Rust 实战**:
使用 `mmap` 配合 `MAP_HUGETLB`。

```rust
// 伪代码：分配 2MB 大页
let len = 2 * 1024 * 1024;
let ptr = mmap(
    null, len, 
    PROT_READ | PROT_WRITE, 
    MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB, 
    -1, 0
);
```

## 3. 系统调用 (System Calls)

系统调用（Syscall）是用户态程序请求内核服务的接口（如读写文件、发送网络包）。

### 3.1 开销来源
Syscall 不仅仅是一个函数调用。它涉及：
1.  **模式切换**: CPU 从 Ring 3 (用户态) 切换到 Ring 0 (内核态)。
2.  **上下文保存**: 保存寄存器状态。
3.  **安全检查**: 内核必须验证用户传入的参数。
4.  **Spectre/Meltdown 补丁**: 现代 CPU 为了防范侧信道攻击，在 Syscall 路径上增加了额外的屏障（如 KPTI），使得 Syscall 开销显著增加（从 ~100ns 增加到 ~500ns+）。

### 3.2 vDSO (virtual Dynamic Shared Object)
某些频繁调用的 Syscall（如 `gettimeofday`, `clock_gettime`）被优化了。内核将这些函数的实现映射到用户空间，使得调用它们就像调用普通函数一样，**无需陷入内核**。
这就是为什么在 Rust 中调用 `Instant::now()` 非常快。

### 3.3 锁的代价 (Cost of Locking): Mutex vs Spinlock

在 HFT 面试中，这是必考题：**为什么我们要自己写 Spinlock 而不用 std::sync::Mutex？**

*   **Mutex (互斥锁)**:
    *   基于操作系统的 `futex` (Fast Userspace Mutex) 系统调用。
    *   **快路径**: 如果没有竞争，它是用户态的原子操作（快）。
    *   **慢路径**: 如果有竞争，线程会陷入内核（Syscall），进入睡眠状态（Context Switch）。
    *   **唤醒**: 当锁释放时，内核唤醒线程（Context Switch）。
    *   **总开销**: 竞争发生时，至少 5-10 微秒。

*   **Spinlock (自旋锁)**:
    *   基于 `Atomic` CAS (Compare-And-Swap) 操作。
    *   **原理**: 线程在一个 `while` 循环中不断尝试获取锁，不让出 CPU。
    *   **优点**: 没有系统调用，没有上下文切换。获取锁的延迟仅为几十纳秒（CAS 指令周期）。
    *   **缺点**: 浪费 CPU 电力。如果持有锁的线程被切走（Preemption），等待者会空转很久（这也是为什么我们需要 `isolcpus`）。

**HFT 结论**: 在关键路径上，我们**只使用 Spinlock**，且临界区（Critical Section）必须极短（几条指令）。

### 3.4 实战：自旋锁 (Spinlock in Action)

Spinlock 最常用于**多生产者-单消费者 (MPSC)** 或 **多生产者-多消费者 (MPMC)** 的队列尾部指针更新。虽然 Lock-free 结构更好，但有时简单的 Spinlock 更容易实现且性能足够。

```rust
use std::sync::atomic::{AtomicBool, Ordering};
use std::cell::UnsafeCell;

pub struct SpinLock<T> {
    lock: AtomicBool,
    data: UnsafeCell<T>,
}

unsafe impl<T: Send> Sync for SpinLock<T> {}

impl<T> SpinLock<T> {
    pub fn new(data: T) -> Self {
        Self {
            lock: AtomicBool::new(false),
            data: UnsafeCell::new(data),
        }
    }

    pub fn lock(&self) -> SpinLockGuard<T> {
        // 1. 尝试获取锁
        // compare_exchange_weak 在循环中通常比 strong 快
        while self.lock.compare_exchange_weak(
            false, 
            true, 
            Ordering::Acquire, 
            Ordering::Relaxed
        ).is_err() {
            // 2. 关键优化：PAUSE 指令
            // 告诉 CPU "我在忙等"，让 CPU 暂停流水线，降低功耗，避免内存顺序冲突
            std::hint::spin_loop(); 
        }
        
        SpinLockGuard { lock: self }
    }
}

pub struct SpinLockGuard<'a, T> {
    lock: &'a SpinLock<T>,
}

impl<'a, T> Drop for SpinLockGuard<'a, T> {
    fn drop(&mut self) {
        self.lock.lock.store(false, Ordering::Release);
    }
}
```

## 4. 中断 (Interrupts)

中断是 CPU 响应外部事件（如网卡数据到达、时钟滴答）的机制。对于 HFT 来说，中断是把双刃剑：它既是获取行情的源头，也是破坏确定性（Determinism）的元凶。

### 4.1 硬件中断 vs 软中断 (HardIRQ vs SoftIRQ)

Linux 的中断处理分为两个阶段：

1.  **上半部 (Top Half / HardIRQ)**:
    *   **极快**: 立即响应硬件信号，屏蔽其他中断。
    *   **任务**: 仅仅把数据从网卡寄存器拷贝到 RAM（Ring Buffer），然后触发软中断。
    *   **HFT 影响**: 会打断当前正在运行的任何代码（包括你的策略线程）。这会导致 **Context Switch** 和 **Cache Pollution**。

2.  **下半部 (Bottom Half / SoftIRQ)**:
    *   **稍慢**: 处理复杂的逻辑（如 TCP/IP 协议栈解析）。
    *   **任务**: 运行在 `ksoftirqd` 线程中，消耗 CPU 时间。

### 4.2 中断亲和性 (SMP Affinity)

为了防止中断打断核心策略线程，我们需要将中断“赶”到非关键核心上。

假设你的 CPU 有 16 个核心：
*   **Core 0-1**: 处理 OS 杂务（SSH, 日志）。
*   **Core 2-3**: 专门处理网卡中断（网卡队列绑定）。
*   **Core 4-15**: **隔离核心 (Isolated Cores)**，运行策略线程。

**操作命令**:
```bash
# 查看当前网卡中断分布
cat /proc/interrupts | grep eth0

# 将网卡 eth0 的中断只绑定到 CPU 2 (掩码 0x4)
# echo 4 > /proc/irq/<irq_num>/smp_affinity
```

### 4.3 局部性原理的破坏者

为什么中断如此可怕？
想象你的策略线程正在 Core 4 上全速运行，L1/L2 Cache 填满了订单簿数据。
突然，网卡中断来了。Core 4 被迫暂停你的线程，跳转到内核的中断处理程序 (ISR)。ISR 执行了一堆代码，把 L1/L2 Cache 全洗了一遍。
等中断处理完，你的线程恢复执行，发现 Cache 全是冷的（Cache Miss），延迟瞬间飙升 10-20 微秒。

**解决方案**: **Kernel Bypass (内核旁路)**。
使用 DPDK 或 OpenOnload，直接在用户态轮询（Polling）网卡，完全绕过内核中断机制。

## 5. 系统调优：消除抖动 (System Tuning: Eliminating Jitter)

即使你写出了完美的代码，操作系统本身的行为（节能、调度）也会毁掉你的延迟。为了让 OS "滚一边去"，我们需要在启动参数 (`/etc/default/grub`) 中动手术。

### 5.1 隔离与无滴答 (Isolation & Tickless)

*   **`isolcpus=4-15`**: 将 CPU 4 到 15 从内核调度器中移除。普通进程（如 SSH、cron）永远不会被调度到这些核心上。只有你的 HFT 线程通过 `taskset` 显式绑定上去才能运行。
*   **`nohz_full=4-15`**: **Tickless Kernel**。通常内核每秒会有 100-1000 次时钟中断（Tick）来检查任务调度。对于 HFT 核心，如果只运行一个任务，这个 Tick 是多余的且有害的。`nohz_full` 告诉内核：如果核心上只有一个任务，就别发 Tick 中断打扰它。
*   **`rcu_nocbs=4-15`**: 将 RCU (Read-Copy-Update) 的回调处理移出这些核心。RCU 回调是内核中的垃圾回收机制，如果不移出，它会随机借用你的 CPU 时间。

### 5.2 禁用节能 (Disable Power Management)

CPU 在空闲时会进入 C-States (C1, C6...) 以省电。
*   **代价**: 从 C6 (深度睡眠) 唤醒到 C0 (全速运行) 需要 **10-100 微秒**！
*   **对策**:
    *   `intel_idle.max_cstate=0`: 禁止进入深层睡眠。
    *   `processor.max_cstate=1`: 限制最大睡眠深度为 C1 (Halt，唤醒极快)。
    *   BIOS 设置: 关闭 Hyper-Threading (超线程)，关闭 Turbo Boost (睿频，导致时钟不稳定)，开启 "Performance Mode"。

### 5.3 启动参数示例

一个标准的 HFT 服务器内核启动参数如下：

```bash
GRUB_CMDLINE_LINUX="isolcpus=4-15 nohz_full=4-15 rcu_nocbs=4-15 intel_idle.max_cstate=0 processor.max_cstate=1 skew_tick=1 hugepages=1024"
```

## 6. 进阶话题 (Advanced Topics)

### 6.1 I/O 模型进化论

在 HFT 中，网络 I/O 是生命线。关于 I/O 模型的详细演进（从阻塞到非阻塞，再到多路复用），请参考 [I/O 模型演进](../network/io_models.md)。

这里我们要强调的是：**标准的多路复用 (Epoll) 对于微秒级竞争来说仍然太慢**。

*   **Epoll 的瓶颈**: 系统调用开销、内存拷贝、中断上下文切换。
*   **HFT 的选择**: **忙轮询 (Busy Polling)**。通过用户态死循环检查数据，消除上下文切换。

### 6.2 内核旁路 (Kernel Bypass)

当 `epoll` 甚至 `busy poll` 都不够快时，瓶颈在于 Linux 内核本身（协议栈处理、内存拷贝）。

关于 Kernel Bypass 的详细原理和实现（DPDK, OpenOnload），请参考 [内核旁路技术](../network/kernel_bypass.md)。

*   **核心思想**: 让用户态程序直接控制网卡，绕过内核协议栈。
*   **收益**: 延迟从 ~10us 降至 <1us。

### 6.3 NUMA 架构 (Non-Uniform Memory Access)

在双路（Dual Socket）服务器上，CPU 0 访问插在 CPU 1 旁边的内存，比访问本地内存要慢 20-50ns (QPI/UPI 总线开销)。

**HFT 黄金法则**:
*   **本地性**: 线程绑定在 CPU Node X，内存分配在 Node X，网卡插在 Node X 的 PCIe 插槽上。
*   **工具**: 使用 `lscpu` 查看拓扑，使用 `numactl --cpunodebind=0 --membind=0 ./my_hft_app` 启动程序。

### 6.4 实时调度 (Real-time Scheduling)

虽然我们使用了 `isolcpus`，但为了双重保险，可以将线程调度策略设置为 `SCHED_FIFO`。

```rust
// 设置当前线程为实时优先级 99
pub fn set_realtime_priority() {
    let params = libc::sched_param { sched_priority: 99 };
    unsafe {
        libc::pthread_setschedparam(
            libc::pthread_self(),
            libc::SCHED_FIFO,
            &params
        );
    }
}
```

*   **注意**: 这是一个危险操作。如果你的线程死循环且没有让出 CPU，这台机器可能会死机（这也是为什么我们需要 `isolcpus`）。

## 7. 总结 (Summary)

1.  **预故障 (Pre-faulting)**: 初始化时摸一遍所有内存。
2.  **内存锁定 (Mlock)**: 防止 Swap。
3.  **大页 (Hugepages)**: 减少 TLB Miss。
4.  **隔离核心 (Isolcpus)**: 避免 OS 调度干扰。
5.  **中断绑定 (SMP Affinity)**: 避免中断打断关键线程。
6.  **内核旁路 (Kernel Bypass)**: 绕过内核协议栈。
7.  **NUMA 亲和性**: 保证内存和网卡在同一节点。


掌握这些 OS 原理，是写出微秒级系统的入场券。

---
下一章：[内存布局与缓存效率](memory_layout.md)

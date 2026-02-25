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

## 5. 总结 (Summary)

1.  **预故障 (Pre-faulting)**: 初始化时摸一遍所有内存。
2.  **内存锁定 (Mlock)**: 防止 Swap。
3.  **大页 (Hugepages)**: 减少 TLB Miss。
4.  **隔离核心 (Isolcpus)**: 避免 OS 调度干扰。
5.  **中断绑定 (SMP Affinity)**: 避免中断打断关键线程。

掌握这些 OS 原理，是写出微秒级系统的入场券。

---
下一章：[内存布局与缓存效率](memory_layout.md)

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

## 4. 中断与异常 (Interrupts & Exceptions)

### 4.1 硬中断 (Hardware Interrupts)
当网卡收到数据包时，它会给 CPU 发送一个电信号（中断）。CPU 必须**立即停止**当前正在做的事情，跳转到中断处理程序 (ISR)。

**解决**: **Core Isolation (核隔离)**。将关键交易线程绑定到特定的 CPU 核心，并配置 OS 使得该核心**不处理任何中断**（除了本地时钟中断）。

## 5. 总结

在面试中，当被问到内存管理时，你应该展示出**整体视角**：

1.  **虚拟 -> 物理**: 理解页表和 TLB 的作用。
2.  **不确定性**: 理解 Page Fault 和 Swap 是延迟杀手。
3.  **解决方案**:
    - **Pre-fault**: 消除运行时的缺页异常。
    - **mlock**: 消除 Swap 风险。
    - **Hugepages**: 扩大 TLB 覆盖范围，减少页表遍历开销。

这才是 HFT 级别的内存管理认知。

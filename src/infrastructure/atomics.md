# 原子操作与内存顺序 (Atomics)

在编写无锁数据结构时，最让人头秃的莫过于内存顺序 (Memory Ordering)。`Relaxed`, `Acquire`, `Release`, `SeqCst` 到底有什么区别？用错了会有什么后果？

本章将剥开 CPU 的外衣，从硬件层面解释内存顺序的本质，并给出一套在 HFT 开发中“既安全又快”的最佳实践。

## 1. 理论背景：为什么需要内存顺序？

在单核时代，CPU 保证指令是按顺序执行的（或者至少看起来是）。但在多核时代，为了性能，硬件做了两件事：

1.  **Store Buffer**: 写入内存太慢，CPU 会先写到本地缓冲。这意味着 Core 1 写的值，Core 2 不一定马上能看到。
2.  **乱序执行 (Out-of-Order Execution)**: 只要没有数据依赖，CPU 可能会交换指令的执行顺序。

**内存屏障 (Memory Barrier)** 就是我们指挥 CPU 和编译器“不要乱动”的令牌。

## 2. Rust 的内存顺序模型

Rust (继承自 C++20) 提供了 5 种内存顺序：

### 2.1 Relaxed (松散)
- **含义**: 只保证原子性，不保证顺序。
- **硬件**: 编译成普通的 `MOV` 指令（在 x86 上）。
- **用途**: 计数器、统计指标。
- **风险**: 你可能看到新的值，但看不到该值依赖的旧数据（因为指令重排）。

```rust
// 计数器增加，谁先谁后无所谓
counter.fetch_add(1, Ordering::Relaxed);
```

### 2.2 Acquire / Release (获取/释放)
这是构建无锁数据结构的基石。它们成对出现，建立 **Happens-Before** 关系。

- **Release (写)**: 确保在我也写入之前的所有操作（包括普通读写），不会被重排到我之后。
    - *潜台词*: "我写完了，把之前的数据都刷出去。"
- **Acquire (读)**: 确保在我读取之后的所有操作，不会被重排到我之前。
    - *潜台词*: "我看到了信号，现在可以安全地读数据了。"

**经典场景**: 生产者-消费者。
1. 生产者写数据 (普通写)。
2. 生产者写 `flag = true` (**Release**)。
3. 消费者读 `flag` (**Acquire**)。
4. 消费者读数据 (普通读)。

如果用 `Relaxed`，消费者可能先读到 `flag = true`，但读到的数据还是旧的（因为重排）。

### 2.3 AcqRel (获取且释放)
- **含义**: 同时具有 Acquire 和 Release 的语义。
- **用途**: RMW (Read-Modify-Write) 操作，如 `compare_exchange`，既要读旧值（Acquire），又要写新值（Release）。

### 2.4 SeqCst (顺序一致性)
- **含义**: 最强的保证。除了 Acq/Rel 的保证外，还保证**全局所有线程看到的指令顺序是一致的**。
- **代价**: 在 x86 上是 `LOCK` 前缀指令或 `MFENCE`，开销巨大（几十到上百周期）。在 ARMv8 上是 `LDAR`/`STLR`，开销较小。
- **HFT 态度**: **尽量不用**。除非你在实现复杂的算法（如 Dekker 算法），或者实在搞不清逻辑（作为兜底）。

## 3. 实战：如何选择？

在 HFT 系统中，我们遵循以下 **"99% 规则"**:

1.  **单纯计数**: 用 `Relaxed`。
2.  **发布数据 (Flag/Index)**: 写用 `Release`，读用 `Acquire`。
3.  **锁/信号量**: `Acquire` 加锁，`Release` 解锁。
4.  **CAS 更新**: 成功用 `AcqRel` (或 `Release` 如果只写)，失败用 `Relaxed` (通常失败不需要屏障)。

### 案例分析：Ring Buffer 的屏障

回顾我们的 Ring Buffer：

```rust
// Producer
unsafe { *buffer.get_unchecked(i) = val; } // 1. 写数据
head.store(i + 1, Ordering::Release);      // 2. 写索引 (Release)

// Consumer
let h = head.load(Ordering::Acquire);      // 3. 读索引 (Acquire)
let val = unsafe { *buffer.get_unchecked(i) }; // 4. 读数据
```

- **Release** 保证了 (1) 绝对在 (2) 之前完成。
- **Acquire** 保证了 (3) 绝对在 (4) 之前完成。
- 因此，(1) -> (2) -> (3) -> (4)，消费者绝对不会读到未初始化的脏数据。

如果全用 `Relaxed`，CPU 可能把 (4) 提到 (3) 之前（预测执行），导致读到旧数据。

## 4. 硬件差异 (x86 vs ARM)

这对跨平台开发至关重要。

- **x86-64 (TSO - Total Store Order)**:
    - 硬件本身提供了很强的保证：Load/Load, Store/Store, Load/Store 不会重排。只有 Store/Load (写后读) 可能重排。
    - 这意味着：在 x86 上，`Release` 和 `Acquire` 编译出来的汇编代码和 `Relaxed` **完全一样**！都是普通的 `MOV`。
    - **陷阱**: 很多只在 x86 上测试的 `Relaxed` 代码是错的，但在 x86 上碰巧能跑。一放到 ARM (如 AWS Graviton, Apple M1) 上就崩了。

- **ARM / POWER (Weakly Ordered)**:
    - 硬件允许几乎所有类型的重排。
    - `Release` 会编译成 `STLR`，`Acquire` 编译成 `LDAR`。
    - **结论**: 必须严格遵守 Rust 的内存模型，不要依赖 x86 的具体行为。

## 5. 性能测试：SeqCst 有多慢？

我们在 AMD Ryzen 9 上测试 `fetch_add`：

```rust
// Criterion Benchmark 伪代码
b.iter(|| {
    a.fetch_add(1, Ordering::Relaxed); // ~0.8 ns
});
b.iter(|| {
    a.fetch_add(1, Ordering::SeqCst);  // ~6.5 ns
});
```

差距接近 **8 倍**。在争用激烈时，`SeqCst` 会锁住总线（或缓存行），导致整个系统停顿。

## 6. 常见陷阱

1.  **误用 `Volatile`**:
    C++ / Java 程序员喜欢用 `volatile` 做同步。在 Rust 中，`std::ptr::read_volatile` **不保证原子性，也不保证线程同步**。它只用于 MMIO (内存映射 I/O)。千万别用它做线程间通信。

2.  **自旋锁中的 `yield`**:
    在等待 `Acquire` 时，不要死循环。
    ```rust
    // BAD
    while flag.load(Ordering::Relaxed) == false {} 
    
    // GOOD
    while flag.load(Ordering::Acquire) == false {
        std::hint::spin_loop(); // 告诉 CPU 我在空转，省电并优化流水线
    }
    ```

---
下一章：[高性能日志 (Logging)](logging.md)

# SPSC/MPSC 队列详解 (Queues)

在上一章中，我们实现了一个基于数组的 SPSC Ring Buffer。然而，在真实的 HFT 系统中，我们面临的通信场景远比“一对一”复杂。最典型的场景是 **MPSC (Multiple Producer Single Consumer)**，例如多个工作线程将日志发送给唯一的日志线程，或多个网关将订单汇聚到撮合引擎。

本章将深入探讨 MPSC 队列的设计权衡，并剖析业界顶级的无锁队列实现。

## 1. 理论背景 (Theory & Context)

### 1.1 为什么 MPSC 很难？
SPSC 之所以常见，是因为每个游标只有一个写者，不需要用 CAS 争抢下一个序号；生产者和消费者之间仍有缓存一致性通信，并非“完全互不干扰”。
但在常见 MPSC 设计中，**多个生产者需要协调谁获得下一个写入位置**。若它们争用同一个原子游标，负载升高后 CAS 失败和缓存行迁移可能明显增加。分片、批量预留或“每个生产者一条 SPSC”可以改变这个争用拓扑。

### 1.2 数组 vs 链表 (Array vs Linked List)
- **数组 (Bounded)**:
    - *优点*: 创建时分配固定槽位，稳态操作可不分配，内存局部性通常较好。
    - *缺点*: 必须定义“满”的语义；一次 `try_push` 可以立即返回 `Full`，上层也可选择有界自旋、park、拒绝或按业务规则丢弃/合并。
- **链表 (Unbounded)**:
    - *优点*: 不受固定槽位数限制，突发时可继续增长。
    - *缺点*: “逻辑无界”不等于永远成功：仍可能 OOM，并把背压转化为内存增长与排队延迟；分配器、节点链接和回收协议也可能争用。它是否 lock-free/wait-free 必须看具体算法，不能从“无界”推出。

**HFT 选择**: 
对于核心交易路径（如订单流），常从**有界数组队列**开始，并依据可测的最大突发、消费者暂停窗口和内存预算确定容量。满时策略必须写进业务协议：订单不能静默丢弃；可恢复行情可以触发 snapshot；指标可能允许采样或合并。
对于日志、监控等路径，可评估分段队列，但仍要设置内存上限、水位告警和降级策略。无界队列没有消灭背压，只是推迟了它出现的位置。

## 2. 核心实现：基于数组的有界队列

下面是教学用的简化实现，保留生产者和消费者两侧的 CAS，因此形态上更接近有界 MPMC，而不是严格 MPSC。若系统确定只有一个消费者，可以去掉消费者间抢占，但仍要处理“生产者已预留、尚未发布”的槽位。不要直接把本节代码当成经过审计的生产容器。

不同资料对 head/tail 的命名方向可能相反；这里 `tail` 是生产者预留位置，`head` 是消费者位置。判断算法时应看“谁写哪个游标”，不要只背名称。

```rust
use std::sync::atomic::{AtomicUsize, Ordering};
use std::cell::UnsafeCell;

// 假设 T: Copy + Default
pub struct BoundedArrayQueue<T> {
    buffer: Vec<UnsafeCell<T>>,
    mask: usize,
    head: AtomicUsize, // 消费者索引
    tail: AtomicUsize, // 生产者索引
    
    // 每槽位 sequence 同时编码期望的全局序号与代次；不是简单的奇偶标记。
    seqs: Vec<AtomicUsize>,
}

// SAFETY: 成功预留游标的线程独占对应 slot；slot 的 Release/Acquire sequence
// 负责发布和回收。T: Send，因为值会在线程间转移。
unsafe impl<T: Send> Sync for BoundedArrayQueue<T> {}

impl<T: Default + Copy> BoundedArrayQueue<T> {
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0, "capacity must be positive");
        let capacity = capacity
            .checked_next_power_of_two()
            .expect("capacity is too large");
        assert!(capacity <= isize::MAX as usize, "capacity is too large");
        let mut buffer = Vec::with_capacity(capacity);
        let mut seqs = Vec::with_capacity(capacity);
        
        for i in 0..capacity {
            buffer.push(UnsafeCell::new(T::default()));
            // 初始化 seq 为索引值，代表第 0 轮
            seqs.push(AtomicUsize::new(i));
        }

        Self {
            buffer,
            mask: capacity - 1,
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
            seqs,
        }
    }

    pub fn try_push(&self, value: T) -> Result<(), T> {
        let mut tail = self.tail.load(Ordering::Relaxed);
        
        loop {
            let index = tail & self.mask;
            let seq = self.seqs[index].load(Ordering::Acquire);
            let diff = seq.wrapping_sub(tail) as isize;

            if diff == 0 {
                // 槽位空闲，且轮次匹配。尝试抢占 tail
                match self.tail.compare_exchange(
                    tail,
                    tail.wrapping_add(1),
                    Ordering::Relaxed,
                    Ordering::Relaxed,
                ) {
                    Ok(_) => {
                        // 抢占成功！写入数据
                        unsafe { *self.buffer[index].get() = value; }
                        // 将 seq + 1，标记为有数据
                        self.seqs[index]
                            .store(tail.wrapping_add(1), Ordering::Release);
                        return Ok(());
                    }
                    Err(current_tail) => {
                        // 抢占失败，tail 被人改了，重试
                        tail = current_tail; 
                    }
                }
            } else if diff < 0 {
                // 槽位被占满（seq < tail），队列满了
                // 或者这一轮已经被写入了
                return Err(value); 
            } else {
                // diff > 0: tail 已经落后了，重新加载 tail
                tail = self.tail.load(Ordering::Relaxed);
            }
        }
    }

    pub fn try_pop(&self) -> Option<T> {
        let mut head = self.head.load(Ordering::Relaxed);
        
        loop {
            let index = head & self.mask;
            let seq = self.seqs[index].load(Ordering::Acquire);
            let next_head = head.wrapping_add(1);
            let diff = seq.wrapping_sub(next_head) as isize;

            if diff == 0 {
                // 槽位有数据 (seq == head + 1)
                match self.head.compare_exchange(
                    head,
                    next_head,
                    Ordering::Relaxed,
                    Ordering::Relaxed,
                ) {
                    Ok(_) => {
                        let value = unsafe { *self.buffer[index].get() };
                        // 将 seq 设为 head + mask + 1，即下一轮的空闲状态
                        self.seqs[index].store(
                            head.wrapping_add(self.mask).wrapping_add(1),
                            Ordering::Release,
                        );
                        return Some(value);
                    }
                    Err(current_head) => {
                        head = current_head;
                    }
                }
            } else if diff < 0 {
                // 数据还没准备好 (seq < head + 1)
                return None;
            } else {
                // diff > 0: head 落后了
                head = self.head.load(Ordering::Relaxed);
            }
        }
    }
}
```

> **代码解析**: 这是 Dmitry Vyukov 有界 MPMC 队列思路的教学化版本。每槽位 sequence 用来区分当前代次的可写/可读状态，并帮助判断空满。它减少了旧值混淆，但有限位宽仍会回绕，正确性依赖容量与 wrapping 距离不变量。原算法作者也特别提醒：使用原子 RMW 不自动等于满足正式的 lock-free 进展保证。

## 3. 性能分析 (Performance Analysis)

### 3.1 竞争回退 (Contention Backoff)
上述代码在生产者竞争较高时，`compare_exchange` 失败后立即重试可能放大缓存一致性流量。可评估有界 Backoff，但退避会同时改变公平性与尾延迟，必须按目标负载测量。

下面是依赖 `crossbeam-utils` 的**教学骨架**，`fail` 与外层预留循环来自具体队列实现，所以不能独立运行。验证时在示例 crate 执行 `cargo add crossbeam-utils`，把 `Backoff` 接入完整 CAS 循环后运行 `cargo check`、Miri/Loom（适用部分）以及高争用分位延迟基准。

```rust,ignore
use crossbeam_utils::Backoff;

// 伪代码：把 backoff 放在一次预留操作的重试循环外。
let backoff = Backoff::new();
// 在循环中
if fail {
    backoff.snooze(); // 自旋几次，然后 yield
}
```

### 3.2 伪共享 (False Sharing)
在 `seqs` 数组中，相邻的 `AtomicUsize` 紧挨着。如果 Core 1 修改 `seqs[0]`，Core 2 修改 `seqs[1]`，它们可能在同一个 Cache Line 上。
把每个 `seq` 都填充到缓存行可以减少相邻槽位的写写伪共享，却会显著增大元数据工作集并降低缓存密度，不是默认优化。应先测多个生产者是否经常同时触达相邻槽位，再比较 padding、分片和批量预留。

## 4. 工业级实现对比

### 4.1 Crossbeam (`crossbeam-queue`)
- **SegQueue**: 无界队列，由多个固定大小的数组（Segment）组成的链表。
    - *优点*: 兼顾了数组的缓存局部性和链表的动态扩容。
    - *缺点*: 增长、跨 block 与回收仍有成本；逻辑无界仍需要外部内存/过载策略。
- **ArrayQueue**: 有界 MPMC 队列，使用每槽位 stamp 协调代次；具体进展保证与实现细节应查看当前版本文档。

### 4.2 Rigtorp (`rigtorp::MPMCQueue`)
- 这是常被参考的 C++ 有界 MPMC 实现。不要把其他语言的移植版视为同一实现，也不要预设它必然快于 Crossbeam；应核对具体版本的类型要求、异常/析构语义，并在相同拓扑与负载下基准。

## 5. 常见陷阱 (Pitfalls)

1.  **饥饿与预留后暂停**:
    无锁/原子队列不保证某个高优先级生产者一定先成功；某线程预留槽位后被抢占，还可能让消费者暂时观察到未发布的洞，影响取决于具体算法。
    **解决**: 尽量减少生产者的数量，或使用每个生产者独立的 SPSC 队列（M x SPSC），然后在消费者端轮询聚合。

2.  **ABA 问题**:
    每槽位 sequence 能区分相邻轮次，但不是“天然永不回头”：整数最终会 wrapping。需要证明在容量约束和最大在途距离下，活跃操作不会把新旧代次混淆。

## 6. 面试追问：有界队列满了，怎样回答才完整？

先区分进展保证和业务策略：`try_push` 立即返回 `Full`，不代表订单已经处理；调用者必须选择拒绝、有限重试、park、降级或按数据类型丢弃/合并。随后说明容量依据（突发速率 × 最长消费者暂停窗口）、水位监控和恢复路径。只回答“把队列调大”会把背压推迟成更长排队。

## 7. 延伸阅读

- [1024 Cores - MPMC Queue](http://www.1024cores.net/home/lock-free-algorithms/queues/bounded-mpmc-queue) - Dmitry Vyukov 的原始博客。
- [Crossbeam 源码分析](https://github.com/crossbeam-rs/crossbeam) - 学习 Rust 并发编程的最佳教材。

---
下一章：[原子操作详解 (Atomics)](atomics.md)

# SPSC/MPSC 队列详解 (Queues)

在上一章中，我们实现了一个基于数组的 SPSC Ring Buffer。然而，在真实的 HFT 系统中，我们面临的通信场景远比“一对一”复杂。最典型的场景是 **MPSC (Multiple Producer Single Consumer)**，例如多个工作线程将日志发送给唯一的日志线程，或多个网关将订单汇聚到撮合引擎。

本章将深入探讨 MPSC 队列的设计权衡，并剖析业界顶级的无锁队列实现。

## 1. 理论背景 (Theory & Context)

### 1.1 为什么 MPSC 很难？
SPSC 之所以快，是因为生产者和消费者互不干扰，只要 `head` 和 `tail` 不重合，它们就可以独立工作。
但在 MPSC 中，**多个生产者必须争抢同一个写入位置 (Tail)**。
这引入了争用 (Contention)。如果使用简单的 CAS (`tail.compare_exchange`)，当并发量大时，失败率会极高，导致 CPU 在空转重试中浪费大量时间。

### 1.2 数组 vs 链表 (Array vs Linked List)
- **数组 (Bounded)**:
    - *优点*: 内存连续，缓存友好，无内存分配。
    - *缺点*: 必须处理“满”的情况。如果队列满了，生产者要么阻塞（Wait-Free 变成 Blocking），要么丢弃数据。
- **链表 (Unbounded)**:
    - *优点*: 永远不满（除非 OOM），生产者总是 Wait-Free。
    - *缺点*: 每次 Push 都需要分配节点（malloc），缓存不友好。

**HFT 选择**: 
对于核心交易路径（如订单流），我们通常选择**大容量的数组队列**，因为分配内存是不可接受的。
对于非关键路径（如日志、监控），我们可以使用**分段链表 (Segmented Linked List)**，它是两者的折中。

## 2. 核心实现：基于数组的 MPSC 队列

这是一个极简的、基于数组的 MPSC 队列实现。它使用 CAS 来预定槽位。

```rust
use std::sync::atomic::{AtomicUsize, Ordering};
use std::cell::UnsafeCell;

// 假设 T: Copy + Default
pub struct MpscArrayQueue<T> {
    buffer: Vec<UnsafeCell<T>>,
    mask: usize,
    head: AtomicUsize, // 消费者索引
    tail: AtomicUsize, // 生产者索引
    
    // 用于标记每个槽位是否可写/可读
    // 偶数轮次: 空闲，可写
    // 奇数轮次: 有数据，可读
    seqs: Vec<AtomicUsize>,
}

unsafe impl<T: Send> Sync for MpscArrayQueue<T> {}

impl<T: Default + Copy> MpscArrayQueue<T> {
    pub fn new(capacity: usize) -> Self {
        let capacity = capacity.next_power_of_two();
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

    pub fn push(&self, value: T) -> Result<(), T> {
        let mut tail = self.tail.load(Ordering::Relaxed);
        
        loop {
            let index = tail & self.mask;
            let seq = self.seqs[index].load(Ordering::Acquire);
            let diff = seq as isize - tail as isize;

            if diff == 0 {
                // 槽位空闲，且轮次匹配。尝试抢占 tail
                match self.tail.compare_exchange(
                    tail, tail + 1, Ordering::Relaxed, Ordering::Relaxed
                ) {
                    Ok(_) => {
                        // 抢占成功！写入数据
                        unsafe { *self.buffer[index].get() = value; }
                        // 将 seq + 1，标记为有数据
                        self.seqs[index].store(tail + 1, Ordering::Release);
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

    pub fn pop(&self) -> Option<T> {
        let mut head = self.head.load(Ordering::Relaxed);
        
        loop {
            let index = head & self.mask;
            let seq = self.seqs[index].load(Ordering::Acquire);
            let diff = seq as isize - (head + 1) as isize;

            if diff == 0 {
                // 槽位有数据 (seq == head + 1)
                match self.head.compare_exchange(
                    head, head + 1, Ordering::Relaxed, Ordering::Relaxed
                ) {
                    Ok(_) => {
                        let value = unsafe { *self.buffer[index].get() };
                        // 将 seq 设为 head + mask + 1，即下一轮的空闲状态
                        self.seqs[index].store(head + self.mask + 1, Ordering::Release);
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

> **代码解析**: 这是经典的 Dmitry Vyukov 的 MPMC 队列算法的简化版（去掉了多消费者部分）。它巧妙地使用 `seqs` 数组解决了 ABA 问题和判断空/满的问题，而不需要单独的 `count` 变量。

## 3. 性能分析 (Performance Analysis)

### 3.1 竞争回退 (Contention Backoff)
上述代码在高并发下有一个致命问题：`compare_exchange` 失败后立即重试。这会导致 CPU 总线流量风暴。
**优化**: 在 CAS 失败后引入 `Backoff`。

```rust
use crossbeam_utils::Backoff;

let backoff = Backoff::new();
// 在循环中
if fail {
    backoff.snooze(); // 自旋几次，然后 yield
}
```

### 3.2 伪共享 (False Sharing)
在 `seqs` 数组中，相邻的 `AtomicUsize` 紧挨着。如果 Core 1 修改 `seqs[0]`，Core 2 修改 `seqs[1]`，它们可能在同一个 Cache Line 上。
**优化**: 将 `seqs` 中的元素填充到 Cache Line 大小。但这会浪费大量内存（8字节 -> 64字节，8倍膨胀）。通常只在极度追求性能时这么做。

## 4. 工业级实现对比

### 4.1 Crossbeam (`crossbeam-queue`)
- **SegQueue**: 无界队列，由多个固定大小的数组（Segment）组成的链表。
    - *优点*: 兼顾了数组的缓存局部性和链表的动态扩容。
    - *缺点*: 跨 Segment 时有微小开销。
- **ArrayQueue**: 有界队列，基于上述 Vyukov 算法。

### 4.2 Rigtorp (`rigtorp::MPMCQueue`)
- C++ 界的标杆。它的 Rust 移植版通常性能优于 Crossbeam，因为它更激进地使用了 padding 和 unsafe。
- 它只支持 `T: Copy`，避免了 `Drop` 带来的复杂性。

## 5. 常见陷阱 (Pitfalls)

1.  **优先级反转 (Priority Inversion)**:
    在无锁队列中，虽然没有锁，但如果高优先级线程一直 CAS 失败（被低优先级线程抢占），也会出现类似现象。
    **解决**: 尽量减少生产者的数量，或使用每个生产者独立的 SPSC 队列（M x SPSC），然后在消费者端轮询聚合。

2.  **ABA 问题**:
    上述基于 `seq` 的实现天然免疫 ABA，因为 `seq` 是单调递增的（包含轮次信息）。但如果使用基于指针的栈（Stack），必须小心。

## 6. 延伸阅读

- [1024 Cores - MPMC Queue](http://www.1024cores.net/home/lock-free-algorithms/queues/bounded-mpmc-queue) - Dmitry Vyukov 的原始博客。
- [Crossbeam 源码分析](https://github.com/crossbeam-rs/crossbeam) - 学习 Rust 并发编程的最佳教材。

---
下一章：[原子操作详解 (Atomics)](atomics.md)

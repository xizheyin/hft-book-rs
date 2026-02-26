# Ring Buffer 实现 (Ring Buffer)

Ring Buffer (环形缓冲区) 是 HFT 系统中最基础、最重要的数据结构。几乎所有的高频交易系统，从 LMAX Disruptor 到 Aeron，其核心都是一个 Ring Buffer。

它不仅仅是一个队列，更是一种设计哲学：**预分配内存**、**无锁并发**、**缓存友好**。

## 1. 理论背景 (Theory & Context)

### 1.1 为什么要用 Ring Buffer？

Ring Buffer (环形缓冲区) 是 HFT 系统中最基础、最重要的数据结构。几乎所有的高频交易系统，从 LMAX Disruptor 到 Aeron，其核心都是一个 Ring Buffer。

```mermaid
graph TD
    subgraph Memory Layout
        Head[Head (Producer)]
        Tail[Tail (Consumer)]
        
        subgraph Buffer [Circular Buffer]
            S0[Slot 0]
            S1[Slot 1]
            S2[Slot 2 (Writing)]
            S3[Slot 3]
            S4[Slot 4 (Reading)]
            S5[Slot 5]
        end
    end
    
    Head -->|Write Index| S2
    Tail -->|Read Index| S4
    
    style Head fill:#f96,stroke:#333
    style Tail fill:#9cf,stroke:#333
    style S2 fill:#f96,stroke:#333
    style S4 fill:#9cf,stroke:#333
```

1.  **零内存分配 (Zero Allocation)**: 在启动时分配一块固定大小的内存，运行过程中不再进行任何 `malloc` 或 `free`。这消除了 GC 压力和内存碎片。
2.  **缓存局部性 (Cache Locality)**: 数组在内存中是连续的，CPU 预取器 (Prefetcher) 可以完美工作。
3.  **避免伪共享 (False Sharing)**: 通过精心设计的填充 (Padding)，确保生产者和消费者的指针位于不同的缓存行。

### 1.2 模运算优化
Ring Buffer 本质上是一个数组，索引会回绕。
通常写法：`index = sequence % capacity`。
但除法（取模）运算在 CPU 中非常昂贵（几十个周期）。

**优化**: 强制要求 capacity 为 2 的幂（如 1024, 4096）。
优化写法：`index = sequence & (capacity - 1)`。
位运算只需 1 个周期。

## 2. 核心实现：SPSC Ring Buffer

我们将实现一个单生产者单消费者 (SPSC) 的 Ring Buffer。这是最快、最简单的变体，常用于行情线程向策略线程传递数据。

### 2.1 数据结构定义

为了消除伪共享 (False Sharing)，我们需要确保 `head` 和 `tail` 位于不同的 Cache Line 上。

```rust
use std::sync::atomic::{AtomicUsize, Ordering};
use std::cell::UnsafeCell;
use std::mem::MaybeUninit;

// 缓存行大小通常为 64 字节，但也可能是 128 (如 Apple Silicon M1/M2)
// 为了安全，我们按 128 对齐
#[repr(align(128))]
struct CacheLinePad;

pub struct SpscRingBuffer<T> {
    // 缓冲区：使用 MaybeUninit 避免 T::default() 的开销，且支持无默认值的类型
    buffer: Vec<UnsafeCell<MaybeUninit<T>>>,
    capacity: usize,
    mask: usize,
    
    // 生产者只写 head，消费者只读 head
    // 放在单独的 cache line 以避免伪共享
    _pad1: CacheLinePad,
    head: AtomicUsize, 
    
    // 消费者只写 tail，生产者只读 tail
    _pad2: CacheLinePad,
    tail: AtomicUsize,
    
    _pad3: CacheLinePad,
}

// 必须实现 Sync，因为我们在多线程间共享
// T 必须是 Send 的，因为数据会在线程间传递
unsafe impl<T: Send> Sync for SpscRingBuffer<T> {}
unsafe impl<T: Send> Send for SpscRingBuffer<T> {}
```

### 2.2 构造函数与初始化

```rust
impl<T> SpscRingBuffer<T> {
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0 && capacity.is_power_of_two(), "Capacity must be power of 2");
        
        let mut buffer = Vec::with_capacity(capacity);
        for _ in 0..capacity {
            buffer.push(UnsafeCell::new(MaybeUninit::uninit()));
        }

        Self {
            buffer,
            capacity,
            mask: capacity - 1,
            _pad1: CacheLinePad,
            head: AtomicUsize::new(0),
            _pad2: CacheLinePad,
            tail: AtomicUsize::new(0),
            _pad3: CacheLinePad,
        }
    }
}
```

### 2.3 生产者逻辑 (Push)

```rust
impl<T> SpscRingBuffer<T> {
    pub fn try_push(&self, value: T) -> Result<(), T> {
        let head = self.head.load(Ordering::Relaxed);
        // Acquire: 确保我们看到了消费者最新的 tail 更新
        let tail = self.tail.load(Ordering::Acquire); 

        if head.wrapping_sub(tail) >= self.capacity {
            return Err(value); // 满了
        }

        let index = head & self.mask;
        
        // SAFETY: 
        // 1. 我们是唯一的生产者 (SPSC)。
        // 2. index 对应的 slot 此时归生产者所有（因为 head - tail < capacity）。
        unsafe {
            let slot = &mut *self.buffer[index].get();
            slot.write(value);
        }

        // Release: 确保 buffer 的写入在 head 更新之前完成
        // 这样消费者看到新的 head 时，buffer 中的数据一定是有效的
        self.head.store(head.wrapping_add(1), Ordering::Release);
        
        Ok(())
    }
}
```

### 2.4 消费者逻辑 (Pop)

```rust
impl<T> SpscRingBuffer<T> {
    pub fn try_pop(&self) -> Option<T> {
        let tail = self.tail.load(Ordering::Relaxed);
        // Acquire: 确保我们看到了生产者最新的 head 更新
        // 以及 buffer 中对应的数据写入
        let head = self.head.load(Ordering::Acquire);

        if tail == head {
            return None; // 空了
        }

        let index = tail & self.mask;

        // SAFETY:
        // 1. 我们是唯一的消费者 (SPSC)。
        // 2. index 对应的 slot 此时归消费者所有（因为 tail < head）。
        let value = unsafe {
            let slot = &*self.buffer[index].get();
            slot.assume_init_read()
        };

        // Release: 告诉生产者这个 slot 已经空出来了
        self.tail.store(tail.wrapping_add(1), Ordering::Release);

        Some(value)
    }
}
```

## 3. 性能分析 (Performance Analysis)

### 3.1 内存顺序详解
*   **Producer Store Head (Release)** <-> **Consumer Load Head (Acquire)**: 
    这构成了同步点。Producer 保证写入数据 -> 更新 Head。Consumer 保证读取 Head -> 读取数据。这防止了 CPU 重排导致 Consumer 读到未初始化的数据。
*   **Consumer Store Tail (Release)** <-> **Producer Load Tail (Acquire)**:
    这也是同步点。Consumer 保证读取数据 -> 更新 Tail。Producer 保证读取 Tail -> 覆盖旧数据。这防止了 Producer 覆盖还未被消费的数据。

### 3.2 批处理优化 (Batching)
在极端高频场景下，每次 Push/Pop 都执行原子操作（尽管是无锁的）仍然昂贵，因为 `Acquire`/`Release` 会影响流水线。
一种优化是**缓存 Head/Tail**：
*   **Producer**: 维护一个本地的 `cached_tail`。只有当 buffer 看起来满了时，才去读取真正的原子 `tail`。
*   **Consumer**: 维护一个本地的 `cached_head`。只有当 buffer 看起来空了时，才去读取真正的原子 `head`。

这可以显著减少 Cache Traffic。

```rust
// 伪代码：带缓存的生产者
if head - self.cached_tail >= self.capacity {
    self.cached_tail = self.tail.load(Ordering::Acquire);
    if head - self.cached_tail >= self.capacity {
        return Err(Full);
    }
}
```

## 3. 性能分析 (Performance Analysis)

### 3.1 内存屏障开销
注意 `try_push` 和 `try_pop` 中的 `Acquire` / `Release` 对。
- `Acquire` 确保我们看到了对方最新的修改。
- `Release` 确保我们的修改对对方可见。
在 x86 上，这几乎是零开销的。在 ARM 上，这对应 `LDAR` / `STLR` 指令，开销也很低。

### 3.2 批处理优化 (Batching)
为了进一步减少原子操作的开销，我们可以引入**批处理**。
消费者可以一次性读取 `tail` 到 `head` 之间的所有数据，处理完后再更新 `tail`。这称为 **Smart Batching**。

```rust
// 批量消费接口示例
pub fn consume_batch<F>(&self, mut handler: F) -> usize 
where F: FnMut(T) 
{
    let tail = self.tail.load(Ordering::Relaxed);
    let head = self.head.load(Ordering::Acquire);
    
    let available = head.wrapping_sub(tail);
    if available == 0 { return 0; }

    // 处理所有可用数据，不更新原子变量
    for i in 0..available {
        let index = (tail + i) & self.mask;
        let val = unsafe { *self.buffer.get_unchecked(index).get() };
        handler(val);
    }

    // 只更新一次原子变量
    self.tail.store(tail.wrapping_add(available), Ordering::Release);
    available
}
```

这种优化可以将吞吐量从每秒 1000 万条提升到 5000 万条以上。

## 4. 常见陷阱 (Pitfalls)

1.  **False Sharing 再次来袭**:
    一定要确保 `head` 和 `tail` 不在同一个 Cache Line。如果 `_pad` 被移除，性能会暴跌 10-50 倍。
    
2.  **Drop 问题**:
    我们在示例中使用了 `T: Copy`。如果 `T` 是 `String` 等需要 Drop 的类型，直接覆盖内存会导致内存泄漏（旧值没被 Drop）。
    **解决**: 对于 Ring Buffer，最好只存 `Copy` 类型（如 `u64` ID, `f64` Price, 固定大小数组）。如果是复杂对象，存索引或指针。

3.  **整数溢出**:
    `head` 和 `tail` 是 `usize`。虽然 64 位整数溢出需要几百年，但最好使用 `wrapping_add` / `wrapping_sub` 来处理溢出逻辑。我们的代码已经这么做了。

## 5. 延伸阅读

- [LMAX Disruptor](https://lmax-exchange.github.io/disruptor/) - Java 高频交易领域的传奇。
- [rigtorp/SPSCQueue](https://github.com/rigtorp/SPSCQueue) - C++11 实现的极简 SPSC 队列。
- [Aeron](https://github.com/real-logic/aeron) - 这里的 Ring Buffer 设计更为复杂，支持多路复用。

---
下一章：[SPSC/MPSC 队列 (Queues)](queues.md)

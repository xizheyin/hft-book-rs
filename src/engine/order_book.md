# 订单簿管理 (Order Book Management)

在交易引擎中，订单簿（Order Book）不仅是数据的容器，更是策略决策的核心依据。上一部分我们在 [L1/L2/L3 数据构建](../connectivity/order_book_data.md) 中讨论了底层的存储结构（如 FlatMap, Intrusive List）。本章将聚焦于如何在多线程环境下**安全、高效地管理**这些数据，并为策略提供极低延迟的访问接口。

## 1. 核心挑战：读写并发 (Read-Write Concurrency)

在典型的 HFT 架构中，存在两种角色的线程：
1.  **Writer (单写者)**: 网络线程（或专门的市场数据线程），负责接收交易所数据并更新订单簿。
2.  **Reader (多读者)**: 策略线程，负责读取订单簿并做出决策。

### 1.1 架构图示

```mermaid
graph TD
    MD[Market Data Feed] -->|Updates| Writer
    subgraph Engine
        Writer[Writer Thread]
        OB[OrderBook (Shared Memory)]
        Reader1[Strategy A]
        Reader2[Strategy B]
        Reader3[Risk Check]
    end
    Writer -->|Write (SeqLock)| OB
    OB -.->|Read (Optimistic)| Reader1
    OB -.->|Read (Optimistic)| Reader2
    OB -.->|Read (Optimistic)| Reader3
    
    style Writer fill:#f96,stroke:#333,stroke-width:2px
    style OB fill:#9cf,stroke:#333,stroke-width:2px
```

### 1.2 锁的困境
*   `Mutex<OrderBook>`: 绝对禁止。锁竞争会导致严重的延迟抖动（Jitter）。
*   `RwLock<OrderBook>`: 依然不够好。Writer 必须等待所有 Readers 释放锁，导致行情更新被阻塞，这在高频场景下是不可接受的（行情更新优先级最高）。

### 1.3 解决方案：SeqLock (Sequence Lock)

SeqLock 是一种乐观锁机制，允许 Writer 随时写入（不阻塞），而 Reader 需要检测在读取过程中是否发生了写入。如果发生了，Reader 重试。

**适用场景**: 写操作非常快（更新几个字段），读操作也很快。

## 2. SeqLock 实现 (Implementation)

SeqLock 是一种乐观锁机制，允许 Writer 随时写入（不阻塞），而 Reader 需要检测在读取过程中是否发生了写入。如果发生了，Reader 重试。

**适用场景**: 写操作非常快（更新几个字段），读操作也很快。

```rust
use std::sync::atomic::{AtomicUsize, Ordering, fence};
use std::cell::UnsafeCell;

pub struct SeqLock<T> {
    seq: AtomicUsize,
    data: UnsafeCell<T>,
}

unsafe impl<T: Send> Sync for SeqLock<T> {}

impl<T> SeqLock<T> {
    pub fn new(val: T) -> Self {
        Self {
            seq: AtomicUsize::new(0),
            data: UnsafeCell::new(val),
        }
    }

    /// Writer: 获取独占访问权
    /// 
    /// # Safety
    /// 必须确保同一时间只有一个 Writer 调用此方法。
    /// 通常通过架构设计（单线程写）来保证，或者在 SeqLock 外部再包一层 Mutex（如果需要多写者）。
    pub fn write(&self, f: impl FnOnce(&mut T)) {
        // 1. 增加序列号 (变为奇数)，表示正在写入
        // Relaxed 即可，因为后续的 fence(Release) 会保证顺序
        let seq = self.seq.load(Ordering::Relaxed);
        self.seq.store(seq + 1, Ordering::Relaxed);

        // 2. 内存屏障：保证之前的写操作不会重排到 seq 更新之后
        // 同时也保证后续的 data 修改不会重排到 seq 更新之前
        fence(Ordering::Release);

        // 3. 执行修改
        // SAFETY: 只有一个 writer，且 seq 为奇数时 reader 会重试
        f(unsafe { &mut *self.data.get() });

        // 4. 内存屏障：保证 data 修改全部完成
        fence(Ordering::Release);

        // 5. 增加序列号 (变为偶数)，表示写入完成
        self.seq.store(seq + 2, Ordering::Relaxed);
    }

    /// Reader: 乐观读取
    pub fn read<R>(&self, f: impl FnOnce(&T) -> R) -> Option<R> {
        // 1. 读取开始序列号
        let seq1 = self.seq.load(Ordering::Acquire);
        
        // 如果 seq 是奇数，说明正在写，直接失败（或由调用者决定自旋）
        if seq1 & 1 != 0 {
            return None;
        }

        // 2. 内存屏障：保证读取 data 发生在读取 seq1 之后
        fence(Ordering::Acquire);

        // 3. 读取数据
        let result = f(unsafe { &*self.data.get() });

        // 4. 内存屏障：保证读取 data 发生在读取 seq2 之前
        fence(Ordering::Acquire);

        // 5. 读取结束序列号
        let seq2 = self.seq.load(Ordering::Acquire);

        // 6. 验证一致性
        if seq1 == seq2 {
            Some(result)
        } else {
            None
        }
    }
}
```

## 3. L3 Order Book 数据结构设计

在 HFT 面试中，**"如何设计一个支持 O(1) Add/Cancel/Execute 的限价订单簿 (Limit Order Book)"** 是最经典的考题。这不仅考察数据结构，还考察对内存布局和缓存友好性的理解。

### 3.1 核心需求
*   **O(1) Order Lookup**: 根据 OrderId 快速找到订单（用于 Cancel/Modify）。
*   **O(1) Price Level Access**: 快速找到最佳买卖价（BBO）以及特定的价格档位。
*   **O(1) Order Insertion**: 在特定价格档位的队尾插入订单（时间优先）。
*   **O(1) Order Deletion**: 从价格档位的任意位置删除订单。

### 3.2 数据结构选型
仅仅使用 `BTreeMap` 是不够的，因为查找是 O(log N)。我们需要组合多种数据结构。

1.  **HashMap<OrderId, NodePtr>**: 用于根据 ID 快速定位订单节点。
2.  **Price Map (BTreeMap<Price, Level> 或 Vec<Level>)**: 用于管理价格档位。
    *   如果是股票（价格稀疏），用 `BTreeMap`。
    *   如果是期货（价格连续且密集），用预分配的 `Vec` 或数组（Direct Indexing）是更快的 O(1)。
3.  **Doubly Linked List (Intrusive)**: 在每个价格档位内部维护订单队列。我们需要双向链表来实现 O(1) 的中间删除。

### 3.3 Rust 实现架构

为了极致性能，我们通常不使用标准库的 `LinkedList`（因为它分配内存且指针不暴露），而是使用**侵入式链表 (Intrusive Linked List)** 配合 **Object Pool (Arena)**。

```rust
use std::ptr::NonNull;
use std::collections::HashMap;

// 1. 订单节点 (Node)
struct OrderNode {
    id: u64,
    price: u64,
    qty: u32,
    // 侵入式链表指针
    prev: Option<NonNull<OrderNode>>,
    next: Option<NonNull<OrderNode>>,
    // 指向所属的价格档位，方便删除时更新档位统计
    parent_level: NonNull<PriceLevel>,
}

// 2. 价格档位 (Level)
struct PriceLevel {
    price: u64,
    total_qty: u64,
    count: u32,
    head: Option<NonNull<OrderNode>>,
    tail: Option<NonNull<OrderNode>>,
}

// 3. 订单簿 (Book)
struct L3OrderBook {
    // 所有的 OrderNode 实际上存储在一个预分配的 Arena 中
    // 这里只存指针
    orders: HashMap<u64, NonNull<OrderNode>>,
    
    // 价格档位表
    // 对于期货，这里可以是 Vec<Option<NonNull<PriceLevel>>> 直接索引
    levels: BTreeMap<u64, NonNull<PriceLevel>>,
    
    // 内存池 (Arena)
    // 实际存储 OrderNode 和 PriceLevel 的地方
    // 避免 malloc/free
    order_arena: Vec<OrderNode>, 
    level_arena: Vec<PriceLevel>,
}
```

### 3.4 关键优化点

1.  **预分配 (Pre-allocation)**: `order_arena` 和 `level_arena` 在启动时分配足够的空间（如 100万个订单），运行时完全无 GC、无系统调用。
2.  **缓存局部性 (Cache Locality)**: 由于 Arena 是连续内存，虽然逻辑上是链表，但在物理上相邻的订单可能在内存中也相邻（如果是顺序插入），这比散乱的堆内存要好得多。
3.  **无指针解引用 (Pointer Swizzling)**: 在极致优化中，可以用 `u32` 索引代替 `usize` 指针（如果 Arena 大小 < 4G），减少内存占用并减轻 Cache 压力。

## 4. 双缓冲 (Double Buffering)

如果读取操作非常耗时（例如策略需要遍历整个订单簿计算复杂指标），SeqLock 会导致 Reader 频繁重试，永远无法成功。

此时，**双缓冲**是更好的选择。

### 4.1 机制
维护两个完全一样的 `OrderBook` 实例：`Front` 和 `Back`。
*   Reader 总是读取 `Front`。
*   Writer 总是写入 `Back`。
*   当 Writer 完成一批更新后，**原子地交换指针**。

```rust
use std::sync::atomic::{AtomicPtr, Ordering};
use std::ptr;

struct DoubleBufferedOrderBook {
    // 两个具体的 OrderBook 实例
    books: [Box<OrderBook>; 2],
    // 指向当前可读的那个
    current_index: AtomicUsize, 
}

impl DoubleBufferedOrderBook {
    pub fn update(&mut self, update: MarketDataUpdate) {
        // 1. 获取后台 buffer 的索引
        let back_index = 1 - self.current_index.load(Ordering::Relaxed);
        
        // 2. 更新后台 buffer
        self.books[back_index].apply(update);
        
        // 3. 发布：切换前台索引
        // 这里需要 Release 语义，保证 update 操作对 Reader 可见
        self.current_index.store(back_index, Ordering::Release);
        
        // 4. 追赶：为了保持两个 buffer 一致，下次需要把这个 update 也应用到另一个 buffer 吗？
        // 双缓冲通常有两种策略：
        // A. Copy-on-Write: 每次 switch 前把 old front 复制到 back (太慢)
        // B. Apply-Twice: update 需要应用两次。一次现在，一次在下次 switch 后。
    }
}
```
**Apply-Twice** 是 HFT 中的常用技巧。Writer 维护一个 `pending_updates` 队列，每次切换 buffer 后，把队列里的更新应用到新的 Back buffer 上。

## 5. 衍生指标计算 (Derived Metrics)

策略通常不需要原始的订单簿，而是需要经过计算的指标。

### 5.1 中间价 (Mid Price)
```rust
pub fn mid_price(&self) -> f64 {
    let best_bid = self.bids.first().map(|l| l.price).unwrap_or(0.0);
    let best_ask = self.asks.first().map(|l| l.price).unwrap_or(0.0);
    (best_bid + best_ask) / 2.0
}
```

### 5.2 加权平均价 (VWAP)
计算前 N 层或前 V 量的 VWAP。
**优化**: 增量计算。
维护 `sum_prod = sum(price * qty)` 和 `total_qty`。
当 Order Add 时，`sum_prod += p * q`。
当 Order Delete 时，`sum_prod -= p * q`。
这样查询 VWAP 是 O(1)。

### 5.3 订单簿不平衡度 (Imbalance)
$$ Imbalance = \frac{Q_{bid} - Q_{ask}}{Q_{bid} + Q_{ask}} $$
用于预测短期价格走势。同样可以增量维护。

## 6. 总结

## 7. 常见陷阱

### 7.1 脏读 (Dirty Reads)
在使用 SeqLock 时，如果 Reader 读取了部分数据（比如 `price`），然后 Writer 修改了数据（`price` 变了），Reader 接着读取了 `quantity`。此时 Reader 读到的是 **新 Price + 旧 Quantity** 还是 **旧 Price + 新 Quantity**？
SeqLock 只能保证事务的原子性（要么全旧，要么全新），前提是 Reader **不应该产生副作用**（如打印日志、发送网络包），并且在 `seq1 == seq2` 检查通过前，读取的数据都是**临时的**。

**危险**: 如果 Reader 基于脏数据除以零（Panic），或者数组越界（Panic），那么 SeqLock 的重试机制也救不了你。
**解决**:
1.  Reader 逻辑必须是 Panic-free 的。
2.  对于数组索引，先做 clamp 或 check，即使数据是脏的。

### 7.2 缓存行失效
Writer 频繁写入会导致 Reader 的 Cache Line 失效（Ping-pong effect）。
**解决**: 将 Reader 感兴趣的聚合数据（如 BBO, Imbalance）单独放在一个 Cache Line 中，与频繁变动的 L3 详细数据分开。

---
下一章：[风控系统 (Risk Management System)](risk.md)

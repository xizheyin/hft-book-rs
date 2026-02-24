# 订单簿管理 (Order Book Management)

在交易引擎中，订单簿（Order Book）不仅是数据的容器，更是策略决策的核心依据。上一部分我们在 [L1/L2/L3 数据构建](../connectivity/order_book_data.md) 中讨论了底层的存储结构（如 FlatMap, Intrusive List）。本章将聚焦于如何在多线程环境下**安全、高效地管理**这些数据，并为策略提供极低延迟的访问接口。

## 1. 核心挑战：读写并发 (Read-Write Concurrency)

在典型的 HFT 架构中，存在两种角色的线程：
1.  **Writer (单写者)**: 网络线程（或专门的市场数据线程），负责接收交易所数据并更新订单簿。
2.  **Reader (多读者)**: 策略线程，负责读取订单簿并做出决策。

### 1.1 锁的困境
*   `Mutex<OrderBook>`: 绝对禁止。锁竞争会导致严重的延迟抖动（Jitter）。
*   `RwLock<OrderBook>`: 依然不够好。Writer 必须等待所有 Readers 释放锁，导致行情更新被阻塞，这在高频场景下是不可接受的（行情更新优先级最高）。

### 1.2 解决方案：SeqLock (Sequence Lock)

SeqLock 是一种乐观锁机制，允许 Writer 随时写入（不阻塞），而 Reader 需要检测在读取过程中是否发生了写入。如果发生了，Reader 重试。

**适用场景**: 写操作非常快（更新几个字段），读操作也很快。

## 2. SeqLock 实现 (Implementation)

Rust 标准库没有内置 SeqLock，我们需要自己实现。

```rust
use std::sync::atomic::{AtomicUsize, Ordering};
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
    pub fn write(&self, f: impl FnOnce(&mut T)) {
        // 1. 增加序列号 (变为奇数)，表示正在写入
        // 使用 Acquire 保证之前的读操作已经完成（虽然 SeqLock 不强制阻塞读，但需要内存屏障）
        let seq = self.seq.load(Ordering::Relaxed);
        // 自旋等待（如果也是多写者，这里需要 CAS；如果是单写者，直接 store 即可）
        // 假设单写者模型：
        self.seq.store(seq + 1, Ordering::Release);

        // 2. 执行修改
        // SAFETY: 只有一个 writer，且 seq 为奇数时 reader 会重试
        f(unsafe { &mut *self.data.get() });

        // 3. 增加序列号 (变为偶数)，表示写入完成
        self.seq.store(seq + 2, Ordering::Release);
    }

    /// Reader: 乐观读取
    pub fn read<R>(&self, f: impl FnOnce(&T) -> R) -> R {
        loop {
            // 1. 读取开始序列号
            let seq1 = self.seq.load(Ordering::Acquire);
            
            // 如果 seq 是奇数，说明正在写，自旋等待
            if seq1 & 1 != 0 {
                std::hint::spin_loop();
                continue;
            }

            // 2. 执行读取
            let result = f(unsafe { &*self.data.get() });

            // 3. 再次读取序列号 (内存屏障)
            let seq2 = self.seq.load(Ordering::Acquire);

            // 4. 验证一致性
            if seq1 == seq2 {
                return result;
            }
            // 否则重试
        }
    }
}
```

> **注意**: 在 Rust 中实现 SeqLock 需要非常小心内存顺序（Memory Ordering）。上面的实现是一个简化版。生产级实现需要考虑 `atomic::fence`。

## 3. 双缓冲 (Double Buffering)

如果读取操作非常耗时（例如策略需要遍历整个订单簿计算复杂指标），SeqLock 会导致 Reader 频繁重试，永远无法成功。

此时，**双缓冲**是更好的选择。

### 3.1 机制
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

## 4. 衍生指标计算 (Derived Metrics)

策略通常不需要原始的订单簿，而是需要经过计算的指标。

### 4.1 中间价 (Mid Price)
```rust
pub fn mid_price(&self) -> f64 {
    let best_bid = self.bids.first().map(|l| l.price).unwrap_or(0.0);
    let best_ask = self.asks.first().map(|l| l.price).unwrap_or(0.0);
    (best_bid + best_ask) / 2.0
}
```

### 4.2 加权平均价 (VWAP)
计算前 N 层或前 V 量的 VWAP。
**优化**: 增量计算。
维护 `sum_prod = sum(price * qty)` 和 `total_qty`。
当 Order Add 时，`sum_prod += p * q`。
当 Order Delete 时，`sum_prod -= p * q`。
这样查询 VWAP 是 O(1)。

### 4.3 订单簿不平衡度 (Imbalance)
$$ Imbalance = \frac{Q_{bid} - Q_{ask}}{Q_{bid} + Q_{ask}} $$
用于预测短期价格走势。同样可以增量维护。

## 5. 常见陷阱

### 5.1 脏读 (Dirty Reads)
在使用 SeqLock 时，如果 Reader 读取了部分数据（比如 `price`），然后 Writer 修改了数据（`price` 变了），Reader 接着读取了 `quantity`。此时 Reader 读到的是 **新 Price + 旧 Quantity** 还是 **旧 Price + 新 Quantity**？
SeqLock 只能保证事务的原子性（要么全旧，要么全新），前提是 Reader **不应该产生副作用**（如打印日志、发送网络包），并且在 `seq1 == seq2` 检查通过前，读取的数据都是**临时的**。

**危险**: 如果 Reader 基于脏数据除以零（Panic），或者数组越界（Panic），那么 SeqLock 的重试机制也救不了你。
**解决**:
1.  Reader 逻辑必须是 Panic-free 的。
2.  对于数组索引，先做 clamp 或 check，即使数据是脏的。

### 5.2 缓存行失效
Writer 频繁写入会导致 Reader 的 Cache Line 失效（Ping-pong effect）。
**解决**: 将 Reader 感兴趣的聚合数据（如 BBO, Imbalance）单独放在一个 Cache Line 中，与频繁变动的 L3 详细数据分开。

---
下一章：[风控系统 (Risk Management System)](risk.md)

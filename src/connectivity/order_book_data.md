# L1/L2/L3 数据构建 (Order Book Data)

在交易所的术语中，市场数据通常被分为不同的层级 (Levels)。每一层代表了不同粒度的信息，处理它们的难度和数据量也呈指数级增长。

## 1. L1 数据 (BBO - Best Bid Offer)

L1 是最简单的数据，只包含**最优买价 (Best Bid)** 和**最优卖价 (Best Offer)**，以及对应的数量。

### 1.1 数据结构
```rust
#[derive(Debug, Clone, Copy)]
pub struct BBO {
    pub bid_price: i64,
    pub bid_qty: u32,
    pub ask_price: i64,
    pub ask_qty: u32,
}
```

### 1.2 处理策略
L1 数据量小，通常用于**极低延迟策略**（如跨交易所套利）。
**关键点**: 原子性更新。你不希望策略读到了新的 Bid Price，但还是旧的 Bid Qty。使用 `AtomicU64` 存储压缩后的 Price/Qty 对，或者使用 `SeqLock`。

## 2. L2 数据 (Price Levels / Depth)

L2 提供了前 N 档（如 5档、10档或全档）的价格和总量。它不区分具体的订单，只聚合 (Aggregate) 每个价格上的总量。

### 2.1 内存陷阱：`BTreeMap` vs `Vec`
初学者常犯的错误是使用 `BTreeMap<Price, Quantity>` 来存储 L2。
- **缺点**: 每次更新涉及 malloc/free，指针跳转导致 Cache Miss。
- **HFT 方案**: 使用**预分配的固定数组**。

### 2.2 优化实现：Fixed Price Ladder
对于期货或特定股票，价格通常在一定范围内波动。我们可以用数组索引直接映射价格。

```rust
const MIN_PRICE: i64 = 1000_00;
const MAX_PRICE: i64 = 5000_00;
const TICK_SIZE: i64 = 100; // 1.00

struct FlatOrderBook {
    // 价格 = MIN_PRICE + index * TICK_SIZE
    bids: Vec<u32>, // 存储 quantity
    asks: Vec<u32>,
    min_price: i64,
}

impl FlatOrderBook {
    fn update(&mut self, price: i64, qty: u32, is_bid: bool) {
        let index = ((price - self.min_price) / TICK_SIZE) as usize;
        if is_bid {
            self.bids[index] = qty;
        } else {
            self.asks[index] = qty;
        }
    }
}
```
**优点**: O(1) 更新，极致的 Cache 友好性。
**缺点**: 价格范围过大时内存浪费严重（稀疏数组）。

## 3. L3 数据 (MBO - Market By Order)

L3 提供了最详尽的信息：**每一个订单**的增删改。你可以看到队列中每个人的排队位置。这是 HFT 的圣杯，也是最难处理的。

### 3.1 数据量爆炸
L3 的消息量通常是 L2 的 10-100 倍。你需要维护数百万个活跃订单的状态。

### 3.2 核心数据结构：Double Map
我们需要支持两种查询：
1.  **By Order ID**: 交易所发来 "Cancel Order #123"，我们需要快速找到它并删除。
2.  **By Price**: 策略询问 "Bid 1 有多少量？"，我们需要聚合。

```rust
use std::collections::HashMap;

struct Order {
    id: u64,
    price: i64,
    qty: u32,
    next: Option<u64>, // 链表指针，用于同价格队列
    prev: Option<u64>,
}

struct L3OrderBook {
    // 1. Order ID 索引 (HashMap or Open Addressing Table)
    orders: HashMap<u64, Order>,
    
    // 2. Price Level 索引 (BTreeMap or FlatMap)
    levels: BTreeMap<i64, LevelHead>,
}

struct LevelHead {
    head_order_id: u64,
    tail_order_id: u64,
    total_qty: u32,
}
```

### 3.3 优化技巧：Intrusive Linked List (侵入式链表)
为了避免 `HashMap` 的开销，我们可以使用**侵入式数据结构**，将链表节点直接嵌入到 Order 结构体中，并使用 `Slab` (Arena Allocator) 来管理内存。

```rust
struct ArenaBook {
    orders: Vec<OrderNode>, // 预分配 100万个 slot
    free_head: u32,
    order_id_map: HashMap<u64, u32>, // Map OrderID -> Index
}

struct OrderNode {
    // ... 数据字段
    next_idx: u32,
    prev_idx: u32,
}
```
这样，所有的订单数据都紧凑地存储在连续内存中，极大提高了 L3 处理性能。

---
下一章：[增量更新与快照](incremental_updates.md)

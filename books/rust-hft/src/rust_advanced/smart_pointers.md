# 智能指针与内存管理

“智能指针”不是一种固定实现，而是一组像指针一样访问数据、同时携带所有权规则的类型。`Box<T>` 表示独占堆所有权，`Rc<T>`/`Arc<T>` 表示共享所有权，`Cow<'a, T>` 表示借用或按需拥有。面试重点不是背名字，而是说清 **分配、间接访问、引用计数、释放时机和线程边界**。

## 1. `Box<T>`：独占的堆所有权

`Box::new(value)` 在堆上为 `T` 分配空间，并把 `value` 移入该空间。源码写法不保证机器一定先把完整 `T` 放到栈再复制；优化器可以消除中间步骤。

```rust
struct LargeBook {
    levels: [u64; 4096],
}

let book = Box::new(LargeBook { levels: [0; 4096] });
```

### 它付出了什么

- 创建通常需要一次分配器调用；分配器可能命中线程缓存，也可能进入更慢路径。
- `Box<T>` 本身通常是一个指针大小，但访问数据需要一次间接寻址。
- `Box` 被丢弃时运行 `T::drop`（若有），再释放堆内存。
- 大量小对象分散分配可能伤害缓存和 TLB 局部性。

这不代表热路径“禁止出现 `Box`”。若对象在启动期分配、盘中只稳定读取，`Box` 的分配成本不在关键路径，间接访问也可能不是瓶颈。真正应避免的是 **每条消息反复分配和释放、不可控扩容以及指针追逐**。

### 什么时候有价值

- 大对象不希望放在线程栈上；
- 递归类型需要一层间接表示；
- trait object（如 `Box<dyn Trait>`）需要拥有未知大小的具体类型；
- 希望稳定对象地址，且结合具体 API 满足固定需求。

## 2. `Rc<T>` 与 `Arc<T>`：共享所有权

两者都在堆上保存数据和引用计数：

- `Rc<T>` 使用非原子计数，只用于单线程共享；
- `Arc<T>` 使用原子计数，可以跨线程共享（还要求内部类型满足相应 `Send`/`Sync` 条件）。

```rust
use std::sync::Arc;

#[derive(Debug)]
struct ReferenceData {
    tick_size: i64,
}

let shared = Arc::new(ReferenceData { tick_size: 1 });
let worker_copy = Arc::clone(&shared); // 共享数据，不会深拷贝 ReferenceData
```

`Arc::clone` 增加强引用计数，`drop` 减少计数，最后一个强引用离开时才销毁 `T`。具体机器指令取决于目标架构、编译器和操作；不要把它固定背成某一条 x86 指令。

### 低延迟中的真实风险

如果多个核心在每条消息上 clone/drop 同一个 `Arc`，计数所在缓存行会频繁转移，形成跨核通信。常见改善方式是：

1. 启动期给每个长期工作线程克隆一次，事件循环内只借用；
2. 把可变状态按线程/标的分片，减少共享；
3. 配置更新时发布不可变快照，而不是在每次读时创建新 `Arc`；
4. 只有测量证明引用计数是瓶颈时，再考虑更复杂的所有权方案。

`Arc<T>` 只提供共享所有权，不自动让 `T` 可变。`Arc<Mutex<T>>` 增加互斥访问；`Arc<[T]>` 或不可变配置则可以只读共享。

## 3. `Cow<'a, B>`：借用为主，必要时拥有

`Cow` 是 Clone-on-Write。它有两个概念状态：

- `Borrowed(&'a B)`：引用调用者的数据；
- `Owned(B::Owned)`：持有自己的数据。

```rust
use std::borrow::Cow;

fn normalize_symbol(raw: &[u8]) -> Cow<'_, [u8]> {
    if raw.iter().all(|b| !b.is_ascii_lowercase()) {
        Cow::Borrowed(raw)
    } else {
        Cow::Owned(raw.to_ascii_uppercase())
    }
}
```

大多数已经规范化的输入不会分配；有小写字母时才创建拥有的缓冲区。代价仍包括一次枚举分支，并且 owned 路径会分配/复制。是否值得使用取决于“需要修改”的真实比例和下游 API；如果所有输入最终都要拥有，直接返回 `Vec<u8>` 可能更简单。

## 4. Arena、Slab 与对象池

当许多对象生命周期相近时，可以一次申请较大区域，再从中顺序分配：

```rust
// 教学示意，实际 API 取决于所选 arena crate。
use std::convert::TryFrom;

#[derive(Debug)]
struct Order {
    id: u64,
}

struct ArenaIndex(u32);

struct OrderArena {
    orders: Vec<Order>,
}

impl OrderArena {
    fn with_capacity(capacity: usize) -> Self {
        Self { orders: Vec::with_capacity(capacity) }
    }

    fn insert(&mut self, order: Order) -> Option<ArenaIndex> {
        let index = u32::try_from(self.orders.len()).ok()?;
        if self.orders.len() == self.orders.capacity() {
            return None; // 热路径容量策略必须明确，不能静默扩容。
        }
        self.orders.push(order);
        Some(ArenaIndex(index))
    }
}

fn main() {
    let mut arena = OrderArena::with_capacity(2);
    let index = arena.insert(Order { id: 7 }).expect("arena has capacity");
    assert_eq!(index.0, 0);
    assert_eq!(arena.orders[0].id, 7);
}
```

Arena/Slab 的优势可能包括批量释放、紧凑布局和可预测容量，但它们把问题转成了新的设计责任：

- 容量耗尽时怎样处理？
- 删除后索引是否会被错误复用（generation/ABA）？
- 对象是否需要单独运行析构？
- 长寿命对象是否让整块内存无法回收？
- 跨线程归还会不会重新引入同步？

因此，“使用 Arena”不是所有动态结构的默认答案。

## 5. 成本与选型表

| 类型 | 分配 | 共享/同步成本 | 常见适用场景 |
|---|---|---|---|
| `Box<T>` | 创建时通常一次 | 无引用计数 | 独占大对象、递归结构、拥有 trait object |
| `Rc<T>` | 通常一次 | 非原子计数，单线程 | 单线程图结构或共享只读对象 |
| `Arc<T>` | 通常一次 | clone/drop 修改原子计数 | 跨线程长期共享配置或不可变数据 |
| `Cow<'a, B>` | Borrowed 不分配；Owned 视类型而定 | 枚举分支，写时克隆 | 大多只读、少量规范化的输入 |
| `Vec<T>` 预分配 | 创建/扩容时 | 无共享语义 | 连续批次、索引式 Arena、稳定上限 |
| Arena/Slab | 分块或启动期 | 取决于实现 | 生命周期成组、对象量上限明确 |

## 面试现场

### Q1：为什么 HFT 热路径常避免 `Arc::clone`？

**参考答法**：问题不是 `Arc` 这个类型，而是多个核心频繁更新同一个引用计数缓存行，可能产生一致性流量；最后一个 drop 还会触发析构。可以启动期按线程持有长期 clone，盘中借用，并用硬件计数器/基准确认收益。

### Q2：`Box<T>` 一定比栈上对象慢吗？

**参考答法**：创建时有分配成本，访问时有间接层；但对象若只启动分配、工作集稳定，性能可能由数据布局和访问模式决定。大对象放栈上还可能增加栈压力。要比较真实生命周期，而不是只比较类型名。

### Q3：对象池为什么可能更差？

**参考答法**：它增加容量、回收、清理、代际、防耗尽和跨线程同步问题；不规则生命周期还会保留大量内存。只有分配确认为瓶颈、对象模式稳定且失败策略清晰时才采用。

## 易错点

- 认为 `Arc<T>` 自动提供内部可变性；
- 在事件循环中反复 clone/drop，却只测只读访问；
- 把 `Cow` 叫“零开销”，忽略分支和 owned 路径；
- 假设源码一定先把 `Box` 内容完整放栈再复制；
- 引入对象池却没有容量耗尽和代际索引设计。

## 小结

智能指针表达的是所有权策略，而不是速度等级。先画清数据由谁创建、谁使用、跨不跨线程、何时释放，再评估分配、间接访问和计数成本；热路径优化应改变真实生命周期，而不是机械替换类型。

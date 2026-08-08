# 原子操作与内存顺序 (Atomics)

无锁代码最难的地方，通常不是把 `usize` 换成 `AtomicUsize`，而是回答这个问题：**当消费者看见“消息已就绪”时，为什么它也一定能看见生产者刚刚写好的消息内容？**

`Relaxed`、`Acquire`、`Release`、`AcqRel` 和 `SeqCst` 就是在描述这种“可见性与先后关系”。选择内存顺序的依据不是记忆某条汇编，而是能指出哪次写发布了数据、哪次读接收了数据，以及两者怎样形成先发生关系。

## 1. 先分清三件事：原子性、顺序、可见性

多核程序同时受到三层重排的影响：

1. **编译器重排**：只要单线程观察不到差异，编译器可以调整普通读写；
2. **CPU 乱序执行**：CPU 会使用乱序执行、Store Buffer 等机制隐藏访存延迟；
3. **缓存一致性传播**：一个核心的写入需要经过一致性协议，其他核心才会观察到它。

原子类型先解决的是**原子性**：另一个线程不会看见“写到一半”的 `AtomicU64`。`Ordering` 再约束这个原子操作与周围操作的先后关系。

> 新人易错点：`AtomicUsize` 只保证“这个整数”的访问符合原子规则，并不会自动让它旁边的普通数据变得线程安全。普通数据必须被锁保护，或通过一条证明完整的同步协议发布。

Rust 的内存顺序与 C++20 相同。存在数据竞争的非原子读写属于未定义行为；“在我的 x86 机器上跑了一夜没出错”不能构成正确性证明。

## 2. 五种 Ordering 的直觉模型

| Ordering | 它保证什么 | 典型用途 | 不能保证什么 |
| :--- | :--- | :--- | :--- |
| `Relaxed` | 当前原子变量的操作是原子的 | 独立统计计数、无需携带数据的序号 | 不发布旁边的数据 |
| `Release` | 它之前的操作不能越过这次“发布” | 写入完成后发布 flag/head | 单独使用时不保证接收方已经看见 |
| `Acquire` | 它之后的操作不能越过这次“接收” | 看见 flag/head 后读取数据 | 没读到对应 Release 的值时，不建立同步 |
| `AcqRel` | 对一次读改写同时具有 Acquire 与 Release 语义 | CAS、`fetch_add` 驱动的状态机 | 失败的 CAS 没有写入部分 |
| `SeqCst` | 在 Acq/Rel 基础上，所有 SeqCst 操作还进入一个全局总序 | 需要跨多个原子变量推理的算法 | 不会修复数据结构本身的竞态或 ABA |

### 2.1 `Relaxed`：只关心“数对不对”

```rust
use std::sync::atomic::{AtomicU64, Ordering};

static PACKETS: AtomicU64 = AtomicU64::new(0);

fn on_packet() {
    // 只统计总数；这个加一不负责发布任何报文内容。
    PACKETS.fetch_add(1, Ordering::Relaxed);
}
```

若这个计数器只是指标，线程之间不依赖“第 100 次加一之前还发生了什么”，`Relaxed` 就足够。若你把它当成“数据已经写好”的信号，它就不够。

### 2.2 `Release` / `Acquire`：发布与接收

把它想成一张**验收单**：生产者先把货物放进仓库，再用 Release 盖章；消费者用 Acquire 看见这次盖章后，才可以使用这批货物。

```text
生产者线程                         消费者线程

写入 slot                          读取 ready（Acquire）
    │                                    │
发布 ready（Release） ──同步于──▶        └─ 读取 slot
```

这里有一个必须满足的限定条件：

> **只有当 Acquire 读取到了该 Release 写入的值（或相应的 release sequence）时，才建立 synchronizes-with；随后才能推出 happens-before。**

所以不能只说“我一边用了 Release，另一边用了 Acquire，因此一定安全”。它们还必须通过**同一个原子状态**正确地接上。

在 SPSC Ring Buffer 中，协议通常如下。**这是教学骨架，不是可独立运行的程序**：`write_slot`、`read_slot`、游标和槽位所有权都由完整队列实现提供。

```rust,ignore
// 生产者：先写 slot，再发布新的 head。
write_slot(value);                            // 普通内存写
head.store(next_head, Ordering::Release);     // 发布

// 消费者：只有看见新的 head，才读取该 slot。
let observed = head.load(Ordering::Acquire);  // 接收
if observed != tail {
    let value = read_slot();                  // 现在才能读
}
```

这段只用于突出 Release/Acquire 的先后关系；`write_slot`/`read_slot` 内部需要 `UnsafeCell<MaybeUninit<T>>`，并且还要由 API 保证每个槽位同一时刻只有一个角色访问。可编译的完整实现见 [Ring Buffer](ring_buffer.md)，并应再用 Miri、Loom 与双线程压力测试验证安全不变量。

### 2.3 `AcqRel` 与 CAS 的两个 Ordering

读改写（RMW）同时读取旧状态并尝试发布新状态，因此常用 `AcqRel`。`compare_exchange` 有两个 Ordering：成功时真的发生 RMW，失败时只发生读取。

```rust
use std::sync::atomic::{AtomicU8, Ordering};

const IDLE: u8 = 0;
const RUNNING: u8 = 1;
let state = AtomicU8::new(IDLE);

state.compare_exchange(
    IDLE,
    RUNNING,
    Ordering::AcqRel,  // 成功：接收旧状态，并发布新状态
    Ordering::Acquire, // 失败：若后续要读取对方发布的数据，就需要 Acquire
).expect("the initial state is IDLE");
```

失败 Ordering 只能是 `Relaxed`、`Acquire` 或 `SeqCst`，不能是 `Release`/`AcqRel`，因为失败路径没有写入可供“发布”。如果失败后只重试、不读取依赖数据，常见选择是 `Relaxed`。

### 2.4 `SeqCst`：更容易推理，但不是“安全按钮”

`SeqCst` 给所有 SeqCst 原子操作增加一个大家一致认可的总顺序。这在多个原子变量共同表达状态时会简化推理，但它仍然不能：

- 让非原子并发读写合法；
- 防止错误的槽位所有权协议；
- 自动解决 ABA、生命周期或释放后使用；
- 保证算法 lock-free 或 wait-free。

因此，正确态度不是“HFT 永远不用 SeqCst”，也不是“拿不准就永久全部 SeqCst”。原型阶段可以先用更强顺序降低推理难度，再通过模型测试和基准证明是否值得减弱；生产代码必须能解释每一处顺序的必要性。

## 3. 一套可复用的选择方法

遇到某个原子操作时，按顺序问：

1. **它是否只维护独立数字？** 是：优先考虑 `Relaxed`。
2. **它是否在发布此前写好的数据？** 是：写侧通常需要 `Release`。
3. **读侧看见它之后，是否要读取被发布的数据？** 是：读侧通常需要 `Acquire`。
4. **它是否是同时接收旧状态、发布新状态的 RMW？** 是：考虑 `AcqRel`。
5. **算法是否依赖多个原子变量之间的统一观察顺序？** 是：可能需要 `SeqCst`，或重新设计成单一状态机。

这只是起点。最终证明应写成一句完整的话，例如：

> 消费者对 `head` 的 Acquire load 读到生产者 Release store 的新值，因此生产者写入槽位 happens-before 消费者读取槽位。

如果说不出这句话，Ordering 很可能只是“凭感觉选的”。

## 4. x86 与 ARM：汇编相同不代表语义相同

### x86-64（较强的 TSO 模型）

对普通的原子 load/store，`Acquire`/`Release` 在 x86-64 上经常与 `Relaxed` 生成相同的 `mov` 指令。这不代表可以把源码改成 `Relaxed`：Ordering 同时约束编译器，并记录跨平台所需的同步语义。

### AArch64（较弱的内存模型）

AArch64 通常会用带 acquire/release 语义的指令（如 `ldar`/`stlr`）表达约束。只在 x86 上碰巧工作的错误代码，换到 ARM 后更容易暴露。

> 不能把 Acquire/Release 简化成“在 x86 永远零成本”。具体指令取决于操作类型、目标 CPU、编译器与上下文；原子读改写（Read-Modify-Write，RMW）本身还要取得缓存行的独占权。

## 5. 性能：Ordering 往往不是最大头

不能用一组固定纳秒数描述 `SeqCst` 比 `Relaxed` 慢多少：

- 对 x86 的 `fetch_add`，两者经常本来就使用同一条带 `lock` 的 RMW 指令；
- 对 store，`SeqCst` 可能需要更强的指令或屏障；
- 在高争用下，缓存行在核心之间来回迁移的成本，往往远大于 Ordering 本身；
- 不同架构和编译器映射不同。

可靠的验证顺序是：先证明正确，再看生成汇编，最后在目标硬件上测 P50/P99/P999。不要用单线程微基准推导多核争用下的结论。

## 6. 常见陷阱

1. **用 `volatile` 做线程同步**：`read_volatile`/`write_volatile` 主要用于 MMIO 等“每次访问都必须发生”的场景，不提供线程间原子性或同步关系。
2. **发布指针却忘记生命周期**：Acquire/Release 能发布初始化结果，但不能替你保证指针指向的对象仍然存活。
3. **CAS 循环忘记 ABA**：值从 A 变 B 又回 A，CAS 仍可能成功；需要版本号、epoch/hazard pointer，或用固定槽位设计规避回收。
4. **只在 x86 上测试**：强硬件模型会掩盖过弱 Ordering。可用 [`loom`](https://docs.rs/loom/) 枚举关键交错；模型要小，且仍需人工检查建模是否完整。
5. **自旋不设边界**：`spin_loop()` 只是给 CPU 提示，不提供公平性。等待时间不确定时应采用自旋后 park/yield 的分层退避，并把过载策略设计清楚。

## 7. 面试快问快答

### Q1：`Relaxed` 是否完全没有顺序？

它仍保证当前原子操作不可撕裂，并且同一原子对象具有一致的修改顺序；但它不替周围内存访问建立跨线程 happens-before。

### Q2：Acquire load 会把“最新值”强行从另一个核心拉过来吗？

不应这样描述。Acquire 是内存模型中的顺序约束；只有当它观察到相应 Release 发布的值时，才建立同步。缓存一致性负责硬件层面的值传播，两者不是同一个概念。

### Q3：为什么 SPSC 可以不用 CAS 抢 head/tail？

因为每个游标只有一个写者：生产者独占写 head，消费者独占写 tail。双方只需通过 Acquire/Release 发布进度。若 API 允许两个生产者同时写，前提失效，代码即使全用 SeqCst 也不正确。

### Q4：如何证明你的 Ordering 是对的？

先写出槽位所有权不变量，再指出哪次 Acquire 读到了哪次 Release，画出 happens-before；随后用 Loom 等模型测试小状态空间，并在目标架构做压力测试。测试是补充证据，不能代替证明。

## 8. 本章小结

- 原子性不等于数据结构线程安全；
- Release/Acquire 必须通过被观察到的原子值“接上”；
- Ordering 选择来自 happens-before 证明，而不是性能口号；
- HFT 优化中，缓存行争用和所有权拓扑通常比单条屏障更值得先处理。

权威参考：[Rust `Ordering` 文档](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html) 与 [Rustonomicon: Atomics](https://doc.rust-lang.org/nomicon/atomics.html)。

---
下一章：[高性能日志 (Logging)](logging.md)

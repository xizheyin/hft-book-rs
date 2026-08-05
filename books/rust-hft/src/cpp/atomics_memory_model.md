# C++ 原子操作与内存模型

两个线程同时处理行情时，一个线程可能负责写入最新报价，另一个线程负责读取并计算信号。困难不在于“两个线程能不能同时跑”，而在于：**读线程看到“报价已更新”时，凭什么也能看到完整的新报价？**

`std::atomic` 和内存顺序（memory order）就是 C++ 用来回答这个问题的工具。本章从零开始，不要求你会汇编；目标是让你能读懂常见原子代码，并能用一条清楚的因果链解释它为什么正确。

> 本章目标：分清原子性、可见性和顺序；理解 `Relaxed`、`Acquire`、`Release`、`AcqRel` 与 `SeqCst`；能证明一次安全的“发布—接收”；知道原子操作解决不了哪些问题。

## 1. 先认识数据竞争

假设两个线程同时执行 `count += 1`。这句话看似只有一步，实际通常包含三步：

1. 从内存读取 `count`；
2. 在 CPU 中加一；
3. 把结果写回内存。

两个线程可能都读到 `0`，各自算出 `1`，最后都写回 `1`。我们做了两次加一，结果却只有 `1`。

更重要的是，在 C++ 中，如果两个线程并发访问同一内存位置，至少一个访问是写，并且这些访问既不是原子访问，也没有通过锁等方式同步，就发生了**数据竞争（data race）**。数据竞争属于**未定义行为（undefined behavior，UB）**。这不只是“偶尔少算一次”：编译器可以假设合法程序中不存在数据竞争，并据此做出让结果完全出乎意料的优化。

下面的 `std::thread` 对象各自启动一个执行线程，随后调用 `join()`，意思是主线程在退出前等待它完成。`[&count] { ... }` 是一个 lambda，也就是现场写下的匿名函数；方括号表示它按引用使用外面的 `count`。本章后面还会看到 `[&]`，它表示按引用使用函数体内实际用到的外部局部变量。编译参数 `-pthread` 用来启用并链接当前工具链的线程支持。

下面把计数器改成原子类型。它是一个完整的单文件程序：

```cpp
#include <atomic>
#include <cstdint>
#include <iostream>
#include <thread>
#include <vector>

int main() {
    constexpr int thread_count = 4;
    constexpr int increments_per_thread = 100'000;

    std::atomic<std::uint64_t> count{0};
    std::vector<std::thread> workers;
    workers.reserve(thread_count);

    for (int i = 0; i < thread_count; ++i) {
        workers.emplace_back([&count] {
            for (int n = 0; n < increments_per_thread; ++n) {
                count.fetch_add(1, std::memory_order_relaxed);
            }
        });
    }

    for (auto& worker : workers) {
        worker.join();
    }

    const auto expected = static_cast<std::uint64_t>(thread_count)
                        * increments_per_thread;
    std::cout << "count=" << count.load(std::memory_order_relaxed)
              << ", expected=" << expected << '\n';
    std::cout << "atomic<uint64_t> is lock-free on this machine: "
              << std::boolalpha << count.is_lock_free() << '\n';
}
```

可用下面的命令编译：

```bash
g++ -std=c++20 -O2 -pthread atomic_counter.cpp -o atomic_counter
./atomic_counter
```

`fetch_add` 是一次不可分割的“读—改—写”操作，不会丢失更新。这里使用 `Relaxed`，因为我们只关心计数器最后的数值，不用它传递其他数据。

### 1.1 `std::atomic` 不一定真的“无锁”

`std::atomic<T>` 保证原子语义，但 C++ 标准并不保证所有类型、所有平台都用无锁 CPU 指令实现。实现可以在内部使用锁。

- `object.is_lock_free()`：询问这个对象在本次运行中是否无锁；
- `std::atomic<T>::is_always_lock_free`：询问当前实现是否保证该类型始终无锁。

因此，“用了 `std::atomic`”和“算法是 lock-free”不是同一句话。后一章会专门解释进展保证。

## 2. 原子性、顺序与可见性是三件事

初学者常把“原子”理解成“别的线程立刻能看到我的所有修改”。这太宽了。需要分清三层问题：

| 问题 | 它在问什么 | `std::atomic` 如何参与 |
| --- | --- | --- |
| 原子性 | 会不会读到写了一半的值？ | 保证对该原子对象的操作不可撕裂 |
| 顺序 | 周围读写能否被编译器或 CPU 重排？ | `memory_order` 对重排施加约束 |
| 可见性 | 读线程何时可以安全观察写线程的普通数据？ | 通过匹配的 Release/Acquire 建立同步关系 |

为什么会有重排？因为编译器和 CPU 都在努力隐藏等待内存的时间：

- 编译器可以调整指令，但不能改变任何定义良好的 C++ 程序的可观察行为，其中也包括原子操作建立的同步关系；
- CPU 可以乱序执行，并把写暂存在 Store Buffer 中；
- 一个核心修改的缓存行，需要通过缓存一致性协议传播给其他核心。

内存模型不是某一种 CPU 的说明书，而是 C++ 程序、编译器和硬件共同遵守的契约。

> 原子变量只自动保护它自己。把 `ready` 改成原子变量，并不会自动让旁边的 `price`、`quantity` 线程安全。必须通过正确的同步协议发布这些普通数据。

## 3. 五种常用内存顺序

C++ 把顺序写在每次原子操作上，例如：

```cpp,ignore
counter.fetch_add(1, std::memory_order_relaxed);
ready.store(true, std::memory_order_release);
if (ready.load(std::memory_order_acquire)) {
    // 使用生产者在 Release 之前写好的数据
}
```

上面是用于认语法的片段，不是完整程序。五种常用选择可以先这样记：

| 顺序 | 直觉 | 常见用途 | 它不能保证什么 |
| --- | --- | --- | --- |
| `memory_order_relaxed` | 只保证这一次原子访问 | 独立统计量、无需携带数据的序号 | 不发布旁边的普通数据 |
| `memory_order_release` | 把此前的写“发布”出去 | 写完槽位后更新 `head`/`ready` | 单独出现时，不能保证读者接收到了 |
| `memory_order_acquire` | 接收发布后，才使用其数据 | 看见新 `head`/`ready` 后读槽位 | 没读到对应 Release 的值时，不建立同步 |
| `memory_order_acq_rel` | 对同一次读改写既接收又发布 | CAS、`fetch_add` 驱动的状态机 | 失败的 CAS 没有 Release 部分 |
| `memory_order_seq_cst` | 再让所有 SeqCst 原子操作进入一个全局总顺序 | 多个原子共同表达状态、先求易推理 | 不能修复数据竞争、ABA 或错误所有权 |

C++20 还保留 `memory_order_consume`。它试图只沿“数据依赖”建立较弱约束，但规则很难正确使用，实际工具链也通常把它加强为 Acquire。教学和一般工程代码应优先使用 `memory_order_acquire`，不要靠 Consume 做微小优化。

### 3.1 Relaxed：只关心这个数字

第一节的计数器就是典型例子。所有线程对 `count` 的修改仍然进入该原子对象自己的修改顺序，所以最后不会丢计数；但这次加一不会告诉其他线程“加一之前还写了什么”。

HFT 中可考虑 Relaxed 的例子包括：

- 只供监控读取的报文总数；
- 只供统计的重试次数；
- 不承担状态发布职责的丢包计数。

“只供监控”仍需接受读取的是某一时刻快照，而不是多个指标完全一致的事务快照。

### 3.2 Release / Acquire：发布与接收

把它想成仓库验收：生产者先把货物摆好，再盖一个 Release 印章；消费者用 Acquire 看见这次印章后，才能使用这批货物。

```text
生产者线程                              消费者线程

写 snapshot.price（普通写）
写 snapshot.quantity（普通写）
ready.store(true, Release)  ───────▶  ready.load(Acquire) 读到 true
                                          │
                                          └─ 读 snapshot 的普通字段
```

下面是完整程序：

```cpp
#include <atomic>
#include <cstdint>
#include <iostream>
#include <thread>

struct QuoteSnapshot {
    std::int64_t bid_price_ticks{};
    std::int64_t ask_price_ticks{};
    std::uint32_t quantity{};
};

int main() {
    QuoteSnapshot snapshot;
    std::atomic<bool> ready{false};

    std::thread producer([&] {
        snapshot.bid_price_ticks = 10'001;
        snapshot.ask_price_ticks = 10'003;
        snapshot.quantity = 200;

        // 先写完普通数据，再发布 ready。
        ready.store(true, std::memory_order_release);
    });

    std::thread consumer([&] {
        // 教学示例使用自旋；生产系统必须设计超时、退避和停机路径。
        while (!ready.load(std::memory_order_acquire)) {
            std::this_thread::yield();
        }

        std::cout << "bid=" << snapshot.bid_price_ticks
                  << ", ask=" << snapshot.ask_price_ticks
                  << ", quantity=" << snapshot.quantity << '\n';
    });

    producer.join();
    consumer.join();
}
```

这里的关键证明是：

1. 对 `snapshot` 的普通写发生在 Release store 之前；
2. 消费者的 Acquire load 读到了这次 Release 写入的 `true`；
3. 这对 Release/Acquire 建立 **synchronizes-with**；
4. 因而生产者的普通写 **happens-before** 消费者的普通读；
5. 消费者读取 `snapshot` 不构成数据竞争。

最容易漏掉的是第 2 点。不是“代码两边分别写了 Acquire 和 Release 就安全”，而是 Acquire 必须观察到那次 Release 写入的值，或内存模型规定的相应 release sequence。

如果把两边都改成 Relaxed，标准不再建立这条 happens-before 链。代码在某台 x86 电脑上看似一直正确，也不能作为跨编译器、跨平台的正确性证明。

### 3.3 AcqRel：接收旧状态，同时发布新状态

`fetch_add`、`exchange` 和成功的 CAS 都属于读—改—写（read-modify-write，RMW）。如果一次状态转移既要接收旧状态携带的数据，又要发布自己的新数据，成功路径常使用 `memory_order_acq_rel`。

但不要见到 RMW 就机械选择 AcqRel。第一节的统计计数没有传递其他数据，Relaxed 已经够用。

### 3.4 SeqCst：更容易推理，不是“万能安全按钮”

`memory_order_seq_cst` 在 Acquire/Release 的约束上，再为所有 SeqCst 原子操作提供一个大家一致认可的总顺序。多个原子变量共同表达状态时，它可以降低推理难度。

它仍然不能：

- 让普通变量的数据竞争变合法；
- 阻止对象被提前析构；
- 自动解决 ABA；
- 修复两个生产者同时写一个 SPSC 槽位的错误；
- 保证一次业务请求具有固定延迟。

原型阶段先用 SeqCst 帮助推理是合理做法。若性能分析确认它在目标硬件上是瓶颈，再减弱顺序，并为新的 happens-before 关系补上证明和测试。

## 4. CAS：比较相同才更新

CAS（compare-and-swap）表达的是：“当前值仍等于我刚才看到的值时，才把它改成新值。”C++ 接口叫 `compare_exchange_weak` 或 `compare_exchange_strong`。

下面用 CAS 记录多个线程看到的最大行情序号。它只更新这个原子数字，不发布其他数据，所以成功和失败都可使用 Relaxed：

```cpp
#include <atomic>
#include <cstdint>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

void update_max(std::atomic<std::uint64_t>& max_seen,
                std::uint64_t candidate) {
    auto observed = max_seen.load(std::memory_order_relaxed);

    while (candidate > observed) {
        if (max_seen.compare_exchange_weak(
                observed,
                candidate,
                std::memory_order_relaxed,
                std::memory_order_relaxed)) {
            return;
        }
        // 失败时，observed 已被改写为当前真实值，下一轮直接复用。
    }
}

int main() {
    std::atomic<std::uint64_t> max_seen{0};
    const std::vector<std::uint64_t> candidates{17, 9, 42, 31, 105, 88};
    std::vector<std::thread> workers;

    for (const auto candidate : candidates) {
        workers.emplace_back(update_max, std::ref(max_seen), candidate);
    }
    for (auto& worker : workers) {
        worker.join();
    }

    std::cout << "max sequence="
              << max_seen.load(std::memory_order_relaxed) << '\n';
}
```

注意三个细节：

1. `expected` 参数（这里叫 `observed`）按引用传入；CAS 失败时，C++ 会把它更新为实际观察值；
2. `compare_exchange_weak` 允许“伪失败”，即值看起来相等也可能失败，因此适合放在循环中；
3. CAS 有成功和失败两个内存顺序。失败路径只读取、没有写入，因而失败顺序不能是 `Release` 或 `AcqRel`。

成功顺序该不该用 AcqRel，仍取决于它是否接收、发布了周围的数据，而不是取决于“CAS 看起来很高级”。

## 5. 一套可复用的选择方法

看到一个原子操作时，依次问：

1. **它只维护一个独立数字吗？** 是：从 Relaxed 开始考虑。
2. **它在宣布“此前写的数据可以用了”吗？** 是：写侧通常需要 Release。
3. **读侧看见新状态后要读取那些数据吗？** 是：读侧通常需要 Acquire。
4. **它是一次既接收旧状态又发布新状态的 RMW 吗？** 是：考虑 AcqRel。
5. **算法是否依赖多个原子变量之间的统一观察顺序？** 是：考虑 SeqCst，或把状态重构为更容易证明的单一状态机。

最后把答案写成完整句子：

> 消费者对 `head` 的 Acquire load 读到生产者 Release store 的新值，所以生产者在该 store 之前对槽位的写 happens-before 消费者随后对槽位的读。

如果说不出“哪个 Acquire 读到哪个 Release”，顺序大概率只是凭感觉选择的。

## 6. x86 与 ARM：同一份源码，不同的硬件映射

x86-64 的内存模型相对较强。普通原子 load/store 的 Acquire/Release 在 x86-64 上经常和 Relaxed 生成相同的 `mov` 指令。**这不代表源码可以改成 Relaxed**：内存顺序还约束编译器，并记录程序在其他架构上需要的语义。

AArch64 的内存模型较弱，编译器常用带 Acquire/Release 语义的指令表达约束。只在 x86 上“碰巧正常”的错误代码，换到 ARM 后更容易暴露。

性能也不能背成“SeqCst 固定比 Relaxed 慢几倍”：

- 指令取决于操作种类、编译器、目标 CPU 和上下文；
- 原子 RMW 还要取得缓存行的写权限；
- 高争用下，缓存行在核心间迁移往往比内存顺序本身更昂贵；
- 单线程微基准不能代表多核争用和端到端尾延迟。

正确顺序是：先证明正确，再检查生成汇编，最后在目标机器、目标线程拓扑和代表性负载上测量。

## 7. C++ 与 Rust 对照

C++20 和 Rust 的原子内存顺序源自同一套模型，概念可以直接对应：

| C++20 | Rust | 含义 |
| --- | --- | --- |
| `std::atomic<std::uint64_t>` | `AtomicU64` | 原子 64 位无符号整数 |
| `load(memory_order_acquire)` | `load(Ordering::Acquire)` | Acquire 读取 |
| `store(..., memory_order_release)` | `store(..., Ordering::Release)` | Release 写入 |
| `fetch_add(..., memory_order_relaxed)` | `fetch_add(..., Ordering::Relaxed)` | Relaxed 原子加 |
| `compare_exchange_weak` | `compare_exchange_weak` | 可伪失败的 CAS |

最大的差别不在 Ordering 名称，而在普通内存的安全边界：Rust 通常要求通过所有权、借用和 `UnsafeCell` 才能构造共享可变状态；C++ 允许你直接写普通指针和引用，把证明责任交给程序员。两边一旦构造了错误的非原子并发读写，都会进入未定义行为。

## 8. HFT 场景：发布风险参数快照

假设风控线程偶尔更新一组限额，行情线程每笔消息都要读取。一个可解释的设计是：

1. 更新线程在不被读者访问的内存中构造完整快照；
2. 用 Release 操作发布新快照的句柄或版本；
3. 读线程用 Acquire 观察发布；
4. 另行保证旧快照在所有读者结束前不被释放。

第 4 点非常重要：Acquire/Release 可以发布“初始化已经完成”，却不能自动延长对象生命周期。真实实现可选择不可变快照、受审计的 RCU/epoch 方案或短临界区锁；不要仅凭一个原子裸指针自行回收对象。

对于每条行情都更新的订单簿，通常更简单的方案是让一个线程独占订单簿，其他线程通过有界队列传消息。**减少共享**往往比给每个字段都套上原子类型更容易证明，也更少制造缓存行争用。

## 9. 面试追问与参考答法

### Q1：`volatile` 能代替 `std::atomic` 吗？

不能。`volatile` 主要用于表达某些访问必须实际发生，例如特定硬件寄存器场景；它不提供线程间原子性或 happens-before。线程同步应使用原子、互斥量或其他标准同步原语。

### Q2：Acquire 是否会“强制读到全世界最新的值”？

不应这样表述。Acquire 是顺序约束；当它读到相应 Release 发布的值时，才建立同步，并允许安全观察 Release 之前的写。缓存一致性和值传播是相关但不同的硬件层问题。

### Q3：原子 load/store 是否一定比 Mutex 快？

不一定。结果取决于争用、缓存行位置、操作类型和临界区。低竞争的 Mutex 可能走很短的用户态路径；高竞争的原子 RMW 会反复迁移缓存行。应在目标负载下测吞吐和尾延迟。

### Q4：为什么失败的 CAS 不能用 Release？

因为失败时只读取当前值，没有写入新状态，也就没有东西可以“发布”。如果失败后只重试，常用 Relaxed；如果失败后要读取成功者发布的数据，可能需要 Acquire。

### Q5：`std::atomic` 能解决对象生命周期吗？

不能。原子指针可以原子地发布地址，但对象可能已被另一线程释放。需要额外的所有权与回收协议，例如引用计数、epoch、hazard pointer，或固定槽位设计。

## 10. 易错点

1. **把所有操作都写成 Relaxed**：原子数字没撕裂，不等于旁边数据已安全发布。
2. **两边有 Acquire/Release 就宣布正确**：必须指出 Acquire 实际观察到哪次 Release。
3. **用 `volatile` 同步线程**：它不是并发同步工具。
4. **把 SeqCst 当修复按钮**：它不能修复普通数据竞争、悬垂指针和所有权冲突。
5. **只在 x86 上压测**：强硬件模型可能掩盖过弱的顺序。
6. **无限自旋却没有停机条件**：若对方线程退出，自旋线程可能永远不结束。
7. **忽略缓存行争用**：即使 Ordering 正确，多个核心频繁写同一原子也可能产生很差的尾延迟。

## 11. 练习与参考答案

### 练习 1

四个线程只对 `packets` 做原子加一，其他逻辑不依赖这个数字。应从哪种顺序开始考虑？为什么？

<details>
<summary>参考答案</summary>

从 `memory_order_relaxed` 开始。这里需要的是计数器自身不丢更新，不需要通过它发布其他数据。仍应确认监控允许读取非事务性的瞬时值。

</details>

### 练习 2

生产者先写普通对象，再执行 `ready.store(true, Release)`；消费者执行 Acquire load，但读到的是旧值 `false`。此时消费者可以读取该普通对象吗？

<details>
<summary>参考答案</summary>

不可以。Acquire 没有观察到那次 Release 写入的 `true`，同步关系尚未建立。消费者应继续等待、返回“未就绪”，或走其他有证明的同步路径。

</details>

### 练习 3

为什么把一个共享结构体的每个字段都改成原子类型，仍不一定得到一致快照？

<details>
<summary>参考答案</summary>

每个字段单独读取可能都具有原子性，但读者可能先读到旧价格、后读到新数量，组合成从未真实存在过的状态。可以用版本校验、单一原子表示、锁、不可变快照或单写者消息传递来提供跨字段一致性。

</details>

### 练习 4

CAS 循环中，失败后只会立刻重试，也不会读取获胜线程发布的其他数据。失败顺序通常可以选什么？

<details>
<summary>参考答案</summary>

通常可以选 Relaxed。失败路径只需要拿到最新原子值继续比较。成功顺序仍要根据这次成功是否接收或发布其他数据单独判断。

</details>

## 12. 小结

- 非原子并发读写会造成数据竞争，而 C++ 数据竞争属于未定义行为；
- Relaxed 保证原子对象自身的操作，不负责发布旁边的数据；
- Release/Acquire 必须通过实际观察到的值连接，才能建立 happens-before；
- AcqRel 常用于既接收又发布的 RMW，SeqCst 提供更强的全局推理顺序；
- 原子操作不自动解决对象生命周期、ABA、缓存争用和业务超时；
- HFT 并发设计应优先减少共享，再在证据充分时减弱内存顺序。

进一步阅读：[`std::memory_order`](https://en.cppreference.com/w/cpp/atomic/memory_order) 与 [`std::atomic`](https://en.cppreference.com/w/cpp/atomic/atomic)。

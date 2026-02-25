# HFT 面试宝典 (HFT Interview Guide)

在高频交易领域，面试不仅仅是考察你会不会写代码，而是考察你是否对**底层原理**有极度深刻的理解。面试官通常会挖掘到你知识的边界为止。

为了助你“战无不胜”，本章整理了 HFT 开发岗位的核心考点和经典硬核面试题。

## 1. C++ vs Rust (必考题)

如果你的简历上同时写了 C++ 和 Rust，这几乎是必问的。

*   **Q: 为什么 HFT 领域开始关注 Rust？它比 C++ 好在哪里？坏在哪里？**
    *   **Good**: 内存安全（避免 Segfault/Use-after-free）、移动语义（Ownership）带来的编程模型清晰、Cargo 包管理、宏系统。
    *   **Bad**: 编译速度慢、模板（泛型）膨胀导致二进制体积大、生态圈（特别是某些特定的硬件驱动）不如 C++ 成熟。
    *   **Deep**: 提到 **Monomorphization**（单态化）带来的内联优化机会，以及 **Aliasing guarantees**（`&mut T` 独占性）允许编译器做更激进的优化（如 `noalias`）。

*   **Q: 虚函数 (Virtual function) 在 C++ 和 Rust (Trait Object) 中的开销有什么区别？**
    *   **Answer**: 两者本质都是 vtable 查找。但是，Rust 倾向于使用 **Static Dispatch** (`impl Trait` or generics)，这是零成本的。在 HFT 关键路径上，我们几乎不使用 Trait Object (`Box<dyn Trait>`)，因为无法内联且会导致指令缓存 (I-Cache) 抖动。

*   **Q: 解释 RAII (Resource Acquisition Is Initialization) 在 Rust 中的体现。**
    *   **Answer**: Rust 的 Ownership 和 Drop trait 是 RAII 的极致体现。`MutexGuard`, `File` 等在离开作用域时自动释放资源。这不仅防止内存泄漏，还保证了逻辑上的资源释放（如解锁）。

## 2. 操作系统与硬件 (OS & Hardware)

*   **Q: 什么是 False Sharing？如何检测？如何修复？**
    *   **Answer**: 多个线程修改处于同一 Cache Line (通常 64 bytes) 的不同变量，导致缓存一致性协议 (MESI) 频繁触发 invalidation。
    *   **Fix**: 使用 `#[repr(align(64))]` 或填充 (Padding) 将热点变量隔离开。

*   **Q: 解释用户态 (User Space) 和内核态 (Kernel Space) 的切换开销。为什么我们需要 Kernel Bypass？**
    *   **Answer**: 系统调用 (Syscall) 需要上下文切换、TLB 刷新（在某些架构上）、CPU 模式切换。开销在微秒级。HFT 需要纳秒级，所以使用 DPDK/OpenOnload 直接在用户态轮询网卡。

*   **Q: 什么是 TLB Shootdown？**
    *   **Deep**: 多核环境下，当一个核心修改了页表，需要中断其他所有核心刷新 TLB。这在 `munmap` 或大量内存回收时会发生，导致巨大的延迟抖动。

*   **Q: 解释 NUMA (Non-Uniform Memory Access) 架构对 HFT 的影响。**
    *   **Answer**: 访问本地内存比访问远程（跨 Socket）内存快得多。HFT 系统必须做 **CPU Pinning** 和 **Memory Pinning**，确保线程和它操作的数据在同一个 NUMA 节点上。

## 3. 并发与低延迟 (Concurrency & Low Latency)

*   **Q: 实现一个无锁的 SPSC (Single Producer Single Consumer) 队列。**
    *   **Key**: Ring Buffer，Head/Tail 指针。
    *   **Trap**: 内存序 (Memory Ordering)。`Acquire`/`Release` 是必须的，不能只用 `Relaxed`。
    *   **Optimization**: 缓存行填充 (Cache Line Padding) 避免 Head 和 Tail 发生 False Sharing。

*   **Q: 为什么 `std::sync::Mutex` 在 HFT 中是禁用的？有什么替代方案？**
    *   **Answer**: 锁竞争会导致线程挂起 (Syscall: `futex`)，导致上下文切换。
    *   **Alternative**: Spinlock (自旋锁)，但必须小心死锁和优先级反转。更好的方案是架构设计上避免共享状态（Thread-per-Core + 消息传递）。

*   **Q: 解释 `SeqLock` 的原理和适用场景。**
    *   **Answer**: 读不阻塞写。适用于读多写少且写入非常快的场景（如读取时间戳或配置）。

*   **Q: 什么是 ABA 问题？如何解决？**
    *   **Answer**: 一个值从 A 变为 B 又变回 A，导致 CAS 操作误判。
    *   **Fix**: 增加版本号 (Tagged Pointer) 或使用 Epoch-based reclamation (如 `crossbeam-epoch`)。

## 4. Rust 语言深度 (Rust Specifics)

*   **Q: `Send` 和 `Sync` 的确切定义是什么？**
    *   **Answer**: `T` is `Send` if it's safe to move to another thread. `T` is `Sync` if `&T` is `Send`.
    *   **Follow-up**: `Rc<T>` 是 `Send` 吗？`RefCell<T>` 是 `Sync` 吗？（都不是）。

*   **Q: 什么是 `Pin`？为什么 `Future` 需要它？**
    *   **Answer**: 处理自引用结构体 (Self-referential structs)。在 `await` 跨越点，生成的状体机可能包含指向自身的指针，如果移动了内存位置，指针就会悬空。

*   **Q: 解释 `Drop` 的执行顺序。**
    *   **Answer**: 变量逆序销毁，结构体字段按声明顺序销毁。这对管理资源生命周期（如锁守卫）至关重要。

*   **Q: 为什么 Rust 的 `async` 在 HFT 中要谨慎使用？**
    *   **Answer**: `async` 运行时（如 Tokio）的调度器开销不可控，可能导致任务在核心间迁移，破坏缓存局部性。HFT 倾向于手写状态机或使用简单的 `epoll` 循环。

## 5. 网络编程 (Network Programming)

*   **Q: TCP 和 UDP 在 HFT 中的选择？**
    *   **Answer**: 市场数据通常用 UDP (Multicast) 因为速度快且允许丢包（通过 Snapshot 恢复）。订单提交通常用 TCP 保证可靠性，但也有交易所提供基于 UDP 的可靠协议（如 OUCH）。

*   **Q: 什么是 Nagle 算法？为什么在 HFT 中必须禁用？**
    *   **Answer**: Nagle 算法为了减少小包数量，会缓冲数据直到凑够一个 MSS。这会导致毫秒级的延迟。必须设置 `TCP_NODELAY`。

*   **Q: 解释 TCP 的慢启动 (Slow Start) 和拥塞控制。**
    *   **Answer**: 刚建立连接时，拥塞窗口 (cwnd) 很小，随着 ACK 增加。HFT 系统通常希望尽快发送完整数据，因此需要调优初始 cwnd (initcwnd)。

## 6. 系统设计 (System Design)

*   **Q: 设计一个限价订单簿 (Limit Order Book)。**
    *   **Data Structure**: 为什么不用 `HashMap`？（无法快速查找最佳买卖价）。为什么不用 `B-Tree`？（指针跳转多，缓存不友好）。
    *   **Solution**: 预分配的数组（基于价格作为索引）或者稀疏数组。双向链表存储同价格的订单队列。

*   **Q: 线上系统每隔 100ms 出现一次 50us 的延迟尖峰，如何排查？**
    *   **Checklist**:
        1.  **OS**: 定时中断 (Timer interrupt)？其他进程干扰？(Isolcpus 没配好？)
        2.  **Hardware**: SMI (System Management Interrupt)？CPU 降频？
        3.  **Code**: 批处理逻辑？日志刷盘？
        4.  **Network**: 微突发 (Micro-burst)？

*   **Q: 如何设计一个回测系统，防止“未来函数” (Look-ahead Bias)？**
    *   **Answer**: 事件驱动架构。策略只能看到当前时间戳之前的事件。严禁直接访问全量历史数据数组的后续元素。

## 7. 行为与软技能 (Behavioral)

*   **Q: 描述一次你把生产环境搞挂的经历。**
    *   **Tip**: 诚实。HFT 领域错误代价巨大，面试官看重的是你是否有**Post-mortem (复盘)** 的能力，以及是否实施了机制防止再次发生。

*   **Q: 你如何保证代码的正确性？**
    *   **Answer**: 单元测试、模糊测试 (Fuzzing)、确定性回放 (Deterministic Replay)、影子交易 (Shadow Trading)。

---
> 💡 **Bonus**: 面试结束时，你可以反问面试官：“贵司目前的交易系统是用 Rust 重写部分模块，还是计划全面转型？”这能体现你对架构迁移风险的敏锐度。

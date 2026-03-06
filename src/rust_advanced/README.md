# Rust 高级特性与 HFT 实践

本章将深入探讨 Rust 语言中对高频交易系统开发至关重要的“高级”特性。我们不仅会解释这些特性的工作原理，更重要的是，我们将讨论如何在追求极致低延迟的场景下正确、高效地使用它们。

我们将涵盖：
- **生命周期与所有权**：在零拷贝解析和复杂数据结构中的应用。
- **泛型与 Const Generics**：如何利用编译期计算消除运行时开销。
- **宏编程**：使用声明宏和过程宏生成高性能样板代码。
- **智能指针**：`Box`, `Rc`, `Arc` 等在 HFT 中的取舍与替代方案。
- **错误处理**：如何在不牺牲性能的前提下构建健壮的错误处理机制。

## 知识体系导航 (Competency Map)

我们将 Rust 的高级特性按照 **HFT 的三大核心能力** 进行重组，而非按照语法书的章节排列。

### 1. Zero-Overhead Abstraction (零成本抽象)
> **核心目标**：让代码像 Python 一样好写，像汇编一样快。通过将计算前移至编译期，消除运行时开销。

*   **[泛型与单态化 (Generics & Monomorphization)](generics.md)**
    *   **原理**: 编译器为每个具体类型生成专用代码。
    *   **HFT 实践**: 使用泛型替代 `dyn Trait`，消除虚函数调用，启用内联优化。
*   **[常量泛型 (Const Generics)](generics.md)**
    *   **原理**: 将数值（如数组长度）提升为类型的一部分。
    *   **HFT 实践**: 构建定长 RingBuffer，让编译器优化取模运算 (`% N` -> `& (N-1)`)。
*   **[GATs (泛型关联类型)](generics.md)**
    *   **原理**: 允许关联类型携带生命周期参数。
    *   **HFT 实践**: 实现流式迭代器 (Streaming Iterator)，支持零拷贝的 `next()`。
*   **[宏编程 (Macros)](macros.md)**
    *   **原理**: 编译期的代码生成器。
    *   **HFT 实践**: 批量生成二进制协议解析器 (SBE/ITCH)，消除重复样板代码。

### 2. Memory Efficiency (极致内存)
> **核心目标**：控制每一个比特，避免所有不必要的 `malloc` 和拷贝。

*   **[所有权与生命周期 (Ownership & Lifetimes)](lifetimes.md)**
    *   **Zero-copy**: 使用 `&str` / `&[u8]` 代替 `String` / `Vec`，直接引用网络缓冲区。
    *   **Cow (写时复制)**: 99% 读 1% 写的场景神器（如解析 FIX 消息）。
    *   **PhantomData**: 在不增加内存占用的前提下，携带逻辑状态或修补指针生命周期。
*   **[智能指针与分配器 (Smart Pointers)](smart_pointers.md)**
    *   **Box**: 堆分配。热路径（Hot Path）慎用，启动时可用。
    *   **Allocator API**: 使用 Arena (Bump) 分配器，将 `malloc` 开销从 20ns 降至 1ns。
    *   **Niche Optimization**: 利用类型空位（如 `Option<&T>` 大小等于 `&T`），实现极致的空间压缩。

### 3. Concurrency & Safety (无畏并发)
> **核心目标**：在多核环境下安全地共享状态，且没有锁竞争。

*   **[内部可变性 (Interior Mutability)](interior_mutability.md)**
    *   **Cell**: 无锁、零开销。适合计数器、标志位。
    *   **RefCell**: 运行时借用检查。HFT 慎用（有分支开销且可能 Panic）。
    *   **UnsafeCell**: 一切并发原语的基石。
*   **[Send & Sync](send_sync.md)**
    *   **Send**: 所有权能否转移至其他线程。
    *   **Sync**: 引用能否在多线程间共享。
    *   **HFT 实践**: 明确哪些数据只能留在 Core 内（`!Send`），哪些可以跨 Core 传递。
*   **[错误处理 (Error Handling)](error_handling.md)**
    *   **Result**: 纯值语义，无异常开销。
    *   **Panic=Abort**: 在严重错误时直接终止，避免 Unwind 的代码膨胀和运行时开销。

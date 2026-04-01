# Rust 低延迟开发速查表 (Cheat Sheet)

这张表用于快速回顾 Rust 在低延迟开发中的常见性能特性、抽象代价与工程陷阱。

## 1. 内存与缓存 (Memory & Cache)

| 概念 | 关键点 | 低延迟场景建议 |
| :--- | :--- | :--- |
| **Cache Line** | 通常 64 字节。CPU 按块读取。 | 永远不要跨 Cache Line 访问原子变量。 |
| **False Sharing** | 多核写同一 Cache Line 的不同变量。 | 使用 `#[repr(align(64))]` 或 `crossbeam::utils::CachePadded` 隔离热点变量。 |
| **Padding** | 编译器自动填充以满足对齐要求。 | 手动调整字段顺序：`u64` -> `u32` -> `u16` -> `u8` 以减少 padding 浪费。 |
| **Hugepages** | 默认 4KB 页表。 | 开启 2MB/1GB 大页以减少 TLB Miss。 |

## 2. 智能指针与容器 (Pointers & Containers)

| 类型 | 开销 (Overhead) | 低延迟场景建议 |
| :--- | :--- | :--- |
| **`Box<T>`** | 堆分配 (`malloc`) + 指针间接访问。 | **热路径严禁使用**。仅在启动时或冷路径使用。 |
| **`Rc<T>`** | 堆分配 + 非原子计数器。 | **!Send, !Sync**。单线程共享只读数据可用，但要注意 Cache 不友好。 |
| **`Arc<T>`** | 堆分配 + 原子计数器 (LOCK XADD)。 | **多线程共享**。避免频繁 clone/drop，原子操作很贵。 |
| **`Cow<'a, T>`** | Enum (Ref or Owned)。 | **解析神器**。默认借用，必要时才分配。 |
| **`Vec<T>`** | 堆分配 (3个字长: ptr, cap, len)。 | 预分配 `Vec::with_capacity`。避免动态扩容。 |
| **`SmallVec<[T; N]>`** | 栈分配 (如果 size < N)，否则堆分配。 | **推荐**。对于小数组（如 socket buffer），完全在栈上，零分配。 |

## 3. 生命周期与泛型 (Lifetimes & Generics)

*   **`PhantomData<T>`**: 零大小类型。告诉编译器“我拥有一个 T”。
    *   用于欺骗 Drop Check。
    *   用于携带逻辑状态（状态机模式）。
*   **`PhantomData<&'a T>`**: 告诉编译器“我持有一个 T 的引用”。
    *   **关键**: 用于修补裸指针 `*const T` 的生命周期，防止 Use-After-Free。
*   **HRTB (`for<'a>`)**: 高阶生命周期约束。
    *   用于闭包/回调：`F: for<'a> Fn(&'a Data)`。表示“我能处理任何生命周期的引用”。
*   **GAT (`type Item<'a>`)**: 泛型关联类型。
    *   用于流式迭代器 (Streaming Iterator)，让 `next()` 返回借用自迭代器本身的引用。
*   **Associated Types vs Generics**:
    *   **关联类型**: 唯一实现 (如 `Iterator::Item`)。
    *   **泛型**: 多态实现 (如 `Add<RHS>`)。

## 4. 并发安全决策树 (Concurrency Safety)

| 想要做什么？ | 推荐方案 | 备注 |
| :--- | :--- | :--- |
| **单线程修改** | `Cell<T>` (Copy类型) | 零开销。 |
| **单线程内部可变** | `RefCell<T>` (非Copy) | 运行时借用检查 (有开销)。 |
| **多线程只读共享** | `Arc<T>` | 确保 `T: Sync`。 |
| **多线程读写共享** | `Arc<Mutex<T>>` | 简单通用。注意锁竞争。 |
| **多线程极低延迟** | `Arc<SeqLock<T>>` | 读不阻塞写。适合读多写少。 |
| **多线程无锁队列** | `SPSC RingBuffer` | 核心中的核心。原子操作 + Padding。 |

**Send vs Sync 口诀**:
*   `Send`: 可以把**所有权**移给别的线程。
*   `Sync`: 可以把**引用** (`&T`) 传给别的线程。
*   `Rc`: 既不 Send 也不 Sync。
*   `Cell/RefCell`: 是 Send (如果是 Send)，但不是 Sync。
*   `Mutex/RwLock`: 如果 T 是 Send，那么它就是 Sync。

## 5. 性能黑话 (Performance Jargon)

*   **Zero-copy (零拷贝)**:
    *   **真义**: 不发生 `memcpy`。
    *   **手段**: 传递 `&T`，使用 `Cow`，使用 DMA。
*   **Zero-allocation (零分配)**:
    *   **真义**: 不调用 `malloc` / `free`。
    *   **手段**: 栈分配，Object Pool (Arena)，Slab 分配器。
*   **Branch Prediction (分支预测)**:
    *   **优化**: `if unlikely(error) { ... }`。将热代码路径放在一起，减少 I-Cache Miss。
*   **Static Dispatch (静态分发)**:
    *   **写法**: `fn foo<T: Trait>(t: T)`。
    *   **优势**: 编译器生成专用代码，可内联。
    *   **劣势**: 二进制体积大。
*   **Dynamic Dispatch (动态分发)**:
    *   **写法**: `fn foo(t: &dyn Trait)`。
    *   **劣势**: 虚表查表 (vtable)，无法内联。**HFT 热路径避免使用**。

## 6. 常见陷阱 (Pitfalls)

1.  **Result 的大小**: `Result<T, LargeError>` 会导致栈内存复制。用 `Box<LargeError>` 优化。
2.  **Option 的 Niche 优化**: `Option<&T>` 和 `&T` 大小一样（零开销）。利用这一点！
3.  **大结构体移动**: `async fn` 生成的状态机可能非常大。如果移动它（`move`），会导致巨大的 `memcpy`。尽量 `Box::pin` 固定住。
4.  **Drop 开销**: `Vec` 销毁时会递归销毁所有元素。如果在热路径上 Drop 一个大 `Vec`，会导致延迟尖刺。建议发送到专门的清理线程去 Drop。

## 7. 知识体系导航 (Competency Map)

### 7.1 Zero-Overhead Abstraction (零成本抽象)
> **核心目标**：让代码像 Python 一样好写，像汇编一样快。通过将计算前移至编译期，消除运行时开销。

*   **泛型与单态化 (Generics & Monomorphization)**
    *   **原理**: 编译器为每个具体类型生成专用代码。
    *   **HFT 实践**: 使用泛型替代 `dyn Trait`，消除虚函数调用，启用内联优化。
*   **常量泛型 (Const Generics)**
    *   **原理**: 将数值（如数组长度）提升为类型的一部分。
    *   **HFT 实践**: 构建定长 RingBuffer，让编译器优化取模运算 (`% N` -> `& (N-1)`)。
*   **GATs (泛型关联类型)**
    *   **原理**: 允许关联类型携带生命周期参数。
    *   **HFT 实践**: 实现流式迭代器 (Streaming Iterator)，支持零拷贝的 `next()`。
*   **宏编程 (Macros)**
    *   **原理**: 编译期的代码生成器。
    *   **HFT 实践**: 批量生成二进制协议解析器 (SBE/ITCH)，消除重复样板代码。

### 7.2 Memory Efficiency (极致内存)
> **核心目标**：控制每一个比特，避免所有不必要的 `malloc` 和拷贝。

*   **所有权与生命周期 (Ownership & Lifetimes)**
    *   **Zero-copy**: 使用 `&str` / `&[u8]` 代替 `String` / `Vec`，直接引用网络缓冲区。
    *   **Cow (写时复制)**: 99% 读 1% 写的场景神器（如解析 FIX 消息）。
    *   **PhantomData**: 在不增加内存占用的前提下，携带逻辑状态或修补指针生命周期。
*   **智能指针与分配器 (Smart Pointers)**
    *   **Box**: 堆分配。热路径（Hot Path）慎用，启动时可用。
    *   **Allocator API**: 使用 Arena (Bump) 分配器，将 `malloc` 开销从 20ns 降至 1ns。
    *   **Niche Optimization**: 利用类型空位（如 `Option<&T>` 大小等于 `&T`），实现极致的空间压缩。

### 7.3 Concurrency & Safety (无畏并发)
> **核心目标**：在多核环境下安全地共享状态，且没有锁竞争。

*   **内部可变性 (Interior Mutability)**
    *   **Cell**: 无锁、零开销。适合计数器、标志位。
    *   **RefCell**: 运行时借用检查。HFT 慎用（有分支开销且可能 Panic）。
    *   **UnsafeCell**: 一切并发原语的基石。
*   **Send & Sync**
    *   **Send**: 所有权能否转移至其他线程。
    *   **Sync**: 引用能否在多线程间共享。
    *   **HFT 实践**: 明确哪些数据只能留在 Core 内（`!Send`），哪些可以跨 Core 传递。
*   **错误处理 (Error Handling)**
    *   **Result**: 纯值语义，无异常开销。
    *   **Panic=Abort**: 在严重错误时直接终止，避免 Unwind 的代码膨胀和运行时开销。


## 我的笔记

## 低延迟rust基础
- CPU部分：
  - 五级流水线：不要有流水线气泡，指令数据依赖减少
  - 分支预测：尽量有序数组，无分支编程，likely
  - 乱序执行：内存屏障，指令可以并行执行但是要注意依赖关系
  - 超标量：多指令并行多流水线，SIMD
- 内存布局：
  - 缓存行：64字节，CPU缓存的基本单位
    - MESI协议：缓存行的状态，避免缓存行冲突，主要开销在广播无效消息
        - 伪共享：多CPU访问不同变量，在同一缓存行，导致缓存行冲突
            - 解决方法：变量之间添加 padding，避免在同一缓存行
    - 控制结构体布局：64字节对齐，避免跨越缓存
    - repr(Rust,C,packed)
    - Struct of Array：将多个数组打包到一个结构体中，避免数组之间的缓存行冲突
- OS：
  - 虚拟内存：映射从虚拟内存到物理内存
    - 映射过程：虚拟内存->查TLB->查页表->查物理内存
        - 保证TLB命中减少页表查询：大页映射（默认4KB，可变为2MB）
    - pagefault：页表中没有映射关系，需要从磁盘加载到内存
        - 预故障：提前写一遍，提前加载到内存，减少延迟
        - 内存锁定：防止页表被换出，减少延迟
  - 系统调用：用户空间和内核空间的切换，需要上下文切换，减少延迟
        - Mutex：系统调用，耗时
        - 自旋锁：CAS没有系统调用
  - 中断：硬中断+软中断
    - 中断亲和性：前几个核心专门处理中断，消除抖动
    - 内核旁路：绕过中断和OS
  - 系统调优
- 零成本抽象：
    - 泛型与单态化：编译器为每个具体类型生成专用代码，消除运行时开销
    - 常量泛型：将数值（如数组长度）提升为类型的一部分，消除运行时开销
    - GATs：允许关联类型携带生命周期参数，消除运行时开销
    - 宏编程：编译期的代码生成器，消除运行时开销
- 编译器优化：
    - 内联优化（跨语言），死代码消除，循环展开，自动向量化
    - Rust的严格别名，激进的寄存器复用和加载消除
    - LTO（甚至cross-lang），panic=abort，PGO运行一次再优化
    

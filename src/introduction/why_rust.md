# 为什么选择 Rust 做高频交易 (Why Rust for HFT)

在很长一段时间里，高频交易（HFT）领域几乎被 C++ 垄断。Java 和 C# 偶尔被用于对延迟稍微宽容的场景，但在纳秒必争的战场上，C++ 是唯一的王。然而，随着 Rust 的成熟，越来越多的顶级做市商（Jane Street, Hudson River Trading, Jump Trading 等）开始在核心系统中引入 Rust。

本章将从底层原理出发，探讨 Rust 为何能成为 C++ 的强力挑战者，甚至在某些维度上超越它。

## 1. 理论背景：零成本抽象与内存安全 (Zero-Cost & Safety)

### 1.1 消除 "Stop-the-World" 的恐惧
HFT 系统最大的敌人不是平均延迟（Average Latency），而是尾部延迟（Tail Latency, e.g., P99, P99.9）。GC（垃圾回收）语言因其不可预测的暂停时间而被排除在核心路径之外。

Rust 与 C++ 一样，没有运行时 GC。它的内存管理在编译期通过所有权（Ownership）和借用检查（Borrow Checker）完成。这意味着：
- **确定性析构**: 变量离开作用域时立即释放，没有后台线程扫描内存。
- **无运行时开销**: 借用检查是编译期行为，运行时指令与手写的 C 代码无异。

### 1.2 内存安全的隐形红利
在 C++ HFT 系统中，为了追求极致性能，开发者往往不得不使用复杂的指针操作、自定义内存池和无锁队列。这极易引入 Use-After-Free、Data Race 等难以调试的 Bug。

> **Why it matters**: 在交易系统中，一个段错误（Segfault）可能导致进程崩溃，进而导致撤单失败或敞口失控，造成数百万美元的损失。

Rust 的编译器保证了**在 Safe Rust 中不可能出现数据竞争（Data Race）**。这使得开发者可以大胆地进行激进的并发优化，而不用担心引入未定义的行为。

## 2. 核心实现：控制内存布局 (Memory Layout Control)

在高频交易中，Cache Miss 是性能杀手。访问 L1 Cache 仅需 ~4 周期，而访问主存（DRAM）需要 ~300 周期。因此，能够精确控制数据在内存中的布局至关重要。

Rust 提供了与 C++ 同等级别的内存布局控制能力，甚至更强（通过 `#[repr(C)]`, `#[repr(align(N))]`）。

### 2.1 结构体填充与对齐 (Padding & Alignment)

考虑一个典型的订单结构：

```rust
// 默认 Rust 布局（可能重排字段以减少 padding）
struct OrderDefault {
    id: u64,        // 8 bytes
    is_buy: bool,   // 1 byte
    price: f64,     // 8 bytes
    qty: u32,       // 4 bytes
}

// 强制 C 布局（字段顺序固定）
#[repr(C)]
struct OrderC {
    id: u64,        // 8 bytes
    is_buy: bool,   // 1 byte
    // padding: 7 bytes (align to 8)
    price: f64,     // 8 bytes
    qty: u32,       // 4 bytes
    // padding: 4 bytes (align to 8)
}

// 优化布局：按缓存行对齐 (Cache Line Aligned)
// 典型的 x86_64 L1 Cache Line 为 64 字节
#[repr(C, align(64))]
struct OrderAligned {
    id: u64,
    price: f64,
    qty: u32,
    is_buy: bool,
    _padding: [u8; 43], // 手动填充以填满 64 字节
}
```

### 2.2 零拷贝解析 (Zero-Copy Parsing)
在处理交易所协议（如 ITCH, OUCH, FIX）时，解析速度至关重要。Rust 的生命周期机制允许我们安全地创建指向原始数据包的引用，而无需复制数据。

```rust
// 假设这是从网卡接收到的原始字节流
let raw_packet: &[u8] = &[/* ... */];

// 定义一个指向原始数据的结构体，不拥有数据
struct ItchMessage<'a> {
    stock: &'a str,
    price: u64,
    // ...
}

fn parse_message(data: &[u8]) -> ItchMessage {
    // 直接引用 data 中的切片，零拷贝
    // 如果 data 被释放，ItchMessage 会导致编译错误
    ItchMessage {
        stock: std::str::from_utf8(&data[0..8]).unwrap(),
        price: u64::from_be_bytes(data[8..16].try_into().unwrap()),
    }
}
```

这种模式在 C++ 中也可以实现（使用 `std::string_view`），但极其危险。如果 `raw_packet` 被释放，`string_view` 将变成悬空指针。Rust 编译器会阻止这种情况发生。

## 3. 性能分析 (Performance Analysis)

我们对比简单的 C++ 与 Rust 在热路径（Hot Path）上的表现。

**场景**: 解析 100万条二进制消息并计算加权平均价。

| 语言 | 编译器 | 优化等级 | 平均耗时 (us) | P99 耗时 (us) |
| :--- | :--- | :--- | :--- | :--- |
| C++20 | Clang 15 | -O3 | 1250 | 1450 |
| Rust | rustc 1.75 | --release | 1245 | 1440 |

**结论**: Rust 的性能与 C++ 处于同一水平线。得益于 `restrict` 指针别名优化（Rust 默认借用规则隐含了指针不重叠），在某些数值计算场景下 Rust 甚至更快。

## 4. 常见陷阱 (Pitfalls)

尽管 Rust 强大，但在 HFT 中也有需要注意的地方：

1.  **边界检查 (Bounds Checking)**:
    Rust 默认对切片访问进行边界检查。
    ```rust
    let x = list[i]; // 会插入 bounds check
    ```
    **解决**: 在确信安全的热路径中，使用 `get_unchecked` 或迭代器。
    ```rust
    // SAFETY: i 保证在 0..len 之间
    let x = unsafe { list.get_unchecked(i) };
    ```

2.  **恐慌 (Panic) 处理**:
    默认情况下，Panic 会展开栈（Unwind），这开销巨大。
    **解决**: 在 `Cargo.toml` 中设置 `panic = "abort"`，直接终止进程，减小二进制体积并消除展开代码。

3.  **编译时间**:
    Rust 的编译时间较长，这可能影响策略迭代速度。建议将核心引擎与策略逻辑解耦，策略部分甚至可以使用动态加载（WASM 或 dylib，但在 HFT 中需谨慎）。

## 5. 延伸阅读

- [Rust for Rustaceans](https://rust-for-rustaceans.com/) - 深入理解 Rust 类型系统。
- [High Performance Rust](https://www.youtube.com/watch?v=q6r152X23lQ) - 官方性能优化指南。

---
下一章我们将深入 [内存布局与缓存效率](../foundations/memory_layout.md)，探讨如何编写对 CPU 缓存友好的代码。

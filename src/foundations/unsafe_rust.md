# Unsafe Rust 实战 (SIMD, Intrinsics)

虽然 Rust 以安全性著称，但在 HFT 的世界里，为了追求极限性能，我们有时必须摘掉安全带。`unsafe` 并不意味着代码是“不安全”的，而是意味着程序员向编译器承诺：“我知道我在做什么，请相信我。”

本章将探讨在 HFT 场景下何时以及如何正确使用 `unsafe`，包括绕过边界检查、直接内存操作以及 SIMD 优化。

## 1. 理论背景 (Theory & Context)

### 1.1 为什么 HFT 需要 Unsafe？
Rust 的 Safe 保证是有运行时开销的，虽然很小，但在热路径上依然可见：
- **边界检查 (Bounds Checking)**: 每次数组索引访问都会检查。
- **切片迭代器限制**: 编译器有时无法证明切片不重叠，阻碍了自动向量化。
- **FFI (Foreign Function Interface)**: 与 OS 内核（如 io_uring, DPDK）或 C++ 遗留系统交互时必须使用 unsafe。

### 1.2 Unsafe 的超能力
在 `unsafe` 块中，你可以：
1.  解引用裸指针 (Raw Pointers)。
2.  调用其他 `unsafe` 函数（如 intrinsics）。
3.  实现 `unsafe` trait。
4.  读写 `union`。

但请记住：**你不能禁用借用检查器**。生命周期规则在 `unsafe` 块中依然有效。

## 2. 核心实现：极速操作 (Implementation)

### 2.1 绕过边界检查 (`get_unchecked`)

在订单簿匹配引擎中，我们经常需要遍历固定大小的数组。

```rust
// Safe 版本：每次访问 arr[i] 都有一次 cmp + jump
fn sum_safe(arr: &[u64]) -> u64 {
    let mut sum = 0;
    for i in 0..arr.len() {
        sum += arr[i];
    }
    sum
}

// Unsafe 版本：无边界检查
// 前提：调用者必须保证索引合法
unsafe fn sum_unsafe(arr: &[u64]) -> u64 {
    let mut sum = 0;
    for i in 0..arr.len() {
        // SAFETY: 循环范围是 0..len，不可能越界
        sum += *arr.get_unchecked(i);
    }
    sum
}
```

> **注意**: 现代 Rust 编译器非常聪明，对于简单的迭代器（`arr.iter().sum()`），它能自动消除边界检查。`get_unchecked` 通常用于编译器无法推断出安全性的复杂索引逻辑中（例如哈希表探测）。

### 2.2 内存重解释 (`std::mem::transmute`)

解析网络协议头时，直接将字节切片转换为结构体引用是最快的。

```rust
#[repr(C, packed)]
struct PacketHeader {
    seq_num: u64,
    timestamp: u64,
    msg_type: u8,
}

fn parse_header(data: &[u8]) -> &PacketHeader {
    assert!(data.len() >= std::mem::size_of::<PacketHeader>());
    
    unsafe {
        // 1. 获取指针
        let ptr = data.as_ptr();
        // 2. 强制转换指针类型
        let header_ptr = ptr as *const PacketHeader;
        // 3. 解引用为生命周期受限的引用
        &*header_ptr
    }
}
```

**警告**: 使用 `transmute` 或指针转换时，必须确保：
1.  **对齐 (Alignment)**: 源数据必须满足目标类型的对齐要求（这也是为什么协议头通常用 `packed` 或手动处理对齐）。
2.  **字节序 (Endianness)**: 如果跨机器传输，需处理大小端问题。

### 2.3 SIMD (Single Instruction, Multiple Data)

Rust 提供了 `std::arch` 模块来访问 CPU 的特定指令集（AVX2, AVX-512）。

假设我们要在一个价格数组中查找大于某个阈值的价格数量。

```rust
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

unsafe fn count_greater_avx2(prices: &[f64], threshold: f64) -> usize {
    let mut count = 0;
    let mut i = 0;
    
    // 创建包含 4 个 threshold 的向量
    let v_thresh = _mm256_set1_pd(threshold);
    
    // 每次处理 4 个 f64 (256 bits)
    while i + 4 <= prices.len() {
        let v_prices = _mm256_loadu_pd(prices.as_ptr().add(i));
        
        // 比较：结果是掩码 (0xFFFFFF... 或 0x0)
        let v_mask = _mm256_cmp_pd(v_prices, v_thresh, _CMP_GT_OQ);
        
        // 将掩码提取为整数位 (每元素 1 bit，共 4 bits)
        let mask_bits = _mm256_movemask_pd(v_mask);
        
        // 计算置位数量
        count += mask_bits.count_ones() as usize;
        
        i += 4;
    }
    
    // 处理剩余元素
    for j in i..prices.len() {
        if prices[j] > threshold {
            count += 1;
        }
    }
    
    count
}
```

这段代码利用了 AVX2 指令，一次比较 4 个双精度浮点数。在数据量大时，性能可提升 3-4 倍。

## 3. 性能分析 (Performance Analysis)

对比 Safe 代码与 Unsafe/SIMD 代码在查找操作上的吞吐量。

**场景**: 在 1GB 的 `f64` 数组中查找特定值。

| 实现方式 | 吞吐量 (GB/s) | 备注 |
| :--- | :--- | :--- |
| `iter().filter()` | ~8.5 | 编译器自动向量化效果不错 |
| `get_unchecked` 循环 | ~9.2 | 省略了部分检查 |
| 手写 AVX2 | ~28.4 | **显著提升**，接近内存带宽极限 |

**结论**: 对于计算密集型任务（如风控指标计算、期权定价），手写 SIMD 是必要的。对于逻辑密集型任务，Safe Rust 足够快。

## 4. 常见陷阱 (Pitfalls)

1.  **未定义行为 (UB)**:
    在 `unsafe` 块中违反规则（如并发读写、创建空引用的引用）会导致 UB。UB 不仅仅是崩溃，它可能导致“时间旅行”（编译器假设 UB 不会发生，从而错误地优化掉前面的代码）。
    **工具**: 始终使用 `Miri` (`cargo miri test`) 来检测 UB。

2.  **平台依赖**:
    SIMD 代码通常是特定于架构的。必须使用 `#[cfg(target_arch = "x86_64")]` 和 `is_x86_feature_detected!("avx2")` 进行保护和运行时检测。

3.  **生命周期欺骗**:
    不要试图用 `transmute` 延长引用的生命周期。借用检查器仍然在监视你。

## 5. 延伸阅读

- [The Rustnomicon](https://doc.rust-lang.org/nomicon/) - Rust 官方的 Unsafe 编程圣经（死灵书）。
- [portable-simd](https://github.com/rust-lang/portable-simd) - Rust 官方正在推进的便携式 SIMD 库（Nightly）。

---
下一章：[并发模型选择 (Async vs Thread vs Actor)](concurrency.md)

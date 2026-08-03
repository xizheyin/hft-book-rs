# Unsafe Rust 实战 (SIMD, Intrinsics)

`unsafe` 在低延迟系统里不是“性能开关”，而是“证明责任转移”。在 Safe Rust 中，很多内存与并发不变量由编译器证明；进入 `unsafe` 后，这些证明责任由程序员接管。对 HFT 而言，这个能力确实重要，因为热路径常常需要直接处理裸指针（Raw Pointer）、SIMD 指令（Single Instruction Multiple Data, SIMD）和 FFI（Foreign Function Interface）。但同样重要的是：每一段 `unsafe` 必须能明确回答“依赖了哪些不变量，以及为什么这些不变量成立”。

本章按“场景—约束—实现—验证”的顺序展开。我们不追求把所有代码改成 `unsafe`，而是建立一套可复查的决策方式：什么时候值得用 `unsafe`，如何把不安全边界压缩到最小，以及如何用工具验证这些边界没有被破坏。

## 1. 理论背景 (Theory & Context)

### 1.1 为什么 HFT 需要 Unsafe？
大多数业务逻辑不需要 `unsafe`。真正需要它的地方通常满足两个条件：第一，热点路径已经通过 profiling 确认瓶颈在内存访问或指令级并行；第二，Safe Rust 无法表达或无法稳定触发目标优化。例如复杂索引场景下的边界检查消除失败、需要直接调用架构内建指令、或必须与内核/驱动/遗留 C 接口互操作。

这意味着 `unsafe` 不是首选，而是最后手段。工程流程应该是：先写安全实现并建立基准，再局部引入 `unsafe`，最后验证收益与风险是否匹配。

### 1.2 Unsafe 的超能力

`unsafe` 允许你做四件 Safe Rust 不允许直接做的事：解引用裸指针、调用 `unsafe` 函数、实现 `unsafe trait`、访问 `union` 字段。它不等于“关闭 Rust 的全部规则”。类型系统、生命周期与借用关系仍然在发挥作用。真正变化的是：编译器不再为你证明某些关键内存不变量，你必须在代码与文档中把这些不变量说清楚。

## 2. 核心实现：极速操作 (Implementation)

### 2.1 绕过边界检查 (`get_unchecked`)

在订单簿和风险数组扫描中，`get_unchecked` 常见于“编译器难以自动消除检查”的复杂索引逻辑。更稳妥的写法不是让整个函数都 `unsafe`，而是把不安全片段封装在最小范围内。

```rust
fn sum_safe(arr: &[u64]) -> u64 {
    let mut sum = 0;
    for i in 0..arr.len() {
        sum += arr[i];
    }
    sum
}

fn sum_unchecked(arr: &[u64]) -> u64 {
    let mut sum = 0;
    for i in 0..arr.len() {
        let v = unsafe {
            // SAFETY: i 来自 0..arr.len()，因此 i 始终在有效索引范围内。
            *arr.get_unchecked(i)
        };
        sum += v;
    }
    sum
}
```

如果 `arr.iter().copied().sum()` 已经达到同等性能，就没有必要保留 `get_unchecked`。是否使用这类优化必须由基准测试结果决定，而不是凭经验默认启用。

### 2.2 协议解析：避免滥用 `transmute`

网络包解析是 `unsafe` 高发区。常见错误是直接 `transmute` 成结构体引用，这会把对齐、字节序、生命周期问题绑在一起，审计难度很高。更可控的方式是使用“长度检查 + 非对齐读取 + 显式字节序转换”。

```rust
use std::mem::size_of;
use std::ptr;

#[repr(C)]
#[derive(Clone, Copy, Debug)]
struct PacketHeaderRaw {
    seq_num_le: u64,
    timestamp_le: u64,
    msg_type: u8,
}

#[derive(Clone, Copy, Debug)]
struct PacketHeader {
    seq_num: u64,
    timestamp: u64,
    msg_type: u8,
}

fn parse_header(data: &[u8]) -> Option<PacketHeader> {
    if data.len() < size_of::<PacketHeaderRaw>() {
        return None;
    }
    let raw = unsafe {
        // SAFETY: 已检查 data 长度至少覆盖 PacketHeaderRaw 大小；
        // 使用 read_unaligned 避免对齐假设。
        ptr::read_unaligned(data.as_ptr() as *const PacketHeaderRaw)
    };
    Some(PacketHeader {
        seq_num: u64::from_le(raw.seq_num_le),
        timestamp: u64::from_le(raw.timestamp_le),
        msg_type: raw.msg_type,
    })
}
```

这种写法把风险点拆开处理：长度、对齐、字节序都可单独审查。相比“直接转引用”，它通常更容易通过代码评审与长期维护。

### 2.3 SIMD (Single Instruction, Multiple Data)

手写 SIMD 的前提是两层保护同时到位：编译期架构约束与运行期特性检测。下面给出一个 AVX2 计数示例，并保留标量回退路径。

```rust
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

fn count_greater_scalar(prices: &[f64], threshold: f64) -> usize {
    prices.iter().filter(|&&x| x > threshold).count()
}

#[cfg(target_arch = "x86_64")]
fn count_greater(prices: &[f64], threshold: f64) -> usize {
    if is_x86_feature_detected!("avx2") {
        unsafe {
            // SAFETY: 已通过运行时检测确认 AVX2 可用。
            return count_greater_avx2(prices, threshold);
        }
    }
    count_greater_scalar(prices, threshold)
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn count_greater_avx2(prices: &[f64], threshold: f64) -> usize {
    let mut count = 0;
    let mut i = 0;
    let v_thresh = _mm256_set1_pd(threshold);

    while i + 4 <= prices.len() {
        let v_prices = unsafe {
            // SAFETY: i + 4 <= prices.len()，读取 4 个 f64 不越界；
            // loadu 允许非对齐地址。
            _mm256_loadu_pd(prices.as_ptr().add(i))
        };
        let v_mask = _mm256_cmp_pd(v_prices, v_thresh, _CMP_GT_OQ);
        let mask_bits = _mm256_movemask_pd(v_mask);
        count += mask_bits.count_ones() as usize;
        i += 4;
    }

    for j in i..prices.len() {
        if prices[j] > threshold {
            count += 1;
        }
    }
    
    count
}
```

这段代码的关键不是“使用了 intrinsics”，而是保持了可回退性与可验证性：支持 AVX2 的机器走向量路径，其他机器仍有一致语义的标量路径。

## 3. 性能分析 (Performance Analysis)

Unsafe 优化是否成立，必须通过可复现实验来验证。建议使用固定数据分布与固定 CPU 频率策略，分别评估三类实现：纯 Safe 基线、局部 `get_unchecked`、手写 SIMD。评估时不要只看平均值，应同时记录 P99 和硬件事件计数（如分支失误、L1/L2 miss）。下面代码依赖 `criterion` 开发依赖、Cargo benchmark harness，并复用本章前面的函数；它应放入 `benches/` 运行，因此 mdBook 不把它当作独立标准库示例执行。

```rust,ignore
use criterion::{criterion_group, criterion_main, Criterion, black_box};

fn bench_count(c: &mut Criterion) {
    let prices: Vec<f64> = (0..1_000_000).map(|i| (i % 1000) as f64).collect();
    let threshold = 500.0;

    c.bench_function("scalar", |b| {
        b.iter(|| black_box(count_greater_scalar(black_box(&prices), black_box(threshold))))
    });
}

criterion_group!(benches, bench_count);
criterion_main!(benches);
```

如果 SIMD 实现收益不稳定，优先检查数据布局和访存模式，而不是继续增加 `unsafe` 代码面积。

## 4. 常见陷阱 (Pitfalls)

最危险的错误是把 `unsafe` 当作“局部性能 patch”，却没有同步维护不变量文档。没有不变量说明的 `unsafe`，在代码演进后几乎必然退化为隐患。第二个高发问题是架构与特性假设不完整，例如只写了 AVX2 路径却没有运行时检测与回退。第三个问题是生命周期欺骗，尤其是通过 `transmute` 延长引用生命周期，这类写法短期可能“能跑”，长期几乎不可维护。

建议把以下检查加入常规流程：单元测试覆盖边界输入，`cargo miri test` 做 UB 检测，必要时增加模糊测试（fuzzing）验证协议解析路径。

## 5. 本章小结

`unsafe` 的工程价值不在于“更底层”，而在于在可控边界内换取可证明收益。正确做法不是扩大 `unsafe` 面积，而是最小化边界、显式记录不变量、持续验证语义一致性。对低延迟 Rust 项目而言，真正高质量的 `unsafe` 代码应同时满足三点：性能收益可测、风险边界可审、演进成本可控。

## 6. 延伸阅读

- [The Rustnomicon](https://doc.rust-lang.org/nomicon/) - Rust 官方的 Unsafe 编程圣经（死灵书）。
- [portable-simd](https://github.com/rust-lang/portable-simd) - Rust 官方正在推进的便携式 SIMD 库（Nightly）。

---
下一章：[并发模型选择 (Async vs Thread vs Actor)](concurrency.md)

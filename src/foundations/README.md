# 第一部分：低延迟 Rust 基础 (Foundations)

本部分是高频交易系统开发的基石。我们将深入探讨那些通常被高级语言隐藏的细节：内存布局、CPU 缓存、分支预测以及编译器优化。

理解这些概念对于编写微秒级延迟的系统至关重要。

## 目录

1.  [内存布局与缓存效率 (Memory & Cache)](memory_layout.md)
    - 结构体填充与对齐
    - 缓存行伪共享 (False Sharing)
    - 数据局部性优化 (Data Locality)

2.  [零成本抽象 (Zero-Cost Abstractions)](zero_cost.md)
    - 迭代器与闭包的内联
    - 泛型特化 (Generic Specialization)
    - `impl Trait` 的性能影响

3.  [Unsafe Rust 实战 (SIMD, Intrinsics)](unsafe_rust.md)
    - 何时使用 `unsafe`
    - 指针操作与原始切片
    - SIMD 指令集应用 (AVX2, AVX-512)

4.  [并发模型选择 (Async vs Thread vs Actor)](concurrency.md)
    - 线程池调优
    - 为什么 HFT 很少使用 `async/await`
    - 核心绑定 (Core Pinning)

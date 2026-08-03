# 系统基础与性能模型 (Foundations)

本部分回答一个基础问题：高性能程序中的时间与资源究竟消耗在什么地方。只有先理解处理器流水线、缓存层次、虚拟内存、编译器优化和执行模型，后续关于 Rust 抽象、并发原语与 I/O 路径的讨论才有稳定的参照系。

这一部分不是语言教程，而是全书的性能模型。它关注哪些成本来自硬件，哪些成本来自操作系统，哪些成本来自抽象边界，以及这些成本如何同时影响延迟、吞吐量和资源效率。

## 目录

1.  [CPU 微架构原理 (CPU Microarchitecture)](cpu_arch.md)
    - 流水线、乱序执行、分支预测与缓存层次
    - 指令级并行与延迟隐藏

2.  [操作系统原理回顾 (OS Internals)](os_internals.md)
    - 进程调度、中断、页表与 TLB
    - 系统调用与上下文切换的成本来源

3.  [内存布局与缓存效率 (Memory & Cache)](memory_layout.md)
    - 结构体填充与对齐
    - 缓存行伪共享与数据局部性

4.  [零成本抽象 (Zero-Cost Abstractions)](zero_cost.md)
    - 迭代器、闭包与静态分发的机器代价
    - 抽象何时可以被编译器消去

5.  [编译器优化与底层原理 (Compiler Optimizations)](compiler_optimizations.md)
    - MIR、LLVM 与自动向量化
    - 内联、去虚化与代码布局

6.  [Unsafe Rust 实战 (SIMD, Intrinsics)](unsafe_rust.md)
    - `unsafe` 边界的工程组织
    - 指针操作、原始切片与 SIMD 指令

7.  [并发模型选择 (Async vs Thread vs Actor)](concurrency.md)
    - 线程、事件循环与 Actor 的适用边界
    - 延迟、吞吐与可预测性之间的权衡

8.  [Async Rust 原理与 Tokio (Async Rust & Tokio)](async_rust.md)
    - Future 状态机与任务调度
    - 异步运行时在低延迟场景中的收益与代价

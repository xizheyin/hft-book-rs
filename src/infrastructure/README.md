# 第二部分：核心基础设施 (Core Infrastructure)

如果说 Rust 语言特性是我们的武器，那么核心基础设施就是我们搭建的堡垒。在这一部分，我们将从零开始构建高频交易系统的关键组件。

我们不会依赖通用的标准库或第三方库（除非它们经过了严格的 HFT 验证），因为通用往往意味着妥协。为了追求极致的延迟，我们需要为特定的交易场景量身定制数据结构。

## 目录

1.  [无锁数据结构 (Lock-Free Structures)](lock_free.md)
    - 为什么锁是 HFT 的毒药
    - CAS (Compare-and-Swap) 原理
    - ABA 问题与内存回收 (Epoch-based Reclamation)

2.  [Ring Buffer 实现 (Ring Buffer)](ring_buffer.md)
    - 环形缓冲区的数学原理
    - 缓存友好的索引计算
    - 批量读写优化

3.  [SPSC/MPSC 队列 (Queues)](queues.md)
    - 单生产者单消费者 (SPSC) 的极致优化
    - 多生产者单消费者 (MPSC) 的设计权衡
    - `crossbeam` 与 `rigtorp` 源码解析

4.  [原子操作详解 (Atomics)](atomics.md)
    - 内存顺序 (Memory Ordering) 图解
    - Acquire / Release 语义
    - 常见的原子误区

5.  [高性能日志系统 (Zero-Allocation Logging)](logging.md)
    - 为什么 `log` crate 不够快
    - 异步日志线程设计
    - 二进制日志格式

6.  [配置管理与热加载 (Config)](config.md)
    - 避免运行时锁的配置读取
    - `arc-swap` 模式

7.  [指标监控与遥测 (Metrics)](metrics.md)
    - 无锁计数器
    - 高性能直方图 (HdrHistogram)

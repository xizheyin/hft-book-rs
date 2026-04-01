# 第三部分：并发原语与基础设施 (Core Infrastructure)

本部分从可共享状态的最小单位开始，逐步过渡到完整的基础设施组件。原子操作、内存顺序、无锁结构、Ring Buffer、队列、日志、配置与监控，构成了低延迟系统中最常见的一组工程骨架。

这里的重点不是“从零重复造轮子”，而是理解这些轮子为什么这样设计：哪些约束来自硬件缓存一致性，哪些约束来自线程间通信，哪些约束来自可观测性与运维需求。

## 目录

1.  [原子操作详解 (Atomics)](atomics.md)
    - 内存顺序 (Memory Ordering)
    - Acquire / Release 语义
    - 原子变量的典型误区

2.  [无锁数据结构 (Lock-Free Structures)](lock_free.md)
    - CAS (Compare-and-Swap) 原理
    - ABA 问题与内存回收
    - Wait-free、Lock-free 与实际工程权衡

3.  [Ring Buffer 实现 (Ring Buffer)](ring_buffer.md)
    - 环形缓冲区的索引模型
    - 缓存友好的布局与批量读写

4.  [SPSC/MPSC 队列 (Queues)](queues.md)
    - 单生产者单消费者 (SPSC) 的极简路径
    - 多生产者单消费者 (MPSC) 的设计权衡

5.  [高性能日志系统 (Zero-Allocation Logging)](logging.md)
    - 热路径上的事件记录
    - 异步落盘与二进制日志格式

6.  [配置管理与热加载 (Config)](config.md)
    - 避免运行时锁的配置读取
    - 热更新与一致性边界

7.  [指标监控与遥测 (Metrics)](metrics.md)
    - 无锁计数器
    - 延迟分布统计与观测基线

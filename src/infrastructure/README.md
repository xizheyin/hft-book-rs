# 吞吐量、并发与基础设施 (Concurrency & Throughput)

本部分从可共享状态的最小单位开始，逐步过渡到完整的基础设施组件。原子操作、内存顺序、无锁结构、Ring Buffer、队列、日志、配置与监控，构成了高性能系统中最常见的一组工程骨架。

这里的重点不是“从零重复造轮子”，而是理解这些轮子为什么这样设计：哪些约束来自硬件缓存一致性，哪些约束来自线程间通信，哪些约束服务于吞吐量，哪些约束又服务于稳定性与可观测性。

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

5.  [吞吐量优化：批处理、流水线与背压](throughput.md)
    - 批处理与摊还成本
    - 流水线并行与背压传播
    - 延迟与吞吐量的权衡边界

6.  [资源效率：分配、零拷贝与对象复用](resource_efficiency.md)
    - 分配器与分配路径
    - 零拷贝、对象池与复用策略
    - 空间效率与可维护性的平衡

7.  [可扩展性设计：分片、Share-Nothing 与核间通信](scalability.md)
    - Share-Nothing 架构
    - 分片、分区与 NUMA 感知设计
    - 核间消息传递与扩展边界

8.  [高性能日志系统 (Zero-Allocation Logging)](logging.md)
    - 热路径上的事件记录
    - 异步落盘与二进制日志格式

9.  [配置管理与热加载 (Config)](config.md)
    - 避免运行时锁的配置读取
    - 热更新与一致性边界

10.  [指标监控与遥测 (Metrics)](metrics.md)
    - 无锁计数器
    - 延迟分布统计与观测基线

# Summary

- [首页：Rust 与 HFT 基础宝典](README.md)
- [前言：这本书解决什么问题](introduction/README.md)
- [如何使用本书：从零基础到面试表达](introduction/how_to_use.md)
- [为什么选择 Rust 构建低延迟系统](introduction/why_rust.md)
- [低延迟系统 Rust 生态概览](introduction/ecosystem.md)

# 第一部分：HFT 业务基础与面试主线

- [HFT 总览：从行情到成交的完整生命周期](hft/README.md)
- [市场微观结构：价格怎样形成](hft/market_microstructure.md)
- [订单类型与撮合优先级](hft/orders_matching.md)
- [延迟预算与关键路径](hft/latency_critical_path.md)
- [HFT 系统设计面试](hft/system_design_interview.md)
- [HFT 高频面试题库](hft/interview_question_bank.md)

# 第二部分：系统基础与性能模型

- [部分导论](foundations/README.md)
- [CPU 微架构原理](foundations/cpu_arch.md)
- [操作系统原理回顾](foundations/os_internals.md)
- [内存布局与缓存效率](foundations/memory_layout.md)
- [零成本抽象](foundations/zero_cost.md)
- [编译器优化与底层原理](foundations/compiler_optimizations.md)
- [Unsafe Rust 实战：SIMD 与 Intrinsics](foundations/unsafe_rust.md)
- [并发模型选择：Async vs Thread vs Actor](foundations/concurrency.md)
- [Async Rust 原理与 Tokio](foundations/async_rust.md)

# 第三部分：Rust 语义与抽象成本

- [部分导论](rust_advanced/README.md)
- [所有权与生命周期进阶](rust_advanced/lifetimes.md)
- [智能指针与内存管理](rust_advanced/smart_pointers.md)
- [内部可变性与 Cell](rust_advanced/interior_mutability.md)
- [Send 与 Sync 的本质](rust_advanced/send_sync.md)
- [错误处理最佳实践](rust_advanced/error_handling.md)
- [泛型与 Const Generics](rust_advanced/generics.md)
- [宏编程实战](rust_advanced/macros.md)
- [闭包与函数指针](rust_advanced/closures.md)

# 第四部分：吞吐量、并发与基础设施

- [部分导论](infrastructure/README.md)
- [原子操作详解](infrastructure/atomics.md)
- [无锁数据结构](infrastructure/lock_free.md)
- [Ring Buffer 实现](infrastructure/ring_buffer.md)
- [SPSC/MPSC 队列](infrastructure/queues.md)
- [吞吐量优化：批处理、流水线与背压](infrastructure/throughput.md)
- [资源效率：分配、零拷贝与对象复用](infrastructure/resource_efficiency.md)
- [可扩展性：分片、Share-Nothing 与核间通信](infrastructure/scalability.md)
- [高性能日志系统](infrastructure/logging.md)
- [配置管理与热加载](infrastructure/config.md)
- [指标监控与遥测](infrastructure/metrics.md)

# 第五部分：网络与高性能 I/O

- [部分导论](network/README.md)
- [网络协议栈基础](network/basics.md)
- [I/O 模型演进](network/io_models.md)
- [TCP 协议优化](network/tcp_optimization.md)
- [UDP 多播处理](network/udp_multicast.md)
- [io_uring 深度解析](network/io_uring.md)
- [内核旁路技术](network/kernel_bypass.md)
  - [DPDK 集成](network/dpdk.md)
  - [AF_XDP 实战](network/af_xdp.md)
  - [Solarflare OpenOnload](network/openonload.md)
- [Linux 网络调优](network/tuning.md)

# 第六部分：行情、协议与订单接入

- [电子市场协议概览](connectivity/protocols.md)
  - [FIX 协议解析](connectivity/fix.md)
  - [二进制协议：SBE、ITCH 与 OUCH](connectivity/binary_protocols.md)
- [市场数据处理](connectivity/market_data.md)
  - [L1/L2/L3 数据构建](connectivity/order_book_data.md)
  - [增量更新、快照与恢复](connectivity/incremental_updates.md)
- [订单路由系统](connectivity/order_routing.md)

# 第七部分：交易引擎、风控与策略

- [订单簿管理](engine/order_book.md)
- [风控系统](engine/risk.md)
  - [预交易风控](engine/pre_trade_risk.md)
  - [持仓管理](engine/position.md)
- [策略框架设计](engine/strategy.md)
  - [信号生成](engine/signals.md)
  - [执行算法](engine/execution.md)

# 第八部分：性能工程、测试与仿真

- [基准测试](optimization/benchmarking.md)
- [性能分析](optimization/profiling.md)
- [CPU 亲和性与隔离](optimization/cpu_affinity.md)
- [编译优化与 PGO](optimization/pgo.md)
- [生产环境部署清单](optimization/deployment.md)
- [单元测试与集成测试](testing/unit_integration.md)
- [模糊测试与属性测试](testing/fuzzing.md)
- [事件驱动回测引擎](simulation/event_driven.md)
- [历史数据回放](simulation/replay.md)
- [高精度时钟模拟](simulation/clock.md)
- [FPGA 交互与 Rust 绑定](optimization/fpga.md)

# 附录

- [HFT 面试术语表](appendix/glossary.md)
- [Rust 低延迟开发速查表](appendix/cheat_sheet.md)
- [C++ 向 Rust 迁移指南](foundations/cpp_migration.md)
- [推荐阅读与官方规范](appendix/reading.md)
- [开源项目资源](appendix/resources.md)

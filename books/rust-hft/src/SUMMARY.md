# Summary

- [首页：系统、Rust、C++ 与 HFT 基础宝典](README.md)

# 第一部分：从零认识计算机系统

- [一次程序怎样在计算机里运行](foundations/computer_execution.md)
- [数据在计算机中怎样表示](foundations/data_representation.md)
- [计算机性能：时间、吞吐量与加速比](foundations/computer_performance.md)
- [ISA 与机器级程序](foundations/isa_machine_code.md)
- [CPU 数据通路、控制与流水线](foundations/cpu_datapath.md)
- [CPU 微架构：分支预测、乱序与并行执行](foundations/cpu_arch.md)
- [存储层次与 Cache 工作原理](foundations/memory_hierarchy.md)
- [内存布局与缓存效率](foundations/memory_layout.md)
- [I/O 硬件：总线、中断与 DMA](foundations/io_hardware.md)
- [操作系统怎样管理程序和硬件](foundations/os_internals.md)
- [进程、线程、文件描述符与管道](foundations/processes_fds.md)
- [进程间通信：信号、共享内存、消息与 Socket](foundations/ipc_signals.md)
- [CPU 调度](foundations/cpu_scheduling.md)
- [操作系统同步：锁、信号量与条件变量](foundations/os_synchronization.md)
- [死锁：原因、判断与处理](foundations/deadlocks.md)
- [内存管理：分配、换页与抖动](foundations/memory_management.md)
- [虚拟内存：程序为什么看见自己的地址空间](foundations/virtual_memory.md)
- [文件系统：名字怎样找到数据](foundations/file_systems.md)
- [I/O 管理：操作系统怎样统一设备](foundations/io_management.md)
- [一次 write 怎样到达持久存储](foundations/file_write_path.md)

# 第二部分：Rust 底层原理与并发

- [为什么选择 Rust 编写系统程序](introduction/why_rust.md)
- [怎样为 Rust 项目选择工具与依赖](introduction/ecosystem.md)
- [Rust 的零成本抽象](foundations/zero_cost.md)
- [编译器怎样理解并优化 Rust 程序](foundations/compiler_optimizations.md)
- [Unsafe Rust：安全边界与证明责任](foundations/unsafe_rust.md)
- [并发基础：线程、锁、消息与 Actor](foundations/concurrency.md)
- [Async Rust：Future、Executor 与 Waker](foundations/async_rust.md)

# 第三部分：Rust 语义与抽象成本

- [所有权与生命周期进阶](rust_advanced/lifetimes.md)
- [智能指针与内存管理](rust_advanced/smart_pointers.md)
- [内部可变性与 Cell](rust_advanced/interior_mutability.md)
- [Send 与 Sync 的本质](rust_advanced/send_sync.md)
- [错误处理最佳实践](rust_advanced/error_handling.md)
- [泛型与 Const Generics](rust_advanced/generics.md)
- [宏编程实战](rust_advanced/macros.md)
- [闭包与函数指针](rust_advanced/closures.md)

# 第四部分：现代 C++ 与系统开发

- [现代 C++：对象生命周期与系统开发](cpp/README.md)
- [C++ 基础复习：重新找回手感](cpp/basics_refresher.md)
- [C++ 最小语法与数据建模](cpp/minimal_syntax.md)
- [编译、链接与内存地图](cpp/compilation_memory.md)
- [指针、引用与 const](cpp/pointers_references.md)
- [对象生命周期与 RAII](cpp/raii_lifetime.md)
- [拷贝、移动与 Rule of Zero/Five](cpp/copy_move.md)
- [智能指针与所有权](cpp/smart_pointers.md)
- [STL 容器与成本模型](cpp/stl_cost_model.md)
- [模板、Concepts 与多态](cpp/templates_polymorphism.md)
- [内存布局、缓存与 False Sharing](cpp/memory_layout.md)
- [错误、异常与未定义行为](cpp/errors_ub.md)
- [原子操作与 C++ 内存模型](cpp/atomics_memory_model.md)
- [无锁结构与 SPSC 队列](cpp/lock_free.md)
- [分配器、对象池与零拷贝](cpp/allocators_zero_copy.md)
- [编译优化、基准与诊断工具](cpp/optimization_tooling.md)
- [C++ HFT 贯穿项目](cpp/hft_capstone.md)

# 第五部分：数据结构、算法与面试编码

- [数据结构、算法与 C++20 实现](algorithms/README.md)
- [数据结构总论：逻辑、存储与抽象类型](algorithms/data_structures_intro.md)
- [复杂度、正确性与测试](algorithms/complexity_correctness.md)
- [线性表：顺序表与链表](algorithms/linear_lists.md)
- [栈、队列与数组](algorithms/stacks_queues_arrays.md)
- [树与二叉树：性质、遍历、Huffman 与堆](algorithms/trees_foundations.md)
- [图：表示关系、遍历网络](algorithms/graph_foundations.md)
- [查找结构：二分、平衡树与哈希表](algorithms/search_structures.md)
- [排序基础：插入、交换、选择、归并与外部排序](algorithms/sorting_foundations.md)
- [从题目到算法：一套固定解题流程](algorithms/problem_solving.md)
- [C++20 算法解题工具箱](algorithms/cpp_toolbox.md)
- [在线笔试输入输出与提交模式](algorithms/online_judge_io.md)
- [数组、字符串与线性模式](algorithms/arrays_strings.md)
- [字符串解析、KMP 与 Trie](algorithms/string_algorithms.md)
- [哈希、排序、区间与二分](algorithms/hashing_binary_search.md)
- [排序、分区与选择](algorithms/sorting_selection.md)
- [栈、队列、双端队列与堆](algorithms/stack_queue_heap.md)
- [链表、递归与树](algorithms/linked_list_tree.md)
- [图、并查集、最短路与回溯](algorithms/graph_search.md)
- [贪心与动态规划](algorithms/greedy_dp.md)
- [动态规划核心模式](algorithms/dp_patterns.md)
- [位运算与数值算法](algorithms/bit_math.md)
- [流式与工程算法](algorithms/streaming_systems.md)
- [进阶数据结构与图算法](algorithms/advanced_structures.md)
- [基础设施与量化岗位场景综合题](algorithms/company_scenarios.md)
- [限时模拟笔试与面试](algorithms/mock_exams.md)
- [追加盲测卷：完整输入输出与陌生组合](algorithms/mock_exams_extra.md)

# 第六部分：吞吐量、并发与基础设施

- [并发与通用基础设施](infrastructure/README.md)
- [原子操作详解](infrastructure/atomics.md)
- [无锁数据结构](infrastructure/lock_free.md)
- [Ring Buffer 实现](infrastructure/ring_buffer.md)
- [队列拓扑：SPSC、MPSC 与 MPMC](infrastructure/queues.md)
- [吞吐量优化：批处理、流水线与背压](infrastructure/throughput.md)
- [资源效率：分配、零拷贝与对象复用](infrastructure/resource_efficiency.md)
- [可扩展性：分片、Share-Nothing 与核间通信](infrastructure/scalability.md)
- [高性能日志系统](infrastructure/logging.md)
- [配置热更新：一致快照、审计与回滚](infrastructure/config.md)
- [指标监控与遥测](infrastructure/metrics.md)

# 第七部分：计算机网络与 Linux I/O

- [计算机网络与 Linux I/O 知识地图](network/README.md)
- [计算机网络概述](network/network_overview.md)
- [物理层：比特怎样变成信号](network/physical_layer.md)
- [数据链路层：帧、差错检测与局域网](network/link_layer.md)
- [网络层：IP、子网与分组转发](network/network_layer.md)
- [路由与控制平面：DV、LS、RIP、OSPF 与 BGP](network/routing_control.md)
- [传输层：UDP、可靠传输与 TCP](network/transport_layer.md)
- [应用层：DNS、HTTP、TLS 与 Socket](network/application_layer.md)
- [Linux 网络收发路径](network/basics.md)
- [I/O 模型：就绪、完成与忙轮询](network/io_models.md)
- [Linux TCP Socket 工程](network/tcp_optimization.md)
- [UDP 组播：分发、检测与恢复](network/udp_multicast.md)
- [io_uring 深度解析](network/io_uring.md)
- [内核旁路技术](network/kernel_bypass.md)
  - [DPDK 集成](network/dpdk.md)
  - [AF_XDP 实战](network/af_xdp.md)
  - [Solarflare OpenOnload](network/openonload.md)
- [Linux 网络调优](network/tuning.md)

# 第八部分：数据库与分布式系统

- [数据库基础](databases/README.md)
- [关系模型与 SQL](databases/relational_sql.md)
- [存储、索引与查询执行](databases/storage_indexes.md)
- [事务与并发控制](databases/transactions_concurrency.md)
- [预写日志（WAL）、恢复、复制与分片](databases/wal_recovery_replication.md)
- [分布式系统基础](distributed/README.md)
- [分布式系统从哪里开始](distributed/distributed_systems_intro.md)
- [复制、法定人数（Quorum）与共识](distributed/replication_consensus.md)
- [分片与缓存：把数据和请求分散开](distributed/partitioning_caching.md)
- [可靠性与跨服务事务](distributed/reliability_transactions.md)

# 第九部分：HFT 业务基础与面试主线

- [HFT 总览：从行情到成交的完整生命周期](hft/README.md)
- [市场微观结构：价格怎样形成](hft/market_microstructure.md)
- [订单类型与撮合优先级](hft/orders_matching.md)
- [延迟预算与关键路径](hft/latency_critical_path.md)
- [HFT 系统设计面试](hft/system_design_interview.md)
- [HFT 高频面试题库](hft/interview_question_bank.md)

# 第十部分：行情、协议与订单接入

- [电子市场协议概览](connectivity/protocols.md)
  - [FIX 协议解析](connectivity/fix.md)
  - [二进制协议：SBE、ITCH 与 OUCH](connectivity/binary_protocols.md)
- [市场数据处理](connectivity/market_data.md)
  - [L1/L2/L3 数据构建](connectivity/order_book_data.md)
  - [增量更新、快照与恢复](connectivity/incremental_updates.md)
- [订单路由系统](connectivity/order_routing.md)

# 第十一部分：交易引擎、风控与策略

- [订单簿管理](engine/order_book.md)
- [风控系统](engine/risk.md)
  - [预交易风控](engine/pre_trade_risk.md)
  - [持仓管理](engine/position.md)
- [策略框架设计](engine/strategy.md)
  - [信号生成](engine/signals.md)
  - [执行算法](engine/execution.md)

# 第十二部分：性能工程、测试与仿真

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

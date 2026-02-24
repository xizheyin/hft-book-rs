# 性能分析 (Profiling)

基准测试告诉我们“代码有多快”，而性能分析（Profiling）告诉我们“代码为什么慢”。

在 HFT 中，我们通常面临两种性能问题：
1.  **CPU 瓶颈**：热点函数消耗了大量 CPU 周期。
2.  **延迟瓶颈**：虽然 CPU 占用率不高，但关键路径因为缓存未命中或锁争用而被阻塞。

## 准备工作：保留调试符号

为了让 Profiler 能将机器码映射回 Rust 源代码，我们需要在 `release` 构建中保留调试符号。这会增加二进制文件的大小，但不会影响运行时性能。

```toml
# Cargo.toml
[profile.release]
debug = true  # 保留调试信息
strip = false # 不要剥离符号表
```

## Linux Perf 与火焰图 (FlameGraphs)

`perf` 是 Linux 内核自带的性能分析工具，功能极其强大。

### 1. 采集数据

```bash
# 以 99Hz 的频率采样所有 CPU，持续 30 秒
# -g: 记录调用栈 (Call graph)
# -p <PID>: 监控特定进程
sudo perf record -F 99 -g -p $(pgrep hft_app) -- sleep 30
```

### 2. 生成火焰图

火焰图 (FlameGraph) 是可视化调用栈最直观的方式。

```bash
# 需要先安装 flamegraph 工具
# cargo install flamegraph

# 直接运行并生成火焰图
cargo flamegraph --root --bin hft_app
```

在火焰图中：
- **X 轴**：表示采样次数（即 CPU 占用时间）。越宽的函数占用 CPU 越多。
- **Y 轴**：表示调用栈深度。
- **平顶 (Plateaus)**：如果在顶层有很宽的“平顶”，说明该函数本身（而非它调用的子函数）消耗了大量 CPU。

## 深入硬件事件 (Hardware Events)

仅仅看 CPU 周期是不够的。有时代码慢是因为缓存未命中。

```bash
# 分析 L1 数据缓存未命中
perf record -e L1-dcache-load-misses -g ...

# 分析分支预测失败
perf record -e branch-misses -g ...

# 分析最后以级缓存 (LLC) 未命中
perf record -e LLC-load-misses -g ...
```

如果发现 `order_book::match_order` 函数有大量的 `LLC-load-misses`，说明你的订单簿内存布局不友好（可能是指针跳转太多），需要考虑改用数组或 Arena 分配器。

## 因果分析 (Causal Profiling): Coz

传统的 Profiler 有一个误区：优化占用 CPU 最多的函数，不一定能提升系统整体吞吐量或降低端到端延迟。因为那个热点可能并不在关键路径上。

`coz` 是一个“因果分析器”。它的工作原理很有趣：它不加速特定的代码，而是通过**虚拟减速**其他代码，来模拟“如果这行代码加速 20% 会发生什么”。

### 安装与使用

```bash
cargo install coz
```

在代码中插入“进度点”：

```rust
// 告诉 Coz：这里是一次交易处理的结束
coz::progress!("transaction_processed");
```

运行：

```bash
coz run --- ./target/release/hft_app
```

Coz 会输出：
> "Optimizing function `process_order` by 15% will increase throughput by 12%."

这比看火焰图猜测更有指导意义。

## 堆内存分析 (Heap Profiling)

如果你的程序总是发生 Minor Page Faults，或者内存碎片化严重，可以使用 `dhat` 或 `bytehound`。

### DHAT (Dynamic Heap Analysis Tool)

DHAT 是 Valgrind 的一部分，它可以精确地告诉你每一行代码分配了多少内存，以及这些内存的生命周期。

```bash
# 需要安装 valgrind
valgrind --tool=dhat ./target/release/hft_app
```

它会指出“短命”的分配（Short-lived allocations），这通常是优化的低垂果实——应该把它们改为栈分配或对象池复用。

## 常见性能杀手

在 Profiling Rust HFT 程序时，常见的瓶颈包括：

1.  **`memcpy` / `memmove`**：通常由 `Clone` 或不必要的 `match` 移动引起。
2.  **`malloc` / `free`**：通常由 `Vec::push` 扩容或 `String` 拼接引起。
3.  **`pthread_mutex_lock`**：锁竞争。
4.  **`syscall`**：频繁的 `read`/`write` 或 `gettimeofday`（如果不是 vDSO）。

## 总结

- 先用 **FlameGraph** 找 CPU 热点。
- 用 **Perf Events** 找缓存和分支预测问题。
- 用 **Coz** 找真正的吞吐量瓶颈。
- 用 **DHAT** 优化内存分配。
- **永远不要猜测**。

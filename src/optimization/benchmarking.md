# 基准测试 (Micro-benchmarking)

在 HFT 开发中，“直觉”往往是错误的。你认为更快的代码，在 CPU 分支预测失败或缓存未命中面前可能慢得离谱。因此，**一切优化必须以基准测试为依据**。

然而，编写正确的基准测试非常困难。编译器会优化掉“无用”的代码，操作系统会引入噪音，CPU 的动态频率调节也会干扰结果。

## 理论背景：为何基准测试很难？

1.  **编译器优化**：Rust (LLVM) 非常聪明。如果你计算了一个值但从未使用，它会直接删除这部分计算代码。
2.  **冷启动 vs 热运行**：代码首次运行需要加载指令缓存 (i-cache) 和数据缓存 (d-cache)，并且分支预测器 (Branch Predictor) 尚未训练。
3.  **环境噪音**：OS 中断、其他进程、电源管理 (Turbo Boost) 都会导致测量抖动。

## Criterion.rs：标准的 Rust 基准测试库

`criterion` 是 Rust 生态中最流行的统计驱动基准测试库。它能自动处理预热 (Warm-up)，并多次运行以消除噪音。

### 依赖配置

```toml
[dev-dependencies]
criterion = "0.5"

[[bench]]
name = "order_book_bench"
harness = false
```

### 编写基准测试

假设我们要测试一个订单簿的插入性能。

```rust
// benches/order_book_bench.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use hft_engine::order_book::OrderBook;
use hft_engine::types::{Order, Side};

fn bench_order_insert(c: &mut Criterion) {
    c.bench_function("order_book_insert", |b| {
        // Setup: 创建 OrderBook
        let mut book = OrderBook::new();
        let mut id = 0;
        
        b.iter(|| {
            id += 1;
            // 使用 black_box 防止编译器优化掉整个循环
            // 如果 OrderBook::add_order 返回值被忽略且无副作用，可能会被优化
            let order = Order::new(id, Side::Buy, 100.0, 10);
            black_box(book.add_order(black_box(order)));
        })
    });
}

criterion_group!(benches, bench_order_insert);
criterion_main!(benches);
```

### 运行测试

```bash
cargo bench
```

Criterion 会生成详细的 HTML 报告（位于 `target/criterion/report/index.html`），展示平均耗时、离群值和分布图。

## 避免编译器陷阱：`black_box`

`std::hint::black_box` 是基准测试中最重要的函数。它告诉编译器：“这个值被外部使用了，不要优化掉它”，或者“这个值的来源是不透明的，不要进行常量折叠”。

**错误示例**：
```rust
b.iter(|| {
    let x = 1 + 1; // 编译器会直接把这行替换为 let x = 2; 甚至直接删除
})
```

**正确示例**：
```rust
b.iter(|| {
    // 强制执行加法
    black_box(black_box(1) + black_box(1));
})
```

## 关注尾部延迟 (Tail Latency)

在 HFT 中，平均延迟 (Mean) 毫无意义。如果你平均延迟 1µs，但每 100 笔交易有一笔延迟 1ms，你就会在最关键的市场波动时刻亏钱。

我们需要关注 P99, P99.9, P99.99 延迟。

### 使用 `hdrhistogram`

`criterion` 默认提供统计数据，但在生产环境或自定义测试工具中，我们需要记录每一次操作的耗时并生成直方图。

```toml
[dependencies]
hdrhistogram = "7.5"
```

```rust
use hdrhistogram::Histogram;
use std::time::Instant;

fn measure_latency() {
    let mut hist = Histogram::<u64>::new_with_bounds(1, 1000_000, 3).unwrap();
    
    for _ in 0..1_000_000 {
        let start = Instant::now();
        
        // 执行操作
        do_work();
        
        let elapsed = start.elapsed().as_nanos() as u64;
        hist.record(elapsed).unwrap();
    }
    
    println!("P50:   {} ns", hist.value_at_quantile(0.50));
    println!("P99:   {} ns", hist.value_at_quantile(0.99));
    println!("P99.9: {} ns", hist.value_at_quantile(0.999));
    println!("Max:   {} ns", hist.max());
}
```

## 基于指令计数的测试 (Instruction Counting)

时间测量总是受 CPU 频率影响。`iai` (或更新的 `iai-callgrind`) 使用 Valgrind/Cachegrind 来模拟 CPU 执行，统计指令数、内存访问数和缓存未命中数。

这种测试极其稳定，不受机器负载影响，非常适合在 CI (Continuous Integration) 中运行。

```toml
[dev-dependencies]
iai = "0.1"
```

```rust
// benches/my_benchmark.rs
use iai::black_box;

fn bench_parsing() {
    let data = b"8=FIX.4.4\x019=100...";
    my_parser::parse(black_box(data));
}

iai::main!(bench_parsing);
```

运行结果会显示：
```text
bench_parsing
  Instructions:  1502
  L1 Accesses:    305
  L2 Accesses:      2
  RAM Accesses:     0
  Estimated Cycles: 1800
```
如果某次提交导致 Instructions 从 1502 变成了 2000，你就知道性能退化了，即使在负载很高的 CI 机器上也能发现。

## 硬件计数器 (Hardware Counters)

在 Linux 上，我们可以使用 `perf` 工具来深入分析。

```bash
# 统计缓存未命中和分支预测错误
perf stat -e cache-misses,branch-misses,instructions,cycles ./target/release/my_hft_app
```

或者在 Rust 代码中使用 `perfcnt` crate 来针对特定代码块进行测量。

## 总结

1.  **Criterion** 用于本地开发，测量真实时间（Wall time）。
2.  **Iai/Cachegrind** 用于 CI，测量指令数和缓存行为，确保无性能回归。
3.  **HdrHistogram** 用于生产环境监控和全链路压测，关注 P99+ 尾部延迟。
4.  永远不要相信 Debug 模式下的性能测试结果。

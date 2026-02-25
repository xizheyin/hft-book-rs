# 高精度时钟模拟 (High-Precision Clock Simulation)

在构建高频交易系统时，时间是唯一的真理。不仅我们需要在生产环境中获取纳秒级精度的当前时间，还需要在回测（Backtesting）和仿真（Simulation）环境中完全控制时间的流逝。

本章将探讨如何设计一个零成本抽象的时钟系统，使其既能在生产环境中利用 CPU 指令集提供极低延迟的时间戳，又能在仿真环境中支持“时间旅行”，实现确定性（Deterministic）回测。

## 1. 为什么不能直接用 `std::time::SystemTime`？

在 Rust 中，`std::time::SystemTime::now()` 或 `Instant::now()` 是获取时间的标准方式。但在 HFT 场景下，它们存在以下问题：

1.  **系统调用开销**：虽然现代 Linux 通过 vDSO (virtual Dynamic Shared Object) 优化了 `gettimeofday` 和 `clock_gettime`，避免了真正的上下文切换，但它仍然包含函数调用和一定的逻辑判断，对于热路径（Hot Path）来说可能太慢（~20-50ns）。
2.  **不可控性**：在回测时，我们需要“伪造”时间。如果策略代码直接调用系统时间，回测将变得不可能，因为回测运行的速度远快于真实时间。
3.  **精度问题**：标准库的时间精度依赖于操作系统，虽然通常是纳秒级，但在某些旧系统或虚拟机中可能退化。

因此，我们需要一个抽象层。

## 2. 时钟抽象 (The Clock Trait)

我们需要定义一个 `Clock` trait，策略和引擎通过它来获取时间，而不是直接调用系统 API。

```rust
pub trait Clock: Send + Sync {
    /// 获取当前时间戳（纳秒）
    fn now_ns(&self) -> u64;

    /// 获取当前时间戳（微秒）
    #[inline(always)]
    fn now_us(&self) -> u64 {
        self.now_ns() / 1000
    }
}
```

在生产代码中，我们使用 `static dispatch`（静态分发）来避免虚函数调用（vtable）的开销。

```rust
pub struct TradingEngine<C: Clock> {
    clock: C,
    // ...
}
```

## 3. 生产环境：基于 RDTSC 的超低延迟时钟

在 x86_64 架构上，CPU 提供了一个名为 `RDTSC` (Read Time-Stamp Counter) 的指令，它返回 CPU 自复位以来的时钟周期数。这是获取时间最快的方法（~10-20ns，甚至更快，取决于流水线）。

### 3.1 挑战与解决方案

直接使用 `rdtsc` 有几个坑：
1.  **多核同步**：在旧 CPU 上，不同核心的 TSC 可能不同步。但在现代 CPU（Nehalem 之后，支持 `invariant TSC`），TSC 是全核同步且频率恒定的，不受变频影响。
2.  **乱序执行**：CPU 可能会重排指令，导致 `rdtsc` 在我们预期的逻辑之前或之后执行。需要使用 `rdtscp` 或内存屏障（`lfence`）来序列化。
3.  **周期转纳秒**：我们需要知道 CPU 的标称频率才能将周期数转换为时间。

### 3.2 实现代码

```rust
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::{_rdtsc, _rdtscp};

pub struct TscClock {
    // 基准时间（纳秒）
    base_ns: u64,
    // 基准 TSC
    base_tsc: u64,
    // 转换因子：纳秒 / TSC 周期
    ns_per_cycle: f64,
}

impl TscClock {
    pub fn new() -> Self {
        // 1. 预热和校准
        // 注意：生产环境应运行更长时间的校准，或者读取 /proc/cpuinfo
        let start = std::time::Instant::now();
        let start_tsc = unsafe { _rdtsc() };
        
        std::thread::sleep(std::time::Duration::from_millis(100));
        
        let end_tsc = unsafe { _rdtsc() };
        let elapsed = start.elapsed();
        
        let cycles = end_tsc - start_tsc;
        let ns = elapsed.as_nanos() as u64;
        
        let ns_per_cycle = ns as f64 / cycles as f64;
        
        println!("TSC Calibration: {} ns/cycle", ns_per_cycle);

        Self {
            base_ns: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos() as u64,
            base_tsc: end_tsc, // 使用结束时的 TSC 作为基准
            ns_per_cycle,
        }
    }
}

impl Clock for TscClock {
    #[inline(always)]
    fn now_ns(&self) -> u64 {
        // SAFETY: 我们只在 x86_64 平台上使用
        let current_tsc = unsafe { _rdtsc() };
        
        // 简单的线性变换：T = T_base + (TSC_now - TSC_base) * factor
        // 注意：浮点运算在某些极低延迟场景可能被视为昂贵，
        // 可以优化为定点数运算 (fixed point arithmetic)
        let delta_cycles = current_tsc.saturating_sub(self.base_tsc);
        self.base_ns + (delta_cycles as f64 * self.ns_per_cycle) as u64
    }
}
```

> **优化提示**：在极构性能代码中，避免 `f64` 乘法。可以使用 `mul_u64_shr` 技巧：将 `factor` 表示为 `(multiplier * 2^shift)` 的形式，用整数乘法和位移代替浮点运算。

## 4. 仿真环境：事件驱动的模拟时钟

在回测中，时间是由**事件**（Event）驱动的，而不是自然流逝的。每当引擎从事件队列中取出一个事件，时钟就瞬间“跳跃”到该事件的时间戳。

```rust
use std::cell::Cell;

pub struct SimClock {
    // 使用 Cell 实现内部可变性，因为 Clock trait 的方法通常是 &self
    current_time: Cell<u64>,
}

impl SimClock {
    pub fn new(start_time_ns: u64) -> Self {
        Self {
            current_time: Cell::new(start_time_ns),
        }
    }

    /// 仅在仿真引擎内部调用，用于更新时间
    pub fn set_time(&self, time_ns: u64) {
        // 确保时间单调递增
        if time_ns < self.current_time.get() {
            panic!("Time travel to the past is not allowed!");
        }
        self.current_time.set(time_ns);
    }
}

impl Clock for SimClock {
    #[inline(always)]
    fn now_ns(&self) -> u64 {
        self.current_time.get()
    }
}
```

### 4.1 避免“未来函数” (Look-ahead Bias)

在仿真中，最危险的错误是策略读取了未来的数据。例如，策略在 `T` 时刻做决策，却读取了 `T + 1ms` 的收盘价。

通过严格的 `Clock` 抽象，我们限制策略只能通过 `now_ns()` 获取当前时间，而这个“当前时间”完全由回测引擎控制。只要回测引擎严格按照时间顺序处理事件，策略就不可能“穿越”到未来。

## 5. 定时器模拟 (Timer Simulation)

策略经常需要设置定时器，例如：“如果 100ms 内没有收到回报，就撤单”。

在生产环境中，这可能通过 `tokio::time::sleep` 或时间轮（Time Wheel）实现。但在回测中，我们不能真的 `sleep` 线程。我们需要将定时器转换为一个**定时事件**（Timer Event），插入到回测的事件队列中。

```rust
pub enum Event {
    MarketData(MarketData),
    Timer(TimerId),
}

// 策略接口增加定时器支持
pub trait StrategyContext {
    fn now(&self) -> u64;
    fn schedule_timer(&mut self, delay_ns: u64, timer_id: u64);
}

// 仿真环境下的实现
impl StrategyContext for BacktestContext {
    fn schedule_timer(&mut self, delay_ns: u64, timer_id: u64) {
        let trigger_time = self.clock.now_ns() + delay_ns;
        self.event_queue.push(EventWrapper {
            timestamp: trigger_time,
            event: Event::Timer(timer_id),
        });
    }
}
```

## 6. 总结

| 特性 | 系统时间 (`SystemTime`) | RDTSC 时钟 | 仿真时钟 (`SimClock`) |
| :--- | :--- | :--- | :--- |
| **开销** | ~20-50ns (vDSO) | ~10ns | < 1ns (内存读取) |
| **来源** | OS 内核 | CPU 寄存器 | 变量 (RAM) |
| **用途** | 日志、非关键路径 | 生产环境核心路径 | 回测、单元测试 |
| **可控性** | 不可控 | 不可控 | 完全可控 |

通过 `Clock` trait 和泛型，我们实现了一套代码在实盘和回测中无缝切换，且在两种场景下都达到了极致的性能。

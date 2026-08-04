# 高精度时钟模拟 (High-Precision Clock Simulation)

在构建高频交易系统时，时间既是输入，也是测量工具。生产环境需要低开销且可追溯的时间戳；回测环境需要完全控制时间推进，保证相同输入产生相同结果。

本章将探讨如何设计一个零成本抽象的时钟系统，使其既能在生产环境中利用 CPU 指令集提供极低延迟的时间戳，又能在仿真环境中支持“时间旅行”，实现确定性（Deterministic）回测。

## 1. 为什么不能直接用 `std::time::SystemTime`？

在 Rust 中，`std::time::SystemTime::now()` 或 `Instant::now()` 是获取时间的标准方式。但在 HFT 场景下，它们存在以下问题：

1.  **开销需要测量**：现代 Linux 常通过 vDSO 实现 `clock_gettime`，不一定进入内核。具体成本依赖时钟类型、CPU 和内核，不能把某个固定纳秒数字当作所有机器的事实。
2.  **不可控性**：在回测时，我们需要“伪造”时间。如果策略代码直接调用系统时间，回测将变得不可能，因为回测运行的速度远快于真实时间。
3.  **“单位”不等于“精度”**：接口返回纳秒单位，不代表每纳秒都会更新，也不代表与 UTC 的误差只有 1ns。resolution、读取开销、同步误差是三个不同概念。

因此，我们需要一个抽象层。

## 2. 时钟抽象 (The Clock Trait)

先区分两种常见语义：

- **单调时间**：只用于比较先后和计算 duration，不受校时回拨影响。
- **墙上时间/UTC**：用于审计、跨机器关联，需要 PTP/NTP 与硬件时间戳支持，可能被校准。

下面的 `Clock` 表示单调时间。策略和引擎通过它获取时间，而不是直接调用系统 API：

```rust
pub trait Clock: Send + Sync {
    /// 单调时间轴上的纳秒值；epoch 由具体实现定义，不能直接当 UTC。
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
pub trait Clock: Send + Sync {
    fn now_ns(&self) -> u64;
}

pub struct TradingEngine<C: Clock> {
    clock: C,
    // ...
}
```

## 3. 生产环境：基于 RDTSC 的超低延迟时钟

在 x86_64 架构上，CPU 提供 TSC（Time-Stamp Counter）。读取它通常很快，但 TSC 是 tick 计数，不天然等于 UTC 纳秒。

### 3.1 挑战与解决方案

直接使用 `rdtsc` 有几个坑：
1.  **能力与同步**：要检查 `constant_tsc`/`nonstop_tsc`、虚拟化环境和多 socket 同步，不能按 CPU 年代直接假定可靠。
2.  **乱序执行**：`RDTSC` 不是完整序列化指令。测量代码区间时通常结合 fence 或 `RDTSCP`，并明确要约束前面的还是后面的指令。
3.  **迁核**：`RDTSCP` 可返回 `TSC_AUX`，常用于发现读数期间是否迁移 CPU；前提是 OS 正确配置。
4.  **tick 转纳秒**：应对稳定参考时钟做校准，并周期性监控漂移。读取 `/proc/cpuinfo` 的“当前 MHz”不是可靠换算方案。
5.  **时间域**：TSC 适合进程内 duration；跨主机审计通常使用同步后的 PHC/UTC 或 NIC 硬件时间戳。

### 3.2 实现代码

下面是依赖 x86_64 `RDTSCP`/`LFENCE` 的**硬件教学骨架**，并引用了本章前面的 `Clock` trait，所以标记为 `rust,ignore`。它不能在当前非 x86 doctest 环境中证明正确；应在确认 RDTSCP 能力、绑定逻辑 CPU 的目标机上运行 `cargo test --release --target x86_64-unknown-linux-gnu tsc_clock`，并把换算结果与独立单调时钟长期对比。

```rust,ignore
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::{__rdtscp, _mm_lfence};

#[cfg(target_arch = "x86_64")]
fn ordered_rdtscp() -> (u64, u32) {
    let mut aux = 0_u32;
    // RDTSCP 约束更早的指令/读取；后接 LFENCE，阻止更晚指令越过读数点。
    let ticks = unsafe {
        let value = __rdtscp(&mut aux);
        _mm_lfence();
        value
    };
    (ticks, aux)
}

#[cfg(target_arch = "x86_64")]
pub struct TscClock {
    // 单调时间轴的基准，不是 UNIX epoch。
    base_ns: u64,
    base_tsc: u64,
    ns_per_tick: f64,
    expected_aux: u32,
}

#[cfg(target_arch = "x86_64")]
impl TscClock {
    pub fn new() -> Self {
        let (start_tsc, start_aux) = ordered_rdtscp();
        let start = std::time::Instant::now();

        // 仅用于说明校准思路。生产实现应多轮采样、拒绝迁核/离群值并监控漂移。
        std::thread::sleep(std::time::Duration::from_millis(100));
        let elapsed = start.elapsed();
        let (end_tsc, end_aux) = ordered_rdtscp();
        assert_eq!(start_aux, end_aux, "calibration migrated between CPUs");

        let ticks = end_tsc - start_tsc;
        let ns = elapsed.as_nanos() as u64;
        let ns_per_tick = ns as f64 / ticks as f64;

        Self {
            base_ns: 0,
            base_tsc: end_tsc,
            ns_per_tick,
            expected_aux: end_aux,
        }
    }
}

#[cfg(target_arch = "x86_64")]
impl Clock for TscClock {
    #[inline(always)]
    fn now_ns(&self) -> u64 {
        let (current_tsc, aux) = ordered_rdtscp();
        debug_assert_eq!(aux, self.expected_aux, "thread migrated to another CPU");
        let delta_ticks = current_tsc.saturating_sub(self.base_tsc);
        self.base_ns + (delta_ticks as f64 * self.ns_per_tick) as u64
    }
}
```

> 这段代码是教学骨架，不是可直接上线的 UTC 时钟。生产实现还要处理校准误差、溢出、漂移、迁核/多 socket、Suspend/VM 行为，并用独立参考时钟持续验证。只有 profiling 证明转换是热点时，才考虑用定点乘法和位移替代 `f64`。

## 4. 仿真环境：事件驱动的模拟时钟

在回测中，时间是由**事件**（Event）驱动的，而不是自然流逝的。每当引擎从事件队列中取出一个事件，时钟就瞬间“跳跃”到该事件的时间戳。

```rust
pub trait Clock: Send + Sync {
    fn now_ns(&self) -> u64;
}

pub struct SimClock {
    current_time: u64,
}

impl SimClock {
    pub fn new(start_time_ns: u64) -> Self {
        Self {
            current_time: start_time_ns,
        }
    }

    /// 仅在仿真引擎内部调用，用于更新时间
    pub fn advance_to(&mut self, time_ns: u64) {
        // 确保时间单调递增
        if time_ns < self.current_time {
            panic!("Time travel to the past is not allowed!");
        }
        self.current_time = time_ns;
    }
}

impl Clock for SimClock {
    #[inline(always)]
    fn now_ns(&self) -> u64 {
        self.current_time
    }
}
```

### 4.1 避免“未来函数” (Look-ahead Bias)

在仿真中，最危险的错误是策略读取了未来的数据。例如，策略在 `T` 时刻做决策，却读取了 `T + 1ms` 的收盘价。

`Clock` 抽象只是第一道门。还必须禁止策略直接访问完整历史数组或未来 cursor，并对相同时间戳定义稳定顺序。例如用 `(timestamp, phase, source, sequence, insertion_id)` 排序，否则两条同时间事件可能因线程调度而交换顺序。

## 5. 定时器模拟 (Timer Simulation)

策略经常需要设置定时器，例如：“如果 100ms 内没有收到回报，就撤单”。

在生产环境中，这可能通过 `tokio::time::sleep` 或时间轮（Time Wheel）实现。但在回测中，我们不能真的 `sleep` 线程。我们需要将定时器转换为一个**定时事件**（Timer Event），插入到回测的事件队列中。

下面是与事件队列集成的**多模块骨架**：`MarketData`、`BacktestContext`、`EventWrapper` 和队列排序规则由项目定义，因此不作为独立 doctest。接入后用 `cargo test timer_event` 验证零延迟、溢出、相同时间戳顺序、取消定时器和“只触发一次”等规则。

```rust,ignore
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
        let trigger_time = self
            .clock
            .now_ns()
            .checked_add(delay_ns)
            .expect("timer timestamp overflow");
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
| **开销** | 依实现与平台，通常走 vDSO | 通常很低，需序列化/换算 | 普通字段读取 |
| **来源** | OS 暴露的时钟 | CPU counter | 仿真状态变量 |
| **用途** | 日志、非关键路径 | 生产环境核心路径 | 回测、单元测试 |
| **可控性** | 不可控 | 不可控 | 完全可控 |

通过 `Clock` trait 和泛型，同一套策略可以在实盘与回测中切换。更重要的是，它让“时间的语义”变得可审查：duration 不受 UTC 校时影响，回测不读取真实时间，审计时间戳也不会与 TSC tick 混为一谈。

## 7. 面试高频问答

### Q1：`SystemTime` 和 `Instant` 有什么区别？

`SystemTime` 对应可校准的墙上时间，适合与 UTC 关联，但可能前跳或回拨；`Instant` 是单调时钟，适合 timeout 和 duration，不能直接当作跨进程 UTC 时间戳。

### Q2：RDTSC 为什么快，为什么又危险？

它直接读取 CPU counter，避免通用时钟读取逻辑；但要确认 counter 稳定与跨核同步，处理指令乱序、迁核、tick 到纳秒校准和漂移，而且它本身没有 UTC 语义。

### Q3：模拟时钟如何避免 look-ahead bias？

只有事件循环可以推进时钟；策略只看到当前事件及此前状态；输入读取与策略可见性隔离；相同 timestamp 使用稳定 tie-break；测试断言时间不倒退并对相同输入比较结果 hash。

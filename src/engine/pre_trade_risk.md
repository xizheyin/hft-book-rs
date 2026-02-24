# 预交易风控实战 (Pre-trade Risk Check)

预交易风控 (Pre-trade Risk) 是交易系统中最关键的“看门人”。它位于策略决策之后、订单发送之前。任何延迟都会直接叠加到 Tick-to-Trade 的关键路径上。

本章我们将实现一个**微秒级**甚至**纳秒级**的预交易风控模块。

## 1. 设计目标

1.  **Zero Allocation**: 检查过程中绝不能分配堆内存。
2.  **Branch Prediction Friendly**: 正常情况下风控应该全部通过，异常路径是极少数。我们要利用这一点优化分支预测。
3.  **Cache Locality**: 风控规则和状态数据应尽可能紧凑，适应 L1 Cache。

## 2. 静态规则检查 (Static Checks)

静态规则是指不依赖当前市场状态或持仓状态的检查。例如：单笔最大下单量。

### 2.1 数据结构布局

为了极致性能，我们将所有静态配置紧凑地打包在一起。

```rust
#[repr(C, align(64))] // 确保独占 Cache Line，避免伪共享
#[derive(Debug, Clone, Copy)]
pub struct StaticRiskConfig {
    pub max_qty: u32,
    pub max_value: u64, // Price * Qty
    pub min_price: i64,
    pub max_price: i64,
    pub fat_finger_price_pct: u8, // 价格偏离百分比，例如 10%
    // 填充至 64 字节
    _padding: [u8; 32], 
}

impl Default for StaticRiskConfig {
    fn default() -> Self {
        Self {
            max_qty: 1000,
            max_value: 1_000_000_000, // 假设价格放大 10000 倍
            min_price: 1_0000,
            max_price: 10000_0000,
            fat_finger_price_pct: 10,
            _padding: [0; 32],
        }
    }
}
```

### 2.2 核心检查逻辑

我们使用 `#[inline(always)]` 和 `unlikely` 来提示编译器。

```rust
use std::intrinsics::unlikely;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum RiskError {
    Ok,
    QtyTooLarge,
    ValueTooLarge,
    PriceOutOfRange,
    FatFinger,
}

#[inline(always)]
pub fn check_static(order: &NewOrder, config: &StaticRiskConfig) -> Result<(), RiskError> {
    // 1. 数量检查
    if unsafe { unlikely(order.quantity > config.max_qty) } {
        return Err(RiskError::QtyTooLarge);
    }

    // 2. 价格范围检查
    if unsafe { unlikely(order.price < config.min_price || order.price > config.max_price) } {
        return Err(RiskError::PriceOutOfRange);
    }

    // 3. 金额检查 (注意溢出)
    let value = (order.price as u64).wrapping_mul(order.quantity as u64);
    if unsafe { unlikely(value > config.max_value) } {
        return Err(RiskError::ValueTooLarge);
    }

    Ok(())
}
```

> **注意**: `std::intrinsics::unlikely` 是 unstable feature。在 Stable Rust 中，可以通过冷热代码分离（将错误处理逻辑放到 `#[cold]` 函数中）达到类似效果，或者使用第三方库 `likely`。

## 3. 动态规则检查 (Dynamic Checks)

动态规则依赖于系统的实时状态，如当前持仓、未结订单（Open Orders）等。这是最难优化的部分，因为涉及到状态更新。

### 3.1 状态管理

我们需要维护每个 Symbol 的风险状态。

```rust
#[repr(C, align(64))]
pub struct RiskState {
    pub position: i32,       // 当前净持仓
    pub open_buy_qty: u32,   // 未成交买单量
    pub open_sell_qty: u32,  // 未成交卖单量
    pub max_position: i32,   // 最大持仓限制
    pub daily_loss: i64,     // 当日亏损
    pub max_daily_loss: i64, // 最大当日亏损限制
}
```

### 3.2 乐观更新与回滚 (Optimistic Update & Rollback)

在多线程环境下（例如多个策略线程共享同一个风控额度），我们通常面临两个选择：
1.  **先检查，再更新**: 存在竞态条件（TOCTOU）。
2.  **锁**: 性能杀手。
3.  **原子操作**: `fetch_add`。

对于 HFT，推荐使用**原子操作预扣除**模式。

```rust
use std::sync::atomic::{AtomicI32, Ordering};

pub struct AtomicRiskState {
    pub position: AtomicI32,
    pub max_position: i32, // 只读配置
}

impl AtomicRiskState {
    #[inline(always)]
    pub fn check_and_update(&self, qty: i32) -> Result<(), RiskError> {
        // 1. 乐观更新：先加上去
        let old_pos = self.position.fetch_add(qty, Ordering::SeqCst);
        let new_pos = old_pos + qty;

        // 2. 检查是否超限
        if unsafe { unlikely(new_pos.abs() > self.max_position) } {
            // 3. 回滚：如果超限了，减回来
            self.position.fetch_sub(qty, Ordering::SeqCst);
            return Err(RiskError::PositionLimitExceeded);
        }

        Ok(())
    }
}
```
**缺点**: 在高并发下，可能会出现“虽然没超限，但大家都回滚了”的活锁情况（不过在 HFT 单机策略中，线程数很少，通常不是问题）。

### 3.3 价格偏离度 (Price Deviation)

检查订单价格是否偏离市场最新成交价（Last Traded Price, LTP）或买一卖一价。这需要访问最新的市场数据。

**挑战**: 访问市场数据可能涉及跨线程读取（从 Market Data 线程到 Strategy 线程）。
**方案**: Strategy 线程应该在其本地缓存一份最新的 BBO (Best Bid Offer)。

```rust
#[inline(always)]
pub fn check_price_deviation(order_price: i64, ref_price: i64, limit_pct: u8) -> Result<(), RiskError> {
    if ref_price == 0 { return Ok(()); } // 还没有市场数据，跳过或拒绝
    
    let diff = (order_price - ref_price).abs();
    let threshold = ref_price * (limit_pct as i64) / 100;
    
    if unsafe { unlikely(diff > threshold) } {
        return Err(RiskError::PriceDeviation);
    }
    Ok(())
}
```

## 4. 组合风控 (Portfolio Risk)

有些风控规则是针对整个账户的，例如总敞口（Total Exposure）。

这通常需要一个全局的 `GlobalRiskState`。为了避免所有策略线程竞争同一个 Cache Line，我们可以使用 **分片计数器 (Sharded Counter)**。

每个线程维护自己的 `LocalExposure`，定期（或在某些触发条件下）与 `GlobalExposure` 同步。或者，简单地将总额度分配给每个线程（Static Allocation）。

## 5. 性能测试 (Benchmarking)

让我们看看这个风控模块有多快。

```rust
// 伪代码，使用 criterion
fn bench_risk_check(c: &mut Criterion) {
    let config = StaticRiskConfig::default();
    let order = NewOrder { ... };
    
    c.bench_function("static_check", |b| {
        b.iter(|| {
            check_static(black_box(&order), black_box(&config))
        })
    });
}
```

**预期结果**:
*   静态检查: **< 2ns** (主要是寄存器比较，无内存访问)。
*   动态检查 (Atomic): **10-20ns** (取决于 CPU 竞争情况)。
*   动态检查 (L3 Cache Miss): **~50ns**。

## 6. 总结

1.  **能静态就静态**: 尽量把规则转化为常量或只读配置。
2.  **原子操作优于锁**: 使用 `fetch_add` 进行乐观并发控制。
3.  **分支预测**: 告诉 CPU 99.99% 的订单都是合法的。
4.  **数据局部性**: 将风控所需的数据放在同一个 Cache Line 中。

---
下一章：[持仓管理 (Position Management)](position.md)

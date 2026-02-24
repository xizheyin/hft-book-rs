# 信号生成 (Signal Generation)

在量化交易中，信号（Signal）是策略决策的输入。它将海量的、嘈杂的市场数据（Market Data）提炼为具有预测能力的指标。

HFT 的信号生成有两个显著特点：
1.  **极低延迟**: 必须在纳秒级完成计算。
2.  **增量更新 (Incremental Updates)**: 不能每次都重算整个历史窗口，必须利用上一次的计算结果。

## 1. 信号流水线 (Signal Pipeline)

```mermaid
graph LR
    A[Market Data] --> B[Derived Data]
    B --> C[Alpha Factors]
    C --> D[Combined Signal]
    D --> E[Execution]
```

*   **Derived Data**: 中间价 (Mid Price), 订单簿不平衡 (Imbalance), 加权均价 (VWAP)。
*   **Alpha Factors**: 动量 (Momentum), 均值回归 (Mean Reversion), 波动率 (Volatility)。
*   **Combined Signal**: 多因子加权打分。

## 2. 增量计算 (Incremental Calculation)

### 2.1 指数移动平均 (EMA)
EMA 是最适合 HFT 的指标，因为它不需要维护历史窗口，只需要上一个值。

$$ EMA_t = \alpha \times Price_t + (1 - \alpha) \times EMA_{t-1} $$

```rust
pub struct Ema {
    alpha: f64,
    value: f64,
    initialized: bool,
}

impl Ema {
    pub fn update(&mut self, price: f64) -> f64 {
        if !self.initialized {
            self.value = price;
            self.initialized = true;
        } else {
            self.value = self.alpha * price + (1.0 - self.alpha) * self.value;
        }
        self.value
    }
}
```
**优化**: 预计算 `1.0 - alpha`，减少一次减法。

### 2.2 滑动窗口 (Sliding Window)
对于简单移动平均 (SMA) 或最大/最小值，我们需要维护一个窗口。
**Ring Buffer** 是最佳选择。

```rust
pub struct SlidingWindowSum {
    window: Vec<f64>, // 或固定数组 [f64; N]
    head: usize,
    sum: f64,
    capacity: usize,
}

impl SlidingWindowSum {
    pub fn update(&mut self, new_val: f64) -> f64 {
        let old_val = self.window[self.head];
        self.window[self.head] = new_val;
        
        // 增量更新 Sum
        self.sum = self.sum - old_val + new_val;
        
        self.head = (self.head + 1) % self.capacity;
        self.sum
    }
}
```
**注意**: 浮点数累加 `sum` 可能会产生精度漂移。建议每隔 N 次 update 重新全量求和一次 (Re-normalization)。

## 3. 复杂信号优化：线性回归 (Linear Regression)

假设我们需要计算价格关于时间的斜率（Slope）。
$$ y = kx + b $$
使用最小二乘法，可以在 $O(1)$ 时间内更新斜率。我们需要维护：
*   $\sum x$, $\sum y$, $\sum x^2$, $\sum xy$

当新数据点进入、旧数据点移出时，更新这 4 个 Sum 即可。

## 4. SIMD 加速

如果需要同时计算 100 个 Symbol 的 EMA，或者计算一个 Symbol 的 16 个不同周期的 EMA，可以使用 SIMD。

```rust
use std::simd::f64x4;

pub struct SimdEma4 {
    alphas: f64x4,
    values: f64x4,
    one_minus_alphas: f64x4,
}

impl SimdEma4 {
    pub fn update(&mut self, prices: f64x4) -> f64x4 {
        // value = alpha * price + (1 - alpha) * value
        // FMA (Fused Multiply-Add) 指令加速
        self.values = self.alphas * prices + self.one_minus_alphas * self.values;
        self.values
    }
}
```

## 5. 示例：订单簿不平衡 (Order Book Imbalance)

这是一个经典的微观结构因子，预测短期价格变动。

$$ I = \frac{V_{bid} - V_{ask}}{V_{bid} + V_{ask}} $$

*   $I > 0$: 买压大，价格可能上涨。
*   $I < 0$: 卖压大，价格可能下跌。

```rust
pub fn calc_imbalance(book: &L2OrderBook, depth: usize) -> f64 {
    let mut bid_qty = 0.0;
    let mut ask_qty = 0.0;
    
    // 只看前 depth 档，且带有衰减权重 (越靠近 BBO 权重越大)
    for i in 0..depth {
        let weight = 1.0 / (i as f64 + 1.0);
        bid_qty += book.bids[i].qty as f64 * weight;
        ask_qty += book.asks[i].qty as f64 * weight;
    }
    
    (bid_qty - ask_qty) / (bid_qty + ask_qty)
}
```

## 6. 信号归一化 (Normalization)

原始信号的量纲各异（价格、成交量、百分比）。为了组合它们，通常需要归一化到 `[-1, 1]` 或 z-score。

在 HFT 中，计算实时的标准差（Standard Deviation）也需要增量算法（Welford's Online Algorithm）。

---
下一章：[执行算法 (Execution Algos)](execution.md)

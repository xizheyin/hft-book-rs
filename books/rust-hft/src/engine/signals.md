# 信号生成 (Signal Generation)

> **面试优先级：P1。** 先会解释输入可信度、增量更新、warm-up 和版本追踪；滑动回归及 SIMD 属于量化研究或性能岗位 P2，不要在没说清信号语义前先背指令优化。

信号把市场数据转换成可供策略使用的特征或分数。中间价、订单簿不平衡、波动率和移动平均都可以是信号输入，但“被称为 signal”不代表它已经具有稳定预测能力。

延迟和更新方式取决于策略时间尺度与预算。增量计算常能减少工作量，但小窗口、低频控制路径或需要纠正漂移时，全量重算也可能更简单可靠。

## 1. 信号流水线

```mermaid
flowchart LR
    A["带序号的可信行情"] --> B["清洗与派生数据"]
    B --> C["单因子"]
    C --> D["归一化 / 组合"]
    D --> E["策略意图"]
    E --> F["风控与执行"]
```

每个输出最好携带：输入行情序号、计算时间、配置/模型版本、是否 warm-up 完成和数据是否 live。这样策略不会把“默认值 0”误当成真实信号。

## 2. EMA：O(1) 状态不等于永远适用

<div class="formula" role="math" aria-label="EMA 下标 t 等于 alpha 乘 x 下标 t，加上一减 alpha 乘 EMA 下标 t 减一">
EMA<sub>t</sub> = αx<sub>t</sub> + (1 − α)EMA<sub>t−1</sub>
</div>

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignalError { InvalidAlpha, NonFiniteInput }

pub struct Ema {
    alpha: f64,
    one_minus_alpha: f64,
    value: Option<f64>,
}

impl Ema {
    pub fn new(alpha: f64) -> Result<Self, SignalError> {
        if !alpha.is_finite() || !(0.0 < alpha && alpha <= 1.0) {
            return Err(SignalError::InvalidAlpha);
        }
        Ok(Self { alpha, one_minus_alpha: 1.0 - alpha, value: None })
    }

    pub fn update(&mut self, x: f64) -> Result<f64, SignalError> {
        if !x.is_finite() {
            return Err(SignalError::NonFiniteInput);
        }
        let next = match self.value {
            None => x,
            Some(old) => x.mul_add(self.alpha, old * self.one_minus_alpha),
        };
        if !next.is_finite() {
            return Err(SignalError::NonFiniteInput);
        }
        self.value = Some(next);
        Ok(next)
    }
}
```

初始化方式会影响前几个输出。也可以用历史均值 warm-up；无论哪种，都应在研究和生产中保持一致，并记录何时从 warming 进入 live。

“预计算一次减法”是否有可测收益取决于编译器和关键路径，不应凭源码行数断言。

## 3. 滑动窗口：先处理未填满和零容量

```rust
pub struct SlidingWindowSum {
    values: Vec<f64>,
    head: usize,
    len: usize,
    sum: f64,
}

impl SlidingWindowSum {
    pub fn new(capacity: usize) -> Option<Self> {
        (capacity > 0).then(|| Self {
            values: vec![0.0; capacity],
            head: 0,
            len: 0,
            sum: 0.0,
        })
    }

    pub fn push(&mut self, x: f64) -> Option<f64> {
        if !x.is_finite() {
            return None;
        }
        let outgoing = if self.len < self.values.len() {
            0.0
        } else {
            self.values[self.head]
        };
        let next_sum = self.sum - outgoing + x;
        if !next_sum.is_finite() {
            return None;
        }
        self.len = (self.len + 1).min(self.values.len());
        self.values[self.head] = x;
        self.sum = next_sum;
        self.head = (self.head + 1) % self.values.len();
        Some(self.sum)
    }

    pub fn mean(&self) -> Option<f64> {
        (self.len > 0).then(|| self.sum / self.len as f64)
    }
}
```

浮点增减会随时间积累舍入误差。可以按固定次数或误差监控周期重新求和，并在测试中与高精度/朴素参考实现比较。若信号用于价格合法性或资金账本，应使用明确的定点口径；研究特征使用浮点也要处理 NaN、Infinity 和平台差异。

Ring buffer 是常见选择，不是所有窗口的“最佳结构”。滑动最大/最小通常需要单调队列；时间窗口还要处理不规则时间戳和过期多个元素。

## 4. 滑动线性回归的隐藏细节

最小二乘可维护 `Σx、Σy、Σx²、Σxy` 来减少每次更新工作，但要先说明：

- `x` 是绝对时间、相对索引还是事件序号；
- 窗口滑动时旧点移出和索引重编号怎样处理；
- 大时间戳会导致数值消减，通常应中心化；
- 分母接近 0 时不能输出无穷斜率；
- 乱序/重复数据怎样处理。

“维护四个和便严格 O(1)”只在定义好的固定窗口算法和数值口径下成立。用朴素 O(N) 版本作为 oracle 做随机对比更可靠。

## 5. SIMD 不是默认优化

SIMD 适合相同操作作用于多个独立因子/标的，前提是数据布局、批大小和关键路径允许。它可能带来：

- 为凑齐向量而等待，增加单事件延迟；
- 不同标的分支/缺失值导致 lane 利用率低；
- 对齐、跨平台和浮点结果差异；
- nightly `portable_simd` 或架构 intrinsic 的工具链维护成本。

先让编译器自动向量化并查看产物，再比较标量、批处理和 SIMD 的端到端 p50/p99。不要为了展示指令集引入没有收益的 `unsafe`。

## 6. 归一化与组合

Z-score：

<div class="formula" role="math" aria-label="z 等于 x 减均值 mu，再除以标准差 sigma">
z = (x − μ) / σ
</div>

当样本不足或 `σ` 接近 0 时，输出无定义；应进入 warming/invalid，而不是除以 0。Welford 算法适合在线累计均值和方差，但“从开盘到现在”的统计与“最近 N 个样本”的滚动统计不是同一个东西。

```rust
fn weighted_sum(factors: &[f64], weights: &[f64]) -> Option<f64> {
    if factors.is_empty()
        || factors.len() != weights.len()
        || factors.iter().chain(weights).any(|x| !x.is_finite())
    {
        return None;
    }
    let result: f64 = factors.iter().zip(weights).map(|(f, w)| f * w).sum();
    result.is_finite().then_some(result)
}
```

静默 `zip` 不等长切断会漏掉因子，所以先检查长度。组合前还要处理量纲、相关性、异常值、模型版本和缺失因子策略。

## 7. 研究结果怎样进入生产

至少验证：

- 没有 future leakage：只使用当时已经可见的数据；
- 训练、回放和生产使用相同事件顺序、warm-up 与缺失值规则；
- 加入费用、延迟、成交模型和容量约束后仍理解结果变化；
- 在多个时间段/市场状态做样本外检验，并报告不确定性；
- 信号失效、行情 stale 或模型文件损坏时能 fail closed/安全降级；
- 监控输入分布、输出饱和、NaN、漂移和决策覆盖率。

统计相关不等于因果，更不保证未来收益。部署信号还要遵守数据许可、交易规则和公司模型治理。

## 8. 面试追问与易错点

**增量算法为什么仍要全量重算？** 用于控制浮点漂移、恢复状态和验证实现；全量版本也是很好的测试 oracle。

**为什么不让 invalid signal 返回 0？** 0 可能是有意义的中性值，会掩盖数据缺失；显式 `Option/Result` 或状态位更安全。

**SIMD 一定降低 tick-to-trade 吗？** 不一定。批处理等待和数据搬运可能抵消计算收益，必须测端到端分布。

易错点包括：alpha 越界、窗口容量为 0、未 warm-up 就交易、NaN 传播、Z-score 除零、绝对时间导致回归数值不稳、`zip` 静默截断，以及把订单簿不平衡度描述成必然价格方向。

验证应使用边界单测、随机序列对比朴素实现、确定性重放、数据缺口/乱序、长时间漂移和目标硬件基准；上线后持续做输入与输出分布监控。

---

下一章：[执行算法 (Execution Algos)](execution.md)

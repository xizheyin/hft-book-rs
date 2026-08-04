# 预交易风控实战 (Pre-trade Risk Check)

预交易风控位于订单意图和实际发送之间。它的第一目标是保证限制不被突破；在此基础上，再把延迟控制在系统预算内。不存在脱离硬件、负载和规则数量的“统一纳秒目标”。

## 1. 需要同时保证什么

1. 检查与额度预占是一个一致动作，避免 TOCTOU；
2. 新单按“最坏情况下全部成交”占用风险；
3. ACK 不改变已确认持仓，只有去重后的 Fill 改变持仓；
4. Reject、Cancel ACK 和 Expire 只释放尚未成交的预占；
5. 运算溢出、行情陈旧或配置缺失时按政策拒绝，而不是默认通过；
6. 每次拒绝都带稳定原因码和配置版本，便于审计。

热路径通常会避免临时分配和远程查询，但“无分配”是经过测量的实现目标，不是删除正确性检查的理由。

## 2. 静态检查：先把单位说清楚

```rust
#[derive(Debug, Clone, Copy)]
pub struct RiskConfig {
    pub max_qty: u64,
    pub max_notional_units: i128,
    pub min_price_ticks: i64,
    pub max_price_ticks: i64,
    pub tick_multiple: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RiskError {
    InvalidQuantity,
    InvalidPrice,
    InvalidTick,
    NotionalTooLarge,
    ArithmeticOverflow,
    InvalidLimit,
    PositionLimit,
    StaleReferencePrice,
}

#[derive(Debug, Clone, Copy)]
pub struct NewOrder {
    pub price_ticks: i64,
    pub quantity: u64,
}

pub fn check_static(order: &NewOrder, cfg: &RiskConfig) -> Result<(), RiskError> {
    if order.quantity == 0 || order.quantity > cfg.max_qty {
        return Err(RiskError::InvalidQuantity);
    }
    if order.price_ticks < cfg.min_price_ticks
        || order.price_ticks > cfg.max_price_ticks
    {
        return Err(RiskError::InvalidPrice);
    }
    if cfg.tick_multiple <= 0 || order.price_ticks % cfg.tick_multiple != 0 {
        return Err(RiskError::InvalidTick);
    }

    let notional = i128::from(order.price_ticks)
        .checked_abs()
        .ok_or(RiskError::ArithmeticOverflow)?
        .checked_mul(i128::from(order.quantity))
        .ok_or(RiskError::ArithmeticOverflow)?;
    if notional > cfg.max_notional_units {
        return Err(RiskError::NotionalTooLarge);
    }
    Ok(())
}
```

实际名义金额还可能包含价格缩放、合约乘数、币种换算和期权/期货特定口径。`wrapping_mul` 不适合风控：溢出后的较小数字可能错误通过。手工填充缓存行也不应靠猜；先检查 `size_of`、访问模式和性能计数器。

`#[inline(always)]` 和分支提示同样不是默认答案。编译器可能自行内联，罕见的拒绝分支也会在事故时集中出现；应查看编译产物并用真实通过/拒绝分布测试。

## 3. 动态检查：区分持仓与预占

只记录一个 `position` 不够。假设已确认持仓为 70，同时有未成交买单 20；再买 15 的最坏多头是 105，而不是 85。

```rust
# use std::convert::TryFrom;
# #[derive(Debug)]
# enum RiskError { InvalidQuantity, InvalidLimit, ArithmeticOverflow, PositionLimit }
#[derive(Debug, Clone, Copy)]
pub enum Side { Buy, Sell }

#[derive(Debug, Default)]
pub struct PositionRisk {
    /// 只由去重后的 Fill 更新。
    confirmed_position: i64,
    /// 已被交易所接受或仍可能被接受的订单剩余量。
    open_buy_qty: u64,
    open_sell_qty: u64,
    max_abs_position: i64,
}

impl PositionRisk {
    /// 由该状态的唯一所有者调用；成功即完成预占。
    pub fn try_reserve(&mut self, side: Side, qty: u64) -> Result<(), RiskError> {
        if qty == 0 {
            return Err(RiskError::InvalidQuantity);
        }
        if self.max_abs_position < 0 {
            return Err(RiskError::InvalidLimit);
        }
        let next_buy = match side {
            Side::Buy => self.open_buy_qty.checked_add(qty),
            Side::Sell => Some(self.open_buy_qty),
        }.ok_or(RiskError::ArithmeticOverflow)?;

        let next_sell = match side {
            Side::Sell => self.open_sell_qty.checked_add(qty),
            Side::Buy => Some(self.open_sell_qty),
        }.ok_or(RiskError::ArithmeticOverflow)?;

        let buy = i64::try_from(next_buy).map_err(|_| RiskError::ArithmeticOverflow)?;
        let sell = i64::try_from(next_sell).map_err(|_| RiskError::ArithmeticOverflow)?;
        let worst_long = self.confirmed_position
            .checked_add(buy)
            .ok_or(RiskError::ArithmeticOverflow)?;
        let worst_short = self.confirmed_position
            .checked_sub(sell)
            .ok_or(RiskError::ArithmeticOverflow)?;

        if worst_long > self.max_abs_position || worst_short < -self.max_abs_position {
            return Err(RiskError::PositionLimit);
        }

        self.open_buy_qty = next_buy;
        self.open_sell_qty = next_sell;
        Ok(())
    }
}
```

生产实现还要按 `OrderId` 保存每张订单的已预占剩余量，否则重复 Reject 或 Cancel ACK 可能多释放额度。

上述模型是保守硬限制：如果当前持仓已经越限，它也可能拒绝普通减仓意图，因为无法假设这张减仓单一定先成交。若业务允许 `reduce-only` 例外，应单独验证方向、最大可减数量、是否可能反手，并处理已有同向未结单；不能简单跳过持仓检查。

### 3.1 事件怎样搬移风险

| 事件 | 已确认持仓 | 未结订单预占 |
| --- | --- | --- |
| New 通过本地风控 | 不变 | 增加整单数量 |
| ACK | 不变 | 通常不变 |
| Partial Fill | 按成交方向改变 | 减少同等成交量 |
| Full Fill | 按成交方向改变 | 对应订单归零 |
| Reject | 不变 | 释放该订单尚未成交量 |
| Cancel 已发送 | 不变 | **不释放** |
| Cancel ACK / Expire | 不变 | 释放权威确认的剩余量 |

Fill、Reject 和 Cancel ACK 必须按协议执行 ID/序号幂等处理。撤单与成交竞态下，可能先部分成交，再取消剩余。

## 4. 为什么一个 `fetch_add` 不等于完整风控

“先对净持仓 `fetch_add(qty)`，超限再 `fetch_sub`”有几个问题：

- 它把订单预占伪装成已确认持仓；
- 同时存在买卖未结单时，只看净额会低估两侧最坏边界；
- 多字段规则不能由一个原子变量一致更新；
- 溢出、重复回报和失败回滚需要额外协议；
- 回滚期间的临时状态会被其他线程观察到。

更容易证明的方案是：

1. 单一风险所有者串行执行 `check + reserve + event update`；
2. 用锁保护完整复合状态，先建立正确基线；
3. 给分片发放总和不超过全局上限的额度租约，并用 generation/fencing 防双主；
4. 只有在规则能压缩成一个原子状态时，才用 CAS 循环并证明所有边界。

锁不天然是“性能杀手”；错误的无锁回滚才会直接破坏风控。

## 5. 价格偏离检查必须包含数据新鲜度

```rust
# #[derive(Debug)]
# enum RiskError { StaleReferencePrice, ArithmeticOverflow, InvalidPrice }
pub fn check_price_deviation(
    order_price: i64,
    reference_price: Option<i64>,
    reference_is_live: bool,
    max_deviation_bps: u32,
) -> Result<(), RiskError> {
    let reference = reference_price
        .filter(|p| *p > 0 && reference_is_live)
        .ok_or(RiskError::StaleReferencePrice)?;

    let diff = (i128::from(order_price) - i128::from(reference)).abs();
    let left = diff
        .checked_mul(10_000)
        .ok_or(RiskError::ArithmeticOverflow)?;
    let right = i128::from(reference)
        .checked_mul(i128::from(max_deviation_bps))
        .ok_or(RiskError::ArithmeticOverflow)?;

    (left <= right).then_some(()).ok_or(RiskError::InvalidPrice)
}
```

参考价可以是 BBO、mid、最新成交或外部理论价，但要配置来源、时间戳、允许陈旧度和单边市场行为。没有参考行情时直接 `Ok(())` 是危险默认值；是否允许特殊减险订单通过，应由明确政策单独处理。

## 6. 组合与全局限额

账户总敞口、行业集中度或期权 Greeks 往往跨标的。周期性把分片计数相加只能用于监控，不能执行必须瞬时不越界的硬限制。常见方案是：

- 将强相关状态交给一个组合风险所有者；
- 预先切分硬额度，保证所有分片额度之和不超过全局上限；
- 给额度转移加版本和 fencing；
- 用独立成交回报持续核对本地状态。

## 7. 怎样验证，而不是猜延迟

- 边界测试：0、上限、上限 ±1、最大整数和负价格；
- 状态测试：New → Partial Fill → Cancel ACK、Cancel/Fill 竞态；
- 性质测试：任何可达状态都满足 worst-long/short 限制；
- 幂等测试：同一 Fill/Reject 重放不改变第二次结果；
- 并发测试：Loom 类模型检查状态所有权/同步；
- 基准：在目标硬件报告通过与拒绝路径的 p50/p99、竞争度和端到端开销。

不要预写“静态检查必为 2ns”一类数字；缓存、编译器、打点和输入分布都会改变结果。

## 8. 面试追问与易错点

**为什么 Cancel 发出后不能释放额度？** 因为交易所确认前订单仍可能成交；只有 Fill 转换占用，或 Cancel ACK/Expire 释放剩余。

**两个方向的未结单能否净额抵消？** 对最大净持仓限制，最坏多头和最坏空头要分别检查。是否允许组合抵消由具体风险模型决定，不能默认两单会同时成交。

**原子一定比锁好吗？** 单字段计数器可能适合原子；多字段不变量用单一所有者或锁更容易正确。选择要有并发证明和基准数据。

常见错误是用 wrapping 运算、把 ACK 当 Fill、重复回报多次更新、用陈旧参考价、多个分片定期汇总却声称是硬限制，以及为追求延迟绕过风控。

---

下一章：[持仓管理 (Position Management)](position.md)

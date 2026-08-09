# 持仓管理 (Position Management)

持仓是成交事实的本地投影。最重要的不变量是：

> **已确认持仓只由去重后的成交（Fill）改变。** New、ACK、Cancel 请求和 Cancel ACK 都不直接改变已确认持仓。

未成交订单会产生风险，但应记录为 reservation/open-order exposure，而不是伪装成已经持有的仓位。两者的关系见[预交易风控](pre_trade_risk.md)。

## 1. 先定义口径

| 状态 | 来源 | 用途 |
| --- | --- | --- |
| Confirmed position | 唯一成交回报 | 持仓账本和成交后风险 |
| Open buy/sell quantity | 订单状态机 | 预交易最坏边界 |
| Strategy view | 上述状态的只读投影 | 策略决策，可能稍旧 |
| External position | Drop copy、经纪商或清算来源 | 独立对账 |

成本方法也不是技术团队随意选择的“最快算法”。平均成本、FIFO、逐笔 lot 等口径取决于产品、会计、税务和报表要求；实时策略估值与正式账本可以采用不同口径，但必须明确转换和核对。

## 2. 平均成本教学实现

下面代码用于解释多空、减仓和反手。它使用 `f64`，没有费用、币种和合约乘数，因此**不能直接作为正式资金账本**。生产系统通常使用十进制定点/足够宽整数，并定义每一步舍入规则。

```rust
#[derive(Debug, Default, Clone, Copy)]
pub struct AverageCostPosition {
    pub quantity: i64,             // 正数为多，负数为空
    pub average_price_ticks: f64,  // 教学简化
    pub realized_pnl_ticks: f64,   // 尚未乘合约乘数、汇率，未扣费用
    pub total_volume: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PositionError {
    ZeroFill,
    InvalidPrice,
    QuantityOverflow,
    VolumeOverflow,
    NumericOverflow,
}

impl AverageCostPosition {
    /// signed_qty: 买入为正，卖出为负。
    pub fn on_fill(
        &mut self,
        signed_qty: i64,
        fill_price_ticks: f64,
    ) -> Result<(), PositionError> {
        if signed_qty == 0 {
            return Err(PositionError::ZeroFill);
        }
        if !fill_price_ticks.is_finite() || fill_price_ticks <= 0.0 {
            return Err(PositionError::InvalidPrice);
        }

        let old_qty = self.quantity;
        let new_qty = old_qty
            .checked_add(signed_qty)
            .ok_or(PositionError::QuantityOverflow)?;
        let fill_abs = signed_qty.unsigned_abs();
        let old_abs = old_qty.unsigned_abs();
        let next_volume = self.total_volume
            .checked_add(fill_abs)
            .ok_or(PositionError::VolumeOverflow)?;
        let mut next_average = self.average_price_ticks;
        let mut next_realized = self.realized_pnl_ticks;

        if old_qty == 0 {
            next_average = fill_price_ticks;
        } else if old_qty.signum() == signed_qty.signum() {
            let old_cost = self.average_price_ticks * old_abs as f64;
            let added_cost = fill_price_ticks * fill_abs as f64;
            next_average = (old_cost + added_cost) / new_qty.unsigned_abs() as f64;
        } else {
            let closed = old_abs.min(fill_abs);
            let pnl_per_unit = if old_qty > 0 {
                fill_price_ticks - self.average_price_ticks
            } else {
                self.average_price_ticks - fill_price_ticks
            };
            next_realized += pnl_per_unit * closed as f64;

            if new_qty == 0 {
                next_average = 0.0;
            } else if old_qty.signum() != new_qty.signum() {
                // 反手后，超出平仓部分以本次成交价建立新成本。
                next_average = fill_price_ticks;
            }
            // 仅减仓且未反手时，剩余仓位平均成本不变。
        }

        if !next_average.is_finite() || !next_realized.is_finite() {
            return Err(PositionError::NumericOverflow);
        }
        self.quantity = new_qty;
        self.average_price_ticks = next_average;
        self.realized_pnl_ticks = next_realized;
        self.total_volume = next_volume;
        Ok(())
    }
}
```

算例：原来多 10，均价 100；卖 15，成交价 103。先平掉 10，产生 `30` 个“价格 tick × 数量”的已实现结果；剩余空 5，新的平均入场价是 103。费用与乘数要在约定层处理。

### 2.1 先去重，再调用 `on_fill`

同一成交回报可能因重连或重放到达多次。更新流程应是：

1. 验证订单、账户、合约和 execution ID；
2. 按协议会话语义判断该 execution ID 是否已应用；
3. 只在第一次应用时更新订单累计成交、持仓、费用和风险；
4. 将“已应用”与状态事件放在同一可恢复顺序中；
5. 重启后恢复去重状态，再接收重放。

不要用 `(价格, 数量, 时间)` 去重，两笔合法成交可能具有完全相同的这些字段。

## 3. Reservation 不是 Shadow Position

“发出买单后立即把持仓加上，Reject 时再减回”会混淆事实与可能性。更清晰的状态是：

```text
confirmed_position = 只由 Fill 更新
open_buy_qty        = 仍可能成交的买单剩余量
open_sell_qty       = 仍可能成交的卖单剩余量

worst_long  = confirmed_position + open_buy_qty
worst_short = confirmed_position - open_sell_qty
```

事件转换：

- New 风控通过：增加对应 open quantity；
- ACK：通常不改变三者；
- Buy Fill 4：`open_buy_qty -= 4`，`confirmed_position += 4`；
- Cancel 请求：不释放；
- Cancel ACK：释放权威确认的 leaves quantity；
- Reject：释放该订单尚未成交的预占。

每次释放都必须关联具体订单及其剩余预占，避免重复回报导致下溢或释放别人的额度。

## 4. 并发所有权

推荐让订单状态、成交去重、已确认持仓和预占由同一账户/分片所有者按序更新。这样一条 Fill 能原子地完成“订单 leaves 减少 → position 增加 → reservation 转换”。

如果其他线程只需要数量，可发布 `AtomicI64` 的派生读视图；但它不提供与平均成本、PnL 和订单预占一致的复合快照。需要完整快照时使用标准锁、不可变 `Arc<Snapshot>` 或经过验证的发布机制，不要对普通 `Position` 套用手写 `UnsafeCell` SeqLock。

内存序不能凭习惯统一用 Relaxed 或 SeqCst。先确定谁发布、谁读取以及需要同时可见的字段，再证明同步关系并用并发测试验证。

## 5. PnL 不是一个无上下文数字

至少区分：

- realized PnL：已平部分，依赖成本方法；
- unrealized PnL：当前仓位相对某个 mark price 的估值；
- fees/rebates：交易费、清算费、返佣等；
- FX 与 contract multiplier；
- gross 与 net、交易日和结算价口径。

行情丢失时 mark 可能陈旧，因此 PnL 告警要携带价格来源和新鲜度。不能用陈旧 PnL 作为唯一自动动作依据。

## 6. 对账与恢复

内部实时持仓不是最终外部事实。系统要用独立 drop copy、经纪商/清算记录核对：

- 每个 execution ID 是否一致；
- 累计成交量和 leaves quantity 是否守恒；
- 账户、合约、币种和交易日映射是否一致；
- 手工交易、改单和 bust/correct 事件是否纳入；
- 本地与外部持仓差异是否为 0。

发现差异时先阻止扩大相关风险，保存差异证据，再按权威来源产生可审计的修复事件；不要静默覆盖本地数字。

## 7. 做题方法：按成交逐笔更新持仓与成本

1. **读题定符号和口径**：多头为正还是空头为负，价格缩放、合约乘数、费用币种、已实现/未实现 PnL 定义先写清。
2. **画成交表**：每笔 Fill 记录执行 ID、方向、数量、价格、成交前仓位/成本、成交后仓位/成本与已实现 PnL 增量。
3. **分三种情况计算**：同方向加仓更新成本；反方向但未穿零先减少仓位并实现对应盈亏；穿零时先平旧仓，剩余数量以成交价建立反向新仓。
4. **Reservation 单独记账**：在途预占不是已成交仓位；Fill 将相应预占转成仓位，Reject/CancelAck 才释放剩余预占。
5. **验算**：重复执行 ID 不二次入账；净数量等于带符号成交量之和；现金流、仓位市值和 PnL 在同一价格/费用口径下对得上；drop copy/清算差异可定位。

常见陷阱：反手时整笔都按平仓算；平均成本与 FIFO 税务/会计口径混用；撤单发送即释放 reservation；费用和乘数漏算；用浮点长期累积货币误差。

## 8. 面试追问、易错点与验证

**ACK 为什么不改变持仓？** ACK 表示订单通常已被接受，尚不代表成交；只有 Fill 是持仓变化事实。

**Cancel 发出后风险能否释放？** 不能。确认前原单可能成交，必须等 Cancel ACK/Expire 或用 Fill 转换对应数量。

**AtomicI64 是否足够？** 只够发布单个数量视图；成本、PnL、open orders 和去重需要一致的复合状态。

易错点包括：精确平仓后忘记把平均成本清零、反手仍沿用旧成本、重复 Fill 更新两次、忽略费用/乘数、把 reservation 当持仓，以及用浮点结果做正式资金账本。

验证至少覆盖：开仓、同向加仓、部分减仓、精确平仓、反手、多空对称、溢出、重复/乱序 Fill、Cancel/Fill 竞态，以及与逐笔朴素参考实现的性质对比。

---

上一章：[预交易风控实战](pre_trade_risk.md) ｜ 下一章：[策略框架设计](strategy.md)

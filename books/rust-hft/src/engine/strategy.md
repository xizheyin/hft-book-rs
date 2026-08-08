# 策略框架设计 (Strategy Framework Design)

策略框架把可信市场状态转换为订单**意图**。它不应绕过预交易风控、直接篡改持仓，或把本地发送结果当作成交事实。

## 1. 设计目标

1. **可测量的延迟**：在给定负载下满足 tick-to-intent / tick-to-trade 的 p50、p99 预算，而不是笼统要求“纳秒级”；
2. **安全边界**：所有意图经过权限、风控、限流和最终网关；
3. **可重放性**：相同初始状态、输入顺序、配置、时钟和随机种子应产生可比较结果；
4. **明确所有权**：订单状态、持仓和风险分别有权威所有者；
5. **易验证**：策略逻辑可在没有真实 socket 的环境中回放和故障注入。

浮点运算、并发调度、外部时间和硬件差异都可能影响逐位确定性，因此必须说明要求的是“业务输出相同”还是“每一位都相同（bit-for-bit）”。

## 2. 基于事件与意图的接口

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct InstrumentId(pub u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ClientOrderId(pub u64);

#[derive(Debug, Clone, Copy)]
pub struct MonoTime(pub u64);

pub struct BookView {
    pub sequence: u64,
    pub is_live: bool,
}

pub enum OrderEvent { Ack, Reject, Fill { quantity: u64 }, CancelAck }
pub struct NewOrderIntent { pub price_ticks: i64, pub quantity: u64 }
pub struct LocalReject;
pub struct OpenExposure { pub buy_qty: u64, pub sell_qty: u64 }

pub trait Strategy<C: StrategyContext> {
    fn on_book(&mut self, book: &BookView, ctx: &mut C);
    fn on_timer(&mut self, now: MonoTime, ctx: &mut C);
    fn on_order_event(&mut self, event: &OrderEvent, ctx: &mut C);
}

pub trait StrategyContext {
    /// 成功只表示本地意图已被接受并分配 Client ID，不表示场所 ACK/Fill。
    fn submit(&mut self, intent: NewOrderIntent) -> Result<ClientOrderId, LocalReject>;
    fn cancel(&mut self, id: ClientOrderId) -> Result<(), LocalReject>;
    fn confirmed_position(&self, instrument: InstrumentId) -> i64;
    fn open_order_exposure(&self, instrument: InstrumentId) -> OpenExposure;
}
```

`BookView` 应携带行情序号、市场状态和 `is_live`；仅有一个非空价格不代表数据可信。`StrategyContext` 提供的是持仓/订单权威状态的只读投影，真正更新由订单回报和成交处理器完成。

## 3. 静态分发与动态分发

泛型或 enum dispatch 可能让编译器内联小回调；选定具体 Context 后，`Box<dyn Strategy<LiveContext>>` 则支持运行时组合和较稳定的编译边界。动态调用并非必然慢到不可用，静态分发也不保证一定内联，还可能增大代码体积和指令缓存压力。

选择方法：

| 需求 | 可考虑 |
| --- | --- |
| 单一固定策略、极短回调 | 泛型/enum dispatch |
| 插件化、运行时切换 | trait object 或进程隔离 |
| 多策略共享网关 | 明确队列、额度和故障隔离 |

`submit` 很可能就在 tick-to-trade 关键路径上，不能因为调用频率比行情低就未经测量地断言动态分发“无影响”。用目标二进制和端到端负载比较。

## 4. 热路径分配的真实边界

堆分配可能造成分配器竞争、缺页或尾延迟，因此常见做法是整数 `InstrumentId`、栈上小意图、预分配有界队列和缓冲复用。但“任何分配绝对禁止”过于绝对：控制面、启动期和冷拒绝路径可以选择更简单的实现。

关键问题是：

- 分配是否位于已定义的关键路径；
- 峰值时对象池满了怎么办；
- 是否会隐式扩容；
- 复用槽位如何防止旧 ID 指向新对象；
- 优化后 p99 是否真的改善。

对象池耗尽时不能默默覆盖活跃订单；应拒绝新意图或安全降级，并保留 Cancel/kill 通道。

## 5. 报价示例：先写状态机，再写价格公式

下面只演示单侧订单生命周期，不代表可盈利策略。价格用整数 tick；真实报价还要处理库存、费用、市场状态、自成交和场所规则。

```rust
# #[derive(Debug, Clone, Copy)]
# struct ClientOrderId(u64);
# struct NewOrderIntent;
# impl NewOrderIntent { fn buy(_price_ticks: i64, _quantity: u64) -> Self { Self } }
# struct LocalReject;
# trait StrategyContext {
#     fn submit(&mut self, intent: NewOrderIntent) -> Result<ClientOrderId, LocalReject>;
#     fn cancel(&mut self, id: ClientOrderId) -> Result<(), LocalReject>;
# }
#[derive(Debug, Clone, Copy)]
enum QuoteState {
    Idle,
    PendingNew { id: ClientOrderId, price_ticks: i64 },
    Working { id: ClientOrderId, price_ticks: i64 },
    PendingCancel { id: ClientOrderId },
}

fn on_target(
    state: &mut QuoteState,
    target_price_ticks: i64,
    ctx: &mut impl StrategyContext,
) {
    match *state {
        QuoteState::Idle => {
            if let Ok(id) = ctx.submit(NewOrderIntent::buy(target_price_ticks, 10)) {
                *state = QuoteState::PendingNew { id, price_ticks: target_price_ticks };
            }
        }
        QuoteState::Working { id, price_ticks } if price_ticks != target_price_ticks => {
            if ctx.cancel(id).is_ok() {
                // 不把 id 清空：Cancel ACK 前旧单仍可能成交。
                *state = QuoteState::PendingCancel { id };
            }
        }
        QuoteState::PendingNew { .. } | QuoteState::PendingCancel { .. } => {
            // 等权威事件；是否允许重叠替代单取决于额外风险预算和场所语义。
        }
        QuoteState::Working { .. } => {}
    }
}
```

事件处理还必须覆盖：

- New ACK：`PendingNew → Working`；
- Reject：释放本地意图/风险，回到可决策状态；
- Partial Fill：更新目标完成量，但订单可能仍 Working/PendingCancel；
- Full Fill：进入终态，不再等待普通 Cancel ACK；
- Cancel ACK：只释放确认的 leaves；
- 连接断开：不能确定的订单进入 Unknown，并保留最坏风险。

绝不能在发出 Cancel 后立即把 `order_id = None`，否则下一个 tick 可能再发一张单，而旧单仍在场内。

## 6. 状态恢复：事件溯源不是只重放 ACK/Fill

要重现策略决策，可能需要：

- 原始或规范化行情及其序号；
- 市场状态、定时器和本地可见时间；
- 配置版本、模型版本和随机种子；
- 订单意图、风控结果、实际发送消息；
- ACK、Reject、Fill、Cancel ACK 和 bust/correct；
- 初始持仓、人工动作和 kill 状态。

重启时只重放本地事件仍不能证明场内订单状态；还要用会话重放、查询和独立 drop copy 对账。在恢复门禁通过前策略不应自动恢复普通新单。

## 7. Async 与时间源

`async fn` 适合大量等待型连接，但在单线程确定性事件循环里，显式状态机通常更容易控制分配、唤醒和事件顺序。这不是“策略中禁止 async”的语言规则；选择要看 I/O 模型、延迟目标和实测。

策略最好由引擎注入时间，主要原因是语义和可重放性：

- 交易所事件时间用于描述外部事件；
- 单调本地时间用于超时和持续时间；
- 墙上时间用于报表，不应直接驱动关键超时。

`SystemTime::now()` 是否发生系统调用取决于平台实现；不能把禁用理由简化为“它一定很慢”。跨核 TSC 也必须验证稳定性与同步，不能凭线程缓存时间保证正确。

## 8. 面试追问、易错点与验证

**为什么策略不能直接持有 socket？** 隔离协议、风控和会话状态，使回放与单元测试可复用，并保证所有订单经过统一发送门。

**相同行情一定产生相同订单吗？** 只有初始状态、配置、时钟、随机性、订单回报顺序等也相同时才可讨论；还要定义数值确定性级别。

**静态分发一定更快吗？** 不一定。它可能内联，也可能造成代码膨胀；应看编译产物和端到端分布。

易错点包括：把 `submit Ok` 当 ACK、把 ACK 当 Fill、Cancel 即清空 ID、策略维护另一份权威持仓、在 stale 行情上报价、使用浮点价格比较 tick，以及用固定纳秒要求替代延迟预算。

验证应包含确定性双跑、行情重复/缺口、ACK/Fill 乱序、Cancel/Fill 竞态、对象池耗尽、限流、时钟跳变和 crash recovery。策略输出还需经过风险/合规审查；报价必须有真实交易意图。

---

下一章：[信号生成 (Signal Generation)](signals.md)

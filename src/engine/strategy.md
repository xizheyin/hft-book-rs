# 策略框架设计 (Strategy Framework)

策略框架是量化交易系统的“大脑”。它定义了策略如何感知市场、如何做出决策以及如何与外部世界交互。

在 HFT 中，策略框架的设计必须兼顾**灵活性**（方便开发新策略）和**极致性能**（不能引入虚函数开销或动态分发）。

## 1. 核心设计原则

1.  **静态分发 (Static Dispatch)**: 使用泛型和 Trait Bounds，避免 `Box<dyn Strategy>` 带来的 vtable 查找开销。
2.  **事件驱动 (Event Driven)**: 策略本质上是一个状态机，响应各种输入事件（行情、成交、定时器）。
3.  **确定性 (Determinism)**: 给定相同的输入序列，策略必须产生相同的输出。这是回测准确性的基石。

## 2. 策略接口 (The Strategy Trait)

我们定义一个核心 Trait，所有具体策略都必须实现它。

```rust
use crate::common::types::{MdUpdate, ExecutionReport, TimerId};
use crate::engine::context::Context;

pub trait Strategy {
    /// 策略初始化
    fn on_init(&mut self, ctx: &mut Context);

    /// 收到市场行情 (L1/L2/L3)
    fn on_market_data(&mut self, ctx: &mut Context, update: &MdUpdate);

    /// 收到订单成交回报
    fn on_execution(&mut self, ctx: &mut Context, fill: &ExecutionReport);

    /// 定时器触发
    fn on_timer(&mut self, ctx: &mut Context, timer_id: TimerId);

    /// 策略停止
    fn on_stop(&mut self, ctx: &mut Context);
}
```

### 2.1 上下文 (Context)
`Context` 是策略与外界交互的唯一窗口。策略不应该直接访问全局变量或单例。
`Context` 提供了：
*   **发送订单**: `ctx.send_order(...)`
*   **查询持仓**: `ctx.get_position(...)`
*   **设置定时器**: `ctx.set_timer(...)`
*   **记录日志**: `ctx.log(...)`

这种设计使得我们在回测时可以轻松替换 `Context` 的实现（Mock），注入历史数据并捕获发单请求。

```rust
pub struct Context<'a> {
    pub order_gateway: &'a mut OrderGateway,
    pub market_data: &'a MarketDataCache,
    pub position_manager: &'a PositionManager,
    // ...
}

impl<'a> Context<'a> {
    #[inline(always)]
    pub fn send_new_order(&mut self, order: NewOrder) {
        // 实际上这里可能会做一些预处理，然后推送到网关队列
        self.order_gateway.send(order);
    }
}
```

## 3. 策略容器 (Strategy Engine)

策略引擎负责驱动策略。在生产环境中，它是一个死循环，不断从 RingBuffer 中拉取事件并分发给策略。

```rust
pub struct Engine<S: Strategy> {
    strategy: S,
    event_bus: Consumer<Event>,
    context: ContextData, // 拥有 Context 所需的数据所有权
}

impl<S: Strategy> Engine<S> {
    pub fn run(&mut self) {
        let mut ctx = self.create_context();
        self.strategy.on_init(&mut ctx);

        loop {
            // 忙轮询 (Busy Polling)
            if let Some(event) = self.event_bus.pop() {
                match event {
                    Event::Md(update) => self.strategy.on_market_data(&mut ctx, &update),
                    Event::Fill(fill) => self.strategy.on_execution(&mut ctx, &fill),
                    Event::Timer(id) => self.strategy.on_timer(&mut ctx, id),
                    Event::Stop => break,
                }
            }
            // 可以插入 CPU relax 指令，或者处理 idle 逻辑
        }

        self.strategy.on_stop(&mut ctx);
    }
}
```

## 4. 示例策略：做市商 (Market Maker)

下面是一个简单的 Ping-Pong 做市策略示例。

```rust
struct PingPongStrategy {
    symbol_id: u16,
    spread: i64,
    qty: u32,
    bid_order_id: Option<u64>,
    ask_order_id: Option<u64>,
}

impl Strategy for PingPongStrategy {
    fn on_market_data(&mut self, ctx: &mut Context, update: &MdUpdate) {
        // 简单的逻辑：在 BestBid - spread 和 BestAsk + spread 挂单
        let bbo = ctx.market_data.get_bbo(self.symbol_id);
        
        let target_bid = bbo.bid_price - self.spread;
        let target_ask = bbo.ask_price + self.spread;

        // 更新买单
        if let Some(oid) = self.bid_order_id {
            // 如果价格变了，修改订单
            // ...
        } else {
            // 发新单
            let oid = ctx.next_id();
            ctx.send_new_order(NewOrder {
                symbol_id: self.symbol_id,
                price: target_bid,
                quantity: self.qty,
                side: Side::Buy,
                cl_ord_id: oid,
                // ...
            });
            self.bid_order_id = Some(oid);
        }
        
        // 更新卖单 (同理)
    }

    fn on_execution(&mut self, ctx: &mut Context, fill: &ExecutionReport) {
        if fill.side == Side::Buy {
            // 买单成交了，立即在上面挂卖单（平仓）
            self.bid_order_id = None;
            // logic to place sell order...
        }
    }
}
```

## 5. 避免常见陷阱

### 5.1 不要在回调中阻塞
`on_market_data` 必须在纳秒级完成。绝对不能做 I/O (文件读写、数据库访问)、锁等待或复杂的数学运算（如矩阵求逆）。
复杂计算应卸载到辅助线程。

### 5.2 状态一致性
策略内部状态（如 `bid_order_id`）必须与交易所状态保持一致。
如果发单失败了（被风控拒绝），必须重置 `bid_order_id = None`，否则策略会以为自己还有挂单，不再补单。

### 5.3 确定性时间
不要在策略里调用 `SystemTime::now()`。这会破坏回测的可重复性。应该使用 `ctx.now()`，在回测时返回历史时间，实盘时返回系统时间。

---
下一章：[信号生成 (Signal Generation)](signals.md)

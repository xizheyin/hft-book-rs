# 策略框架设计 (Strategy Framework Design)

交易策略是 HFT 系统的“大脑”。一个优秀的策略框架应该让 Quant 能够专注于 Alpha 逻辑，而不用关心底层的网络通信、订单路由或风控细节。

## 1. 设计目标

1.  **极低延迟 (Ultra-Low Latency)**: 从收到 Market Data 到发出 Order 的路径必须是纳秒级的。
2.  **安全性 (Safety)**: 必须防止策略发送非法订单（Fat Finger），这通常通过预交易风控（Pre-Trade Risk）实现。
3.  **确定性 (Determinism)**: 相同的输入必须产生相同的输出，这对回测和调试至关重要。
4.  **易用性 (Ergonomics)**: 提供清晰、类型安全的 API。

## 2. 核心架构：基于 Trait 的回调系统

我们使用 Rust 的 `trait` 来定义策略接口。为了实现零成本抽象，我们优先使用静态分发（泛型）。

```rust
pub trait Strategy {
    // 市场数据回调
    fn on_tick(&mut self, tick: &Tick);
    fn on_order_book_update(&mut self, book: &OrderBook);
    
    // 订单状态回调
    fn on_order_ack(&mut self, order_id: OrderId);
    fn on_order_fill(&mut self, fill: &Fill);
    fn on_order_reject(&mut self, reason: RejectReason);
}
```

### 2.1 静态分发 vs 动态分发

在 HFT 中，我们通常为每个策略编译一个独立的二进制文件，或者使用 Enum Dispatch，而不是 `Box<dyn Strategy>`。

```rust
// 推荐：静态分发
struct Engine<S: Strategy> {
    strategy: S,
    risk_manager: RiskManager,
    order_router: OrderRouter,
}

impl<S: Strategy> Engine<S> {
    #[inline(always)]
    fn on_market_data(&mut self, data: MarketData) {
        // 1. 更新内部状态
        // 2. 调用策略
        self.strategy.on_tick(&data.tick);
    }
}
```

这种方式允许编译器将 `on_tick` 完全内联到 Engine 的循环中，消除函数调用开销。

## 3. 上下文与指令发送

策略不应该直接持有网络 socket。相反，它应该通过一个 `Context` 对象与外界交互。这有助于单元测试和回测。

```rust
pub trait StrategyContext {
    fn send_order(&mut self, order: NewOrder) -> Result<OrderId, RejectReason>;
    fn cancel_order(&mut self, order_id: OrderId);
    fn get_position(&self, symbol: Symbol) -> i64;
}

// 策略实现示例
struct MyMarketMaker {
    context: Box<dyn StrategyContext>, // 在这里使用动态分发是可以接受的，因为 send_order 不是热路径
    // 或者使用泛型 Context
}

impl Strategy for MyMarketMaker {
    fn on_tick(&mut self, tick: &Tick) {
        if tick.price > 100.0 {
            self.context.send_order(NewOrder::new(Side::Buy, 100.0, 10));
        }
    }
}
```

## 4. 避免内存分配

在策略的热路径（Hot Path）中，绝对不能分配堆内存。

### 4.1 预分配对象池
对于 `NewOrder` 对象，不要每次都 `new`。使用对象池或者在栈上分配。

### 4.2 避免 String
使用 `FixedString<N>` 或者 `u64` 类型的 ID。

```rust
// 错误
struct Tick {
    symbol: String, // 堆分配！
}

// 正确
struct Tick {
    symbol_id: u64, // 映射到 Symbol Map
    // 或者
    symbol: [u8; 8],
}
```

## 5. 状态管理与恢复

策略通常是有状态的（Stateful）。例如，它需要记住当前的持仓、未完成订单（Open Orders）以及一些计算指标（如移动平均线）。

如果进程崩溃重启，如何恢复状态？

1.  **持久化 (Persistence)**: 定期将状态序列化到共享内存或磁盘（太慢）。
2.  **事件溯源 (Event Sourcing)**: 推荐。重启时，重放当天的所有 `Fill` 和 `Ack` 消息，重建内存状态。

## 6. 实战：一个简单的做市策略

让我们实现一个最简单的做市策略：在最佳买卖价上各挂一个单子（Quoting）。

```rust
struct SimpleMarketMaker<C: StrategyContext> {
    ctx: C,
    spread: f64,
    qty: u32,
    bid_order_id: Option<OrderId>,
    ask_order_id: Option<OrderId>,
}

impl<C: StrategyContext> Strategy for SimpleMarketMaker<C> {
    fn on_order_book_update(&mut self, book: &OrderBook) {
        let best_bid = book.best_bid();
        let best_ask = book.best_ask();
        
        let target_bid = best_bid - self.spread;
        let target_ask = best_ask + self.spread;

        // 逻辑简化：如果价格变动超过阈值，撤单重发
        if let Some(oid) = self.bid_order_id {
            if (self.current_bid_price(oid) - target_bid).abs() > 0.01 {
                self.ctx.cancel_order(oid);
                self.bid_order_id = None; // 等待 CancelAck 再发新单？这就涉及复杂的状态机了
            }
        } else {
             self.bid_order_id = Some(self.ctx.send_order(NewOrder::buy(target_bid, self.qty)).unwrap());
        }
        
        // Ask 侧同理...
    }
}
```

## 7. 常见陷阱

1.  **回调地狱 (Callback Hell)**:
    异步编程（Future/Async）虽然在 Web 开发中很流行，但在 HFT 策略逻辑中，**状态机 (State Machine)** 模式通常比 Async/Await 更可控、更高效。不要在策略中使用 `async fn`。

2.  **重复发送 (Double Sending)**:
    如果没有正确处理 `Pending` 状态，策略可能会在收到 Ack 之前连续发送多个订单。必须维护订单的生命周期状态。

3.  **时间源问题**:
    不要在策略中调用 `SystemTime::now()`。这会产生系统调用开销。应该由 Engine 传入当前的 Exchange Time 或由专门的 TSC 时钟线程提供的本地时间。

---
下一章：我们将探讨如何从市场数据中提取有价值的信号 —— [信号生成 (Signal Generation)](signals.md)。

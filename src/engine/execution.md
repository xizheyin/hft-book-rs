# 执行算法 (Execution Algos)

策略层决定了“买什么”和“买多少”，而执行层（Execution Layer）决定了“怎么买”。

在 HFT 中，执行不仅仅是简单的发单，更是一场关于**微观结构**和**博弈论**的战斗。优秀执行算法的目标是：
1.  **最小化冲击成本 (Impact Cost)**: 不要因为你的买入把价格推高。
2.  **最大化成交概率 (Fill Rate)**: 想买的时候能买到。
3.  **捕获价差 (Spread Capture)**: 尽量以 Bid 买入，以 Ask 卖出（做市商模式）。

## 1. 挂单类型 (Order Types)

### 1.1 Limit Order (限价单)
最基本的类型。但在 HFT 中，我们需要更高级的属性：
*   **Post-Only (只做 Maker)**: 如果该订单会立即成交（Taker），则自动撤单或调整价格。这保证了你总是获得 Maker Rebate（交易所返佣）。
*   **IOC (Immediate or Cancel)**: 立即成交否则撤销。用于 Taker 策略探测流动性。
*   **FOK (Fill or Kill)**: 全部成交否则撤销。

### 1.2 Iceberg (冰山单)
隐藏真实数量，只显示一小部分（Display Qty）。
**HFT 对抗**: HFT 算法会通过探测（Ping）来发现冰山单，并利用这一信息（例如，如果发现大买单，HFT 会抢先买入推高价格）。

## 2. 常见执行算法

### 2.1 Pegging (挂钩策略)
始终跟随 BBO (Best Bid Offer)。
*   **Peg to Best Bid**: 永远挂在买一价。如果买一价上涨，自动改单跟进。
*   **Peg to Mid**: 挂在中间价（通常用于暗池）。

**实现难点**: 当大量 HFT 同时 Peg 时，会引发“改单风暴” (Quote Flickering)。你需要控制改单频率，避免被交易所限流 (Throttling)。

### 2.2 Sniper (狙击手)
当发现明显的套利机会或错误定价时，不计成本地吃掉流动性。
**关键**: 速度。谁快谁赢。通常使用 IOC 订单。

### 2.3 TWAP / VWAP (时间/成交量加权平均)
用于大单拆分。HFT 通常作为这种算法的**对手方**（识别出有人在跑 VWAP，然后进行掠夺性交易）。但 HFT 自己平仓时也会用到微缩版的 TWAP（在 1 秒内拆成 100 单）。

## 3. 队列位置估计 (Queue Position Estimation)

在 L3 数据中，你可以确切知道自己在队列的哪个位置。但在 L2 数据中，你只能估计。

假设当前 Best Bid 有 1000 手。你挂了 10 手在后面。
1.  **保守估计**: 你在第 1010 位。
2.  **进阶估计**: 如果有人撤单，你前面的队伍会缩短吗？
    *   如果是 FIFO 撮合：前面的撤单让你前进。
    *   如果是 Pro-Rata 撮合（如期货）：按比例分配。

**算法**:
维护一个变量 `position_in_queue`。
*   当 Trade 发生且 Price == MyPrice: `position_in_queue -= trade_qty`。
*   当 Cancel 发生且 Price == MyPrice:
    *   在 L2 中无法确定撤单是谁的。通常假设撤单均匀分布，或者假设撤单主要发生在队尾（对你有利）。

## 4. 延迟套利与对冲 (Latency Arbitrage & Hedging)

### 4.1 跨交易所套利
A 交易所价格 100，B 交易所价格 101。
**执行**:
1.  并发发送：同时发单买 A 卖 B。风险：单边成交 (Legging Risk)。
2.  被动-主动 (Passive-Aggressive): 先在 A 挂买单（Maker）。成交后，立即去 B 吃单（Taker）。

### 4.2 智能路由 (Smart Order Routing - SOR)
如果你要在多个交易所买入 1000 股。
SOR 会根据各交易所的流动性和延迟，决定分配多少数量。
**目标**: 让所有子订单**同时**到达各交易所，防止先到达的订单惊动市场，导致其他交易所价格瞬间逃离。

## 5. 代码实现模式：执行状态机

执行逻辑通常独立于策略逻辑。

```rust
enum ExecutionState {
    Idle,
    Working(u64), // OrderID
    Filled,
    Rejected,
}

struct ExecutionAlgo {
    target_qty: u32,
    filled_qty: u32,
    state: ExecutionState,
}

impl ExecutionAlgo {
    fn on_tick(&mut self, ctx: &mut Context) {
        match self.state {
            ExecutionState::Idle => {
                if self.filled_qty < self.target_qty {
                    // 发出第一笔子订单
                    let child_qty = calc_child_qty();
                    ctx.send_order(...);
                    self.state = ExecutionState::Working(oid);
                }
            }
            ExecutionState::Working(oid) => {
                // 检查是否需要改单 (Reprice)
                if need_reprice() {
                    ctx.cancel_replace(oid, ...);
                }
            }
            _ => {}
        }
    }
}
```

---
下一章：[优化与硬件篇 (Optimization & Hardware)](../optimization/cpu_affinity.md)

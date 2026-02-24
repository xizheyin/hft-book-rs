# 持仓管理 (Position Management)

持仓管理模块负责实时跟踪策略的持仓数量、平均成本以及盈亏（PnL）。它是连接执行层（Execution）和风控层（Risk）的桥梁。

在高频交易中，持仓更新必须极快，以便风控模块能立即使用最新的持仓数据进行检查。

## 1. 核心数据结构

我们需要跟踪每个 Instrument（合约/股票）的持仓状态。

```rust
#[derive(Debug, Clone, Copy, Default)]
pub struct Position {
    pub symbol_id: u16,
    pub quantity: i32,      // 净持仓：正数为多，负数为空
    pub avg_price: f64,     // 持仓均价
    pub realized_pnl: f64,  // 已实现盈亏
    pub total_volume: u64,  // 总成交量
}
```

### 1.1 成本计算方法
通常有两种计算持仓成本的方法：
1.  **加权平均价 (Weighted Average Price)**: 最常用。
2.  **FIFO (First-In, First-Out)**: 需要维护一个队列，内存开销大，HFT 中较少使用。

我们采用**加权平均价**。

## 2. 持仓更新逻辑

当收到成交回报 (Execution Report - Fill) 时，我们需要更新持仓。

```rust
impl Position {
    pub fn on_fill(&mut self, fill_qty: i32, fill_price: f64) {
        let old_qty = self.quantity;
        let new_qty = old_qty + fill_qty;

        if old_qty == 0 {
            // 开仓
            self.avg_price = fill_price;
        } else if (old_qty > 0 && fill_qty > 0) || (old_qty < 0 && fill_qty < 0) {
            // 加仓 (同方向)
            // avg_price = (old_value + new_value) / new_qty
            let old_val = old_qty as f64 * self.avg_price;
            let new_val = fill_qty as f64 * fill_price;
            self.avg_price = (old_val + new_val) / new_qty as f64;
        } else {
            // 减仓/平仓 (反方向)
            // 均价不变，计算已实现盈亏
            // PnL = (Exit Price - Entry Price) * Qty * Multiplier
            // 这里假设 Multiplier = 1
            
            let closed_qty = if new_qty.abs() < old_qty.abs() {
                // 部分平仓
                fill_qty.abs()
            } else {
                // 全部平仓或反手
                old_qty.abs()
            };

            let pnl = if old_qty > 0 {
                (fill_price - self.avg_price) * closed_qty as f64
            } else {
                (self.avg_price - fill_price) * closed_qty as f64
            };
            
            self.realized_pnl += pnl;

            // 如果反手了 (例如持多 10，卖出 20 -> 持空 10)
            if (old_qty > 0 && new_qty < 0) || (old_qty < 0 && new_qty > 0) {
                self.avg_price = fill_price;
            }
        }

        self.quantity = new_qty;
        self.total_volume += fill_qty.abs() as u64;
    }
}
```

> **注意**: 浮点数运算在某些极端情况下可能会累积误差。对于期货/数字货币，建议使用定点数（如 `i64` 表示微元）。

## 3. 并发更新与无锁设计

在 HFT 系统中，可能有多个线程会读取持仓（风控线程、策略线程、监控线程），而网络线程负责写入持仓。

### 3.1 读多写少场景

持仓更新频率取决于成交频率，通常远低于行情更新频率。
我们可以使用 `SeqLock`（在[订单簿管理](order_book.md)中介绍过）来保护 `Position` 结构体。

### 3.2 原子化持仓 (Atomic Position)

如果只需要跟踪 `quantity`（用于风控），可以直接使用 `AtomicI64`。我们将 `quantity` 和 `symbol_id` 打包在一个 `u64` 中（如果 symbol id 够小）。或者仅使用 `AtomicI32` 存储 quantity。

```rust
use std::sync::atomic::{AtomicI64, Ordering};

pub struct AtomicPositionManager {
    // 假设 symbol_id 是 index
    positions: Vec<AtomicI64>, 
}

impl AtomicPositionManager {
    pub fn get(&self, symbol_id: usize) -> i64 {
        self.positions[symbol_id].load(Ordering::Acquire)
    }

    pub fn add(&self, symbol_id: usize, qty: i64) {
        self.positions[symbol_id].fetch_add(qty, Ordering::SeqCst);
    }
}
```

## 4. 浮动盈亏 (Unrealized PnL)

浮动盈亏是基于当前市场价格计算的。

$$ Unrealized PnL = (Mark Price - Avg Price) \times Position $$

*   **Mark Price**: 可以是最新成交价 (LTP)，也可以是买一卖一的中间价 (Mid Price)。
*   **计算时机**: 通常在策略循环中按需计算，或者由监控线程定期计算，不建议在热路径中实时更新。

## 5. 对账与纠错 (Reconciliation)

本地维护的持仓可能与交易所端的实际持仓不一致（由于丢包、系统重启、Bug）。

### 5.1 定期查询
每隔一段时间（如 1秒 或 1分钟），或者在启动时，发送 `PositionRequest` 给交易所。

### 5.2 强制同步
收到交易所的持仓快照后，强制覆盖本地持仓。

```rust
pub fn reconcile(&mut self, exchange_qty: i32) {
    if self.quantity != exchange_qty {
        log::error!("Position mismatch! Local: {}, Exchange: {}. Syncing...", 
                    self.quantity, exchange_qty);
        // 强制同步逻辑：
        // 1. 修改 quantity
        // 2. 可能需要调整 avg_price (虽然交易所通常不发 avg_price)
        self.quantity = exchange_qty;
        
        // 触发风控重算
        self.trigger_risk_check();
    }
}
```

## 6. 多策略管理

如果一个账户跑多个策略，我们通常需要维护两套持仓：
1.  **Strategy Position**: 策略视角的持仓（逻辑持仓）。
2.  **Account Position**: 账户视角的总持仓（物理持仓）。

$$ Account Position = \sum Strategy Position $$

风控通常基于 **Account Position**，而信号生成基于 **Strategy Position**。

---
下一章：[策略框架设计 (Strategy Framework)](strategy.md)

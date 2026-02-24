# 风控系统 (Risk Management System)

在 HFT 中，风控系统（Risk Management System, RMS）不仅仅是“刹车”，它是让你敢于开快车的保障。如果你的策略逻辑出现 Bug（例如无限循环发送买单），或者收到错误的市场数据，毫秒级的延迟就可能导致数百万美元的损失。

一个优秀的高频风控系统必须满足两个看似矛盾的要求：
1.  **极高的可靠性**: 必须拦截所有危险指令。
2.  **极低的延迟**: 不能显著增加 Order to Tick 的延迟。通常预算在 **100ns - 500ns** 之间。

## 1. 风控的分层架构 (Layered Architecture)

风控通常分为三层：

### 1.1 预交易风控 (Pre-trade Risk)
*   **位置**: 在策略生成订单之后，发送到网关之前。
*   **特点**: **同步 (Synchronous)**，**阻塞 (Blocking)**。
*   **延迟敏感度**: 极高。必须在热路径 (Hot Path) 上执行。
*   **检查项**:
    *   单笔订单最大数量 (Max Order Quantity)。
    *   单笔订单最大金额 (Max Order Value)。
    *   价格偏离度 (Price Deviation): 买价是否高于市场价太多？
    *   胖手指检查 (Fat Finger): 价格是否为 0？数量是否为负？

### 1.2 盘中风控 (Intraday / Post-trade Risk)
*   **位置**: 独立风控线程或网关收到成交回报 (Fill) 后。
*   **特点**: **异步 (Asynchronous)**。
*   **检查项**:
    *   最大持仓限制 (Max Position)。
    *   累计亏损限制 (Max Drawdown)。
    *   单位时间最大发送次数 (Message Rate Limit)。

### 1.3 交易所风控 (Exchange Risk)
*   **位置**: 交易所端。
*   **特点**: 最后的防线。
*   **检查项**: 保证金检查、Drop Copy 监控。

## 2. 零开销设计 (Zero-Overhead Design)

为了在几百纳秒内完成检查，我们不能查数据库，不能有锁竞争，不能分配内存。

### 2.1 静态配置与编译期优化
对于某些硬限制（如最大单笔数量），可以使用 `const generics` 或在启动时加载到 Cache Line 友好的结构中。

```rust
pub struct RiskConfig {
    pub max_order_qty: u32,
    pub max_order_value: u64,
    pub min_price: i64,
    pub max_price: i64,
}

// 热路径上的检查函数
#[inline(always)]
pub fn check_new_order(order: &NewOrder, config: &RiskConfig) -> Result<(), RiskError> {
    if order.quantity > config.max_order_qty {
        return Err(RiskError::OrderTooLarge);
    }
    if order.price < config.min_price || order.price > config.max_price {
        return Err(RiskError::PriceOutOfRange);
    }
    Ok(())
}
```

### 2.2 全局状态管理 (Global State)
如果多个策略线程共享同一个风控额度（例如总持仓限制），就需要跨线程通信。
*   **原子操作**: 使用 `AtomicI64` 维护当前持仓。
*   **本地缓存 (Thread-local Cache)**: 每个线程分配一部分额度，用完再去全局池申请。

## 3. 熔断机制 (Kill Switch)

当系统检测到异常（如 PnL 剧烈波动、错误率飙升、心跳丢失）时，必须立即触发熔断。

### 3.1 软件熔断
一个全局的 `AtomicBool` 标志位。所有发单逻辑在执行前必须检查此标志。

```rust
static SYSTEM_ACTIVE: AtomicBool = AtomicBool::new(true);

pub fn send_order(...) {
    if !SYSTEM_ACTIVE.load(Ordering::Relaxed) {
        return; // 被熔断
    }
    // ...
}

pub fn trigger_kill_switch() {
    SYSTEM_ACTIVE.store(false, Ordering::SeqCst);
    // 立即发送 Cancel All 请求
    cancel_all_open_orders();
}
```

### 3.2 硬件熔断
有些 HFT 公司会使用 FPGA 网卡作为最后的网关。如果软件层失控（例如死循环发包），FPGA 层的看门狗 (Watchdog) 会直接切断物理连接或丢弃数据包。

## 4. 常见陷阱

1.  **整数溢出**: 计算 `Price * Quantity` 时，如果使用 `u32` 可能会溢出。务必使用 `u64` 或 `u128`。
2.  **并发更新导致的超限**:
    *   线程 A 检查持仓：`Current (100) + New (10) < Max (105)`? -> False (允许)。
    *   线程 B 检查持仓：`Current (100) + New (10) < Max (105)`? -> False (允许)。
    *   结果：持仓变成 120，超过 105。
    *   **解决**: 使用 `fetch_add` 预扣除，如果超限则回滚（`fetch_sub`）。

---
下一章：[预交易风控实现 (Pre-trade Check)](pre_trade_risk.md)

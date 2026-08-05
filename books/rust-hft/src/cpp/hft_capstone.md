# C++ HFT 贯穿项目：从行情到发单意图

前面的章节分别介绍语言和性能概念。本章把它们装进同一条简化交易链路，让你看见：一个 C++ 类型为什么存在，它保护的业务规则是什么，以及出错时系统为什么应当停下来。

> **本章目标**：读完后，你应能画出“行情更新 → 本地订单簿 → 信号 → 盘前风控 → 网关”的数据流，独立编译示例，并说出它距离生产系统还缺什么。

## 1. 先看全局，不急着看语法

我们要实现的是下面这条教学链路：

```mermaid
flowchart LR
    A[行情更新] --> B[校验价格和数量]
    B --> C[更新本地最优买卖价]
    C --> D[生成下单意图]
    D --> E[盘前风控]
    E --> F[生成订单编号]
    F --> G[交给真实网关的位置]
```

几个词先用白话解释：

- **行情更新**：交易所告诉我们某个价格现在有多少可见数量；
- **本地订单簿**：程序在自己内存里维护的市场状态副本；
- **信号**：策略认为“现在可能值得做什么”，但它还不是订单；
- **盘前风控**：下单前最后一次检查数量和持仓边界；
- **网关**：把内部订单转换成交易所协议并管理订单状态的组件。

最重要的边界是：**策略只能提出意图，不能绕过风控直接发单。**

## 2. 先定义五条不变量

“不变量”就是在当前模型和适用条件内，程序运行过程中始终必须为真的规则。本例假设一个单一撮合场所正处于正常的连续交易阶段，不处理集合竞价、锁定/交叉市场或多场所聚合视图。在这个教学边界内使用：

1. 价格使用整数 tick，且必须大于 0；
2. 行情数量不能为负，数量为 0 表示删除该价位；
3. 有买卖两侧时，最高买价必须低于最低卖价；若真实场所允许或会报告其他状态，应按其当前协议建模；
4. 单笔订单数量不能超过上限；
5. 假设新订单全部成交后，持仓仍不能越过限制。

先写规则再写代码，可以避免“程序跑得很快，却快速地产生错误订单”。

## 3. 一个可以独立编译的最小程序

下面只使用 C++20 标准库。它维护最优买卖价，生成一个非常简单的教学信号，经过风控后打印订单。`Gateway::send` 只是网关的替身，并没有真的连接交易所。

代码中的 `using PriceTicks = std::int64_t` 只是给现有整数类型起一个更好读的别名，并不会阻止编译器把价格、数量等相同底层类型混用。真实系统可以进一步使用强类型封装，并为单位换算补上 checked 运算。

```cpp
#include <algorithm>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <vector>

using PriceTicks = std::int64_t;
using Quantity = std::int32_t;
using OrderId = std::uint64_t;

enum class Side { Buy, Sell };

constexpr std::string_view side_name(Side side) {
    return side == Side::Buy ? "BUY" : "SELL";
}

struct BookUpdate {
    Side side;
    PriceTicks price_ticks;
    Quantity quantity;
};

struct Level {
    PriceTicks price_ticks;
    Quantity quantity;
};

class TopOfBook {
public:
    bool apply(const BookUpdate& update) {
        if (update.price_ticks <= 0 || update.quantity < 0) {
            return false;
        }

        auto update_one_side = [&](auto& levels) {
            const auto old_it = levels.find(update.price_ticks);
            std::optional<Quantity> old_quantity;
            if (old_it != levels.end()) {
                old_quantity = old_it->second;
            }

            if (update.quantity == 0) {
                levels.erase(update.price_ticks);
            } else {
                levels.insert_or_assign(update.price_ticks, update.quantity);
            }

            if (is_crossed()) {
                // 本例选择拒绝会制造“买价 >= 卖价”的更新，并恢复旧状态。
                if (old_quantity.has_value()) {
                    levels.insert_or_assign(update.price_ticks, *old_quantity);
                } else {
                    levels.erase(update.price_ticks);
                }
                return false;
            }
            return true;
        };

        if (update.side == Side::Buy) {
            return update_one_side(bids_);
        }
        return update_one_side(asks_);
    }

    std::optional<Level> best_bid() const {
        if (bids_.empty()) {
            return std::nullopt;
        }
        const auto& [price, quantity] = *bids_.begin();
        return Level{price, quantity};
    }

    std::optional<Level> best_ask() const {
        if (asks_.empty()) {
            return std::nullopt;
        }
        const auto& [price, quantity] = *asks_.begin();
        return Level{price, quantity};
    }

private:
    bool is_crossed() const {
        return !bids_.empty() && !asks_.empty()
            && bids_.begin()->first >= asks_.begin()->first;
    }

    // 买价从高到低排列，所以 begin() 是最高买价。
    std::map<PriceTicks, Quantity, std::greater<PriceTicks>> bids_;
    // 卖价从低到高排列，所以 begin() 是最低卖价。
    std::map<PriceTicks, Quantity, std::less<PriceTicks>> asks_;
};

struct OrderIntent {
    Side side;
    PriceTicks limit_price_ticks;
    Quantity quantity;
};

std::optional<OrderIntent> make_signal(const TopOfBook& book) {
    const auto bid = book.best_bid();
    const auto ask = book.best_ask();
    if (!bid.has_value() || !ask.has_value()) {
        return std::nullopt;
    }

    const PriceTicks spread = ask->price_ticks - bid->price_ticks;
    const auto bid_quantity = static_cast<std::int64_t>(bid->quantity);
    const auto ask_quantity = static_cast<std::int64_t>(ask->quantity);

    // 纯教学规则：价差不超过 2 tick，且买一数量大于卖一的两倍时买入。
    if (spread <= 2 && bid_quantity > 2 * ask_quantity) {
        return OrderIntent{
            Side::Buy,
            ask->price_ticks,
            std::min<Quantity>(10, ask->quantity)
        };
    }
    return std::nullopt;
}

class PreTradeRisk {
public:
    PreTradeRisk(std::int64_t max_position, Quantity max_order_quantity)
        : max_position_(max_position),
          max_order_quantity_(max_order_quantity) {
        // 配置在进入热路径前验证，避免负限额和算术边界破坏风控。
        if (max_position < 0 || max_order_quantity <= 0) {
            throw std::invalid_argument(
                "max position must be non-negative and order limit positive");
        }
    }

    bool approve(const OrderIntent& intent) const {
        if (intent.limit_price_ticks <= 0 || intent.quantity <= 0
            || intent.quantity > max_order_quantity_) {
            return false;
        }

        const auto quantity = static_cast<std::int64_t>(intent.quantity);
        if (intent.side == Side::Buy) {
            return position_ <= max_position_ - quantity;
        }
        return position_ >= -max_position_ + quantity;
    }

private:
    std::int64_t position_{0};
    std::int64_t max_position_;
    Quantity max_order_quantity_;
};

struct OutboundOrder {
    OrderId id;
    Side side;
    PriceTicks limit_price_ticks;
    Quantity quantity;
};

class Gateway {
public:
    std::optional<OutboundOrder> send(const OrderIntent& intent) {
        if (next_id_ == std::numeric_limits<OrderId>::max()) {
            return std::nullopt;
        }
        const OutboundOrder order{
            next_id_, intent.side, intent.limit_price_ticks, intent.quantity
        };
        ++next_id_;
        std::cout << "send id=" << order.id
                  << " side=" << side_name(order.side)
                  << " price_ticks=" << order.limit_price_ticks
                  << " quantity=" << order.quantity << '\n';
        return order;
    }

private:
    OrderId next_id_{1};
};

int main() {
    TopOfBook book;
    const std::vector<BookUpdate> updates{
        {Side::Buy, 10'000, 120},
        {Side::Sell, 10'002, 40}
    };

    for (const auto& update : updates) {
        if (!book.apply(update)) {
            std::cerr << "reject invalid book update\n";
            return 1;
        }
    }

    const auto bid = book.best_bid();
    const auto ask = book.best_ask();
    if (bid.has_value() && ask.has_value()) {
        std::cout << "BBO " << bid->price_ticks << " x " << bid->quantity
                  << " / " << ask->price_ticks << " x " << ask->quantity
                  << '\n';
    }

    const auto intent = make_signal(book);
    if (!intent.has_value()) {
        std::cout << "no order intent\n";
        return 0;
    }

    const PreTradeRisk risk(/*max_position=*/100, /*max_order_quantity=*/20);
    if (!risk.approve(*intent)) {
        std::cout << "risk rejected order intent\n";
        return 0;
    }

    Gateway gateway;
    const auto order = gateway.send(*intent);
    if (!order.has_value()) {
        std::cerr << "order id space exhausted\n";
        return 1;
    }
    return 0;
}
```

在 Linux 或 macOS 上，可以保存为 `mini_hft.cpp` 后编译：

```bash
c++ -std=c++20 -O2 -Wall -Wextra -Wpedantic mini_hft.cpp -o mini_hft
./mini_hft
```

预期输出中的订单编号和字段类似：

```text
BBO 10000 x 120 / 10002 x 40
send id=1 side=BUY price_ticks=10002 quantity=10
```

## 4. 按数据流读代码

第一次读完整程序时，不要从每个分号开始抠。按下面五步找对象：

### 第一步：行情进入 `TopOfBook`

`BookUpdate` 只是数据，`TopOfBook::apply` 才负责维护规则。它拒绝非法价格、负数量和交叉盘口；拒绝时还会恢复更新前的状态。

这里使用 `std::map` 是为了让示例容易读，并不表示它一定适合生产热路径。真实系统可能使用数组、稠密价格索引或专门的数据结构；选择必须由产品价格范围和基准结果决定。

### 第二步：策略只返回 `OrderIntent`

`make_signal` 没有网络句柄，也不能调用交易所。这样设计能让策略计算与发单权限分开，方便回放、测试和审计。

例子中的数量不平衡规则只用于展示数据流，**不是投资建议，也没有经过收益验证**。

### 第三步：风险检查最坏结果

买 10 手时，风控问的不是“现在持仓有没有超限”，而是“如果这 10 手全部成交，会不会超限”。构造函数先验证配置，说明错误限额不能进入热路径。生产系统还要把未成交订单、合约乘数、名义金额、频率限制和组合风险算进去。

### 第四步：网关分配订单编号

`Gateway` 拥有 `next_id_`，所以编号责任有明确归属；耗尽前返回失败，避免无符号回绕后产生重复编号。真实网关还要持久化会话和编号状态，并处理编码、发送、ACK、成交、撤单竞态、重连和幂等恢复。

### 第五步：`main` 只负责串联

`main` 像流程导演：它没有把订单簿、策略和风控揉成一个巨型类。组件边界清楚后，单元测试和替换实现都会更容易。

## 5. Rust 与 C++ 的心智模型对照

| 目标 | C++ 示例 | Rust 中常见表达 | 需要自己特别小心的地方 |
|---|---|---|---|
| 表达买卖方向 | `enum class Side` | `enum Side` | 避免用 0/1 魔法数字 |
| 可能没有结果 | `std::optional<T>` | `Option<T>` | 使用前检查是否有值 |
| 独占组件状态 | 普通对象成员 | 所有权与 `&mut self` | C++ 编译器不会普遍阻止悬空引用 |
| 自动释放资源 | RAII 析构 | `Drop` | C++ 中仍要选择正确所有权类型 |
| 有序价位 | `std::map` | `BTreeMap` | 数据结构成本要实际测量 |

两种语言都能表达相同业务链路。主要差异不是“哪种语法短”，而是谁在编译期帮你检查所有权和并发约束，以及团队要承担多少人工审查责任。

## 6. 这还不是生产 HFT 系统

这个例子故意省略了大量内容：

- 没有行情序号、丢包检测、快照拼接和恢复状态机；
- 只有聚合价位，没有 L3 单笔订单与精确撮合优先级；
- 没有未成交订单预占、成交回报和真实持仓更新；
- 没有字节序、协议长度、校验和与会话序号；
- 没有多线程所有权协议，也没有延迟分布和容量证据；
- 没有真实交易所规则、合规审计和 kill switch。

因此，正确的表述是“这是可编译的数据流骨架”，而不是“这是可以实盘使用的交易系统”。

## 7. 推荐的渐进练习

不要一次把示例改成几千行。按这个顺序扩展：

1. 为非法价格、负数量和交叉盘口各加一个测试；
2. 加入 `sequence`，发现跳号后停止生成新意图；
3. 让风险记录未成交买卖数量，撤单确认前不释放占用；
4. 给订单增加 `PendingNew`、`Working`、`PendingCancel` 等状态；
5. 使用固定输入回放，比较每次运行的最终状态哈希；
6. 最后才建立基准，比较替换数据结构前后的 P50/P99。

## 8. 面试追问与参考答法

### Q1：为什么策略不能直接持有网关？

**参考骨架**：把策略与发单权限分开，可以强制所有订单经过统一风控，也方便离线回放。代价是多一个组件边界；热路径成本需要测量，但不能为了省一次调用破坏风险边界。

### Q2：为什么价格用整数？

**参考骨架**：整数 tick 能明确单位，避免很多二进制浮点比较问题，哈希和相等判断也更可控。仍需检查缩放、乘数和溢出；整数并不会自动保证金额正确。

### Q3：为什么这里的 `std::map` 不一定合适？

**参考骨架**：它通常包含节点分配和指针跳转，缓存局部性可能不如连续存储。但是否是瓶颈取决于价格范围、更新模式和数据规模，应先用代表性回放与剖析证明，再替换实现。

### Q4：行情断档后应该怎样处理？

**参考骨架**：标记对应订单簿不可信，停止依赖它产生的新订单；保留受控撤单或 kill 能力；通过重传或快照恢复，验证序号和不变量后再回到 Live。

## 9. 易错点

- 把“产生信号”说成“订单已经发送”；
- 风控只看当前持仓，不算未成交订单和最坏成交结果；
- 盘口更新失败后仍保留一半修改；
- 用浮点数直接比较协议价格，却没有定义缩放单位；
- 看到 `-O3` 就声称系统已经低延迟；
- 把教学策略当成经过验证的交易策略。

## 10. 练习与参考答案

### 练习 1

当前持仓是 95，上限是 100，策略想买 10。应该通过吗？

<details>
<summary>参考答案</summary>

不应通过。按全部成交计算，最坏多头持仓会变成 105。若其他限制允许，可以把数量缩小到最多 5，但“自动缩量”本身也应是明确的产品规则，不能静默发生。

</details>

### 练习 2

为什么收到撤单请求不等于可以立即释放风险占用？

<details>
<summary>参考答案</summary>

因为撤单和成交存在竞态。在权威的撤单确认到达前，原订单仍可能成交，所以应保留剩余数量对应的风险占用。

</details>

### 练习 3

如果要测量把 `std::map` 换成数组是否有收益，至少应固定哪些条件？

<details>
<summary>参考答案</summary>

至少固定硬件、编译器与 flags、行情样本、价格分布、订单簿深度、更新类型比例、预热方式和计时边界；同时验证两种实现的输出状态一致，并比较延迟分布而不只看平均值。

</details>

## 小结

- 先画数据流和定义不变量，再选择 C++ 类型；
- 信号、风控和网关是三个不同责任；
- RAII、`enum class`、`std::optional` 能帮助表达边界，但不能替代业务验证；
- 可编译只是第一步，生产系统还需要恢复、状态机、测试、测量和审计证据。

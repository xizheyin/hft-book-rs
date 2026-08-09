# C++ 基础诊断与动手练习

本章不再重复讲一遍 C++ 语法。变量、函数、分支、循环、`enum class`、`struct` 和 `class` 的概念与例子，统一由上一章 [C++ 最小语法与数据建模](minimal_syntax.md) 主讲。本章只做三件事：从空白文件写程序、用编译器定位错误、通过练习判断下一步该补哪一章。

每道题都按同一顺序完成：先预测，再独立编码，最后才展开答案。仅仅“看懂答案”不能说明你已经会写。

## 1. 空白文件诊断题

不要复制现有代码。请新建 `diagnostic.cpp`，完成下面的要求：

1. 定义三个 32 位数量：`100`、`0`、`200`；
2. 用范围 `for` 逐个检查，跳过不大于零的数量；
3. 用 64 位整数累计有效数量；
4. 用 `assert` 验证有效数量之和是 `300`，有效元素数是 `2`；
5. 编译并运行，然后解释为什么累计值比单个输入更适合使用更宽的整数类型。

编译命令如下。`-Wall -Wextra -Wpedantic` 会打开一组常用警告；它们不能证明程序正确，但能更早暴露许多可疑写法。

```bash
c++ -std=c++20 -Wall -Wextra -Wpedantic diagnostic.cpp -o diagnostic
./diagnostic
```

按下面四项各记一分：能从空白文件开始、能独立通过编译、主动处理无效值、能解释每种类型的用途。分数只用于定位知识缺口，不用于评价能力。

<details>
<summary>参考答案与逐步解答</summary>

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>

int main() {
    const std::int32_t quantities[]{100, 0, 200};
    std::int64_t valid_total{0};
    std::size_t valid_count{0};

    for (const std::int32_t quantity : quantities) {
        if (quantity <= 0) {
            continue;
        }
        valid_total += std::int64_t{quantity};
        ++valid_count;
    }

    assert(valid_total == 300);
    assert(valid_count == 2);
}
```

执行过程是：先看到 `100`，累计值变成 `100`、计数变成 `1`；再看到 `0`，`continue` 结束本轮，不修改结果；最后看到 `200`，累计值变成 `300`、计数变成 `2`。

单个数量是 32 位，并不表示很多个数量的总和仍能放进 32 位。这里先把每个有效数量转换为 64 位，再进行加法，使这次加法在 64 位中完成。真实程序仍要根据“最多累计多少项、每项最大多少”证明 64 位是否足够；如果仍可能越界，就必须在运算前检查。

`assert` 用来检查程序员认为测试中必须成立的内部条件。它可能在定义 `NDEBUG` 的构建中被移除，因此不能代替对文件、网络或用户输入的正式校验。

</details>

### 根据卡点回到唯一主讲章节

| 卡点 | 说明还没掌握什么 | 应回到哪里 |
|---|---|---|
| 写不出 `#include`、`main` 或编译命令 | 程序外形与构建阶段 | [最小语法](minimal_syntax.md)第 1 节；[编译与链接](compilation_memory.md) |
| 分不清初始化、赋值、`const`、`auto` | 名字、值与静态类型 | [最小语法](minimal_syntax.md)第 2～4 节 |
| 说不清 `if`、`continue`、范围 `for` 的执行顺序 | 控制流 | [最小语法](minimal_syntax.md)第 6～7 节 |
| 不理解参数中的 `&`、`const T&` | 别名与生命周期 | [指针、引用与 const](pointers_references.md) |
| 不知道 `vector` 的 `size`、`capacity` 或引用失效 | 动态数组与容器成本 | [STL 容器与成本模型](stl_cost_model.md) |
| 不知道何时用 `optional`、枚举结果或异常 | 失败怎样进入类型和控制流 | [错误、异常与未定义行为](errors_ub.md) |
| 能写对但无法定位崩溃或慢在哪里 | 调试证据链 | [Linux 故障诊断](../optimization/linux_debugging.md) |

## 2. 综合动手题：从行情输入到风控结果

这道题用一个简化订单流程串起类型、函数、分支和边界检查。它只是编程练习，不是交易策略。

先根据接口独立实现：

```cpp,ignore
enum class Side { Buy, Sell, Unknown };

struct MarketUpdate {
    std::string symbol;
    std::int64_t bid_ticks;
    std::int64_t ask_ticks;
    std::int32_t bid_quantity;
    std::int32_t ask_quantity;
};

struct OrderCandidate {
    std::string symbol;
    Side side;
    std::int32_t quantity;
};

// 1. 实现 is_valid_market(update)。
// 2. 实现 choose_side(update)，返回 std::optional<Side>。
// 3. 实现 is_allowed(order, current_position, max_abs_position)。
// 4. 在 main 中区分无效行情、没有信号、风控拒绝和允许发送。
```

`std::optional<Side>` 表示“可能有一个 `Side`，也可能没有”。本题把“行情有效，但数量差不足以作出方向判断”表示为空值；详细的错误表达方式由[错误处理章节](errors_ub.md)主讲。

约束如下：

- 买价和卖价都必须为正，并且买价严格小于卖价；
- 买卖数量都必须为正；
- 买量比卖量至少多 `100` 时选择买入，反之选择卖出，否则没有方向；
- 候选订单数量固定为 `200`；
- 预计持仓的绝对值不能超过 `1'000`；
- 数量相减和持仓相加不能依赖可能溢出的 32 位有符号运算。

<details>
<summary>完整参考实现与解答</summary>

```cpp
#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>
#include <string>

enum class Side {
    Buy,
    Sell,
    Unknown,
};

struct MarketUpdate {
    std::string symbol;
    std::int64_t bid_ticks;
    std::int64_t ask_ticks;
    std::int32_t bid_quantity;
    std::int32_t ask_quantity;
};

struct OrderCandidate {
    std::string symbol;
    Side side;
    std::int32_t quantity;
};

[[nodiscard]] bool is_valid_market(const MarketUpdate& update) {
    return !update.symbol.empty()
        && update.bid_ticks > 0
        && update.ask_ticks > update.bid_ticks
        && update.bid_quantity > 0
        && update.ask_quantity > 0;
}

[[nodiscard]] std::optional<Side> choose_side(
    const MarketUpdate& update) {
    if (!is_valid_market(update)) {
        return std::nullopt;
    }

    const std::int64_t bid_quantity{update.bid_quantity};
    const std::int64_t ask_quantity{update.ask_quantity};
    constexpr std::int64_t threshold{100};

    if (bid_quantity - ask_quantity >= threshold) {
        return Side::Buy;
    }
    if (ask_quantity - bid_quantity >= threshold) {
        return Side::Sell;
    }
    return std::nullopt;
}

[[nodiscard]] bool is_allowed(const OrderCandidate& order,
                              std::int32_t current_position,
                              std::int32_t max_abs_position) {
    if (order.quantity <= 0 || max_abs_position <= 0) {
        return false;
    }

    std::int64_t signed_quantity{0};
    switch (order.side) {
        case Side::Buy:
            signed_quantity = std::int64_t{order.quantity};
            break;
        case Side::Sell:
            signed_quantity = -std::int64_t{order.quantity};
            break;
        case Side::Unknown:
            return false;
    }

    const std::int64_t projected =
        std::int64_t{current_position} + signed_quantity;
    return projected >= -std::int64_t{max_abs_position}
        && projected <= std::int64_t{max_abs_position};
}

[[nodiscard]] const char* side_name(Side side) {
    switch (side) {
        case Side::Buy:
            return "BUY";
        case Side::Sell:
            return "SELL";
        case Side::Unknown:
            return "UNKNOWN";
    }
    return "UNKNOWN";
}

int main() {
    const MarketUpdate invalid{"ABC-FUT", 10'025, 10'025, 900, 600};
    assert(!is_valid_market(invalid));

    const MarketUpdate no_signal{"ABC-FUT", 10'024, 10'025, 650, 600};
    assert(!choose_side(no_signal).has_value());

    const OrderCandidate allowed{"ABC-FUT", Side::Buy, 200};
    assert(is_allowed(allowed, 800, 1'000));
    assert(!is_allowed(allowed, 801, 1'000));
    assert(!is_allowed({"ABC-FUT", Side::Buy, 0}, 0, 1'000));
    assert(!is_allowed({"ABC-FUT", Side::Unknown, 200}, 0, 1'000));

    const MarketUpdate update{"ABC-FUT", 10'024, 10'025, 900, 600};
    const std::int32_t current_position{700};
    constexpr std::int32_t order_quantity{200};
    constexpr std::int32_t max_abs_position{1'000};

    if (!is_valid_market(update)) {
        std::cout << "reject: invalid market update\n";
        return 0;
    }

    const auto side = choose_side(update);
    if (!side) {
        std::cout << "skip: no signal\n";
        return 0;
    }

    const OrderCandidate order{update.symbol, *side, order_quantity};
    if (!is_allowed(order, current_position, max_abs_position)) {
        std::cout << "reject: position limit\n";
        return 0;
    }

    std::cout << "send " << side_name(order.side) << ' '
              << order.quantity << ' ' << order.symbol << '\n';
}
```

处理顺序不能随意颠倒：先拒绝无效输入，再判断是否有方向，最后计算候选订单的预计持仓。两个 32 位数量先转换为 64 位再相减；当前持仓也先转换为 64 位再相加。这样避免“先在 32 位中溢出，之后再扩大已经来不及”的错误。

</details>

### 四次修改实验与逐项答案

每次只改一处，先写下预测，再运行验证。

1. 把 `update` 的买量从 `900` 改为 `650`。
   **答案：**买量 `650` 与卖量 `600` 只差 `50`，小于阈值 `100`，`choose_side` 返回空值，输出 `skip: no signal`。
2. 保持原行情，把 `current_position` 从 `700` 改为 `900`。
   **答案：**买入 `200` 后预计持仓为 `1'100`，超过上限 `1'000`，输出 `reject: position limit`。
3. 让 `bid_ticks` 与 `ask_ticks` 都为 `10'025`。
   **答案：**买价不再严格小于卖价，`is_valid_market` 返回 `false`，输出 `reject: invalid market update`。
4. 把买卖数量交换为买量 `600`、卖量 `900`。
   **答案：**卖量多 `300`，选择 `Sell`；当前持仓从 `700` 降到 `500`，仍在范围内，输出 `send SELL 200 ABC-FUT`。

## 3. 故障现象速查：先定位，再回主讲章

这张表不是概念讲义，而是代码失败时的分流表。

| 现象 | 最可能的原因 | 怎样确认 | 主讲章节 |
|---|---|---|---|
| 局部整数每次运行结果不同 | 读取了未初始化值 | 开启警告和 MemorySanitizer；检查每条读取路径 | [错误与 UB](errors_ub.md) |
| `if` 里意外修改了变量 | 把 `=` 写成了 `==` | 读编译器第一条警告，打印分支前后的值 | [最小语法](minimal_syntax.md) |
| `3 / 2` 得到 `1` | 两个操作数都是整数 | 写出每个操作数的静态类型 | [数据表示](../foundations/data_representation.md) |
| 把结果存入 `int64_t` 仍出现错误 | 运算先在较窄类型中溢出 | 检查运算符两侧类型，而不只看结果变量 | [错误与 UB](errors_ub.md) |
| 与 `size()` 比较时负数变得很大 | 有符号与无符号转换 | 打印或在调试器中查看两边类型和值 | [最小语法](minimal_syntax.md) |
| 范围 `for` 修改没有作用，或复制很多对象 | 循环变量按值复制 | 检查循环变量是 `auto`、`auto&` 还是 `const auto&` | [拷贝与移动](copy_move.md) |
| `vector` 插入后旧引用崩溃 | 扩容或插入使引用失效 | 记录操作前后的 `data()`、`size()`、`capacity()` | [STL 成本模型](stl_cost_model.md) |
| 对空容器取首尾元素崩溃 | `front()` / `back()` 要求元素存在 | 调用前检查 `empty()` | [STL 成本模型](stl_cost_model.md) |
| 取 `optional` 的值时报错 | 没有先判断是否含值 | 先检查 `has_value()` 或布尔状态 | [错误与 UB](errors_ub.md) |
| 发布构建漏掉业务检查 | 把 `assert` 当作输入校验 | 用 `-DNDEBUG` 构建并测试非法输入 | [错误与 UB](errors_ub.md) |
| 函数返回后引用失效 | 返回了局部对象的指针或引用 | 画出对象离开作用域的时刻 | [指针、引用与生命周期](pointers_references.md) |
| 成员无法从外部访问 | `class` 成员默认是 `private` | 检查 `public:` / `private:` 的位置 | [最小语法](minimal_syntax.md) |

## 4. 口头诊断题与答案

先在 30 秒内用自己的话回答，再看本页答案。答不出时回到表中指定的唯一主讲章节，不要在不同章节重复背同一概念。

### 4.1 初始化和赋值有什么区别？

初始化在对象创建时给出初始状态；赋值修改已经存在的对象。复杂类型的初始化和赋值可能调用不同的函数，也可能具有不同成本。

### 4.2 `const` 有什么价值？

它把“不应通过当前名字或接口修改”的意图交给编译器检查，也减少读代码时需要考虑的状态变化。它不等于线程安全，也不保证对象绝无其他修改路径。

### 4.3 `auto` 会让 C++ 变成动态类型语言吗？

不会。编译器在编译期推导出一个确定类型，后续操作仍接受静态类型检查。协议字段和重要数值边界不能只靠 `auto` 猜宽度。

### 4.4 何时按值传递，何时使用 `const T&`？

小型标量和枚举通常按值最清楚；只读访问较大对象时常用 `const T&` 避免一次复制。最终还要结合所有权、对象大小、调用频率和测量结果，不能把它背成绝对规则。

### 4.5 引用和指针最直观的区别是什么？

引用通常表达“对象必须存在，并在绑定后不改绑”；指针可以用 `nullptr` 表示没有对象，也可以改为指向别处。两者都不会自动延长所指对象的生命周期。

### 4.6 `array` 和 `vector` 怎样选择？

元素数量在编译期固定时可以考虑 `array`；数量在运行时变化时常以 `vector` 为默认候选。还要检查容量、分配时机、访问模式和引用失效规则。

### 4.7 `reserve(100)` 之后能写 `values[0]` 吗？

不能。`reserve` 只保证容量至少达到目标，不创建元素，`size()` 仍可能是零。添加一个元素可用 `push_back`；创建指定数量的元素可用 `resize`。

### 4.8 为什么推荐 `enum class` 表示有限状态？

它让状态拥有独立类型和作用域，也不会像传统枚举那样轻易隐式转换成整数，因此能减少把方向、错误码和普通数字混用的错误。

### 4.9 `optional<T>` 解决什么问题？

它在类型中表达“可能有一个 `T`，也可能没有”，避免用 `-1`、`0` 等魔法值冒充缺失。它只表达有或无，不携带详细失败原因。

### 4.10 为什么 `assert` 不能承担业务校验？

发布构建可能关闭断言。外部输入非法是程序必须正常处理的情况，应走明确的拒绝、报错或降级分支，而不是只依赖开发期断言。

### 4.11 `vector` 扩容后，原元素引用还有效吗？

无效。扩容会把元素搬到新的存储区域，原来的指针、引用和迭代器都会失效。即使没有扩容，插入和擦除也可能让操作位置及其后的引用失效。

### 4.12 为什么整数运算要在运算前扩大或检查？

表达式先按操作数类型计算，生成结果后再存入大类型可能已经太晚。有符号整数溢出是未定义行为；即使提前扩大，也必须先证明更大的类型能容纳所有可能结果，否则仍要做边界检查。

## 5. 笔试代码题的固定检查顺序

遇到短代码输出题或找错题，画一张执行跟踪表，不要只在脑中跳步：

| 语句 | 读取的值与类型 | 修改的对象 | 分支或循环结果 | 容器状态 |
|---|---|---|---|---|

1. 写出每个名字的静态类型、初值和作用域；先处理整数除法、窄化和有符号/无符号转换。
2. 按运算符规则求表达式，副作用单独记入“修改的对象”；不要臆测求值次序。
3. 把每次条件判断的布尔结果写下来；循环同时记录下标、第一次迭代和退出边界。
4. 函数调用要区分按值复制、引用别名和指针可空；调用结束后划掉已经离开作用域的局部对象。
5. 容器操作同步更新 `size` 和 `capacity`；可能重分配时，立即划掉旧迭代器、指针和引用。
6. 最后检查每次读取是否来自仍存活且已初始化的对象，每条错误路径是否真正返回或拒绝。

## 6. 分项练习与逐题答案

### 练习 A：统计无效数量

实现 `invalid_count`：数量不在闭区间 `[1, 150]` 时记为无效。至少覆盖混合输入、全部有效和全部无效三组测试。

<details>
<summary>参考答案与解答</summary>

```cpp
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

[[nodiscard]] std::size_t invalid_count(
    const std::array<std::int32_t, 4>& quantities) {
    std::size_t count{0};
    for (const std::int32_t quantity : quantities) {
        if (quantity < 1 || quantity > 150) {
            ++count;
        }
    }
    return count;
}

int main() {
    const std::array<std::int32_t, 4> mixed{100, 200, -1, 50};
    const std::array<std::int32_t, 4> all_valid{1, 150, 2, 149};
    const std::array<std::int32_t, 4> all_invalid{0, 151, -1, 200};

    assert(invalid_count(mixed) == 2);
    assert(invalid_count(all_valid) == 0);
    assert(invalid_count(all_invalid) == 4);
}
```

闭区间 `[1, 150]` 的反面是“小于 `1` 或大于 `150`”，所以条件使用 `||`。边界值 `1` 和 `150` 必须保留在有效测试中，防止把 `<` / `>` 错写成 `<=` / `>=`。

</details>

### 练习 B：安全地修改数量

实现 `try_add_quantity`。它接收可变引用和 32 位增量；如果结果超出 `std::int32_t` 的范围，保持原对象不变并返回 `false`。

<details>
<summary>参考答案与解答</summary>

```cpp
#include <cassert>
#include <cstdint>
#include <limits>
#include <string>

struct Quote {
    std::string symbol;
    std::int32_t quantity;
};

[[nodiscard]] bool try_add_quantity(Quote& quote, std::int32_t delta) {
    const std::int64_t candidate =
        std::int64_t{quote.quantity} + std::int64_t{delta};

    if (candidate < std::numeric_limits<std::int32_t>::min()
        || candidate > std::numeric_limits<std::int32_t>::max()) {
        return false;
    }

    quote.quantity = static_cast<std::int32_t>(candidate);
    return true;
}

int main() {
    Quote normal{"ABC-FUT", 300};
    assert(try_add_quantity(normal, 50));
    assert(normal.quantity == 350);

    Quote upper{"ABC-FUT", std::numeric_limits<std::int32_t>::max()};
    assert(!try_add_quantity(upper, 1));
    assert(upper.quantity == std::numeric_limits<std::int32_t>::max());

    Quote lower{"ABC-FUT", std::numeric_limits<std::int32_t>::min()};
    assert(!try_add_quantity(lower, -1));
    assert(lower.quantity == std::numeric_limits<std::int32_t>::min());
}
```

两个 32 位有符号整数之和一定能放入 64 位有符号整数，所以可以先在 64 位中计算候选值，再与 32 位上下界比较。只有检查通过后才写回，失败时原对象保持不变。

</details>

### 练习 C：查找最优有效价格

给定一组买方报价，忽略非正价格或非正数量，返回最大的有效价格；没有有效报价时返回空 `optional`。

<details>
<summary>参考答案与解答</summary>

```cpp
#include <cassert>
#include <cstdint>
#include <optional>
#include <vector>

struct Bid {
    std::int64_t price_ticks;
    std::int32_t quantity;
};

[[nodiscard]] std::optional<std::int64_t> best_bid_price(
    const std::vector<Bid>& bids) {
    std::optional<std::int64_t> best;

    for (const Bid& bid : bids) {
        if (bid.price_ticks <= 0 || bid.quantity <= 0) {
            continue;
        }
        if (!best || bid.price_ticks > *best) {
            best = bid.price_ticks;
        }
    }
    return best;
}

int main() {
    const std::vector<Bid> bids{
        {10'023, 100},
        {10'025, 0},
        {10'024, 250},
    };

    const auto best = best_bid_price(bids);
    assert(best.has_value());
    assert(*best == 10'024);

    const std::vector<Bid> empty;
    assert(!best_bid_price(empty).has_value());

    const std::vector<Bid> all_invalid{{0, 100}, {10'025, 0}};
    assert(!best_bid_price(all_invalid).has_value());
}
```

初始时没有“当前最大值”，因此用空 `optional` 表达缺失，而不是选择可能与合法价格冲突的魔法数字。每次只在报价同时满足价格和数量条件时更新结果。空容器和全部无效是两条不同输入路径，但输出都应为空。

</details>

### 练习 D：让拒绝原因进入类型

实现 `check_risk`，让调用者能区分方向非法、数量非法、配置非法和持仓超限，而不是只得到一个 `false`。

<details>
<summary>参考答案与解答</summary>

```cpp
#include <cassert>
#include <cstdint>

enum class Side {
    Buy,
    Sell,
    Unknown,
};

enum class RiskResult {
    Allowed,
    InvalidSide,
    InvalidQuantity,
    InvalidLimit,
    PositionLimitExceeded,
};

struct OrderCandidate {
    Side side;
    std::int32_t quantity;
};

[[nodiscard]] RiskResult check_risk(const OrderCandidate& order,
                                    std::int32_t current_position,
                                    std::int32_t max_abs_position) {
    if (order.quantity <= 0) {
        return RiskResult::InvalidQuantity;
    }
    if (max_abs_position <= 0) {
        return RiskResult::InvalidLimit;
    }

    std::int64_t signed_quantity{0};
    switch (order.side) {
        case Side::Buy:
            signed_quantity = std::int64_t{order.quantity};
            break;
        case Side::Sell:
            signed_quantity = -std::int64_t{order.quantity};
            break;
        case Side::Unknown:
            return RiskResult::InvalidSide;
    }

    const std::int64_t projected =
        std::int64_t{current_position} + signed_quantity;
    if (projected < -std::int64_t{max_abs_position}
        || projected > std::int64_t{max_abs_position}) {
        return RiskResult::PositionLimitExceeded;
    }
    return RiskResult::Allowed;
}

int main() {
    assert(check_risk({Side::Buy, 200}, 800, 1'000)
           == RiskResult::Allowed);
    assert(check_risk({Side::Buy, 200}, 801, 1'000)
           == RiskResult::PositionLimitExceeded);
    assert(check_risk({Side::Sell, 200}, -800, 1'000)
           == RiskResult::Allowed);
    assert(check_risk({Side::Sell, 200}, -801, 1'000)
           == RiskResult::PositionLimitExceeded);
    assert(check_risk({Side::Buy, 0}, 0, 1'000)
           == RiskResult::InvalidQuantity);
    assert(check_risk({Side::Buy, 1}, 0, 0)
           == RiskResult::InvalidLimit);
    assert(check_risk({Side::Unknown, 1}, 0, 1'000)
           == RiskResult::InvalidSide);
}
```

返回枚举把所有调用者需要处理的结果列在同一个类型中。测试同时覆盖两个恰好到达边界的情况、两个越界情况和三种非法输入，避免只测“正常买入”一条路径。

</details>

## 7. 后续导航

如果空白诊断不能独立完成，先回到[最小语法](minimal_syntax.md)。如果练习能运行但解释不清对象是否复制、引用何时失效或整数为何安全，就按第 1 节的定位表进入相应主讲章。

真正恢复手感的标准不是读完本页，而是你能在空白文件中完成题目、用第一条编译错误定位问题，并能解释正常路径、边界路径和失败路径为什么得到当前结果。

# C++ 基础复习：重新找回手感

如果你曾经学过 C++，却已经几年没有写，重新打开一个 `.cpp` 文件时很容易出现一种感觉：每个词都眼熟，但就是不知道第一行该写什么。初学者也会遇到相似的问题——概念好像听懂了，真正面对空白编辑器却无从下手。

本章不是第二本语法手册，而是一组**恢复手感的短练习**。我们只复习最常用、最容易遗忘的部分，并把它们放进简化的行情与风控场景。想系统学习每个语法细节，可以随时回到 [C++ 最小语法与数据建模](minimal_syntax.md)。

> 本章目标：重新独立写出、编译并修改短小的 C++20 程序；会用变量、函数、分支、循环和常用容器；能为最基本的函数参数和数据类型做出有理由的选择；最后完成一个小型行情与风控练习。

## 0. 怎样使用本章：读、敲、改

只阅读代码，很容易产生“我已经会了”的错觉。更有效的做法是让每个例子经过三遍：

1. **读**：先不运行，用自己的话预测程序会输出什么；
2. **敲**：不要复制，亲手输入到一个空白 `.cpp` 文件中，编译并运行；
3. **改**：完成例子后的修改任务，再次预测、编译和运行。

如果代码编译失败，不要立刻回到书里逐字对照。先看编译器报告的**第一条错误**，尝试自己解释。找错也是 C++ 手感的一部分。

建议在一个临时目录中完成练习，每个程序单独保存：

```text
cpp-refresh/
├── 01_warmup.cpp
├── 02_values.cpp
├── 03_flow.cpp
└── ...
```

完成一个例子后，可以在终端中按向上方向键找回上一条编译命令，只替换文件名。这样注意力会留在代码上，而不是反复输入命令。

### 30～90 分钟快速诊断

如果你不确定自己忘了多少，先不要往下看参考程序。打开一个空白文件，尝试完成这道诊断题：

1. 创建 `std::vector<std::int32_t>`，放入 `100`、`0`、`200`；
2. 写函数 `valid_total(const std::vector<std::int32_t>&)`，跳过非正数量并返回 64 位总量；
3. 在 `main` 中用 `assert` 验证正常输入得到 `300`、空容器得到 `0`；
4. 编译、运行，并解释为什么参数使用 `const&`、总量使用 64 位整数。

按下面四项各记一分：能从空白文件开始、能通过编译、主动处理空输入、能解释类型与参数。不是考试；得分只用来决定下一步从哪里复习。

| 时间 | 怎么做 | 怎样判断下一步 |
|---|---|---|
| 30 分钟 | 不看答案完成上面的空白文件诊断；卡住后再读第 1、3、5 节 | 少于 3 分就从本章顺序学习；3～4 分可按遗忘点跳读 |
| 60 分钟 | 再完成第 6、7、8 节的“动手改”，口头回答第 11 节前 8 题 | 能运行但解释不清参数、类型或缺失值，就复习对应小节和链接章节 |
| 90 分钟 | 不看答案独立完成第 9 节综合练习，再运行四次修改实验 | 能解释每个拒绝分支和整数转换，就可以进入六周路线 |

“编译通过”只说明语法和类型大体成立。快速诊断还要检查三件事：你能否预测输出、能否解释参数为什么这样写、能否主动修改而不靠逐行照抄。

## 1. 先让一个程序跑起来

把下面的程序亲手保存为 `01_warmup.cpp`：

```cpp
#include <cstdint>
#include <iostream>

int main() {
    const std::int32_t price_ticks{10'025};
    const std::int32_t quantity{300};
    const std::int64_t notional_ticks{
        std::int64_t{price_ticks} * std::int64_t{quantity}
    };

    std::cout << "notional ticks: " << notional_ticks << '\n';
}
```

然后编译和运行：

```bash
c++ -std=c++20 -Wall -Wextra -Wpedantic 01_warmup.cpp -o 01_warmup
./01_warmup
```

这些选项可以先这样记：

- `-std=c++20`：按 C++20 的规则编译；
- `-Wall -Wextra -Wpedantic`：请编译器多提醒一些可疑写法；
- `-o 01_warmup`：把生成的程序命名为 `01_warmup`。

不同电脑上的命令也可能叫 `g++` 或 `clang++`。源码如何经过编译、链接变成可执行文件，见[编译、链接与基本内存模型](compilation_memory.md)。

### 1.1 只读第一条报错

现在故意删掉 `quantity{300}` 后面的分号，再次编译。你可能会看到很多行错误。先不要数有多少条，只处理第一条：

```text
01_warmup.cpp:6:5: error: expected ';' ...
```

这类信息通常包含：

- 文件名：`01_warmup.cpp`；
- 行号和列号：例如第 6 行、第 5 列；
- 严重程度：`error` 表示无法继续生成程序，`warning` 表示能继续但值得检查；
- 编译器的猜测：例如缺少 `;`。

编译器发现问题的位置，不一定就是你写错的位置。少了右括号或分号时，它可能直到下一行才发现“读不下去了”。修好第一条错误后重新编译，后面许多连带错误往往会一起消失。

### 动手改

把 `price_ticks` 改为 `10'030`，把 `quantity` 改为 `250`。运行前先用纸算出结果。这里先把两个 32 位整数扩大到 64 位，再进行乘法，避免乘法先在较窄的有符号整数中溢出。真实系统若输入本身就是 64 位，还需要在运算前检查范围，不能假设“换成大类型就永远安全”。

## 2. 变量：初始化、`const`、`auto` 与显式转换

多年没写 C++ 时，最容易退回“先声明，之后再说”的习惯。局部变量如果没有初始化，读取它不会可靠地得到零。更稳妥的默认习惯是：**创建对象时就给它一个有效值，能不修改就加 `const`**。

```cpp
#include <cstdint>
#include <iostream>

int main() {
    const std::int32_t raw_price_ticks{10'025};
    const auto price_ticks = raw_price_ticks; // 推导为 std::int32_t

    const double average_quantity{125.75};
    const auto displayed_quantity =
        static_cast<std::int32_t>(average_quantity);

    std::int32_t refresh_count{0};
    refresh_count = refresh_count + 1;

    std::cout << "price: " << price_ticks << '\n';
    std::cout << "displayed quantity: " << displayed_quantity << '\n';
    std::cout << "refresh count: " << refresh_count << '\n';
}
```

把四个概念分开：

- **初始化**发生在对象出生时：`refresh_count{0}`；
- **赋值**修改一个已经存在的对象：`refresh_count = ...`；
- `const` 表示不能通过这个名字再修改对象；
- `auto` 让编译器从右侧推导类型，不表示“这个变量没有类型”或“运行时再决定类型”。

`static_cast<std::int32_t>(average_quantity)` 明确告诉读者：这里有意把 `double` 转成整数，小数部分会被截去。当前常量 `125.75` 有限且在目标范围内，所以转换成立。显式写出转换并不会自动让它变安全；运行时值若是 NaN、无穷，或截断后的值超出 `std::int32_t` 可表示范围，浮点转整数不是“自动夹到边界”，而会产生未定义行为。转换前仍要验证范围，并确认截断符合业务含义。

本书偏爱花括号初始化，因为它能阻止一些悄悄丢失信息的窄化转换：

```cpp,ignore
// 故意不能编译：125.75 不能用花括号直接初始化 int。
const int quantity{125.75};
```

基础代码中常见的几种外形可以先这样辨认：

```cpp,ignore
int uninitialized; // 没有初始值，读取它是错误的
int zero{};        // 值初始化，这里的 int 得到 0
int copy = 5;      // 拷贝初始化
int direct(5);     // 直接初始化
int list{5};       // 列表初始化，并拒绝一部分窄化转换
```

它们对简单整数看起来接近，但对类类型可能选择不同构造函数，不能把括号机械替换。`{}` 也不是“让任何类的所有字节自动清零”的魔法；类自己的构造函数仍要正确初始化成员。

### 什么时候使用 `auto`

可以用一个朴素规则起步：

- 右侧已经让类型很清楚时使用 `auto`，例如迭代器或较长的模板类型；
- 类型承载业务含义时写出来，例如协议明确规定的 `std::int32_t` 数量；
- 不要用 `auto` 掩盖重要转换。

还要留意：普通 `auto` 默认得到一个新值，而不是引用。

```cpp,ignore
Quote quote{/* ... */};
auto copy = quote;             // 复制一份 Quote
const auto& view = quote;      // 只读引用，不复制
```

### 动手改

去掉 `refresh_count` 的 `const` 是不需要的，因为它本来就不是 `const`。试着给 `price_ticks` 赋新值，观察编译器如何阻止修改。然后把 `displayed_quantity` 的目标类型改成 `std::int64_t`，解释“类型变宽”为什么仍没有恢复被截掉的小数。

## 3. `if`、`for` 与函数：让代码表达步骤

函数把一个问题命名，`if` 表达选择，`for` 表达重复。下面的程序验证四档数量，并求出有效总量：

```cpp
#include <array>
#include <cstdint>
#include <iostream>

[[nodiscard]] bool is_valid_quantity(std::int32_t quantity) {
    return quantity > 0;
}

[[nodiscard]] std::int64_t total_quantity(
    const std::array<std::int32_t, 4>& quantities) {
    std::int64_t total{0};
    for (const std::int32_t quantity : quantities) {
        if (is_valid_quantity(quantity)) {
            total += std::int64_t{quantity};
        }
    }
    return total;
}

int main() {
    const std::array<std::int32_t, 4> quantities{100, 200, -1, 50};

    std::cout << "valid total: " << total_quantity(quantities) << '\n';
}
```

从外向内读：

1. `main` 创建四个数量；
2. `total_quantity` 用范围 `for` 逐个读取；
3. `if` 只让正数进入求和；
4. 函数返回总量。

`[[nodiscard]]` 提醒调用者不要随手丢掉函数结果。它通常表现为编译器警告，不是业务上的强制校验。

总量使用 64 位整数，单项使用 32 位整数。每次相加前都把单项扩大，这样四个任意 32 位整数的总和可以安全放进 64 位整数。真实程序若容器长度不受约束，累计值仍可能越界，需要额外的上限和溢出检查。

### 两种常见 `for`

只关心元素时，范围 `for` 最直接：

```cpp,ignore
for (const auto quantity : quantities) {
    // 使用 quantity
}
```

需要下标时，再使用带计数器的形式：

```cpp,ignore
for (std::size_t i{0}; i < quantities.size(); ++i) {
    // i 是下标，quantities[i] 是元素
}
```

循环条件必须保证下标小于 `size()`；`i <= quantities.size()` 会在最后一次访问越过尾部。

### 动手改

把过滤条件改为“数量必须在 1 到 150 之间”。然后增加一个 `invalid_count` 函数，返回无效元素个数。先自己写，再看本章末尾的参考答案。

### 3.1 `while`、`switch` 与函数重载

范围 `for` 适合“逐个处理一组元素”。不知道准确重复次数、只知道“条件成立就继续”时，可以用 `while`。消息类型只有有限几种时，`switch` 往往比一串相等比较更容易扫读。

下面的教学程序依次分发三类消息：

```cpp
#include <array>
#include <cstddef>
#include <iostream>
#include <string_view>

enum class MessageType {
    Quote,
    Trade,
    Heartbeat,
};

void print_payload(int sequence) {
    std::cout << "sequence=" << sequence << '\n';
}

void print_payload(std::string_view text) {
    std::cout << "text=" << text << '\n';
}

int main() {
    const std::array<MessageType, 3> messages{
        MessageType::Quote,
        MessageType::Trade,
        MessageType::Heartbeat,
    };

    std::size_t cursor{0};
    while (cursor < messages.size()) {
        switch (messages[cursor]) {
            case MessageType::Quote:
                std::cout << "handle quote: ";
                print_payload(101);
                break;
            case MessageType::Trade:
                std::cout << "handle trade: ";
                print_payload("200 shares");
                break;
            case MessageType::Heartbeat:
                std::cout << "handle heartbeat\n";
                break;
        }
        ++cursor;
    }
}
```

读代码时留意三点：

- `while` 每次进入循环前检查条件；这里的 `++cursor` 让处理位置向前移动，漏掉它会造成死循环；
- `switch` 根据枚举值选择 `case`，每个分支末尾的 `break` 防止继续落入下一个分支；
- 两个 `print_payload` 同名，但参数类型不同。编译器根据调用实参选择版本，这叫**函数重载**。

这里的 `std::string_view` 只在函数调用期间查看字符，不拥有它们，也不会延长来源的生命周期。本例传入字符串字面量，因此字符在整个程序期间都存在；如果视图来自一个稍后被销毁或修改的 `std::string`，保存该视图就可能悬空。更完整的所有权与失效规则见 STL 专章。

函数也可以按参数数量重载，例如 `print(int)` 和 `print(int, int)`。但不能只靠返回类型区分；即使把调用结果赋给一个类型已经写明的变量，返回类型也不参与区分同名重载。

按值参数上的顶层 `const` 也不能构成新重载：`void print(int)` 与 `void print(const int)` 对调用者是同一个参数类型。完整的重载排名很复杂，基础阶段只需先读懂候选参数；遇到 `no matching function` 或 `call is ambiguous`，先看编译器随后给出的 `note` 列出了哪些候选。

```cpp,ignore
// 故意错误：参数列表完全相同，只有返回类型不同，不能构成重载。
int status();
bool status();
```

入门阶段把重载理解到这里就够了：同一个动作对不同输入有自然含义时可以同名；如果两个操作的业务含义不同，直接起两个清楚的名字通常更好。

表示空指针时使用 `nullptr`，不要用 `0` 或旧式 `NULL`。`nullptr` 有专门的空指针类型，参与重载选择时更不容易被当成普通整数。

### 动手改

增加 `MessageType::Reject` 以及对应的 `case`，调用 `print_payload("risk rejected")`。然后暂时删掉一个 `break`，观察输出为什么会多处理一个分支，再立刻把它恢复。

## 4. 函数参数：先做四种最小选择

C++ 的参数写法很多。恢复基础时，先掌握下面四种就能处理大量普通代码：

| 写法 | 最小直觉 | 常见用途 |
|---|---|---|
| `T value` | 给函数一个值 | 小型数字、枚举，或函数需要自己的副本 |
| `const T& value` | 必须存在，只读，不复制整个对象 | 读取较大的对象 |
| `T& value` | 必须存在，函数会修改原对象 | 明确的输出或原地修改 |
| `const T* value` | 可以没有对象，只读访问 | `nullptr` 表示“没有” |

```cpp
#include <cstdint>
#include <iostream>
#include <string>

struct Quote {
    std::string symbol;
    std::int64_t price_ticks;
    std::int32_t quantity;
};

[[nodiscard]] bool is_positive(std::int32_t value) { // 按值
    return value > 0;
}

void print_quote(const Quote& quote) { // 必须存在，只读
    std::cout << quote.symbol << ' '
              << quote.price_ticks << " x " << quote.quantity << '\n';
}

void clear_quantity(Quote& quote) { // 必须存在，并修改原对象
    quote.quantity = 0;
}

void print_if_present(const Quote* quote) { // 可以没有
    if (quote == nullptr) {
        std::cout << "no quote\n";
        return;
    }
    print_quote(*quote);
}

int main() {
    Quote quote{"ABC", 10'025, 300};

    std::cout << std::boolalpha << is_positive(quote.quantity) << '\n';
    print_quote(quote);
    print_if_present(&quote);

    clear_quantity(quote);
    print_if_present(&quote);
    print_if_present(nullptr);
}
```

这里的裸指针和引用只表达“访问”，不自动表达谁拥有对象。`print_if_present` 解引用前先检查 `nullptr`；引用虽然通常不能为空，却仍可能指向已经销毁的对象。完整的生命周期规则见[指针、引用、`const` 与对象生命周期](pointers_references.md)。

不要机械地把所有参数都写成 `const T&`。复制一个 `int` 很便宜，按值更简单；是否复制一个复杂对象，则要结合语义和测量判断。

### 动手改

新增函数 `[[nodiscard]] bool try_add_quantity(Quote& quote, std::int32_t delta)`。为了避免把错误的加法带进金融示例，不要直接写 `quote.quantity += delta`。先把两个 32 位输入转换为 64 位再相加，检查结果是否位于 `std::int32_t` 的范围内；安全时写回并返回 `true`，超出范围时保持原对象不变并返回 `false`。这个练习的完整答案在后文。

## 5. `string`、`array` 和 `vector`：先会最常用操作

这三个类型可以先这样区分：

- `std::string`：自己拥有一串字符，适合保存合约名等文本；
- `std::array<T, N>`：长度 `N` 在编译期固定，元素连续；
- `std::vector<T>`：长度运行时可变，元素也连续。

`string::size()` 返回字符存储单元数量，不能普遍当作“人眼看到的 Unicode 字符数”。`std::array` 自身没有动态容量，但这不保证包含它的整个对象一定物理放在所谓“栈”上，也不保证元素类型内部不会分配。

```cpp
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

int main() {
    const std::string symbol{"ABC-FUT"};
    std::cout << "symbol length: " << symbol.size() << '\n';

    std::array<std::int64_t, 3> fixed_prices{10'025, 10'024, 10'023};
    fixed_prices[1] = 10'020;

    std::vector<std::int64_t> recent_prices;
    recent_prices.reserve(4);
    recent_prices.push_back(10'025);
    recent_prices.push_back(10'023);
    recent_prices.push_back(10'024);

    std::sort(recent_prices.begin(), recent_prices.end());

    std::cout << "best fixed price: " << fixed_prices.front() << '\n';
    std::cout << "recent count: " << recent_prices.size() << '\n';
    std::cout << "lowest recent price: " << recent_prices.front() << '\n';
    std::cout << "highest recent price: " << recent_prices.back() << '\n';
}
```

最常用的操作并不多：

- `size()` 返回元素个数；
- `empty()` 判断是否没有元素；
- `front()` / `back()` 读取首尾元素，调用前必须确认容器非空；
- `vector::push_back()` 在尾部添加元素；
- `vector::reserve()` 预留容量，但**不会创建元素**；
- `vector::resize()` 改变实际元素数量，必要时创建或销毁元素；
- `begin()` / `end()` 表示算法操作的半开区间。

一个容易忘记的初始化差别是：

```cpp,ignore
std::vector<int> five_zeros(5); // 5 个元素，每个为 0
std::vector<int> one_five{5};  // 1 个元素，值为 5
```

括号版本在这里选择“元素个数”构造函数，花括号版本优先匹配初始化列表。它再次说明：初始化形式是类型接口的一部分，不能只看标点长得像不像。

范围循环也要主动决定是否复制：`for (auto value : values)` 每轮得到一份值；`for (const auto& value : values)` 只读原元素；`for (auto& value : values)` 可以修改原元素。对小整数按值通常最清楚，对较大对象则要明确复制是否符合语义。

`prices[i]` 不检查边界；`prices.at(i)` 越界时会抛出异常。两者都要求你知道下标语义，不能因为 `at` 会检查就随意使用外部输入作为下标。

### `vector` 引用何时失效

如果 `vector` 扩容，它会搬到新的连续存储中，原先指向元素的所有指针、引用和迭代器都会失效。没有扩容时也不能笼统地说“全部安全”：

- 尾部 `push_back` 不扩容时，原有元素的引用、指针和迭代器仍有效，但旧的 `end()` 失效；
- 在中间插入且不扩容时，插入点之前的迭代器和引用仍有效，插入点及其后的会失效；
- 擦除元素后，被擦除位置及其后的迭代器和引用会失效。

因此不要保存一个元素引用，再随意修改同一个 `vector` 的结构。更完整的成本与失效规则见 [STL 容器、迭代器与算法的成本模型](stl_cost_model.md)。

### 动手改

先判断 `recent_prices.empty()`，再打印首尾元素。然后增加一个价格，观察 `size()` 和 `capacity()`；不要假设容量一定按两倍增长，因为具体增长策略由标准库实现决定。

## 6. `enum class`、`struct` 与 `class`：给业务概念起名字

仅用几个散落的整数表示一笔报价，很容易把买卖方向、价格和数量传错位置。自定义类型能把业务结构写进代码。

```cpp
#include <cstdint>
#include <iostream>
#include <string>

enum class Side {
    Buy,
    Sell,
    Unknown,
};

struct Order {
    std::string symbol;
    Side side;
    std::int32_t quantity;
};

class RiskLimits {
public:
    explicit RiskLimits(std::int32_t max_abs_position)
        : max_abs_position_(max_abs_position) {}

    [[nodiscard]] bool is_valid() const {
        return max_abs_position_ > 0;
    }

    [[nodiscard]] bool allows(const Order& order,
                              std::int32_t current_position) const {
        if (!is_valid() || order.quantity <= 0) {
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

        return projected >= -std::int64_t{max_abs_position_}
            && projected <= std::int64_t{max_abs_position_};
    }

private:
    std::int32_t max_abs_position_;
};

int main() {
    const RiskLimits limits{1'000};
    const Order order{"ABC-FUT", Side::Buy, 300};

    std::cout << std::boolalpha
              << "config valid: " << limits.is_valid() << '\n'
              << "order allowed: " << limits.allows(order, 800) << '\n';
}
```

这里出现了三个层次：

- `enum class Side` 定义有限且不会悄悄当成整数使用的买卖方向；
- `struct Order` 把一组相关数据装进同一个对象，成员默认公开；
- `class RiskLimits` 把数据和操作放在一起，使用 `private` 隐藏内部成员、用 `public` 提供接口。

`RiskLimits(...)` 是构造函数。成员初始化列表中的 `max_abs_position_(max_abs_position)` 在对象创建时直接初始化成员。`allows(...) const` 末尾的 `const` 表示该方法不会通过 `this` 修改当前 `RiskLimits` 对象。

`explicit` 阻止某些意外的隐式构造。对只有一个普通参数的构造函数，它通常是一个稳妥的默认选择。

风控计算先把 32 位持仓和数量提升为 64 位再相加。任意两个 32 位有符号整数的和都能放进 64 位整数，所以这里不会发生有符号溢出。函数还保留了真实业务检查：数量必须为正、配置必须有效、预计持仓不能超过限额。

### `struct` 和 `class` 不是“数据与高级对象”的区别

两者都能有构造函数、方法和访问控制。最明显的语言差别是默认访问权限：

- `struct` 成员默认 `public`；
- `class` 成员默认 `private`。

项目通常用 `struct` 表达简单的数据组合，用 `class` 表达需要维护不变量的类型，但这是一种约定，不是语言强制规则。资源如何随着对象生命周期自动清理，见[构造、析构、RAII 与对象生命周期](raii_lifetime.md)。

### 动手改

把 `Order` 的方向改成 `Side::Unknown`，确认 `allows` 明确拒绝。然后为 `Side` 编写一个使用 `switch` 的 `side_name` 函数，并让未知方向返回 `"UNKNOWN"`；不要把所有“非 Buy”状态自动当成卖出。

## 7. `std::optional`：把“可能没有”写进类型

查找不一定成功。使用 `0` 或 `-1` 表示“没有价格”，会与合法业务值混在一起；返回裸指针又会带来生命周期问题。只需要返回一个小值时，`std::optional<T>` 是很清楚的选择。

```cpp
#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

struct Quote {
    std::string symbol;
    std::int64_t price_ticks;
};

[[nodiscard]] std::optional<std::int64_t> find_price(
    const std::vector<Quote>& quotes,
    std::string_view wanted_symbol) {
    for (const Quote& quote : quotes) {
        if (quote.symbol == wanted_symbol) {
            return quote.price_ticks;
        }
    }
    return std::nullopt;
}

int main() {
    const std::vector<Quote> quotes{
        {"ABC-FUT", 10'025},
        {"XYZ-FUT", 20'010},
        {"ZERO", 0},
    };

    if (const auto price = find_price(quotes, "ABC-FUT")) {
        std::cout << "found: " << *price << '\n';
    } else {
        std::cout << "ABC-FUT not found\n";
    }

    const auto missing = find_price(quotes, "NO-SUCH-SYMBOL");
    std::cout << "missing has value: "
              << std::boolalpha << missing.has_value() << '\n';

    const auto zero = find_price(quotes, "ZERO");
    assert(zero.has_value());
    assert(*zero == 0); // optional 有值；内部数值为 0
}
```

可以把 `optional<int64_t>` 想成一个拥有内部值的盒子：里面要么有一个 `int64_t`，要么明确为空。它不是指针，也不表示共享所有权。

- `return value;` 返回有值状态；
- `return std::nullopt;` 返回无值状态；
- `if (result)` 或 `result.has_value()` 检查是否有值；
- 检查后用 `*result` 取值；若保存的是对象，也可在检查后使用 `result->member`；
- `value_or(default_value)` 可以提供默认值，但前提是该默认值真的具有业务含义。

直接对空 `optional` 调用 `.value()` 会抛出异常；直接用 `*result` 访问空状态则不满足接口前提。两种写法都不能代替事先检查。

`std::optional` 只表达“有或没有”，不解释失败原因。如果调用者需要区分“合约不存在”“行情过期”“字段损坏”，就应该使用能携带错误原因的结果类型。

还要区分“盒子是否存在”和“盒子里的布尔值”：`std::optional<bool>{false}` **有值**，只是内部值为 `false`。`if (result)` 检查的是是否存在，不是在判断内部布尔值为真。

### 动手改

把函数改为返回整个 `Quote` 的副本：`std::optional<Quote>`。然后思考：如果 `Quote` 很大或复制成本很高，返回副本是否仍合适？这时可以重新设计所有权，也可以返回引用包装；不要直接返回指向临时对象的引用或指针。

## 8. `assert`：检查开发期假设，不代替业务校验

`assert(condition)` 适合表达“如果程序内部逻辑正确，这个条件一定成立”。它能在开发和测试时尽早暴露错误，但发布构建可能通过定义 `NDEBUG` 把断言完全移除。启用断言时，条件失败通常会打印诊断并调用 `std::abort` 终止进程；它不是返回给业务调用者的错误，也不会自动变成可以恢复的异常。

```cpp
#include <cassert>
#include <cstdint>
#include <iostream>

[[nodiscard]] bool is_order_quantity_allowed(
    std::int32_t quantity,
    std::int32_t max_order_quantity) {
    assert(max_order_quantity > 0); // 调用前应已验证的内部配置不变量

    // 这是真正的业务校验，即使 assert 被关闭也仍然存在。
    return quantity > 0 && quantity <= max_order_quantity;
}

int main() {
    const std::int32_t configured_limit{1'000};

    if (configured_limit <= 0) {
        std::cout << "invalid risk configuration\n";
        return 1;
    }

    const std::int32_t external_quantity{-20};
    if (!is_order_quantity_allowed(external_quantity, configured_limit)) {
        std::cout << "order rejected\n";
        return 0;
    }

    std::cout << "order accepted\n";
}
```

这个例子保留了两道不同的检查：

- 启动或加载配置时，用普通 `if` 拒绝非法风控配置；
- 函数中的 `assert` 检查调用方本应保证的内部不变量；
- 外部订单数量继续由普通代码校验，不能只写在 `assert` 中。

不要在断言里放必须发生的操作：

```cpp,ignore
// 坏例子：关闭断言后，read_message() 可能根本不会被调用。
assert(read_message());
```

行情字段、订单数量、配置文件和网络消息都属于可能出错的外部输入。即使在发布版本，它们也必须经过正常的业务校验，并得到明确的拒绝、错误或降级行为。

### 动手改

把 `external_quantity` 改成 `500` 和 `1'500`，分别预测结果。然后用 `-DNDEBUG` 再编译一次，确认业务结果并没有因为断言关闭而改变：

```bash
c++ -std=c++20 -DNDEBUG -Wall -Wextra -Wpedantic 08_assert.cpp -o 08_assert
```

## 9. 综合练习：从一条行情生成风控后的订单

现在把前面的基础拼起来。我们设计一个极小的处理流程：

1. 验证最优买卖价和数量；
2. 比较买卖盘数量，得到一个教学信号；
3. 生成固定数量的候选订单；
4. 根据当前持仓和限额决定是否允许发送。

这不是可用于交易的策略。它只是把变量、函数、分支、自定义类型、`optional` 和整数范围放进同一个可运行练习。

### 9.1 先自己实现

下面只给出接口和处理顺序，代码片段故意不完整：

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

// 1. 编写 is_valid_market(update)。
// 2. 编写 choose_side(update)，返回 std::optional<Side>。
// 3. 编写 is_allowed(order, current_position, max_abs_position)。
// 4. 在 main 中打印“拒绝原因”或最终订单。
```

约束如下：

- 买价和卖价都必须为正，且 `bid_ticks < ask_ticks`；
- 买卖数量都必须为正；
- 买量比卖量至少多 `100` 时选择买入，反之选择卖出，否则没有信号；
- 候选订单数量固定为 `200`；
- 预计持仓绝对值不能超过 `1'000`；
- 不能依赖可能发生有符号溢出的加法。

### 9.2 完整参考实现

先完成自己的版本，再对照下面的实现：

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
    assert(is_allowed(allowed, 799, 1'000));
    assert(is_allowed(allowed, 800, 1'000)); // 恰好到限额
    assert(!is_allowed(allowed, 801, 1'000));
    assert(!is_allowed({"ABC-FUT", Side::Buy, 0}, 0, 1'000));
    assert(!is_allowed(allowed, 0, 0));

    const OrderCandidate unknown{"ABC-FUT", Side::Unknown, 200};
    assert(!is_allowed(unknown, 0, 1'000));

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

这段程序有几个刻意的设计：

- 外部行情先验证，再进入信号计算；
- `optional<Side>` 把“行情有效但没有信号”表达为正常状态；
- 两个 32 位数量先转换为 64 位再相减，因此差值不会发生有符号溢出；
- 预计持仓也在 64 位中计算；
- 无效行情、无信号和风控拒绝得到不同输出。

真实 HFT 系统还需要处理序号、时间戳、重复或乱序消息、订单状态、价格上下限、额度恢复、网关失败等大量问题。这里的目标只是练熟语言基础，不是提供生产策略。

### 继续修改

依次做下面四次实验，每次先预测输出：

1. 把买量改为 `650`，观察“没有信号”；
2. 把当前持仓改为 `900`，观察买单被限额拒绝；
3. 让 `bid_ticks` 等于 `ask_ticks`，观察行情被拒绝；
4. 交换买卖数量，让程序生成卖单。

## 10. 常见遗忘坑：看到就停一下

### 10.1 未初始化的局部变量

```cpp,ignore
int quantity;
std::cout << quantity << '\n'; // 坏例子：读取未初始化的值
```

声明时初始化。若“暂时没有值”本身有意义，考虑 `optional`。

### 10.2 `=` 与 `==`

`=` 是赋值，`==` 是比较。编译警告能发现一部分错误，但不能替代你理解条件表达式。

### 10.3 整数除法

```cpp,ignore
const int ratio = 3 / 2; // 结果是 1，不是 1.5
```

如果业务需要小数，要明确选择表示方式。价格和金额是否适合浮点数，要由精度与协议要求决定，不能只加一个 `double` 就结束设计。

### 10.4 相乘之后才扩大类型

```cpp,ignore
// 坏例子：乘法可能先在 int32_t 中溢出，之后转换已经太晚。
const std::int64_t value = std::int64_t{price_ticks * quantity};

// 至少要在运算前扩大输入；输入范围更大时还要先检查。
const std::int64_t safer =
    std::int64_t{price_ticks} * std::int64_t{quantity};
```

### 10.5 有符号与无符号数混用

`container.size()` 返回无符号的 `std::size_t`。把负数和它比较可能产生意外转换。下标循环优先使用 `std::size_t`，外部带符号输入则先验证非负，再做经过检查的转换。

### 10.6 范围 `for` 无意中复制对象

```cpp,ignore
for (auto quote : quotes) {        // 每次复制 quote
}

for (const auto& quote : quotes) { // 只读访问原元素
}
```

对 `int` 这类小值，按值遍历很自然；对较大对象，应有意识地决定是否复制。

### 10.7 保存 `vector` 元素引用后继续插入

扩容会让全部元素引用失效；即使没有扩容，中间插入或擦除也会让相应位置及其后的引用失效。普通下标可以跨重新分配，但中间插入或删除会改变它对应的逻辑元素，仅检查下标仍在范围内还不够。应先完成结构修改再取引用，或用稳定业务 ID 加代际编号重新查找；只有已经证明容器只做尾部追加等操作时，才能依赖旧下标仍代表同一对象。

### 10.8 对空容器调用 `front()` / `back()`

先检查 `empty()`。它们不会返回一个“空元素”。

### 10.9 没检查就取 `optional`

先判断是否有值，再解引用。`value_or(default)` 只有在默认值确实具有业务含义时才使用，不能悄悄把“行情缺失”变成价格零。

### 10.10 把 `assert` 当风控

断言可能在发布构建中消失。外部输入验证、额度检查和错误处理必须使用正常控制流。

### 10.11 返回局部对象的指针或引用

```cpp,ignore
const Quote& make_quote() {
    Quote local{/* ... */};
    return local; // 坏例子：函数结束后 local 已销毁
}
```

这是悬空引用。需要拥有结果时通常按值返回，让编译器完成返回值优化或移动。

### 10.12 忘记 `class` 默认是 `private`

`struct` 默认公开，`class` 默认私有。遇到“成员无法访问”的错误时，检查 `public:` 和 `private:` 的位置。

## 11. 面试自测：先用自己的话回答

不要背标准句子。每道题先尝试说出“它解决什么实际问题”，再补语法。

### 1. 初始化和赋值有什么区别？

初始化在对象创建时给出初始状态；赋值修改已经存在的对象。构造复杂对象时，两者可能调用完全不同的操作。

### 2. `const` 有什么价值？

它把“不应通过当前接口修改”的意图交给编译器检查，也减少读代码时需要考虑的状态变化。它不是并发安全保证，也不表示世界上绝无其他路径能修改同一对象。

### 3. `auto` 会不会让 C++ 变成动态类型语言？

不会。编译器仍会在编译期推导出一个确定类型，后续操作照常接受静态类型检查。

### 4. 何时按值、何时用 `const T&`？

小型标量和枚举通常按值最清楚；只读访问较大对象时常用 `const T&` 避免一次复制。最终仍要结合所有权语义、类型大小和测量，而不是只看一条规则。

### 5. 引用和指针最直观的区别是什么？

引用通常表示对象必须存在并且绑定后不改绑；指针可以用 `nullptr` 表示没有对象，也可以改为指向别处。两者都不会自动管理所访问对象的生命周期。

### 6. `array` 和 `vector` 怎样选择？

元素数量在编译期固定时可以选 `array`；数量运行时变化时常以 `vector` 为默认候选。还要考虑容量上限、分配时机和引用失效。

### 7. `reserve(100)` 之后能不能写 `values[0]`？

不能。`reserve` 只保证容量至少达到目标，不创建元素，`size()` 仍可能是零。要添加元素可用 `push_back`，要创建指定数量元素可用 `resize`。

### 8. 为什么推荐 `enum class`？

它把有限状态放进独立类型，作用域清楚，也不会像传统枚举那样轻易隐式转换成整数，能减少把方向、状态和普通数字混用的错误。

### 9. `optional<T>` 解决什么问题？

它在类型中明确表达“可能有一个 `T`，也可能没有”，避免用魔法数字冒充缺失值。它不携带详细失败原因。

### 10. 为什么 `assert` 不能承担业务校验？

发布构建可能关闭断言。即使断言开启，外部输入非法也是程序需要正常处理的情况，不一定是内部逻辑不可能发生的错误。

### 11. `vector` 扩容后，原元素引用还有效吗？

无效。扩容会搬迁元素，所有指向旧元素的指针、引用和迭代器都会失效。没有扩容也要根据插入或擦除位置判断，不能一概而论。

### 12. 为什么金融整数运算要在运算前扩大或检查？

因为表达式先按操作数类型计算，结果生成后再放进大类型可能已经太晚。有符号整数溢出属于未定义行为；扩大只在目标类型确实足以容纳所有可能结果时才足够，否则必须先检查边界。

## 12. 练习与完整参考答案

### 练习 A：统计无效数量

为第 3 节的数组编写 `invalid_count`：数量不在闭区间 `[1, 150]` 时记为无效。

<details>
<summary>展开完整参考答案</summary>

```cpp
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>

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
    const std::array<std::int32_t, 4> quantities{100, 200, -1, 50};
    const std::array<std::int32_t, 4> all_valid{1, 150, 2, 149};
    const std::array<std::int32_t, 4> all_invalid{0, 151, -1, 200};

    assert(invalid_count(quantities) == 2);
    assert(invalid_count(all_valid) == 0);
    assert(invalid_count(all_invalid) == 4);
    std::cout << "invalid: " << invalid_count(quantities) << '\n';
}
```

</details>

### 练习 B：安全地修改报价数量

实现 `try_add_quantity`。它接收可变引用和增量；若相加结果超出 `std::int32_t` 范围，保持原对象不变并返回 `false`。

<details>
<summary>展开完整参考答案</summary>

```cpp
#include <cassert>
#include <cstdint>
#include <iostream>
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
    Quote quote{"ABC-FUT", 300};
    assert(try_add_quantity(quote, 50));
    assert(quote.quantity == 350);

    Quote upper{"ABC-FUT", std::numeric_limits<std::int32_t>::max()};
    assert(!try_add_quantity(upper, 1));
    assert(upper.quantity == std::numeric_limits<std::int32_t>::max());

    Quote upper_edge{
        "ABC-FUT", std::numeric_limits<std::int32_t>::max() - 1};
    assert(try_add_quantity(upper_edge, 1));
    assert(upper_edge.quantity == std::numeric_limits<std::int32_t>::max());

    Quote lower{"ABC-FUT", std::numeric_limits<std::int32_t>::min()};
    assert(!try_add_quantity(lower, -1));
    assert(lower.quantity == std::numeric_limits<std::int32_t>::min());

    Quote lower_edge{
        "ABC-FUT", std::numeric_limits<std::int32_t>::min() + 1};
    assert(try_add_quantity(lower_edge, -1));
    assert(lower_edge.quantity == std::numeric_limits<std::int32_t>::min());

    std::cout << "checked quantity: " << quote.quantity << '\n';
}
```

这里两个 32 位整数先扩大为 64 位再相加。任意两个 32 位有符号整数之和都能放进 64 位整数，因此可以安全地检查再写回。

</details>

### 练习 C：查找最优买价

给定一组报价，忽略非正价格或非正数量，返回最大的有效买价；没有有效报价时返回空 `optional`。

<details>
<summary>展开完整参考答案</summary>

```cpp
#include <cassert>
#include <cstdint>
#include <iostream>
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

    std::cout << "best valid bid: " << *best << '\n';
}
```

</details>

### 练习 D：给风控拒绝增加原因

把综合练习中的 `is_allowed` 从 `bool` 改成下面的结果类型，让调用者能区分方向非法、数量非法、配置非法和持仓超限：

```cpp,ignore
enum class RiskResult {
    Allowed,
    InvalidSide,
    InvalidQuantity,
    InvalidLimit,
    PositionLimitExceeded,
};
```

<details>
<summary>展开完整参考答案</summary>

```cpp
#include <cassert>
#include <cstdint>
#include <iostream>

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

[[nodiscard]] const char* result_name(RiskResult result) {
    switch (result) {
        case RiskResult::Allowed:
            return "allowed";
        case RiskResult::InvalidSide:
            return "invalid side";
        case RiskResult::InvalidQuantity:
            return "invalid quantity";
        case RiskResult::InvalidLimit:
            return "invalid limit";
        case RiskResult::PositionLimitExceeded:
            return "position limit exceeded";
    }
    return "unknown";
}

int main() {
    assert(check_risk({Side::Buy, 200}, 800, 1'000)
           == RiskResult::Allowed); // 恰好到正限额
    assert(check_risk({Side::Buy, 200}, 801, 1'000)
           == RiskResult::PositionLimitExceeded);
    assert(check_risk({Side::Sell, 200}, -800, 1'000)
           == RiskResult::Allowed); // 恰好到负限额
    assert(check_risk({Side::Sell, 200}, -801, 1'000)
           == RiskResult::PositionLimitExceeded);
    assert(check_risk({Side::Buy, 0}, 0, 1'000)
           == RiskResult::InvalidQuantity);
    assert(check_risk({Side::Buy, 1}, 0, 0)
           == RiskResult::InvalidLimit);
    assert(check_risk({Side::Unknown, 1}, 0, 1'000)
           == RiskResult::InvalidSide);

    const RiskResult result = check_risk({Side::Buy, 200}, 800, 1'000);
    std::cout << result_name(result) << '\n';
}
```

返回枚举比返回一个难以解释的数字更清楚。实际项目可能用携带更多上下文的错误类型，但基础思想相同：把调用者需要处理的结果显式表达出来。

</details>

## 13. 后续导航

如果这一章还有“知道答案但写不顺”的地方，不必急着学高阶内容。把前八个例子关掉书重新写一遍，通常比再读十页更有效。

接下来可以按遗忘点选择路线：

- 语句、类型、函数或自定义类型仍不熟：回到 [C++ 最小语法与数据建模](minimal_syntax.md)；
- 不清楚报错来自编译、链接还是运行阶段：阅读[编译、链接与基本内存模型](compilation_memory.md)；
- `&`、`*`、`const T&` 和生命周期容易混：阅读[指针、引用、`const` 与对象生命周期](pointers_references.md)；
- `vector` 扩容、迭代器和容器选择不清楚：阅读 [STL 容器、迭代器与算法的成本模型](stl_cost_model.md)；
- 想理解对象为何能自动清理资源：阅读[构造、析构、RAII 与对象生命周期](raii_lifetime.md)；
- 基础已经恢复，希望按面试节奏继续：进入 [C++ 面试六周路线](interview_roadmap.md)。

最后记住：恢复 C++ 手感不等于一次背完语言标准。你真正需要的是一个可靠的小循环——写一小段、打开警告、读第一条错误、修改、再运行。这个循环熟练后，后面的高级内容才会有落脚点。

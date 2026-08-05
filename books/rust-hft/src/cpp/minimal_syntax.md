# C++ 最小语法与数据建模

第一次打开 C++ 文件时，你可能会看到 `#include`、`std::`、花括号、圆括号和分号挤在一起。先不要急着背规则。本章只做一件事：让你能从上到下读懂一段短程序，并能用最少的语法表达报价和订单。

本章是 C++ 部分的第一章。你不需要学过 C，也不需要提前理解内存、指针或模板。下一章才会解释源码怎样经过编译和链接变成程序。

> 本章目标：能看懂语句、表达式、分号和大括号；能声明、初始化和修改变量；能选择最基本的数据类型；能编写函数、分支和循环；能用 `enum class`、`struct` 与 `class` 表达简化的 `Side`、`Quote` 和 `Order`；对命名空间和头文件有最小直觉。

## 1. 先读懂一个完整程序

下面的程序计算一笔订单对应的“价格刻度数 × 数量”并输出结果。它很短，却已经包含了最常见的 C++ 外形：

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

先把每一部分翻译成日常语言：

- `#include <cstdint>` 让程序知道 `std::int64_t` 这个整数类型的声明；
- `#include <iostream>` 让程序知道标准输出工具 `std::cout`；
- `int main()` 是这个命令行程序开始执行的位置；
- `{` 和 `}` 圈出 `main` 包含的代码；
- `std::int64_t{price_ticks} * std::int64_t{quantity}` 先扩大输入，再做乘法；
- `std::cout << ...` 把内容依次送到终端；
- `"notional ticks: "` 是一段字符串；
- `'\n'` 表示换行；
- 每条简单声明或操作的末尾都有分号 `;`。

数字中的单引号用于分组，方便人阅读。`10'025` 和 `10025` 是同一个整数。

乘法中的 `std::int64_t{price_ticks}` 暂时可以读作“先把 32 位输入扩大成 64 位整数”。两个 32 位有符号整数的取值乘积能放进 64 位有符号整数，所以这里要在相乘**之前**扩大两边。若写成 `std::int64_t{price_ticks * quantity}`，乘法会先按较小类型发生；结果即使随后放进大类型，也无法补救此前的溢出。真实协议若本来就允许 64 位价格和数量，则还要在乘法前做范围检查，不能假设更大的整数永远够用。

### 1.1 表达式、语句和代码块

这三个词会反复出现：

- **表达式（expression）**会计算出一个值。例如 `price_ticks * quantity` 得到一个整数，`quantity > 0` 得到真或假；
- **语句（statement）**要求程序完成一件事。例如声明变量、给变量赋值或输出一行；
- **代码块（block）**是由 `{` 和 `}` 围起来的一组语句。函数、分支和循环都可以拥有代码块。

可以把表达式想成“算出答案”，把语句想成“执行命令”。一个表达式也能成为语句的一部分：

```cpp,ignore
// 这些是局部语法片段，不是独立程序。
price_ticks * quantity                 // 表达式：算出一个值
const auto total{price_ticks * quantity}; // 声明语句：创建并初始化 total
std::cout << total << '\n';            // 输出语句
```

C++ 大多不在意普通换行。下面的两种写法对编译器表达的是同一件事：

```cpp,ignore
// 两段都是局部语法片段。
const int quantity{300};

const int
quantity
{
    300
};
```

但人非常在意排版。稳定的缩进能让大括号的范围一眼可见，本书采用第一种写法。

### 1.2 分号放在哪里

一个实用的入门规则是：

- 普通变量声明、赋值、函数调用后写 `;`；
- 函数、`if` 和循环的代码块 `}` 后通常不写 `;`；
- `struct`、`class` 和 `enum class` 的完整定义以 `};` 结束。

最后一条看起来例外，是因为整个类型定义本身是一条声明。后文看到实例时会更自然。

### 1.3 注释只写给人看

`//` 后直到本行末尾是单行注释。`/* ... */` 是多行注释。注释不会成为程序执行的操作：

```cpp
#include <iostream>

int main() {
    // 这一行说明接下来的数字是教学用订单数量。
    const int quantity{300};

    /* 多行注释可以跨行，
       但普通说明通常用多个 // 更易读。 */
    std::cout << quantity << '\n';
}
```

## 2. 声明、初始化和赋值不是同一件事

变量可以先用一个简单直觉理解：**变量是程序给某个值起的名字，类型规定这个名字能表示哪一类数据**。

```cpp
#include <cstdint>
#include <iostream>

int main() {
    std::int64_t quantity{100}; // 声明 quantity，并用 100 初始化
    quantity = 120;             // 把已经存在的 quantity 改为 120

    const std::int64_t price_ticks{10'025};
    const bool has_positive_quantity{quantity > 0};

    std::cout << price_ticks << ' '
              << quantity << ' '
              << std::boolalpha << has_positive_quantity << '\n';
}
```

逐个区分：

- **声明（declaration）**告诉编译器一个名字及其类型，例如 `std::int64_t quantity`；
- **初始化（initialization）**在变量刚出现时给它初始值，例如 `{100}`；
- **赋值（assignment）**修改已经存在的变量，例如 `quantity = 120;`。

`=` 在声明中经常表示初始化，在变量已经存在时表示赋值。虽然两者长得一样，发生的时机不同：

```cpp,ignore
// 局部语法片段。
int quantity = 100; // 声明 + 初始化
quantity = 120;     // 赋值
```

本书的简单标量示例常用花括号初始化：`int quantity{100};`。它能阻止一部分悄悄丢失信息的转换。例如下面的代码无法通过编译，因为 `100.5` 不是一个完整整数：

```cpp,ignore
// 故意错误：花括号初始化不接受这种窄化转换。
int quantity{100.5};
```

### 2.1 不要让局部数字处于未知状态

下面的写法声明了一个局部整数，却没有给初始值：

```cpp,ignore
// 故意展示坏例子：不要读取没有初始化的普通局部整数。
int quantity;
std::cout << quantity << '\n';
```

读取这种未初始化的值不是“默认得到 0”。程序可能出现不可预测结果。最简单的习惯是：**声明变量时就给出有业务意义的初始值**。如果暂时没有有效值，后续可以学习 `std::optional` 来明确表达“目前没有”。

### 2.2 `=` 和 `==` 不要混淆

- `quantity = 100`：把 `100` 赋给 `quantity`；
- `quantity == 100`：比较两边是否相等，结果是 `true` 或 `false`。

把赋值写进条件通常很可疑：

```cpp,ignore
// 故意展示易错写法。它是赋值，不是相等比较。
if (quantity = 100) {
    // quantity 被改成 100，而 100 又会被当成“真”。
}
```

编译时开启警告能帮助发现一部分这类问题，但理解两个运算符的含义更重要。

## 3. 最常用的数据类型

类型不只是“占几个字节”。它还在说明一份数据可以表示什么、允许进行哪些操作。入门阶段先认识下面几类：

| 类型 | 适合表达 | 示例 |
|---|---|---|
| `int` | 一般用途的整数 | 重试次数、很小的教学计数 |
| `std::int32_t` | 明确为 32 位的有符号整数 | 协议字段、数量（按协议选择） |
| `std::int64_t` | 明确为 64 位的有符号整数 | 价格刻度、订单编号、累计数量 |
| `std::uint32_t` | 明确为 32 位的无符号整数 | 协议明确规定的非负位字段 |
| `float` / `double` | 近似表示带小数的数 | 统计值、展示值，是否适用取决于业务 |
| `bool` | 真或假 | 是否通过风控 |
| `char` | 一个字符编码单元 | 教学消息类型 `'Q'` |
| `std::string` | 自己拥有的一串字符 | 合约名称 `"BTC-CNY"` |

`std::int64_t` 等类型来自 `<cstdint>`。常见平台都提供这些固定宽度整数；真实协议实现还要同时确认字段范围、符号和字节序。

### 3.1 整数、浮点数、布尔值、字符与字符串

下面的程序把几种类型放在同一处，便于观察：

```cpp
#include <cstdint>
#include <iostream>
#include <string>

int main() {
    const std::int64_t price_ticks{10'025};
    const std::int32_t quantity{300};
    const double reference_price{100.25};
    const bool risk_passed{true};
    const char message_type{'Q'};
    const std::string symbol{"BTC-CNY"};

    std::cout << symbol << ' ' << message_type << '\n';
    std::cout << "price ticks: " << price_ticks << '\n';
    std::cout << "quantity: " << quantity << '\n';
    std::cout << "reference price: " << reference_price << '\n';
    std::cout << "risk passed: "
              << std::boolalpha << risk_passed << '\n';
}
```

注意两种引号：

- 单引号 `'Q'` 表示一个 `char`；
- 双引号 `"BTC-CNY"` 表示一串字符，可以用来初始化 `std::string`。

`true` 和 `false` 是两个布尔值。`std::boolalpha` 让输出显示为单词 `true` 或 `false`，而不是数字 `1` 或 `0`。

`double` 通常使用二进制浮点格式，它不能精确表示所有十进制小数。不能因为屏幕打印了 `100.25`，就假设所有十进制价格都能被精确保存。

### 3.2 为什么教学报价使用整数价格

如果某市场规定最小价格变动单位是 0.01 元，那么：

\[
100.25\ \text{元} = 10\,025\ \text{个价格刻度}
\]

于是可以把 `100.25` 元保存成整数 `10'025`。这种表示有三个好处：

- 相等比较更直接；
- 加减时不会引入常见的二进制小数误差；
- 数据范围和溢出边界更容易明确。

```cpp
#include <cstdint>
#include <iostream>

int main() {
    const std::int64_t bid_ticks{10'025};
    const std::int64_t ask_ticks{10'027};
    const std::int64_t spread_ticks{ask_ticks - bid_ticks};

    std::cout << "spread: " << spread_ticks << " ticks\n";
}
```

这不表示可以随手把任意小数乘以 100 再强制转成整数。真实系统应按照交易场所协议解析价格，并检查比例、舍入规则和范围。整数也不是无限大；超出类型范围仍会出错。

### 3.3 有符号和无符号：不要只看“不能为负”

`std::uint32_t` 的 `u` 表示 unsigned，即无符号。它不能表示负数，却会在减到 0 以下时回绕到一个很大的数。下面是危险直觉的局部示意：

```cpp,ignore
// 易错片段：如果 quantity 为 0，减 1 不会得到 -1。
std::uint32_t quantity{0};
quantity = quantity - 1;
```

因此，“业务上数量非负”并不自动意味着无符号类型一定更安全。有些系统使用有符号整数，再显式检查 `quantity > 0`；如果网络协议明确规定无符号字段，则按协议解析并在边界处校验。关键是先写清数据范围，再选类型。

## 4. `const` 和 `auto`

### 4.1 `const`：这个名字不能再拿来修改值

如果变量初始化后不应改变，可以在类型前写 `const`：

```cpp,ignore
// 局部语法片段。
const int max_order_quantity{1'000};
// max_order_quantity = 2'000; // 打开这一行会编译失败。
```

默认使用 `const` 能让读者更快看出哪些值会变化。它也是编译器可以检查的一条约束。不过 `const` 的完整含义会在指针与引用章节继续展开；本章先把它理解为“不能通过这个名字重新赋值”。

### 4.2 `auto` 是静态类型推导，不是动态类型

`auto` 让编译器根据初始化表达式推导类型：

```cpp
#include <iostream>
#include <string>

int main() {
    auto retry_count = 0;                    // 推导为 int
    const auto symbol = std::string{"BTC-CNY"}; // 推导为 std::string
    const auto risk_passed = true;           // 推导为 bool

    retry_count = 1; // 可以，1 仍然是 int

    std::cout << symbol << ' '
              << retry_count << ' '
              << std::boolalpha << risk_passed << '\n';
}
```

编译器在编译程序时就确定了每个 `auto` 的类型。运行到一半时，变量不会突然变成另一种类型：

```cpp,ignore
// 故意错误：retry_count 已经被推导为 int。
auto retry_count = 0;
retry_count = std::string{"one"};
```

`auto` 也不会替你决定正确的业务宽度。`auto price_ticks = 10'025;` 通常会推导成 `int`，但价格协议也许需要 64 位范围。因此：

- 类型从右边一眼就能看出时，`auto` 可以减少重复；
- 协议字段、需要固定宽度的数据和重要业务边界，显式写出 `std::int64_t` 等类型通常更清楚。

## 5. 函数：给一段计算起名字

函数把可重复的步骤装进一个有名字的代码块。下面把数量检查和名义刻度计算分别写成函数：

```cpp
#include <cstdint>
#include <iostream>

bool is_valid_quantity(std::int32_t quantity) {
    return quantity > 0;
}

std::int64_t notional_ticks(std::int32_t price_ticks,
                            std::int32_t quantity) {
    return std::int64_t{price_ticks} * std::int64_t{quantity};
}

int main() {
    const std::int32_t price_ticks{10'025};
    const std::int32_t quantity{300};

    std::cout << "valid quantity: "
              << std::boolalpha << is_valid_quantity(quantity) << '\n';
    std::cout << "notional ticks: "
              << notional_ticks(price_ticks, quantity) << '\n';
}
```

以第一个函数为例：

```text
bool is_valid_quantity(std::int32_t quantity)
^^^^ ^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^
返回类型     函数名              参数
```

- **返回类型**说明函数最后交回什么类型的值；
- **函数名**描述这段计算的含义；
- 圆括号中的**参数（parameter）**是函数内部使用的输入名字；
- `return` 结束这次调用，并把值交回调用位置；
- `is_valid_quantity(quantity)` 中传入的 `quantity` 是**实参（argument）**。

本例按值传递两个小整数，也就是函数获得各自的值。较大对象如何避免不必要复制，会在指针、引用以及复制与移动章节解释。

`notional_ticks` 把输入限制为 32 位，并在乘法前把两边分别扩大到 64 位。把返回类型写成 `std::int64_t` 本身还不够：运算使用什么宽度取决于乘号两边的类型，而不是最后接收结果的类型。这条规则也适用于加法。

若函数只完成操作、不返回业务值，可以把返回类型写成 `void`：

```cpp,ignore
// 局部函数片段，省略了头文件和 main。
void print_rejection() {
    std::cout << "order rejected\n";
}
```

`main` 的返回类型是 `int`。执行到 `main` 的结尾等价于成功返回 `0`，所以本书的简单程序经常省略显式的 `return 0;`。

## 6. 用 `if` 和 `else` 作决定

`if` 根据条件选择是否执行一个代码块；`else` 处理其余情况：

```cpp
#include <cstdint>
#include <iostream>

int main() {
    const std::int32_t current_position{900};
    const std::int32_t buy_quantity{150};
    const std::int64_t position_limit{1'000};
    const std::int64_t projected_position{
        std::int64_t{current_position} + std::int64_t{buy_quantity}
    };

    if (buy_quantity <= 0) {
        std::cout << "reject: quantity must be positive\n";
    } else if (projected_position > position_limit) {
        std::cout << "reject: position limit\n";
    } else {
        std::cout << "accept\n";
    }
}
```

这里同样先把两个 32 位输入扩大成 64 位，再做加法。不要写成 `std::int64_t{current_position + buy_quantity}` 并期待它更安全：圆括号内部的加法会先按 32 位完成，外层转换发生得太晚。真实风控还要验证输入来源、买卖方向和 64 位边界；本例只演示计算宽度的顺序。

圆括号中的表达式必须能作为真或假判断。常见比较运算符如下：

| 运算符 | 含义 |
|---|---|
| `==` | 等于 |
| `!=` | 不等于 |
| `<` / `<=` | 小于 / 小于等于 |
| `>` / `>=` | 大于 / 大于等于 |
| `&&` | 两个条件都为真 |
| `\|\|` | 至少一个条件为真 |
| `!` | 把真和假反过来 |

即使分支里只有一条语句，也建议保留大括号。这样以后新增语句时，不容易让代码意外跑到条件外面。

不要在 `if` 的圆括号后面多写分号：

```cpp,ignore
// 易错片段：分号形成了空语句，后面的代码块不再受 if 控制。
if (projected_position <= position_limit); {
    send_order();
}
```

## 7. 用 `for` 重复处理

### 7.1 传统 `for`：明确控制次数

传统 `for` 的圆括号里有三段：初始化、继续条件和每轮后的更新。

```cpp
#include <iostream>

int main() {
    for (int message_index{0}; message_index < 3; ++message_index) {
        std::cout << "process message " << message_index << '\n';
    }
}
```

执行顺序是：

1. `int message_index{0}` 只执行一次；
2. 检查 `message_index < 3`；
3. 条件为真时执行代码块；
4. `++message_index` 把索引加一；
5. 回到第 2 步。

因此输出索引为 `0`、`1`、`2`，不会输出 `3`。从 0 开始计数在 C++ 中很常见。

### 7.2 范围 `for`：依次查看每个元素

如果只想依次处理一组值，不需要自己维护下标，可以使用范围 `for`：

```cpp
#include <cstdint>
#include <iostream>

int main() {
    const std::int32_t quantities[]{100, 200, 300};
    std::int64_t total_quantity{0};

    for (const std::int32_t quantity : quantities) {
        total_quantity = total_quantity + quantity;
        std::cout << "seen: " << quantity << '\n';
    }

    std::cout << "total: " << total_quantity << '\n';
}
```

`quantities` 是一个长度由初始值数量推导出来的固定数组。每轮循环都会取出下一个整数，放进本轮的局部变量 `quantity`。后续 STL 章节会介绍 `std::array`、`std::vector` 和更完整的遍历成本。

当某个条件满足时，`break` 可以结束整个循环，`continue` 可以跳过本轮余下语句。初学时不要急着把分支、`break` 和 `continue` 叠很多层；先让控制流程能从上到下读清楚。

### 7.3 lambda：在使用位置写一个小函数

有时一段操作很短，只会在附近使用，专门给它起一个全局函数名反而把阅读位置拉远。C++ 可以用 **lambda（匿名函数）**把小函数直接写在使用处：

```cpp
#include <cstdint>
#include <iostream>

int main() {
    const auto is_positive = [](std::int64_t quantity) {
        return quantity > 0;
    };

    const std::int64_t max_price_ticks{10'025};
    std::int64_t accepted_count{0};

    const auto record_if_cheap =
        [&accepted_count, max_price_ticks](std::int64_t price_ticks) {
            if (price_ticks <= max_price_ticks) {
                accepted_count = accepted_count + 1;
            }
        };

    record_if_cheap(10'024);
    record_if_cheap(10'030);

    const auto print_summary = [&]() {
        std::cout << "positive quantity: "
                  << std::boolalpha << is_positive(300) << '\n';
        std::cout << "accepted: " << accepted_count << '\n';
    };

    print_summary();
}
```

先按外形读：

```text
[捕获列表](参数列表) { 函数体 }
```

- `[]` 是空捕获列表，表示 lambda 不直接使用所在函数的局部变量；
- `[&accepted_count, max_price_ticks]` 表示按引用使用外层的 `accepted_count`，按值保存一份 `max_price_ticks`；因此它能修改原来的计数，而价格上限是创建 lambda 时保存的值；
- `[&]` 表示把函数体实际用到的外层局部变量默认按引用捕获；
- `record_if_cheap(10'024)` 和普通函数调用一样，圆括号里传入实参；
- lambda 表达式会产生一个具体对象，所以这里用 `const auto` 给它起局部名字。

`[&name]` 中的 `&` 可以暂时理解为“不要另存一份，直接使用外面的那个变量”。引用的完整规则会在后续章节解释。能精确列出名字时，`[&accepted_count]` 往往比宽泛的 `[&]` 更容易审查；这里同时展示 `[&]`，是因为后续的算法和线程代码中经常能看到它。

引用捕获不会自动延长外层变量的存在时间，也不会让多线程读写自动安全。如果 lambda 被保存到外层变量已经消失之后，或交给另一个线程并同时修改共享数据，仍可能出错。并发章节会专门解释生命周期、`std::thread` 和同步；本节只要求你会辨认捕获列表并调用 lambda。

## 8. `enum class`：给有限选项起名字

订单方向只有少数合法选项。若用 `1` 表示买、`2` 表示卖，读者必须记住神秘数字；传入 `3` 时也不够直观。`enum class` 可以定义一组有限且带名字的值：

```cpp
#include <iostream>
#include <string>

enum class Side {
    buy,
    sell
};

std::string side_name(Side side) {
    if (side == Side::buy) {
        return "buy";
    }
    return "sell";
}

int main() {
    const Side order_side{Side::buy};
    std::cout << side_name(order_side) << '\n';
}
```

这里的类型名是 `Side`，合法值是 `Side::buy` 和 `Side::sell`。`::` 可以先读作“到这个名字所属的区域中查找”：

- `Side::buy`：到 `Side` 的范围中找 `buy`；
- `std::cout`：到标准库的 `std` 命名空间中找 `cout`。

`enum class` 不会随意把方向当成整数参与计算，这比用裸数字表达业务状态更安全。它的定义仍然以 `};` 结束。

## 9. `struct`：把相关字段组成一条记录

报价不只是价格，还可能包含合约、方向和数量。若把它们作为四个互不相关的变量传来传去，很容易调换顺序。`struct` 可以把相关数据组成一个新类型：

```cpp
#include <cstdint>
#include <iostream>
#include <string>

enum class Side {
    buy,
    sell
};

struct Quote {
    std::string symbol;
    Side side;
    std::int64_t price_ticks;
    std::int64_t quantity;
};

int main() {
    const Quote best_bid{"BTC-CNY", Side::buy, 10'025, 300};

    std::cout << best_bid.symbol << ' '
              << best_bid.price_ticks << ' '
              << best_bid.quantity << '\n';
}
```

`Quote` 是我们定义的新类型，里面四个名字叫**数据成员（data member）**。创建 `best_bid` 时，花括号里的值依照成员声明顺序初始化。通过点号访问成员，例如 `best_bid.price_ticks`。

这样的 `struct` 适合表示一条结构简单、字段可以直接查看的记录。它不是“没有类型的字典”：字段名称和类型在编译时已经固定，不能运行到一半再随意添加字段。

字段顺序写错有时仍能编译。例如两个字段恰好都是 `std::int64_t` 时，把价格和数量颠倒，类型系统未必能发现。因此应使用清楚的变量名、构造函数或更强的业务类型，并为边界值写测试。

### 9.1 `struct` 也能有成员函数

成员函数是“属于这个类型的函数”，可以直接读取同一个对象的成员：

```cpp
#include <cstdint>
#include <iostream>

struct Quote {
    std::int64_t price_ticks;
    std::int64_t quantity;

    bool is_valid() const {
        return price_ticks > 0 && quantity > 0;
    }
};

int main() {
    const Quote quote{10'025, 300};
    std::cout << std::boolalpha << quote.is_valid() << '\n';
}
```

`quote.is_valid()` 表示调用 `quote` 的成员函数。函数圆括号后的 `const` 表示它承诺不通过当前对象修改普通数据成员。更完整的 `const` 规则会在后续章节展开；现在可以把它理解成“只检查，不改报价”。

## 10. `class`、`public`、`private` 与构造函数

有些类型不希望调用者随意改内部字段。例如订单编号应为正数、数量应大于 0。`class` 可以把对外操作和内部表示分开：

```cpp
#include <cstdint>
#include <iostream>

enum class Side {
    buy,
    sell
};

class Order {
public:
    Order(std::int64_t order_id,
          Side side,
          std::int32_t price_ticks,
          std::int32_t quantity)
        : order_id_{order_id},
          side_{side},
          price_ticks_{price_ticks},
          quantity_{quantity} {
    }

    bool is_valid() const {
        return order_id_ > 0 && price_ticks_ > 0 && quantity_ > 0;
    }

    bool is_buy() const {
        return side_ == Side::buy;
    }

    std::int64_t notional_ticks() const {
        return std::int64_t{price_ticks_} * std::int64_t{quantity_};
    }

private:
    std::int64_t order_id_;
    Side side_;
    std::int32_t price_ticks_;
    std::int32_t quantity_;
};

int main() {
    const Order order{42, Side::buy, 10'025, 300};

    std::cout << "valid: " << std::boolalpha << order.is_valid() << '\n';
    std::cout << "buy: " << order.is_buy() << '\n';
    std::cout << "notional ticks: " << order.notional_ticks() << '\n';
}
```

先看访问范围：

- `public:` 后的名字可以由调用者使用；
- `private:` 后的名字只能由这个类自己的成员函数等受许可代码直接访问；
- 因此 `order.notional_ticks()` 可以调用，`order.quantity_` 不能在 `main` 中直接读取。

`Order(...)` 是**构造函数（constructor）**。它与类同名，没有返回类型，在创建 `Order` 时运行。构造函数后的冒号开始**成员初始化列表**：

```cpp,ignore
// 构造函数局部片段。
Order(std::int64_t order_id, std::int64_t quantity)
    : order_id_{order_id}, quantity_{quantity} {
}
```

`order_id_{order_id}` 的左边是数据成员，花括号里是参数。末尾下划线只是本书采用的命名习惯，用来区分私有成员和参数，不是 C++ 的特殊语法。

`struct` 和 `class` 都能拥有数据成员、成员函数和构造函数。两者最重要的语言差别之一是默认访问权限：

- `struct` 默认是 `public`；
- `class` 默认是 `private`。

实践中常用 `struct` 表达简单记录，用 `class` 隐藏表示并维护规则，但这是一种项目约定，不是语言强制。

上面的教学类允许构造出无效订单，再用 `is_valid()` 检查。生产接口还必须决定：无效输入是在构造前拒绝、返回错误，还是使用一个保证始终有效的订单类型。仅仅把字段放进 `private` 并不会自动建立正确业务规则。

`notional_ticks()` 延续前面的范围约定：成员输入是 32 位，先分别扩大成 64 位再乘。若类需要保存 64 位价格或数量，就不能照搬这个证明；应先检查乘法是否超出目标类型，或选用经过验证的更宽表示。

## 11. 命名空间：给名字分组

大型项目里可能有多个叫 `Quote` 的类型，例如行情报价和风控快照。命名空间可以给相关名字划定区域，减少冲突：

```cpp
#include <cstdint>
#include <iostream>

namespace market_data {

struct Quote {
    std::int64_t price_ticks;
    std::int64_t quantity;
};

bool is_valid(Quote quote) {
    return quote.price_ticks > 0 && quote.quantity > 0;
}

} // namespace market_data

int main() {
    const market_data::Quote quote{10'025, 300};
    std::cout << std::boolalpha
              << market_data::is_valid(quote) << '\n';
}
```

`market_data::Quote` 表示命名空间 `market_data` 里的 `Quote`。标准库的 `std::string`、`std::cout` 也是同样的查找直觉。

初学阶段建议保留完整前缀，不要在头文件或大范围内写 `using namespace std;`。完整名字稍长，却能清楚说明名称来自哪里，也能减少同名冲突。

## 12. 头文件：先看到“有什么”，再寻找“怎样做”

当程序变大时，不会把所有代码都塞进一个 `.cpp`。常见做法是：

- `.hpp` 或 `.h` 头文件放其他代码需要看到的类型和函数声明；
- `.cpp` 源文件放普通函数的具体实现；
- 使用者通过 `#include` 让当前源文件看到所需声明。

可以把头文件理解成餐厅菜单：它告诉别人“有什么、需要什么输入、会返回什么”，但不必写出厨房的每一步。下面展示三个文件的最小外形，因此标记为不能单独运行的片段：

```cpp,ignore
// quote.hpp：对外可见的声明
#pragma once
#include <cstdint>

namespace market_data {

struct Quote {
    std::int64_t price_ticks;
    std::int64_t quantity;
};

bool is_valid(Quote quote); // 只有声明，以分号结束

} // namespace market_data

// quote.cpp：函数定义
#include "quote.hpp"

bool market_data::is_valid(Quote quote) {
    return quote.price_ticks > 0 && quote.quantity > 0;
}

// main.cpp：使用接口
#include "quote.hpp"
#include <iostream>

int main() {
    const market_data::Quote quote{10'025, 300};
    std::cout << market_data::is_valid(quote) << '\n';
}
```

`bool is_valid(Quote quote);` 只有函数长什么样，没有函数体，叫**声明**。带 `{ ... }` 的版本写出了具体操作，叫**定义**。`#pragma once` 告诉常见编译器同一个头文件在一次处理过程中只纳入一次；跨平台项目也可能使用宏形式的 include guard。

`#include` 可以先理解为“让当前源文件看到另一份文本中的声明”，不是程序运行后再加载一个模块。为什么声明能放在头文件、定义怎样在最后组合起来，会在下一章专门解释。

## 13. 把语法合起来：从报价到订单判断

下面的完整程序只使用本章已经介绍的工具。它依次处理几条简化报价，跳过无效数据，并在买价满足条件时创建订单：

```cpp
#include <cstdint>
#include <iostream>
#include <string>

enum class Side {
    buy,
    sell
};

struct Quote {
    std::string symbol;
    Side side;
    std::int64_t price_ticks;
    std::int64_t quantity;

    bool is_valid() const {
        return price_ticks > 0 && quantity > 0;
    }
};

struct Order {
    std::string symbol;
    Side side;
    std::int64_t price_ticks;
    std::int64_t quantity;
};

bool should_buy(Quote quote, std::int64_t max_price_ticks) {
    return quote.is_valid()
        && quote.side == Side::sell
        && quote.price_ticks <= max_price_ticks;
}

int main() {
    const Quote quotes[]{
        {"BTC-CNY", Side::sell, 10'030, 200},
        {"BTC-CNY", Side::sell, 10'024, 0},
        {"BTC-CNY", Side::sell, 10'025, 300}
    };
    const std::int64_t max_price_ticks{10'025};

    for (const Quote quote : quotes) {
        if (!should_buy(quote, max_price_ticks)) {
            std::cout << "skip quote\n";
            continue;
        }

        const Order order{
            quote.symbol,
            Side::buy,
            quote.price_ticks,
            100
        };
        std::cout << "create order: "
                  << order.symbol << ' '
                  << order.price_ticks << ' '
                  << order.quantity << '\n';
    }
}
```

这只是语法教学，不是一套真实策略：

- 没有行情时序、订单簿、手续费和成交概率；
- 没有账户状态、持仓上限和订单状态机；
- `price_ticks * quantity` 等计算还需要范围检查；
- 按值传递 `Quote` 和循环变量会复制数据，后续会学习怎样安全地只读访问原对象；
- 真实系统不能根据这样一个条件直接发单。

它的作用是展示一条清楚的数据流：先用类型表示输入，再用函数命名判断，用分支处理结果，最后构造输出。低延迟优化也要建立在正确且可读的数据流之上。

## 14. Rust 心智模型对照（没学过可跳过）

本节只是给已经读过 Rust 部分的读者搭桥。如果你没有 Rust 基础，直接跳到下一节，不会影响后文。

| 想表达的事 | Rust | C++ | 提醒 |
|---|---|---|---|
| 默认不修改的局部值 | `let x = 1;` | `const int x{1};` | C++ 局部变量不写 `const` 时默认可修改 |
| 可修改的局部值 | `let mut x = 1;` | `int x{1};` | 两边都应先初始化 |
| 类型推导 | `let x = 1;` | `auto x = 1;` | `auto` 仍是编译期确定的静态类型 |
| 记录类型 | `struct Quote { ... }` | `struct Quote { ... };` | C++ 类型定义结尾有分号 |
| 方法 | `impl Quote { fn ... }` | 直接写在 `struct` / `class` 中 | C++ 成员函数后的 `const` 表示只读当前对象 |
| 有限选项 | `enum Side { Buy, Sell }` | `enum class Side { buy, sell };` | C++ 使用 `Side::buy` 访问枚举值 |
| 模块式分组直觉 | `mod market_data` | `namespace market_data` | 构建与可见性机制并不完全等价 |
| 只读参数 | 常见 `&Quote` | 本章暂用按值传递 | C++ 的 `const Quote&` 将在下一批基础章节解释 |

最需要避免的误解是：C++ 的 `const` 不等于 Rust 的完整借用规则，`auto` 也不等于动态类型。这里只做语法导航，不把两种语言说成一一等价。

## 15. 常见坑

- **漏写分号**：普通声明或调用后没有 `;`，错误有时会指向下一行；
- **多写分号**：`if (condition);` 会产生一个空语句，让后面的代码块不受条件控制；
- **把 `=` 当成 `==`**：前者赋值，后者比较；
- **读取未初始化数字**：普通局部整数不会自动得到可靠的 0；
- **认为 `auto` 会动态变类型**：类型在编译时已经确定；
- **用浮点数直接承担所有价格语义**：十进制报价、舍入和协议范围需要明确设计；
- **认为无符号数不会出错**：从 0 再减会回绕，边界检查仍然必要；
- **混淆 `char` 和字符串**：`'Q'` 是单个字符，`"Q"` 是字符序列；
- **省略分支大括号**：修改代码时容易让缩进和真实控制范围不一致；
- **弄错 `struct` 初始化顺序**：花括号值按成员声明顺序对应；
- **以为 `private` 自动保证业务正确**：它限制直接访问，但构造函数和公开方法仍要维护规则；
- **在头文件写 `using namespace std;`**：会把大量名字带给所有包含者，增加冲突；
- **把整数当成无限大**：订单编号、价格、数量和乘积都必须考虑允许范围。

## 16. 面试追问与参考答法

### Q1：声明、初始化和赋值有什么区别？

**参考答法**：声明引入名字和类型；初始化在对象刚建立时给它初始值；赋值修改已经存在的对象。例如 `int quantity{100};` 同时声明并初始化，后面的 `quantity = 120;` 是赋值。

### Q2：`auto` 是动态类型吗？

**参考答法**：不是。编译器根据初始化表达式在编译期推导出一个具体静态类型，变量运行时不能随意换成另一种类型。协议宽度有明确要求时仍应显式写类型。

### Q3：为什么价格常用整数刻度表示？

**参考答法**：把价格换成协议规定的最小单位后，相等比较和加减更直接，能避免常见二进制浮点小数误差。但仍要检查转换规则、整数范围和乘法溢出。

### Q4：`struct` 和 `class` 有什么区别？

**参考答法**：两者都能有字段、成员函数和构造函数。一个关键语言差别是默认访问权限：`struct` 默认 `public`，`class` 默认 `private`。项目常用前者表示简单记录、后者隐藏实现，但这是约定，不是强制。

### Q5：为什么订单方向更适合 `enum class` 而不是整数？

**参考答法**：`Side::buy` 和 `Side::sell` 直接表达含义，合法取值集中在类型中，而且不会轻易和普通整数混用。它能减少神秘数字和参数传错，但输入解析时仍要处理未知值。

### Q6：成员函数末尾的 `const` 表示什么？

**参考答法**：它表示该成员函数承诺不通过当前对象修改普通数据成员，因此可以在 `const` 对象上调用。它不自动等于线程安全，完整规则还涉及可变成员和别名。

### Q7：头文件中的函数声明有什么作用？

**参考答法**：声明告诉使用者函数名、参数和返回类型，使当前源文件能检查调用是否匹配；函数定义再提供具体操作。多个源文件如何组合由编译和链接过程完成。

### Q8：为什么 `if` 和循环建议总写大括号？

**参考答法**：即使目前只有一条语句，大括号也明确标出控制范围。以后添加日志或检查时，不容易出现缩进看似属于分支、实际上已经落到分支外的错误。

## 17. 练习与参考答案

### 练习 1：读代码

下面程序会输出什么？哪一行是初始化，哪一行是赋值？

```cpp,ignore
// 推演片段。
int quantity{100};
quantity = quantity + 50;
std::cout << (quantity == 150) << '\n';
```

<details>
<summary>参考答案</summary>

`int quantity{100};` 同时声明并初始化变量。第二行先计算 `100 + 50`，再把 `150` 赋给已经存在的 `quantity`。最后的比较结果为真；没有设置 `std::boolalpha` 时，标准输出通常显示 `1`。

</details>

### 练习 2：修复条件

下面代码本来想在数量为 0 时拒绝订单，有哪两个问题？

```cpp,ignore
// 故意错误。
if (quantity = 0); {
    std::cout << "reject\n";
}
```

<details>
<summary>参考答案</summary>

条件中应该使用比较 `quantity == 0`，而不是赋值 `quantity = 0`；圆括号后不应有分号。可以改成：

```cpp,ignore
if (quantity == 0) {
    std::cout << "reject\n";
}
```

</details>

### 练习 3：选择类型

以下数据分别优先考虑什么类型：订单方向、协议规定的 64 位价格刻度、是否通过风控、合约名称？

<details>
<summary>参考答案</summary>

订单方向可定义 `enum class Side`；明确的 64 位价格刻度可用 `std::int64_t`；是否通过风控用 `bool`；自己拥有的合约名称可先用 `std::string`。真实系统还要依据协议范围和所有权要求调整。

</details>

### 练习 4：写一个函数

编写 `is_valid_quote`，当价格和数量都大于 0 时返回 `true`。

<details>
<summary>参考答案</summary>

```cpp,ignore
bool is_valid_quote(std::int64_t price_ticks,
                    std::int64_t quantity) {
    return price_ticks > 0 && quantity > 0;
}
```

这是局部答案；放入完整程序时还要包含 `<cstdint>`，并在 `main` 中调用和验证边界值。

</details>

### 练习 5：建立报价记录

定义一个 `Quote`，包含 `symbol`、`side`、`price_ticks` 和 `quantity`，再创建一条卖方报价。

<details>
<summary>参考答案</summary>

```cpp,ignore
enum class Side { buy, sell };

struct Quote {
    std::string symbol;
    Side side;
    std::int64_t price_ticks;
    std::int64_t quantity;
};

const Quote best_ask{"BTC-CNY", Side::sell, 10'027, 200};
```

在完整程序中需要包含 `<cstdint>` 和 `<string>`。四个初始值按成员声明顺序对应。

</details>

### 练习 6：解释封装

为什么把 `Order::quantity_` 放在 `private` 后，仍然不能断言每个 `Order` 都有效？

<details>
<summary>参考答案</summary>

`private` 只阻止外部代码直接访问字段。构造函数仍可能接受 0 或负数量，公开成员函数也可能破坏规则。类必须在所有创建和修改入口检查不变量，调用者还要按接口约定处理错误。

</details>

### 练习 7：比较两种循环

只想依次打印固定数组里的每个数量，需要元素下标吗？应该先选择传统 `for` 还是范围 `for`？

<details>
<summary>参考答案</summary>

不需要下标时，范围 `for` 通常更直接：

```cpp,ignore
for (const std::int32_t quantity : quantities) {
    std::cout << quantity << '\n';
}
```

如果业务确实需要位置、步长或同时访问相邻元素，再使用下标循环，并认真检查边界。

</details>

## 小结

C++ 的最小阅读顺序是：先认出类型和名字，再看表达式算出什么，最后看语句和大括号决定它何时执行。变量应在声明时初始化；`const` 表达不再修改，`auto` 只做编译期类型推导。函数给计算起名字，`if` 负责选择，`for` 负责重复。

面向 HFT 数据建模时，可以用 `enum class` 表示有限业务状态，用 `struct` 组织简单记录，用 `class` 划分公开接口和内部表示。价格常以协议规定的整数刻度表达，但整数、访问权限和类型名称都不会自动保证业务正确，仍需明确范围与不变量。下一章将解释这些源码怎样被编译、链接并开始运行，以及变量在程序执行时放在哪里、存在多久。

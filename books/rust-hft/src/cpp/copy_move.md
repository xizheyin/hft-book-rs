# 拷贝、移动语义与 Rule of Zero/Five

把一个整数赋给另一个整数，复制几个字节就够了；把一个拥有百万个元素的容器赋给另一个对象，复制全部元素可能很贵。C++ 用“拷贝”和“移动”区分两种意图：**拷贝产生一份独立内容，移动允许新对象接管旧对象的资源**。

## 1. 值语义：两个对象还是两个名字

先区分两个概念：

- `T b = a;` 通常创建新对象 `b`，内容从 `a` 拷贝；
- `T& b = a;` 不创建新的 `T`，`b` 只是 `a` 的引用别名。

```cpp
#include <iostream>
#include <string>

int main() {
    std::string original{"ORDER-42"};
    std::string copy = original;
    std::string& alias = original;

    copy[0] = 'X';
    alias[0] = 'A';

    std::cout << "original: " << original << '\n';
    std::cout << "copy: " << copy << '\n';
}
```

`copy` 有自己的字符串值，修改它不影响 `original`。`alias` 指向同一个对象，修改它就是修改 `original`。

对 `std::string` 而言，具体实现可能使用短字符串优化，小字符串未必动态分配；但语义上 `copy` 仍是独立值。不要从语义直接猜某次机器成本。

## 2. 拷贝到底复制什么

类对象的拷贝通常由**拷贝构造函数**完成：

```cpp,ignore
// 语法片段：展示特殊成员函数签名，不是完整程序。
class Batch {
public:
    Batch(const Batch& other);            // 拷贝构造
    Batch& operator=(const Batch& other); // 拷贝赋值
};
```

- 拷贝构造：用已有对象创建新对象；
- 拷贝赋值：目标对象已经存在，用另一个对象的值替换它。

编译器在条件满足时会自动生成这些操作，并逐个拷贝成员。若成员是 `std::vector`，拷贝通常要为目标准备存储并复制元素；若成员是裸指针，默认拷贝只复制地址，不会自动复制所指对象，也不会自动解决所有权。

### 2.1 浅拷贝为何可能危险

下面是故意展示的错误所有权类：

```cpp,ignore
// 故意错误：默认拷贝只复制 data 地址，两个对象析构时会重复 delete[]。
class BadBuffer {
public:
    explicit BadBuffer(std::size_t size) : data(new char[size]) {}
    ~BadBuffer() { delete[] data; }

private:
    char* data;
};

int main() {
    BadBuffer first{1024};
    BadBuffer second = first; // 浅拷贝地址
}
```

正确的现代设计通常直接使用 `std::vector<std::byte>` 或 `std::unique_ptr<std::byte[]>` 作为成员，让标准类型表达所有权，而不是自己配对 `new[]`/`delete[]`。

## 3. 移动：转交资源，不是瞬间搬运所有字节

许多拥有型标准容器在移动时，可以把内部指针、长度和容量等管理信息转给新对象，而不用复制全部元素。下面的包装类把拷贝和移动打印出来：

```cpp
#include <cstddef>
#include <iostream>
#include <utility>
#include <vector>

class Batch {
public:
    explicit Batch(std::size_t count) : values_(count, 7) {}

    Batch(const Batch& other) : values_(other.values_) {
        std::cout << "copy\n";
    }

    Batch(Batch&& other) noexcept : values_(std::move(other.values_)) {
        std::cout << "move\n";
    }

    [[nodiscard]] std::size_t size() const {
        return values_.size();
    }

private:
    std::vector<int> values_;
};

int main() {
    Batch original{1'000};
    Batch copied = original;
    Batch moved = std::move(original);

    std::cout << copied.size() << ' ' << moved.size() << '\n';
}
```

程序不读取 `original.size()` 来推断其移动后具体值。它仍是一个可以析构、可以重新赋值的合法 `Batch`，但除非类型文档给出更强保证，不应假设它仍有 1,000 个元素，也不应一律假设它为空。

### 3.1 移动不保证永远便宜

移动的成本由类型决定：

- `std::unique_ptr<T>` 移动通常只转移指针；
- 普通固定数组 `std::array<T, N>` 移动要逐元素移动，可能与复制同数量级；
- 使用特殊分配器的容器在某些移动赋值场景可能无法简单接管存储；
- 小字符串可能直接移动内嵌字符；
- 一个自定义类型的移动构造函数可以执行任意合法逻辑。

所以“move 是 O(1)”不是语言普遍保证，必须看具体类型和具体操作。

## 4. 左值、右值和 `std::move`

这些术语用来描述表达式如何被使用。初学阶段可以先这样理解：

- **左值（lvalue）**通常指有身份、之后还可通过名字找到的对象表达式；
- **右值（rvalue）**通常指临时值或允许被取走资源的表达式；
- `T&&` 是右值引用，在重载选择和转发中用于表达这种机会。

```cpp
#include <iostream>
#include <string>
#include <utility>

void inspect(const std::string&) {
    std::cout << "lvalue/readonly path\n";
}

void inspect(std::string&&) {
    std::cout << "rvalue path\n";
}

int main() {
    std::string symbol{"DEMO"};
    inspect(symbol);
    inspect(std::string{"TEMP"});
    inspect(std::move(symbol));
}
```

关键点：`std::move(symbol)` **没有自己搬动任何字符**。它大致是在说：“请把这个表达式当成可以匹配移动接口的右值。”真正是否移动，要看后续选中了哪个构造函数或重载，以及那个函数做了什么。

### 4.1 为什么不能到处加 `std::move`

若把仍需使用的对象过早标成可移动，后续代码只能依赖其移动后保证。对 `const` 对象使用 `std::move` 也常无法调用需要 `T&&` 的普通移动构造，因为移动通常要修改源对象，最终可能退化为复制。

```cpp,ignore
// 局部片段：常见但没有收益的写法。
const std::string symbol{"DEMO"};
std::string another = std::move(symbol); // 通常调用拷贝构造，而非普通移动构造
```

只在所有权确实应转移、源对象之后不再依赖原值时使用 `std::move`。

## 5. 被移动对象处于什么状态

标准库类型通常承诺被移动对象仍然**有效但状态未指定（valid but unspecified）**。这意味着：

- 可以安全析构；
- 可以给它赋新值；
- 可以调用文档允许且不依赖具体旧值的操作；
- 不应猜它一定为空或保留原值，除非该类型明确承诺。

```cpp
#include <iostream>
#include <string>
#include <utility>

int main() {
    std::string source{"MARKET-DATA"};
    std::string destination = std::move(source);

    source = "REUSED";
    std::cout << destination << '\n';
    std::cout << source << '\n';
}
```

重新赋值是让被移动对象恢复明确业务状态的简单办法。

## 6. Rule of Zero：优先让成员替你管理

如果类只组合值类型和标准 RAII 成员，通常不需要声明任何特殊成员函数：

```cpp
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

struct OrderBookSnapshot {
    std::string symbol;
    std::vector<std::int64_t> bid_prices;
    std::vector<std::int64_t> ask_prices;
};

int main() {
    OrderBookSnapshot first{"DEMO", {100, 99}, {101, 102}};
    OrderBookSnapshot second = first;
    std::cout << second.symbol << ' ' << second.bid_prices.size() << '\n';
}
```

编译器组合各成员的析构、复制和移动行为。减少手写特殊成员函数，通常也减少忘记处理某个新成员的风险。

## 7. Rule of Five：确实手管资源时要一起考虑

若类型直接拥有原始资源并自定义析构，通常需要一起审视五个操作：

1. 析构函数；
2. 拷贝构造函数；
3. 拷贝赋值运算符；
4. 移动构造函数；
5. 移动赋值运算符。

这叫 Rule of Five（五法则），不是要求五个都必须实现；可以显式 `= delete` 禁止某些操作。核心是不要只写析构却忘记默认复制的含义。

下面的接口片段展示一个不可复制、可移动的资源类型：

```cpp,ignore
// 声明片段，没有实现和 main，不作为独立程序编译。
class SocketHandle {
public:
    explicit SocketHandle(int descriptor) noexcept;
    ~SocketHandle();

    SocketHandle(const SocketHandle&) = delete;
    SocketHandle& operator=(const SocketHandle&) = delete;

    SocketHandle(SocketHandle&& other) noexcept;
    SocketHandle& operator=(SocketHandle&& other) noexcept;
};
```

实际项目优先复用成熟句柄包装器；手写时还需处理无效句柄值、自移动赋值、关闭失败和平台接口。

### 7.1 `= default` 与 `= delete`

- `= default` 明确请求编译器生成默认行为；
- `= delete` 明确禁止该操作，让误用在编译期失败。

独占资源应禁止复制：

```cpp
#include <iostream>
#include <memory>
#include <utility>

class PacketBuffer {
public:
    explicit PacketBuffer(std::size_t size)
        : data_(std::make_unique<unsigned char[]>(size)), size_(size) {}

    PacketBuffer(const PacketBuffer&) = delete;
    PacketBuffer& operator=(const PacketBuffer&) = delete;
    PacketBuffer(PacketBuffer&&) noexcept = default;
    PacketBuffer& operator=(PacketBuffer&&) noexcept = default;

    [[nodiscard]] std::size_t size() const {
        return size_;
    }

private:
    std::unique_ptr<unsigned char[]> data_;
    std::size_t size_;
};

int main() {
    PacketBuffer first{2048};
    PacketBuffer second = std::move(first);
    std::cout << second.size() << '\n';
}
```

这里默认移动会移动 `unique_ptr`，并复制整数 `size_`。严格来说，被移动的 `first.size()` 仍可能返回旧数字，因为默认移动不会自动把 `size_` 清零；因此业务 API 不应把这个数字解释为仍拥有有效缓冲区。若需要更强不变量，应定制移动操作或重新设计状态表达。

## 8. `noexcept` 为什么会影响容器选择移动

当 `std::vector<T>` 扩容时，需要把已有元素转移到新存储。为了提供异常安全保证，如果 `T` 的移动构造可能抛异常且又可以复制，标准容器可能选择复制而不是移动。

因此一个确实不会抛的移动构造通常应标记 `noexcept`。但不能为了性能虚假承诺：一旦 `noexcept` 函数真的抛出，程序会调用 `std::terminate`。

## 9. 返回值与复制消除

按值返回对象不等于必然先构造临时对象再复制。C++17 起，一些场景保证复制消除；命名返回值优化（NRVO）在常见编译器中也很普遍，但具体条件不同。

```cpp
#include <cstdint>
#include <iostream>
#include <vector>

std::vector<std::int64_t> make_prices() {
    std::vector<std::int64_t> prices;
    prices.reserve(3);
    prices.push_back(100);
    prices.push_back(101);
    prices.push_back(102);
    return prices;
}

int main() {
    const std::vector<std::int64_t> prices = make_prices();
    std::cout << prices.size() << '\n';
}
```

不要写 `return std::move(prices);` 试图“帮助”编译器；它可能阻碍 NRVO。清晰按值返回，让编译器应用语言规则和优化。

## 10. 参数设计与成本

| 需求 | 常见参数形式 | 主要含义 |
|---|---|---|
| 只读且不接管 | `const T&` | 避免复制，调用期间借用 |
| 修改调用者对象 | `T&` | 可变借用 |
| 小型普通值 | `T` | 直接值传递，清晰且常较便宜 |
| 函数要保存自己的副本或接管 | `T` 后移入成员 | 调用者可传左值复制、右值移动 |
| 明确只接收可移动对象 | `T&&` | 更专门的所有权/重载接口 |

“所有类型都传 `const&`”并非最佳规则。整数、指针和小型轻量结构按值传递通常更自然；对复杂 API 还要考虑别名、生命周期、代码体积和 ABI。

## 11. 教学算例：复制批次的量级

假设一个行情批次有 50,000 条记录，每条 32 字节。一次深拷贝至少涉及：

\[
50{,}000 \times 32 = 1{,}600{,}000\ \text{bytes}
\]

约 1.6 MB 数据，还可能需要分配目标存储。若移动一个采用普通兼容分配器的 `std::vector<Record>`，常见实现只需转移少量管理字段，但这不是所有容器和所有配置的普遍保证。

低延迟优化还要问：能否根本不在热路径转移整个批次，而是预分配缓冲、交换槽位所有权或就地处理？移动比复制便宜，不代表频繁改变所有权一定是最佳架构。

## 12. Rust 心智模型对照

| 场景 | Rust | C++ |
|---|---|---|
| 普通赋值 | 非 `Copy` 值通常移动，旧绑定不能再用 | 类型若可复制，左值通常复制 |
| 显式深拷贝 | `Clone::clone` | 拷贝构造/赋值通常由语法隐式选择 |
| 简单位复制 | `Copy` | 平凡可复制类型等概念，但规则不完全相同 |
| 强制提供移动机会 | 所有权语义内建 | `std::move` 转为右值表达式 |
| 移动后源对象 | 通常不能再通过旧绑定使用 | 对象仍存在，通常有效但状态未指定 |
| 独占堆值 | `Box<T>` 不可隐式克隆 | `unique_ptr<T>` 不可复制、可以移动 |

如果带着 Rust 直觉读 C++，最需要改的一点是：C++ 左值赋值可能悄悄做昂贵复制，而被移动对象的名字仍可见。

## 13. 跨组件边界的所有权转移

生产者把请求批次、张量任务或市场消息交给消费者时，常见选择包括：

- 复制批次：简单隔离，但数据量大时成本高；
- 移动拥有容器：避免深拷贝，但生产者失去原资源，需要新缓冲；
- 预分配多个槽位，传递索引/所有权：成本更稳定，但容量耗尽和代际复用要设计；
- 共享引用计数对象：使用方便，但引用计数和跨核缓存行可能进入热路径。

没有一种方案只靠 `std::move` 就完成并发正确性。还必须说明生产者/消费者数量、满队列语义、缓冲区何时可复用和线程同步。

## 14. 面试追问与参考答法

### Q1：`std::move` 是否真的移动对象？

**参考答法**：它主要把表达式转换为可匹配右值引用的形式，本身通常不移动资源。后续是否发生移动取决于重载选择和类型的移动操作实现。

### Q2：被移动对象还能使用吗？

**参考答法**：它仍然存在并会析构；标准库类型通常处于有效但未指定状态，可以重新赋值，但不应假定具体旧值或一定为空，除非文档有更强保证。

### Q3：什么是 Rule of Zero 和 Rule of Five？

**参考答法**：Rule of Zero 是优先用标准 RAII 成员组合所有权，不手写特殊成员函数。若确实直接管理资源并自定义析构，就应一起审视析构、拷贝构造/赋值、移动构造/赋值，这就是 Rule of Five；不支持的操作应删除。

### Q4：为什么移动构造常标记 `noexcept`？

**参考答法**：容器扩容为了异常安全，在移动可能抛且复制可用时可能选择复制。真实不抛的移动标记 `noexcept` 能让容器安全选择移动；虚假标记会在抛异常时终止程序。

## 15. 易错点

- 把引用别名误当成独立拷贝；
- 拥有裸指针的类使用默认浅拷贝，导致重复释放；
- 认为 `std::move` 一执行，源对象立刻自动清空；
- 移动后继续依赖源对象的旧业务值；
- 对 `const` 对象使用 `std::move` 并期待一定移动；
- 在 `return` 中无必要地写 `std::move`，妨碍复制消除；
- 认为所有移动都是常数时间；
- 给可能抛异常的移动操作虚假加 `noexcept`；
- 只实现析构函数，忘记审视复制和移动。

## 做题方法

拷贝移动题为每个对象维护“资源句柄 + 状态”，并统计特殊成员调用：

1. 标出表达式产生的是左值、亡值还是纯右值，由可用重载和语言规则判断调用拷贝还是移动；不要只看是否写了 `std::move`。
2. 每次构造新对象都记录构造来源；每次赋值则先处理目标已有资源，再取得源的值，构造与赋值不能混算。
3. 移动后把源标成“有效但状态未指定”，只能执行类型契约允许的操作；若自定义类型承诺空状态，可在实现中明确并测试。
4. 遇到返回值和临时对象，先应用保证的 copy elision，再统计剩余构造；不能把一次没有出现的移动错误归因于优化器偶然行为。
5. 容器扩容时检查元素移动构造是否 `noexcept`；为保持强异常保证，容器可能在可用时选择拷贝。
6. 最后按生命周期逆序统计析构，构造成功的对象数应与析构数一致，资源取得与释放也应一一配对。

验算可在教学类型中给每个对象唯一 ID 并打印特殊成员，但输出只是观察特定程序；最终解释仍应符合值类别、重载解析和消除规则。

## 16. 练习与参考答案

### 练习 1

`std::vector<int> b = a;` 与 `std::vector<int>& b = a;` 的区别是什么？

<details>
<summary>参考答案</summary>

前者创建独立 `vector` 值，通常复制元素并准备自己的存储；后者只是给 `a` 起引用别名，不复制容器，任何修改都作用于同一个对象。

</details>

### 练习 2

函数接收一个大字符串并永久保存到成员中，希望调用者传左值时复制、传临时值时移动。一个常见接口怎样写？

<details>
<summary>参考答案</summary>

可以按值接收 `std::string value`，再用 `member_(std::move(value))` 移入成员。左值调用先复制到参数，右值调用可移动到参数，再从参数移入成员。是否适合仍取决于调用频率、字符串大小和 API 需求。

</details>

### 练习 3

一个类型移动后承诺“可析构、可赋值”，但没有承诺为空。代码能否用 `if (source.empty())` 判断资源一定已被转移？

<details>
<summary>参考答案</summary>

不能把 `empty()` 的结果当作移动语义的普遍证明。应依赖类型文档明确保证，或让程序逻辑在移动后不读取旧业务状态，并在需要时重新赋值。

</details>

## 小结

拷贝创建独立值，移动给类型一次转移资源的机会；具体成本由类型、分配器和上下文决定。`std::move` 只是表达意图，真正操作由构造或赋值函数完成。现代 C++ 优先遵循 Rule of Zero，用标准成员组合所有权；确实手管资源时再完整审视 Rule of Five，并让被移动状态与异常保证清晰可用。

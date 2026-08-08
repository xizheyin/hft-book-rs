# 构造、析构、RAII 与对象生命周期

程序除了管理内存，还要管理文件、锁、网络句柄、线程和缓冲区。若每条成功、失败、提前返回路径都手写一次释放，很容易漏掉。C++ 的核心办法是 **RAII**：把资源交给对象管理，让对象的生命周期决定资源何时取得和释放。

## 1. RAII 的直觉：资源装进自动关闭的盒子

RAII 全称是 Resource Acquisition Is Initialization，常译为“资源获取即初始化”。这个名字不太直观，可以先记成：

> 创建管理对象时建立资源不变量；管理对象离开生命周期时自动撤销它。

例如一个作用域计时器在构造时记录开始时间，在析构时报告耗时：

```cpp
#include <chrono>
#include <iostream>
#include <string_view>

class ScopeTimer {
public:
    explicit ScopeTimer(std::string_view name)
        : name_(name), start_(std::chrono::steady_clock::now()) {}

    ~ScopeTimer() {
        const auto elapsed = std::chrono::steady_clock::now() - start_;
        const auto nanos =
            std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count();
        std::cout << name_ << ": " << nanos << " ns\n";
    }

private:
    std::string_view name_;
    std::chrono::steady_clock::time_point start_;
};

int main() {
    ScopeTimer timer{"teaching block"};
    volatile int result = 0;
    for (int i = 0; i < 100; ++i) {
        result += i;
    }
    (void)result;
}
```

这里：

- `ScopeTimer(...)` 是构造函数，与类同名，没有返回类型；
- `~ScopeTimer()` 是析构函数，名字前有 `~`；
- 成员初始化列表 `: name_(...), start_(...)` 直接初始化成员；
- `timer` 离开 `main` 作用域时，析构函数自动运行。

`name_` 是不拥有字符的视图。本例传入字符串字面量，它在整个程序期间都有效；若改为运行时字符串，就必须保证字符串活得比计时器久，或让计时器自己保存一份 `std::string`。

这个计时器只适合演示。示例中的 `volatile` 会强制特定访问、改变被测循环，而且它不是可靠的 benchmark “防优化黑盒”，不要照搬到性能实验。真实低延迟测量要处理预热、优化、时钟读取开销、CPU 频率、线程迁移、输入分布和分位数；在每条消息上输出日志也会严重改变被测路径。

## 2. 构造函数建立不变量

**不变量（invariant）**是“对象只要处于可用状态，就必须成立的条件”。一个价格档位可以要求数量非负：

```cpp
#include <cstdint>
#include <iostream>
#include <stdexcept>

class PriceLevel {
public:
    PriceLevel(std::int64_t price_ticks, std::int64_t quantity)
        : price_ticks_(price_ticks), quantity_(quantity) {
        if (quantity < 0) {
            throw std::invalid_argument{"quantity must be non-negative"};
        }
    }

    [[nodiscard]] std::int64_t price_ticks() const {
        return price_ticks_;
    }

    [[nodiscard]] std::int64_t quantity() const {
        return quantity_;
    }

private:
    std::int64_t price_ticks_;
    std::int64_t quantity_;
};

int main() {
    const PriceLevel level{10'025, 300};
    std::cout << level.price_ticks() << ' ' << level.quantity() << '\n';
}
```

构造成功后，调用者就能依赖 `quantity() >= 0`。真实热路径可能不用抛异常处理外部输入，而是先在解析边界验证并返回显式错误；这里的重点是对象不能半初始化后假装可用。

### 2.1 初始化优先于“先默认、再赋值”

成员按**类中声明的顺序**初始化，不按初始化列表书写顺序。推荐让两者保持一致：

```cpp,ignore
// 结构片段：没有 main，仅用于说明初始化顺序。
class Example {
public:
    Example(int price, int quantity)
        : price_(price), quantity_(quantity) {}

private:
    int price_;     // 先初始化
    int quantity_;  // 后初始化
};
```

若后声明的成员依赖先声明的成员，这个顺序尤其重要。编译器警告通常能发现初始化列表顺序不一致。

### 2.2 `explicit` 防止意外转换

单参数构造函数可能被编译器用于隐式转换。`explicit` 要求调用者明确构造：

```cpp
#include <cstdint>
#include <iostream>

class OrderId {
public:
    explicit OrderId(std::uint64_t value) : value_(value) {}

    [[nodiscard]] std::uint64_t value() const {
        return value_;
    }

private:
    std::uint64_t value_;
};

void cancel(OrderId id) {
    std::cout << "cancel " << id.value() << '\n';
}

int main() {
    cancel(OrderId{42});
    // cancel(42); // explicit 阻止把任意整数悄悄当成 OrderId
}
```

这种轻量类型能防止把价格、数量和订单号混传。性能是否与裸整数相当仍应结合布局、优化构建和调用边界验证。

## 3. 析构函数撤销不变量

析构函数在对象生命周期结束时运行，用于释放它拥有的资源。最常见的析构函数往往不是我们自己写的，而是标准类型已经实现的：

- `std::vector` 负责销毁元素并释放自己的动态存储；
- `std::string` 负责管理字符存储；
- `std::unique_ptr` 负责销毁独占对象；
- `std::lock_guard` 负责解锁；
- `std::fstream` 负责关闭文件。

把这些成员组合进业务类，编译器生成的析构函数会按规则调用它们。这就是 **Rule of Zero（零法则）**：若成员类型已经正确管理资源，业务类尽量不自己实现析构、复制和移动操作。

```cpp
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

struct Snapshot {
    std::string symbol;
    std::vector<std::int64_t> bid_prices;
};

int main() {
    Snapshot snapshot{"DEMO", {10'025, 10'024, 10'023}};
    std::cout << snapshot.symbol << ' ' << snapshot.bid_prices.size() << '\n';
}
```

`Snapshot` 没有手写析构函数，仍会正确清理 `string` 和 `vector`。这是现代 C++ 中非常重要的默认选择。

## 4. 作用域退出不只包括“走到最后一行”

自动对象会在多种离开路径上析构：

- 正常执行到代码块末尾；
- `return` 提前返回；
- 抛出异常并进行栈展开；
- `break`/`continue` 离开相应局部作用域。

下面用计数器模拟一个必须归还的资源：

```cpp
#include <iostream>

class ActiveRequest {
public:
    explicit ActiveRequest(int& active_count) : active_count_(active_count) {
        ++active_count_;
    }

    ~ActiveRequest() {
        --active_count_;
    }

    ActiveRequest(const ActiveRequest&) = delete;
    ActiveRequest& operator=(const ActiveRequest&) = delete;

private:
    int& active_count_;
};

bool process(bool valid, int& active_count) {
    ActiveRequest request{active_count};
    if (!valid) {
        return false;
    }
    return true;
}

int main() {
    int active_count = 0;
    process(false, active_count);
    std::cout << active_count << '\n';
}
```

即使 `process` 提前返回，`request` 仍会析构，所以最终计数回到 0。复制被删除，是因为同一份“活跃请求责任”不能被两个管理对象重复归还。

## 5. 锁也是资源

互斥锁的“持有状态”可以由 RAII guard 管理：

```cpp
#include <iostream>
#include <mutex>

class Counter {
public:
    void increment() {
        const std::lock_guard<std::mutex> guard{mutex_};
        ++value_;
    }

    [[nodiscard]] int value() const {
        const std::lock_guard<std::mutex> guard{mutex_};
        return value_;
    }

private:
    mutable std::mutex mutex_;
    int value_{0};
};

int main() {
    Counter counter;
    counter.increment();
    std::cout << counter.value() << '\n';
}
```

`lock_guard` 构造时加锁，析构时解锁。即使受保护代码将来增加提前返回，也不容易漏掉 `unlock`。这里 `mutable` 允许只读成员函数修改同步工具；这并不让任意业务字段都可在 `const` 接口中随意修改。

真实并发程序还要设计锁顺序、临界区范围和竞争行为。RAII 解决“忘记解锁”，不解决死锁或高竞争。

## 6. 异常安全：RAII 为什么重要

假设函数先取得资源，后面的步骤可能失败。手写释放容易漏掉：

```cpp,ignore
// 故意展示脆弱模式：new 后若中间步骤抛异常，delete 不会执行。
void fragile() {
    Buffer* buffer = new Buffer{};
    parse_or_throw(*buffer);
    delete buffer;
}
```

使用拥有对象后，栈展开会调用析构：

```cpp,ignore
// 局部片段：Buffer 和 parse_or_throw 由具体项目提供。
void safer() {
    auto buffer = std::make_unique<Buffer>();
    parse_or_throw(*buffer);
} // 正常返回或异常离开都会清理 buffer
```

异常安全常按保证强弱描述：

- **基本保证**：失败后不泄漏资源，对象不变量仍成立、对象仍处于有效状态，但业务值可能已经改变；
- **强保证**：失败后操作看起来像没有发生；
- **不抛异常保证**：操作承诺不抛出异常，常由 `noexcept` 表达。

具体 API 提供哪种保证必须查文档和实现约定。低延迟系统有时禁用异常或在热路径避免抛出，但 RAII 仍然有价值：正常返回、提前返回和对象组合都需要确定清理。

### 6.1 析构函数不要抛异常

析构函数默认通常被视为不抛异常。若在另一个异常展开过程中，析构又抛出异常，程序会终止。析构中的清理应设计成可完成且不抛；错误可在更早的显式 `close`/`flush` 阶段报告，具体策略取决于资源语义。

## 7. 生命周期嵌套和析构顺序

一个对象由多个成员组成时，析构大致按构造的反方向进行：

1. 先执行类自身析构函数体；
2. 再按成员声明的相反顺序析构成员；
3. 再处理基类部分。

局部变量也通常按成功构造的相反顺序析构。这样，如果后构造的资源依赖先构造的资源，清理时会先撤销依赖者。

```cpp
#include <iostream>
#include <string_view>

struct Trace {
    std::string_view name;

    explicit Trace(std::string_view value) : name(value) {
        std::cout << "+ " << name << '\n';
    }

    ~Trace() {
        std::cout << "- " << name << '\n';
    }
};

struct Engine {
    Trace network{"network"};
    Trace strategy{"strategy"};
};

int main() {
    Engine engine;
}
```

`network` 先构造，`strategy` 后构造；销毁时相反。真实系统不能仅依赖隐含顺序处理重要业务关停，还应设计停止接收、排空队列、撤单确认和审计落盘等显式协议。

## 8. 析构时机与集中清理

若一个批次对象拥有 `N` 个需要逐个销毁的子对象，而一次子对象清理的平均成本为 `D`，离开作用域时的清理量可以先粗略写成 `N × D`。这只是定位问题的模型：真实成本还受析构逻辑、缓存、分配器、操作系统和硬件影响。

RAII 保证“会清理”，却不会让清理工作消失。如果大对象在请求或事件处理路径尾部集中析构，就可能形成耗时尖峰。可考虑：

- 把对象生命周期提升到事件循环外并复用；
- 在启动期预留容量，减少逐条元素分配；
- 分批处理非关键清理，但必须保持资源上限；
- 用基准和性能计数器确认瓶颈。

不能为了隐藏延迟就永久不释放资源，那只是把问题变成泄漏或无界增长。

## 9. Rust 心智模型对照

| 意图 | Rust | C++ |
|---|---|---|
| 作用域清理 | `Drop` | 析构函数 |
| 独占资源 | 普通拥有值或 `Box<T>` | 普通拥有成员或 `unique_ptr<T>` |
| 锁守卫 | `MutexGuard` | `std::lock_guard` / `std::unique_lock` |
| 禁止复制 | 非 `Copy` 类型仍可显式 `Clone` | `= delete` 复制构造与复制赋值 |
| 失败传播 | `Result` / panic 展开策略 | 返回值 / 异常；异常策略由项目决定 |

两种语言都鼓励让资源跟随值的生命周期。差别在于 C++ 可定制复制、移动和析构，并允许更多裸引用关系；因此一个 RAII 类型还必须明确“能否复制、能否移动”。

## 10. 三类系统中的资源管理

RAII 可以管理后端的连接和锁、AI Infra 的设备缓冲与事件，也可以管理交易系统的 socket、内存映射和会话。共同点是：资源的创建、有效状态和释放规则都由一个对象表达。

在需要持续处理请求或事件的系统中，常见用途包括：

- 启动阶段管理 socket、文件描述符、内存映射和线程；
- 用 guard 管理短临界区；
- 让策略、订单簿、会话按明确依赖顺序关停；
- 在测试中确保临时资源和模拟连接被清理。

需要同时看到两面：

- RAII 提高错误路径和提前返回的可靠性；
- 析构可能释放内存、关闭句柄、等待线程或执行用户代码，成本并非自动可预测。

因此热路径对象应优先使用轻量析构或复用，并避免让一个看似普通的局部变量在作用域末尾触发大量工作。

## 11. 面试追问与参考答法

### Q1：什么是 RAII？

**参考答法**：把资源所有权封装进对象，构造时建立有效状态，析构时释放资源。自动对象在正常返回、提前返回和异常栈展开时都会析构，因此比在每条分支手写清理更可靠。

### Q2：RAII 是否只用于内存？

**参考答法**：不是。文件、socket、锁、线程、内存映射、临时配置切换都能用作用域对象管理。关键是资源具有可定义的取得和释放动作。

### Q3：什么是 Rule of Zero？

**参考答法**：若成员类型已经正确表达所有权，业务类尽量不自行实现析构、复制和移动，让编译器组合成员的行为。这样更少出现重复释放和漏改特殊成员函数的问题。

### Q4：析构时机确定，是否表示低延迟？

**参考答法**：不表示。确定性回答“何时执行”，不回答“执行多久”。析构可能遍历大量元素、调用分配器、关闭 I/O 或等待线程，应避免把不可控清理放到关键路径，并实际测量。

## 12. 易错点

- 只在正常路径释放资源，忽略提前返回和异常；
- 手写拥有裸指针，却保留默认复制，造成两个对象重复释放；
- 在析构函数中抛异常；
- 误以为初始化列表的书写顺序决定成员构造顺序；
- 把 `const` 成员函数当作不需要并发同步；
- 在持锁 guard 的作用域中做慢 I/O，却没有意识到锁一直持有；
- 把大量析构工作放在逐条消息尾部；
- 为了控制释放时机而放弃 RAII，重新引入泄漏风险。

## 13. 练习与参考答案

### 练习 1

一个函数取得锁后有三处提前 `return`。应手写三次 `unlock()`，还是使用 guard？为什么？

<details>
<summary>参考答案</summary>

通常使用 `std::lock_guard` 或按需要使用 `std::unique_lock`。guard 离开每个作用域路径时自动解锁，未来新增返回路径也不容易漏掉。但仍需缩小 guard 的作用域并分析死锁与竞争。

</details>

### 练习 2

类 `Book` 只包含 `std::string`、`std::vector<Level>` 和整数成员，是否通常需要手写析构函数？

<details>
<summary>参考答案</summary>

通常不需要。成员都能自行管理资源，编译器生成的析构函数会组合它们的析构行为，符合 Rule of Zero。只有额外不变量或特殊资源确实要求定制时才增加特殊成员函数。

</details>

### 练习 3

为什么把 10,000 个节点的容器局部变量放在热路径中可能形成延迟尖峰，即使它完全使用 RAII？

<details>
<summary>参考答案</summary>

离开作用域时仍需销毁节点并可能逐次归还内存。RAII 保证清理不遗漏，却不消除清理工作。可评估复用、连续存储、批处理或把生命周期移出逐条消息路径，并测量整体效果。

</details>

## 小结

构造函数负责建立对象的有效状态，析构函数负责撤销它拥有的资源；RAII 把这两个动作与对象生命周期绑定。现代 C++ 优先组合标准所有权类型并遵循 Rule of Zero，从而让正常、提前返回和异常路径共享同一套清理逻辑。低延迟工程还要继续问：清理虽然确定发生，但它的工作量是否可控、是否处在热路径。

# STL 容器、迭代器与算法的成本模型

STL 是 C++ 标准库中一组相互配合的容器、迭代器和算法。它们让我们不必重复实现动态数组、排序和查找，但“标准库”不等于“所有场景都一样快”。选型要看元素如何布局、何时分配、地址是否稳定，以及操作的时间复杂度。

## 1. 先理解三个角色

STL 的基本协作方式是：

- **容器（container）**保存元素，如 `vector<int>`；
- **迭代器（iterator）**表示容器中的位置，像受容器规则约束的通用指针；
- **算法（algorithm）**通过迭代器范围工作，如 `sort`、`find`、`lower_bound`。

```cpp
#include <algorithm>
#include <array>
#include <iostream>

int main() {
    std::array<int, 5> prices{103, 100, 102, 101, 104};
    std::sort(prices.begin(), prices.end());

    const auto found = std::find(prices.begin(), prices.end(), 102);
    if (found != prices.end()) {
        std::cout << "found at index "
                  << std::distance(prices.begin(), found) << '\n';
    }
}
```

范围通常写成 `[begin, end)`：包含 `begin` 指向的元素，不包含 `end`。`end()` 是尾后位置，能用于比较，不能解引用。

## 2. 复杂度：先估算增长趋势

复杂度不是具体纳秒，而是输入规模 `n` 增大时，操作量如何增长：

- `O(1)`：操作量大致不随 `n` 增长，例如 `vector` 已有容量时尾部插入；
- `O(log n)`：每一步大约排除一半，例如有序数组二分查找；
- `O(n)`：可能检查或移动全部元素；
- `O(n log n)`：常见比较排序量级。

两个操作同为 `O(n)`，实际性能仍可能相差很大。连续扫描通常容易利用缓存和预取，而链表扫描会沿指针跳转。常数、内存分配、分支和数据分布都重要。

## 3. `std::array<T, N>`：长度编译期固定

`std::array` 把固定数量元素直接包含在对象中，没有独立的动态容量：

```cpp
#include <array>
#include <cstdint>
#include <iostream>

int main() {
    std::array<std::int64_t, 4> top_prices{10'025, 10'024, 10'023, 10'022};
    for (const std::int64_t price : top_prices) {
        std::cout << price << '\n';
    }
}
```

适合：

- 最大数量在编译期确定；
- 希望元素连续、对象可直接作为成员；
- 不需要运行时扩缩容。

`N` 是类型的一部分，所以 `array<int, 4>` 和 `array<int, 8>` 是不同类型。大数组作为局部自动对象可能增加线程栈压力；也可以把包含它的拥有对象放在其他适当存储中。

## 4. `std::vector<T>`：连续动态数组

`vector` 是非常重要的默认候选：元素连续，支持按下标随机访问，能动态改变元素数量。

```cpp
#include <cstdint>
#include <iostream>
#include <vector>

int main() {
    std::vector<std::int64_t> prices;
    prices.reserve(4);

    prices.push_back(10'025);
    prices.push_back(10'024);
    prices.push_back(10'023);

    std::cout << "size = " << prices.size() << '\n';
    std::cout << "capacity >= " << prices.capacity() << '\n';
    std::cout << "second = " << prices[1] << '\n';
}
```

### 4.1 `size` 与 `capacity`

- `size()`：当前真实存在多少个元素；
- `capacity()`：不重新分配时最多能容纳多少个元素。

`reserve(4)` 只预留容量，不创建 4 个元素，因此之后不能直接访问 `prices[3]`。`resize(4)` 才会让 4 个元素存在，并按规则初始化新增元素。

```cpp,ignore
// 故意错误：reserve 后 size 仍为 0，prices[0] 越界。
std::vector<int> prices;
prices.reserve(100);
prices[0] = 42;
```

### 4.2 扩容发生了什么

当 `push_back` 时容量不足，`vector` 通常会：

1. 申请一块更大的连续存储；
2. 把已有元素移动或复制过去；
3. 销毁旧元素并释放旧存储；
4. 在新存储加入元素。

增长倍率是实现策略，不应假定永远为 2 倍。这次操作可能比普通尾插慢很多，并让指向旧元素的指针、引用和迭代器失效。

### 4.3 `reserve` 是容量策略，不是万能优化

已知上限时预留容量可以减少扩容，但也有代价：

- 预留过大增加内存占用和首次触页压力；
- 真实上限被突破时仍会扩容，除非代码显式拒绝；
- `reserve` 不初始化元素，也不保证页面已经物理驻留；
- 容量需求变化时要监控和压测。

热路径若要求“绝不扩容”，应主动检查：

```cpp
#include <cstddef>
#include <iostream>
#include <vector>

class BoundedBatch {
public:
    explicit BoundedBatch(std::size_t limit) : limit_(limit) {
        values_.reserve(limit);
    }

    [[nodiscard]] bool try_push(int value) {
        // reserve 只保证实际 capacity >= 请求值，业务上限要单独保存。
        if (values_.size() >= limit_) {
            return false;
        }
        values_.push_back(value);
        return true;
    }

    [[nodiscard]] std::size_t size() const {
        return values_.size();
    }

private:
    std::size_t limit_;
    std::vector<int> values_;
};

int main() {
    BoundedBatch batch{2};
    std::cout << batch.try_push(10) << '\n';
    std::cout << batch.try_push(20) << '\n';
    std::cout << batch.try_push(30) << '\n';
    std::cout << batch.size() << '\n';
}
```

返回 `false` 只是教学策略。真实行情系统要定义容量耗尽后是丢弃、降级、断开重建还是触发告警，不能静默遗漏数据。

## 5. 迭代器、指针和引用何时失效

容器修改可能让之前保存的位置失效。以 `vector` 为例：

- 发生重新分配时，指向全部元素的指针、引用和迭代器全部失效；
- 即使没有重新分配，插入或删除也会使操作位置及其后的指针、引用和迭代器失效（旧的尾后迭代器也在内）；
- `clear`、析构等会结束元素生命周期。

```cpp,ignore
// 故意错误：第二次 push_back 可能触发扩容，saved 随后可能悬空。
std::vector<int> values;
values.reserve(1);
values.push_back(10);
int* saved = &values[0];
values.push_back(20);
return *saved;
```

修复不能只靠“这次测试地址没变”。可在容量稳定期间使用索引，并在容器修改后重新取得引用；或选择提供所需地址稳定性的结构，同时接受其其他成本。

### 5.1 `at()` 与 `operator[]`

- `values[index]` 不做标准要求的边界检查，越界是未定义行为；
- `values.at(index)` 越界时抛出 `std::out_of_range`。

外部输入边界应在解析处显式验证。热路径选择哪种接口需要结合项目异常策略、已证明不变量和构建配置，而不是盲目删除检查。

## 6. `deque`、`list` 与地址稳定性权衡

### 6.1 `std::deque<T>`

`deque` 通常由多个内存块组成，支持头尾较高效插入删除和随机访问，但元素不保证像 `vector` 那样处于一整块连续内存。其迭代器失效规则也不同且与操作有关，使用前应查标准库文档。

### 6.2 `std::list<T>`

`list` 是双向链表，已知节点位置时插入删除可为 `O(1)`，且其他节点迭代器常较稳定。但每个节点通常需要额外指针和独立存储，遍历会指针追逐，缓存局部性往往较差。

“插入是 `O(1)`”不包含找到插入位置的时间。若为了插入先线性扫描，整体仍是 `O(n)`。在现代 CPU 上，小到中等规模数据即使需要移动元素，`vector` 也可能比链表更快；结论要按真实负载测量。

## 7. 有序映射与哈希映射

### 7.1 `std::map<Key, Value>`

`map` 通常实现为平衡树：

- 查找、插入、删除通常 `O(log n)`；
- 键保持排序；
- 节点通常独立分配，遍历存在指针追逐；
- 除被删除元素外，许多操作对已有迭代器较稳定。

### 7.2 `std::unordered_map<Key, Value>`

`unordered_map` 是哈希表：

- 平均查找、插入常描述为 `O(1)`；
- 最坏情况可退化为 `O(n)`；
- 扩桶/rehash 可能产生显著成本并让迭代器失效；
- 性能依赖哈希质量、装载因子、容量和访问分布；
- 不提供按键排序遍历。

```cpp
#include <cstdint>
#include <iostream>
#include <string>
#include <unordered_map>

int main() {
    std::unordered_map<std::string, std::int64_t> positions;
    positions.reserve(4);
    positions.emplace("ALPHA", 100);
    positions.emplace("BETA", -50);

    const auto found = positions.find("ALPHA");
    if (found != positions.end()) {
        std::cout << found->second << '\n';
    }
}
```

用 `find` 不会在键不存在时自动插入；`positions["MISSING"]` 则可能插入默认值。只读查询误用 `operator[]` 会改变容器，是常见 bug。

### 7.3 订单簿是否该用 `map`

不能只凭“价格有序”就选 `map`。若价格范围可映射到紧凑 tick 索引，数组或分段数组可能更有局部性；若档位稀疏且插删频繁，树结构可能更方便；若只维护前 N 档，小型有序 `vector` 也可能合适。要结合标的价格范围、更新分布、最坏延迟和内存上限基准测试。

## 8. `std::string`、`string_view` 与字符所有权

`std::string` 拥有字符，能扩容和修改；`std::string_view` 只保存字符区间视图，不拥有内容。

```cpp
#include <iostream>
#include <string>
#include <string_view>

bool is_demo_symbol(std::string_view symbol) {
    return symbol == "DEMO";
}

int main() {
    const std::string owned{"DEMO"};
    std::cout << is_demo_symbol(owned) << '\n';
    std::cout << is_demo_symbol("OTHER") << '\n';
}
```

`string_view` 适合短期只读参数，避免为了调用而构造拥有字符串。但不能保存指向已销毁字符串或已被覆盖接收缓冲区的 view。

字符串具体是否分配受长度、容量和实现的短字符串优化影响。`reserve` 可减少扩容，却不改变字符串拥有数据这一语义。

## 9. 标准算法：让意图和范围更清楚

常用算法包括：

- `std::find`：线性查找；
- `std::sort`：排序；
- `std::lower_bound`：在已排序范围中二分查找第一个不小于目标的位置；
- `std::transform`：逐元素转换；
- `std::accumulate`：归约求和等操作（位于 `<numeric>`）；
- `std::ranges` 中的 C++20 范围算法：可直接接收范围，减少 `begin/end` 重复。

### 9.1 有序价格档位的查找

```cpp
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <vector>

struct Level {
    std::int64_t price_ticks;
    std::int64_t quantity;
};

int main() {
    std::vector<Level> levels{{100, 10}, {102, 30}, {105, 20}};
    const std::int64_t target = 102;

    const auto it = std::lower_bound(
        levels.begin(), levels.end(), target,
        [](const Level& level, std::int64_t price) {
            return level.price_ticks < price;
        });

    if (it != levels.end() && it->price_ticks == target) {
        std::cout << it->quantity << '\n';
    }
}
```

`lower_bound` 要求范围按同一个谓词相对于目标值保持 partitioned；通常就是按相同排序关系有序。违反这个标准前置条件会导致未定义行为，不只是“返回一个没有业务意义的位置”。标准算法不会替你维护订单簿不变量。

### 9.2 排序与投影

```cpp
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <ranges>
#include <vector>

struct Quote {
    std::int64_t price_ticks;
    std::int64_t quantity;
};

int main() {
    std::vector<Quote> quotes{{103, 10}, {101, 20}, {102, 30}};
    std::ranges::sort(quotes, {}, &Quote::price_ticks);

    for (const Quote& quote : quotes) {
        std::cout << quote.price_ticks << ' ' << quote.quantity << '\n';
    }
}
```

投影 `&Quote::price_ticks` 告诉算法按哪个字段比较。静态算法表达通常能被内联优化，但比较器分支、元素移动和数据布局仍决定真实成本。

## 10. `push_back`、`emplace_back` 与“原地构造”

`emplace_back(args...)` 用参数在容器尾部构造元素；`push_back(value)` 放入已有值。`emplace_back` 可能少一个临时对象，但并非自动更快：

- 容器扩容时仍要转移旧元素；
- 简单标量没有可省的大对象；
- 复杂参数转发可能让代码更难读；
- `push_back` 对已经存在的对象语义更清楚。

先选择表达意图最清晰的写法，再通过构造计数或基准确认差异。

## 11. 容器清理不等于释放容量

对 `vector` 调用 `clear()` 会销毁元素并把 `size` 变为 0，通常不要求把 `capacity` 归还给分配器。这对批次复用很有帮助：下一批可以重用存储。

`shrink_to_fit()` 只是非强制请求，可能重新分配并使迭代器失效；频繁调用会破坏复用效果。若内存必须在某阶段归还，应设计明确生命周期并测量具体实现。

## 12. 成本对照表

下表描述常见标准复杂度与典型布局，具体操作和实现规则仍应查所用标准库文档。

| 容器 | 随机访问 | 尾部插入 | 中间插入 | 查找 | 布局/主要风险 |
|---|---:|---:|---:|---:|---|
| `array<T,N>` | `O(1)` | 不可扩容 | `O(n)` 手动移动 | 无序 `O(n)` | 连续、容量编译期固定 |
| `vector<T>` | `O(1)` | 摊销 `O(1)` | `O(n)` | 无序 `O(n)` | 连续；扩容尖峰与地址失效 |
| `deque<T>` | `O(1)` | 通常 `O(1)` | `O(n)` | 无序 `O(n)` | 分块；非整体连续 |
| `list<T>` | 不支持下标 | 已知位置 `O(1)` | 已知位置 `O(1)` | `O(n)` | 节点分配、指针追逐 |
| `map<K,V>` | 不支持下标式连续访问 | — | 插入 `O(log n)` | `O(log n)` | 有序树、节点与分支 |
| `unordered_map<K,V>` | 按键平均 `O(1)` | — | 插入平均 `O(1)` | 平均 `O(1)`，最坏 `O(n)` | rehash、哈希质量、内存开销 |

“摊销 `O(1)`”表示把许多次操作平均后为常数量级，不表示每一次都同样快。尾延迟敏感时必须关注那次扩容。

## 13. 教学算例：小型有序档位的移动量

假设只维护前 16 档报价，每个 `Level` 教学上按 16 字节估算。向最前面插入一档，最坏需移动约 16 个元素：

\[
16 \times 16 = 256\ \text{bytes}
\]

这段连续移动可能很便宜，也可能因元素类型、分支和频率而不合适。若改用链表，虽然节点插入本身可为 `O(1)`，但查找位置、节点分配和遍历指针追逐可能更贵。这个算例说明：**小 `n` 时，复杂度标签往往不如内存布局和常数重要**。

## 14. Rust 心智模型对照

| C++ | Rust 近似对应 | 关键提醒 |
|---|---|---|
| `std::vector<T>` | `Vec<T>` | 扩容都可能移动存储并使旧引用失效；Rust 借用规则更常在编译期阻止持有引用再修改 |
| `std::array<T,N>` | `[T; N]` | 长度均是类型的一部分 |
| `std::span<T>` | `&mut [T]` / `&[T]` 的视图直觉 | C++ 不跟踪同等生命周期与独占规则 |
| `std::string` | `String` | 都拥有字符，但编码/接口细节不同 |
| `std::string_view` | `&str` 的借用直觉 | `string_view` 不保证 UTF-8，也容易悬空 |
| `std::unordered_map` | `HashMap` | 哈希器、迭代顺序、复杂度细节均需看各自实现 |

Rust 常阻止“持有 `Vec` 元素引用时又扩容”的代码；C++ 允许写出这段程序，是否失效由程序员根据容器规则判断。

## 15. HFT 联系：容器选择从访问模式出发

行情与订单系统常见访问模式：

- **固定前 N 档**：`array` 或固定容量结构容易控制上限；
- **批量消息**：预留过容量的 `vector` 可连续扫描和复用；
- **订单 ID 查询**：哈希表方便，但要控制装载因子、rehash 和最坏输入；
- **稀疏价格档位**：树或分段结构可能合适，需要和紧凑索引方案比较；
- **稳定句柄**：可使用索引 + generation，而不是长期保存可能失效的元素指针。

设计时至少记录：最大容量、满时行为、删除与复用规则、是否允许盘中 rehash、迭代顺序是否有业务含义、以及哪些操作落在关键路径。

## 16. 面试追问与参考答法

### Q1：`vector::reserve` 和 `resize` 有什么区别？

**参考答法**：`reserve` 至少调整容量，不改变元素数量；`resize` 改变 `size`，会构造新增元素或销毁多余元素。`reserve(100)` 后访问 `[0]` 仍越界，直到元素被真正加入。

### Q2：为什么 `vector` 扩容会让指针失效？

**参考答法**：它可能申请新的连续存储并移动/复制全部元素，旧地址不再承载那些对象。所有指向旧元素的指针、引用和迭代器都不能继续使用。

### Q3：`unordered_map` 查找一定是 `O(1)` 吗？

**参考答法**：通常说平均 `O(1)`，最坏可退化到 `O(n)`。实际延迟还受哈希质量、冲突、装载因子、rehash、分配和缓存影响，尾延迟场景要测量并控制容量。

### Q4：链表插入 `O(1)`，为什么可能比 `vector` 慢？

**参考答法**：已知节点位置才是 `O(1)`，找位置可能仍为 `O(n)`；节点独立分配、额外指针和指针追逐损害缓存。`vector` 的连续移动对小型数据常很高效，需按访问模式基准测试。

### Q5：`clear()` 会释放 `vector` 容量吗？

**参考答法**：它销毁元素并令 `size` 为 0，但通常保留容量以便复用。标准不要求 `clear` 把存储归还；需要释放时应设计更明确的生命周期，而不是假设某个实现行为。

## 17. 易错点

- `reserve` 后直接按下标写不存在的元素；
- 保存 `vector` 元素地址后继续插入，忽略扩容失效；
- 解引用 `end()`；
- 对无序范围调用 `lower_bound`；
- 用 `unordered_map::operator[]` 做只读查询，意外插入键；
- 把平均 `O(1)` 当成每次固定时延；
- 看到链表插入 `O(1)` 就忽略找位置与节点分配；
- 保存 `string_view` 超过底层字符串或缓冲区生命周期；
- 每批都 `shrink_to_fit`，破坏容量复用；
- 无容量耗尽策略地声称“已经预分配所以不会扩容”；
- 使用容器默认迭代顺序承担协议或审计语义。

## 18. 练习与参考答案

### 练习 1

执行 `values.reserve(1'000)` 后，`values.size()` 是多少？能否立即写 `values[999]`？

<details>
<summary>参考答案</summary>

若原来为空，`size()` 仍为 0。不能访问 `[999]`，因为元素尚不存在。可以逐个 `push_back`，或在确实需要创建 1,000 个元素时使用 `resize(1'000)`。

</details>

### 练习 2

需要每次按顺序扫描 64 个固定价格槽，并频繁读取。`array`、`list` 哪个更值得先基准？为什么？

<details>
<summary>参考答案</summary>

通常先考虑 `std::array<Level, 64>`：容量固定、元素连续、无节点分配，顺序扫描局部性好。若有其他特殊要求再比较其他结构；最终仍应以真实元素类型和更新模式测量。

</details>

### 练习 3

哈希表已在启动时 `reserve`，是否就能保证盘中永不 rehash？

<details>
<summary>参考答案</summary>

不能仅凭一次 `reserve` 保证。还要确认实际元素上限、`max_load_factor`、后续插入量以及所用标准库语义。可显式监控容量/桶数并设计超限行为，在目标实现上验证。

</details>

### 练习 4

解析器返回 `string_view` 指向复用缓冲区。把 view 存进 `vector` 是否让字符也被复制并拥有？

<details>
<summary>参考答案</summary>

不会。`vector` 只复制各个 view 的起点和长度等视图信息，字符仍在原缓冲区。缓冲区复用后，这些 view 可能全部指向被覆盖的数据。长期保存应复制字符或转移缓冲区所有权。

</details>

## 小结

STL 容器的选择要同时考虑语义、复杂度和内存布局。`array` 适合固定容量，`vector` 是连续动态集合的重要默认候选，树和哈希表用于不同查找需求。预分配能把部分工作移出热路径，但必须配合明确上限；所有保存的指针、引用和迭代器都要遵守失效规则。算法让意图更清晰，却不会替程序维护排序、边界和生命周期不变量。

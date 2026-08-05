# C++20 算法题工具箱：把伪代码稳定翻译成程序

想到算法却写不出 C++，往往不是思路问题，而是工具还不熟：哈希表怎样判断存在、最小堆模板参数怎么写、`size_t` 为什么减一后变得很大。本章不重讲整门 C++，只整理算法题最常用的一小组工具，并用 Top-K 问题走完一遍“伪代码 → C++20 → 边界测试”。

> **本章目标**：能为题目选择常用标准容器；能把半开区间、映射、集合、队列、栈和堆翻译成 C++；能写清函数接口和整数类型；不会把库调用误当作零成本操作。

如果变量、函数、引用或 `vector` 仍然陌生，先完成 [C++ 基础复习](../cpp/basics_refresher.md)。容器布局、迭代器失效和标准复杂度的完整解释见 [STL 成本模型](../cpp/stl_cost_model.md)。

## 1. 先建立“伪代码概念 → C++ 类型”映射

| 伪代码概念 | C++20 常见选择 | 先记住的边界 |
|---|---|---|
| 动态数组 | `std::vector<T>` | 下标范围是 `[0, size())`，扩容可能使引用失效 |
| 固定长度数组 | `std::array<T, N>` | `N` 是类型的一部分 |
| 字符串 | `std::string` | `size()` 是字节/代码单元数量，不等于通用 Unicode 字符数 |
| 键到值的映射 | `std::unordered_map<K, V>` | 平均常数查找，不承诺最坏常数；`operator[]` 可能插入 |
| 是否见过某个键 | `std::unordered_set<T>` | 只保存键，不需要虚构一个布尔值 |
| 有序映射/集合 | `std::map` / `std::set` | 常见操作 `O(log n)`，节点式布局 |
| 先进先出 | `std::queue<T>` | 读取 `front()` 前先确认非空 |
| 后进先出 | `std::stack<T>` | 读取 `top()` 前先确认非空 |
| 最大堆 | `std::priority_queue<T>` | 默认 `top()` 是最大元素 |
| 最小堆 | `std::priority_queue<T, std::vector<T>, std::greater<T>>` | 需要 `<functional>`，`top()` 是最小元素 |
| 可能没有答案 | `std::optional<T>` | 取值前检查 `has_value()` 或布尔状态 |
| 一对值 | `std::pair<A, B>` | 可用结构化绑定 `auto [a, b]` |

这张表是默认起点，不是机械规则。例如需要保持键有序时选 `map`，只需平均快速查找时常选 `unordered_map`；输入很小或访问连续时，简单 `vector` 扫描可能更容易写、也可能实际更快。

## 2. 函数接口：先让输入、输出和修改权清楚

算法题中常见三种参数写法：

```cpp,ignore
// 小型标量按值传递。
bool is_valid(std::int64_t value);

// 只读大型容器通常用 const 引用，避免复制并禁止函数修改。
std::int64_t sum(const std::vector<std::int64_t>& values);

// 题目明确要求原地修改时使用可变引用。
void sort_in_place(std::vector<std::int64_t>& values);
```

不要为了“省复制”把返回局部 `vector` 改成返回引用。按值返回拥有结果最清楚，编译器可以使用返回值优化和移动语义。

题目说“不允许修改输入”时，`const std::vector<T>&` 能把这条约束写进接口。若算法确实需要排序，可先复制：

```cpp,ignore
std::vector<std::int64_t> copy = values;
std::ranges::sort(copy);
```

复制本身需要 `O(n)` 时间和空间，复杂度分析不能漏掉。

## 3. 整数与下标：最常见的正确性陷阱

### 3.1 根据数值上界选择类型

- 元素数量和容器下标通常使用 `std::size_t`；
- 业务整数可优先使用宽度明确的 `std::int32_t`、`std::int64_t`；
- 求和、乘积和距离可能需要在运算**之前**扩大类型；
- 若题目数值可能超过 64 位，需要检查、使用更宽表示或重新设计比较方式，不能希望溢出“自动截断成合理值”。

```cpp,ignore
// 错：两个 int32_t 先按 32 位相乘，转换结果时可能已经溢出。
const std::int64_t not_safe = price * quantity;

// 对给定上界足够时，先扩大一个操作数。
const std::int64_t widened = std::int64_t{price} * quantity;
```

### 3.2 无符号下标不要盲目倒着减

`std::size_t` 是无符号类型，`0 - 1` 会回绕成很大的值。下面的循环很危险：

```cpp,ignore
for (std::size_t i = values.size() - 1; i >= 0; --i) {
    // i >= 0 对无符号类型永远为真。
}
```

需要反向遍历时，可使用反向迭代器，或把“减一”写在确认大于零之后：

```cpp,ignore
for (auto it = values.rbegin(); it != values.rend(); ++it) {
    // 使用 *it
}
```

### 3.3 比较有符号值与容器长度

若输入中的 `k` 可能为负，先在有符号域检查 `k < 0`，再转换为 `size_t`。把负数直接转换为无符号类型会得到很大的值。

## 4. 查找与插入：避免 `operator[]` 的隐藏副作用

对 `unordered_map` 执行 `counts[key]` 时，若键不存在，会插入一个默认构造的值。这对计数很方便：

```cpp,ignore
++counts[value];
```

但只想查询时，`operator[]` 可能悄悄改变容器。此时使用：

```cpp,ignore
const auto found = counts.find(value);
if (found != counts.end()) {
    // found->second 是对应值
}
```

C++20 也提供 `contains`，适合只问键是否存在。需要同时取得映射值时，`find` 避免再查一次。

## 5. 标准算法：写出意图，同时尊重前置条件

常用操作包括：

- `std::sort` / `std::ranges::sort`：排序；
- `std::find`：线性查找；
- `std::lower_bound`：在满足分区前提的范围中找第一个不小于目标的位置；
- `std::upper_bound`：找第一个大于目标的位置；
- `std::reverse`：反转范围；
- `std::accumulate`：归约求和，初始值类型会影响计算类型；
- `std::min_element` / `std::max_element`：返回最小/最大元素的迭代器。

标准算法不会替你维护前置条件。对无序数组调用 `lower_bound`，不能把结果当作可靠的二分查找答案。

下面的独立程序把常用容器和操作放在一个最小例子里：

```cpp
#include <algorithm>
#include <cassert>
#include <functional>
#include <iostream>
#include <queue>
#include <stack>
#include <unordered_map>
#include <unordered_set>
#include <vector>

int main() {
    std::vector<int> values{4, 1, 4, 2};
    std::ranges::sort(values);
    assert((values == std::vector<int>{1, 2, 4, 4}));

    const auto first_four = std::lower_bound(values.begin(), values.end(), 4);
    assert(first_four != values.end() && *first_four == 4);

    std::unordered_map<int, int> counts;
    std::unordered_set<int> seen;
    for (const int value : values) {
        ++counts[value];
        seen.insert(value);
    }
    assert(counts.at(4) == 2);
    assert(seen.contains(2));

    std::queue<int> fifo;
    fifo.push(10);
    fifo.push(20);
    assert(fifo.front() == 10);
    fifo.pop();
    assert(fifo.front() == 20);

    std::stack<int> lifo;
    lifo.push(10);
    lifo.push(20);
    assert(lifo.top() == 20);

    std::priority_queue<int> max_heap;
    max_heap.push(3);
    max_heap.push(8);
    assert(max_heap.top() == 8);

    std::priority_queue<int, std::vector<int>, std::greater<int>> min_heap;
    min_heap.push(3);
    min_heap.push(8);
    assert(min_heap.top() == 3);

    std::cout << "toolbox checks passed\n";
}
```

这段程序用于恢复接口手感，不表示一道题应该同时使用所有容器。真正解题时，应选择维持不变量所需的最小工具。

## 6. 白话题意：找最大的 `k` 个数

题目如下：

> 给定一组 64 位整数 `values` 和非负整数 `k`，返回其中最大的 `min(k, values.size())` 个数，结果按从大到小排列。重复值应保留，输入不能被修改。

例子：

```text
values = [5, 1, 9, 3, 9], k = 3
结果 = [9, 9, 5]
```

边界语义已经明确：

- `k == 0` 返回空；
- 输入为空返回空；
- `k` 大于元素数量时返回全部元素；
- 重复的 `9` 是两个不同输入元素，所以结果保留两个 `9`；
- 返回值必须降序，但不要求相同值之间有额外稳定顺序。

## 7. 暴力基线：复制、完整排序、截取前 `k` 个

最直接的做法：

```text
复制 values 得到 copy
把 copy 从大到小完整排序
保留前 min(k, copy.size) 个元素
返回 copy
```

设 `n` 为输入长度、`m = min(k, n)`：

- 复制需要 `O(n)`；
- 完整排序需要 `O(n log n)`；
- 缩短结果本身不改变主导项；
- 额外空间至少为保存副本/结果的 `O(n)`。

这个方案简单，`k` 接近 `n` 时通常很合理。优化不能只看“大 O 更漂亮”，还要看 `k` 的大小、实现复杂度和真实输入。

## 8. 关键观察与不变量：只保留当前最好的 `k` 个

若 `k` 远小于 `n`，无需完整排序所有元素。扫描过程中只保留当前最大的 `k` 个：

- 容器不足 `k` 个时，直接加入；
- 容器已有 `k` 个时，只需知道其中最小的是谁；
- 新值不大于这个最小值，就没有资格进入当前 Top-K；
- 新值更大，则移除当前最小值，再加入新值。

“能快速取得当前最小值”正是大小为 `k` 的最小堆擅长的操作。

处理完前 `i` 个元素后，维护下面的不变量：

> 最小堆中保存了前 `i` 个元素里最大的 `min(k, i)` 个值；堆顶是这些保留值中最小的一个。

## 9. 语言无关伪代码

```text
如果 k == 0：
    返回空数组

创建空的最小堆 heap

依次读取每个 value：
    如果 heap 的元素数小于 k：
        把 value 放入 heap
    否则如果 value 大于 heap 的最小值：
        删除 heap 的最小值
        把 value 放入 heap

把 heap 中所有值取出到 result
把 result 从大到小排序
返回 result
```

这里在新值等于堆顶时不替换。因为题目只关心返回数值，多保留哪一个相等元素没有区别；若题目要求返回原下标或稳定顺序，比较键必须包含下标规则。

## 10. 正确性：为什么堆里始终是当前 Top-K

用归纳法说明不变量：

- **初始化**：尚未处理元素时堆为空，恰好保存前 0 个元素中的最大 0 个；
- **堆未满**：加入当前值后，已经处理的元素数不超过 `k`，所有已处理元素都应保留；
- **堆已满且新值不大于堆顶**：堆中已有 `k` 个值都不小于新值，所以新值不必进入最大的 `k` 个；
- **堆已满且新值大于堆顶**：堆顶是当前保留值中最小的。用更大的新值替换它后，得到新前缀中最大的 `k` 个值。

因此扫描结束后，堆保存整个输入的 Top-K。最后排序只改变输出顺序，不改变保存的值。

## 11. 复杂度：别漏掉最终输出排序

令 `m = min(k, n)`：

- 堆最多保存 `m` 个元素；
- 每次插入或替换为 `O(log m)`；
- 扫描最坏为 `O(n log m)`；
- 最后把 `m` 个结果降序排序为 `O(m log m)`；
- 除返回结果外，堆额外使用 `O(m)` 空间。

若只要第 `k` 大而不要求返回排序后的全部 Top-K，可以直接使用扫描结束后的堆顶，省去最终排序。标准库 `nth_element` 也是重要候选，具有不同的平均复杂度和原地修改特征，应根据题目约束选择。

## 12. 完整 C++20：基线、最小堆与随机差分

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <iostream>
#include <queue>
#include <random>
#include <vector>

[[nodiscard]] std::vector<std::int64_t> top_k_by_sorting(
    const std::vector<std::int64_t>& values,
    std::size_t k) {
    std::vector<std::int64_t> result = values;
    std::ranges::sort(result, std::greater<>{});
    if (result.size() > k) {
        result.resize(k);
    }
    return result;
}

[[nodiscard]] std::vector<std::int64_t> top_k_by_heap(
    const std::vector<std::int64_t>& values,
    std::size_t k) {
    if (k == 0 || values.empty()) {
        return {};
    }

    const std::size_t keep = std::min(k, values.size());
    std::priority_queue<
        std::int64_t,
        std::vector<std::int64_t>,
        std::greater<std::int64_t>> min_heap;

    for (const std::int64_t value : values) {
        if (min_heap.size() < keep) {
            min_heap.push(value);
        } else if (value > min_heap.top()) {
            min_heap.pop();
            min_heap.push(value);
        }
    }

    std::vector<std::int64_t> result;
    result.reserve(keep);
    while (!min_heap.empty()) {
        result.push_back(min_heap.top());
        min_heap.pop();
    }
    std::ranges::sort(result, std::greater<>{});
    return result;
}

void check_case(const std::vector<std::int64_t>& values,
                std::size_t k) {
    assert(top_k_by_heap(values, k) == top_k_by_sorting(values, k));
}

int main() {
    check_case({}, 0);
    check_case({}, 5);
    check_case({4}, 0);
    check_case({4}, 1);
    check_case({4}, 8);
    check_case({5, 1, 9, 3, 9}, 3);
    check_case({3, 3, 3}, 2);
    check_case({-8, -2, -5}, 2);
    check_case({1, 2, 3, 4}, 4);

    std::mt19937 generator{20260805U};
    std::uniform_int_distribution<int> length_distribution{0, 60};
    std::uniform_int_distribution<std::int64_t> value_distribution{-100, 100};
    std::uniform_int_distribution<int> k_distribution{0, 80};

    for (int round = 0; round < 3'000; ++round) {
        const auto length = static_cast<std::size_t>(length_distribution(generator));
        std::vector<std::int64_t> values(length);
        for (std::int64_t& value : values) {
            value = value_distribution(generator);
        }
        check_case(values, static_cast<std::size_t>(k_distribution(generator)));
    }

    const auto answer = top_k_by_heap({5, 1, 9, 3, 9}, 3);
    for (const std::int64_t value : answer) {
        std::cout << value << ' ';
    }
    std::cout << '\n';
}
```

这里使用完整排序版作为测试 oracle（参照实现）。两种实现都复制或保存自己的数据，不修改输入。`keep` 先取 `min(k, n)`，所以当 `k > n` 时堆不会等待不存在的元素。

## 13. 边界测试：Top-K 的 `k` 经常让代码出错

至少检查：

- 空输入配 `k = 0` 和 `k > 0`；
- 非空输入配 `k = 0`；
- `k = 1`、`k = n`、`k > n`；
- 全部值相同；
- 全部为负数，避免错误地把初始最大值设为 0；
- 重复的最大值；
- 输入原本升序、降序和随机顺序。

如果在线笔试把 `k` 读成有符号整数，应先拒绝负数，再转换为 `size_t`。本章函数直接接收 `size_t`，相当于接口已经承诺 `k` 非负。

## 14. 面试追问与选择权衡

### Q1：为什么不总用最小堆？

当 `k` 接近 `n` 时，完整排序更简单，常数和内存访问也可能更友好。堆方案的优势主要出现在 `k` 明显小于 `n`、数据流式到达或无需保存全部输入时。最终选择要结合约束，而不是背“Top-K 必须用堆”。

### Q2：如果只要第 `k` 大呢？

对合法的 `1 <= k <= n`，大小为 `k` 的最小堆扫描结束后，堆顶就是第 `k` 大。也可讨论 `nth_element`；它通常会修改输入范围，若不允许修改则需要副本。

### Q3：如果要求相同数值按原下标排序呢？

堆元素不能只保存数值，还要保存 `{value, index}`，并把完整排序规则写进比较器。必须先确认“更大”的定义，避免堆的比较规则与最终输出规则不一致。

### Q4：如果数据无限到达呢？

固定 `k` 时，堆只需 `O(k)` 状态，适合单遍流式处理。但若要求随时支持不同的任意 `k`，就不能从一个固定大小的堆凭空恢复已丢弃数据。

## 15. C++ 写题时的检查清单

提交前快速检查：

- [ ] 所需头文件是否齐全？
- [ ] 空容器上是否调用了 `front()`、`back()`、`top()` 或 `pop()`？
- [ ] `size() - 1` 之前是否确认非空？
- [ ] 有符号与无符号比较是否清楚？
- [ ] 加法、乘法、中点或计数是否会溢出？
- [ ] 只查询映射时是否意外使用 `operator[]` 插入了键？
- [ ] 排序、哈希和堆操作的复杂度是否计入？
- [ ] 保存的迭代器、指针或引用是否可能因容器修改而失效？
- [ ] 比较器是否满足严格弱序，是否与题意中的顺序一致？
- [ ] 返回“没有答案”的方式是否明确？

## 16. 练习与完整参考答案

### 练习 A：合并两个有序数组

给定两个从小到大排列的 64 位整数数组，返回一个包含全部元素的新有序数组。重复值应保留，输入不能修改。要求 `O(n + m)` 时间。

<details>
<summary>思路、伪代码与完整 C++20 答案</summary>

暴力基线可以连接两个数组后完整排序，时间 `O((n+m) log(n+m))`。关键观察是两个输入各自有序；每次未输出元素中的最小值，只可能是两个当前头部之一。

不变量：进入每轮比较前，`result` 已按序包含两个输入已消费前缀中的全部元素；两个指针分别指向尚未消费的第一个元素。

```text
i = 0, j = 0, result = 空数组

当 i 未到第一个数组末尾 且 j 未到第二个数组末尾：
    把两个当前元素中较小者加入 result
    移动对应指针

把尚未结束的数组剩余部分依次加入 result
返回 result
```

每个元素恰好加入一次，时间 `O(n + m)`；除返回结果外额外使用 `O(1)` 状态，返回结果本身为 `O(n + m)`。

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <vector>

[[nodiscard]] std::vector<std::int64_t> merge_sorted(
    const std::vector<std::int64_t>& left_values,
    const std::vector<std::int64_t>& right_values) {
    std::vector<std::int64_t> result;
    result.reserve(left_values.size() + right_values.size());

    std::size_t i = 0;
    std::size_t j = 0;
    while (i < left_values.size() && j < right_values.size()) {
        if (left_values[i] <= right_values[j]) {
            result.push_back(left_values[i]);
            ++i;
        } else {
            result.push_back(right_values[j]);
            ++j;
        }
    }

    while (i < left_values.size()) {
        result.push_back(left_values[i]);
        ++i;
    }
    while (j < right_values.size()) {
        result.push_back(right_values[j]);
        ++j;
    }
    return result;
}

int main() {
    assert(merge_sorted({}, {}).empty());
    assert((merge_sorted({1, 3}, {}) == std::vector<std::int64_t>{1, 3}));
    assert((merge_sorted({}, {2, 4}) == std::vector<std::int64_t>{2, 4}));
    assert((merge_sorted({1, 3, 5}, {2, 4, 6})
            == std::vector<std::int64_t>{1, 2, 3, 4, 5, 6}));
    assert((merge_sorted({1, 2, 2}, {2, 2, 3})
            == std::vector<std::int64_t>{1, 2, 2, 2, 2, 3}));
    assert((merge_sorted({-5, -1}, {-3, 0})
            == std::vector<std::int64_t>{-5, -3, -1, 0}));
    std::cout << "all merge checks passed\n";
}
```

真实程序在计算 `left_values.size() + right_values.size()` 前还可能需要考虑极端容量溢出和分配失败；普通算法题通常由输入规模保证结果可表示、可分配。

</details>

### 练习 B：出现次数最多的值

返回数组中出现次数最多的值；若有多个值次数相同，返回数值较小者；空数组返回空。

<details>
<summary>思路、伪代码与完整 C++20 答案</summary>

暴力办法可对每个位置重新扫描并计数，时间 `O(n²)`。使用哈希映射保存每个值的次数，先完成计数，再扫描映射选出“次数最大，次数相同则数值最小”的候选。

```text
如果输入为空：返回空

创建映射 counts
对每个 value：counts[value] 增加 1

best 尚未设置
对每个 (value, count)：
    如果 best 未设置，或 count 更大，或次数相同且 value 更小：
        更新 best
返回 best.value
```

哈希操作按平均情况计算时，时间 `O(n)`、额外空间 `O(u)`，其中 `u` 是不同数值数量，最坏 `u = n`。不依赖哈希表的遍历顺序，因为平局规则写进了比较条件。

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <optional>
#include <unordered_map>
#include <vector>

[[nodiscard]] std::optional<std::int64_t> most_frequent_value(
    const std::vector<std::int64_t>& values) {
    if (values.empty()) {
        return std::nullopt;
    }

    std::unordered_map<std::int64_t, std::size_t> counts;
    counts.reserve(values.size());
    for (const std::int64_t value : values) {
        ++counts[value];
    }

    std::optional<std::int64_t> best_value;
    std::size_t best_count = 0;
    for (const auto& [value, count] : counts) {
        if (!best_value || count > best_count
            || (count == best_count && value < *best_value)) {
            best_value = value;
            best_count = count;
        }
    }
    return best_value;
}

int main() {
    assert(!most_frequent_value({}).has_value());
    assert(most_frequent_value({7}) == 7);
    assert(most_frequent_value({4, 2, 4, 3, 2, 4}) == 4);
    assert(most_frequent_value({5, 5, 2, 2}) == 2);
    assert(most_frequent_value({-1, 3, -1, 3}) == -1);
    std::cout << *most_frequent_value({4, 2, 4, 3, 2, 4}) << '\n';
}
```

</details>

## 小结

C++ 工具箱的目标不是让代码充满模板，而是让数据结构直接对应算法需要维护的事实：集合回答“是否见过”，映射保存“键对应什么状态”，队列和栈规定取出顺序，堆快速暴露当前极值，`optional` 明确表达“可能没有答案”。先用伪代码确定这些语义，再选择最小的标准库工具，翻译会稳定得多。

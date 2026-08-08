# 从题意到程序：用一道题建立固定解题流程

第一次看到算法题时，脑中一片空白很正常。真正可训练的能力不是“立刻想到最优解”，而是即使暂时没想到，也知道下一步该做什么。本章用一道很小的题走完整个流程：先写一定正确的办法，再找重复工作，最后翻译成 C++20 并主动测试。

## 1. 白话题意：两数之和到底在问什么

题目如下：

> 给定一组 32 位整数 `values` 和一个 64 位整数 `target`。请找出两个**不同位置**，使这两个位置上的数之和等于 `target`。找到任意一组即可；没有答案时返回空。

先把它改写成自己的话：

```text
我要从数组中挑两个不同下标 i 和 j，
让 values[i] + values[j] == target。
找到一组就返回两个下标，否则明确表示没有。
```

这里有三个容易漏掉的词：

- 返回的是**下标**，不是数值；
- 两个位置必须不同，因此一个元素不能使用两次；
- “任意一组”表示不要求字典序最小，也不要求找出全部答案。

如果面试官没有说明这些条件，应先询问。在线笔试无法询问时，就从题面、函数签名和样例中确认，仍不清楚则把合理假设写在注释或答案说明中。

## 2. 先检查约束，不急着套题型

本章采用以下约束：

- `values` 可以为空，也可以只有一个元素；
- 元素可以为负数、零或重复；
- 不允许修改输入；
- 只返回任意一组合法下标；
- 数组元素是 `std::int32_t`，计算时扩大到 `std::int64_t`；
- `n` 表示元素数量。

最后两条很重要。两个 32 位有符号整数相加一定能放入 64 位有符号整数，因此先扩大再计算，可以避免 32 位有符号溢出的未定义行为。优化版还会先排除“不可能由两个 32 位整数相加得到”的极端 `target`，这样后续的 `target - value` 也始终落在 64 位范围内。

先手算几个例子：

| 输入 | `target` | 结果 | 原因 |
|---|---:|---|---|
| `[2, 7, 11, 15]` | 9 | `(0, 1)` | `2 + 7 = 9` |
| `[3, 3]` | 6 | `(0, 1)` | 数值可相同，但下标不同 |
| `[3]` | 6 | 空 | 同一个位置不能用两次 |
| `[-4, 7, 2]` | 3 | `(0, 1)` | 负数也合法 |
| `[]` | 0 | 空 | 没有两个位置 |

## 3. 暴力基线：把题意直接翻译成枚举

最直接的办法是枚举所有下标对：先选左边的 `i`，再选右边的 `j`。为了不重复检查 `(i, j)` 和 `(j, i)`，只让 `j > i`。

```text
对于 i 从 0 到 n - 1：
    对于 j 从 i + 1 到 n - 1：
        如果 values[i] + values[j] 等于 target：
            返回 (i, j)
返回空
```

这个办法为什么不会漏？任意两个不同下标总有一个较小、一个较大；把较小者记作 `i`、较大者记作 `j`，嵌套循环一定会检查这一对。

它的时间复杂度是 `O(n²)`，因为最坏情况下要检查大约

\[
\frac{n(n-1)}{2}
\]

对元素。除返回结果外，它只使用常数个局部变量，额外空间是 `O(1)`。

`O(n²)` 不等于“永远不能用”。若 `n` 最多只有 20，它可能已经足够简单可靠；若 `n` 可以达到十万，就需要减少重复扫描。

## 4. 关键观察：第二个数其实已经被第一个数决定

当正在查看 `value` 时，与它配对的数必须是：

\[
needed = target - value
\]

因此我们不必再次扫描所有旧元素，只需回答一个问题：`needed` 之前是否出现过？

这正是哈希表适合处理的查询。为了返回下标，我们保存“数值 → 某个已出现下标”的映射。

### 4.1 循环不变量

在开始处理下标 `j` 之前，维护下面的不变量：

> `seen` 中恰好记录了区间 `[0, j)` 内已经处理过的数值及其下标。

先查询、后插入当前值很关键。这样，查到的下标一定小于 `j`，不会把同一个位置使用两次。

如果数组是 `[3, 3]`，处理第二个 `3` 时，第一个 `3` 已在 `seen` 中，因此仍能正确找到重复数值组成的答案。

## 5. 语言无关伪代码

```text
创建空映射 seen，键是数值，值是下标

对于 j 从 0 到 n - 1：
    value = values[j]
    needed = target - value

    如果 seen 中存在 needed：
        返回 (seen[needed], j)

    如果 seen 中还没有 value：
        记录 seen[value] = j

返回空
```

“只保留某个数值最早出现的下标”不是正确性所必需，但能让行为更稳定，也避免同一个键被反复覆盖。题目只要求任意答案，因此保留最早或最新下标都可以；面试中应说明自己的选择。

## 6. 正确性：为什么它既不会错报，也不会漏报

可以从两个方向说明。

### 6.1 返回答案时一定合法

假设算法在下标 `j` 返回 `(i, j)`：

- 根据不变量，`i` 来自已经处理的区间 `[0, j)`，所以 `i < j`，两个位置不同；
- 查询条件保证 `values[i] == target - values[j]`；
- 因此 `values[i] + values[j] == target`。

所以算法不会返回一个错误答案。

### 6.2 存在答案时一定能找到

假设存在一组答案 `(p, q)`，且 `p < q`。处理 `q` 之前，`p` 已经处理过，根据不变量，`values[p]` 已记录在 `seen` 中。又因为

\[
values[p] = target - values[q]
\]

处理 `q` 时的查询一定能找到一个合法旧下标并返回。因此算法不会漏掉所有答案。

### 6.3 不变量怎样保持

- 初始化时 `j = 0`，区间 `[0, 0)` 为空，空映射正好记录了其中所有元素；
- 若本轮没有返回，就把 `values[j]` 记录下来；进入下一轮时，映射覆盖的已处理区间变成 `[0, j + 1)`；
- 因此不变量在每一轮都成立。

## 7. 复杂度：说明平均情况，不把哈希说成绝对常数

循环处理 `n` 个元素。若哈希表查询和插入平均为 `O(1)`，则：

- 平均时间复杂度：`O(n)`；
- 额外空间复杂度：`O(n)`。

标准哈希表的最坏情况可能因大量冲突退化，所以不应笼统宣称“严格最坏 `O(n)`”。若输入有序，也可以考虑双指针，用 `O(1)` 额外空间完成；若不允许额外内存，可先复制并排序，但返回原下标会增加处理工作。

## 8. 完整 C++20：同时保留基线作参照

下面的程序包含暴力版、哈希版和一组边界测试。`std::optional` 表示“可能没有答案”，`std::pair` 保存两个下标。

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <optional>
#include <random>
#include <unordered_map>
#include <utility>
#include <vector>

using IndexPair = std::pair<std::size_t, std::size_t>;

[[nodiscard]] std::optional<IndexPair> two_sum_brute_force(
    const std::vector<std::int32_t>& values,
    std::int64_t target) {
    for (std::size_t i = 0; i < values.size(); ++i) {
        for (std::size_t j = i + 1; j < values.size(); ++j) {
            const std::int64_t sum =
                std::int64_t{values[i]} + std::int64_t{values[j]};
            if (sum == target) {
                return IndexPair{i, j};
            }
        }
    }
    return std::nullopt;
}

[[nodiscard]] std::optional<IndexPair> two_sum_hash(
    const std::vector<std::int32_t>& values,
    std::int64_t target) {
    constexpr std::int64_t min_possible_sum =
        std::int64_t{INT32_MIN} + std::int64_t{INT32_MIN};
    constexpr std::int64_t max_possible_sum =
        std::int64_t{INT32_MAX} + std::int64_t{INT32_MAX};
    if (target < min_possible_sum || target > max_possible_sum) {
        return std::nullopt;
    }

    std::unordered_map<std::int64_t, std::size_t> seen;
    seen.reserve(values.size());

    for (std::size_t j = 0; j < values.size(); ++j) {
        const std::int64_t value = values[j];
        const std::int64_t needed = target - value;

        const auto found = seen.find(needed);
        if (found != seen.end()) {
            return IndexPair{found->second, j};
        }

        // try_emplace 不覆盖同一个数值更早出现的下标。
        seen.try_emplace(value, j);
    }
    return std::nullopt;
}

[[nodiscard]] bool is_valid_answer(
    const std::vector<std::int32_t>& values,
    std::int64_t target,
    const std::optional<IndexPair>& answer) {
    if (!answer) {
        return false;
    }
    const auto [i, j] = *answer;
    if (i >= values.size() || j >= values.size() || i == j) {
        return false;
    }
    return std::int64_t{values[i]} + std::int64_t{values[j]} == target;
}

void check_case(const std::vector<std::int32_t>& values,
                std::int64_t target) {
    const auto expected = two_sum_brute_force(values, target);
    const auto actual = two_sum_hash(values, target);

    // 题目允许任意一组答案，所以比较“是否存在”，而非强求下标相同。
    assert(expected.has_value() == actual.has_value());
    if (actual) {
        assert(is_valid_answer(values, target, actual));
    }
}

int main() {
    check_case({}, 0);
    check_case({3}, 6);
    check_case({2, 7, 11, 15}, 9);
    check_case({3, 3}, 6);
    check_case({-4, 7, 2}, 3);
    check_case({1, 2, 4, 8}, 99);
    check_case({INT32_MAX, INT32_MIN}, -1);
    check_case({1, 2}, INT64_MIN);
    check_case({1, 2}, INT64_MAX);

    // 固定种子的随机差分测试：每次运行都可复现。
    std::mt19937 generator{20260805U};
    std::uniform_int_distribution<std::int32_t> length_distribution{0, 20};
    std::uniform_int_distribution<std::int32_t> value_distribution{-20, 20};
    std::uniform_int_distribution<std::int32_t> target_distribution{-40, 40};

    for (int round = 0; round < 2'000; ++round) {
        const auto length = static_cast<std::size_t>(length_distribution(generator));
        std::vector<std::int32_t> values(length);
        for (std::int32_t& value : values) {
            value = value_distribution(generator);
        }
        check_case(values, target_distribution(generator));
    }

    const auto answer = two_sum_hash({2, 7, 11, 15}, 9);
    assert(answer.has_value());
    std::cout << answer->first << ' ' << answer->second << '\n';
}
```

`reserve` 用来减少哈希表扩容次数，不改变算法语义，也不保证每次操作都是固定耗时。函数开头的可行和范围检查既能立即拒绝不可能的目标，也避免对极端 64 位目标做可能溢出的减法。差分测试没有证明所有无限可能输入，但能用简单参考实现快速覆盖大量组合，特别适合检查优化版是否改变了行为。

## 9. 边界测试：不要只重复题目样例

上面的测试分别覆盖了：

- 空数组和单元素数组；
- 普通答案；
- 两个相同数值位于不同位置；
- 负数；
- 没有答案；
- 32 位最大值和最小值参与运算；
- 大量小规模随机输入与基线差分。

还有一个容易犯的测试错误：题目允许返回任意一组答案时，不应要求优化版与基线返回完全相同的下标。正确的检查是“两者是否都认为答案存在”，以及返回下标本身是否合法。

## 10. 面试时怎样边写边说

可以用下面的短句让面试官跟上你的思路：

> 我先确认返回任意一组下标，并且同一个位置不能用两次。暴力枚举所有下标对是 `O(n²)`。重复工作是：对每个当前值，我都在重新寻找它需要的配对值。扫描时维护已见数值到下标的映射，就能平均 `O(1)` 查询。我的不变量是处理 `j` 前，映射只包含 `[0,j)`；因此先查后插不会复用当前位置。整体平均时间 `O(n)`、额外空间 `O(n)`。

这段表达同时覆盖了题意、基线、观察、不变量和复杂度。无需在写第一行代码前讲五分钟，但也不要完全沉默。

## 11. 常见错误

### 11.1 先插入当前值，再查找

下面的片段可能在 `values = [3]`、`target = 6` 时错误地使用同一个位置两次：

```cpp,ignore
seen[value] = j;
if (seen.contains(target - value)) {
    return IndexPair{seen[target - value], j};
}
```

### 11.2 把重复数值误认为重复位置

`[3, 3]` 中两个 `3` 的值相同，但位置不同，是合法答案。真正要禁止的是 `i == j`。

### 11.3 直接使用 32 位加法

```cpp,ignore
// 两个 int32_t 先按 32 位相加，可能在转换前已经溢出。
if (values[i] + values[j] == target) {
    // ...
}
```

应在运算前扩大至少一个操作数。

### 11.4 只背“哈希表 O(1)”

哈希表通常给平均常数时间，但碰撞、扩容、哈希质量和输入分布会影响实际行为。面试算法分析要说清平均与最坏，不必因此拒绝使用标准哈希表。

## 12. 追问与参考思路

### Q1：如果输入已经从小到大排序，能否不用哈希表？

可以使用左右双指针。和太小时移动左指针，和太大时移动右指针；时间 `O(n)`、额外空间 `O(1)`。正确性依赖输入有序。

### Q2：如果必须返回所有不重复的数值对呢？

需要先定义“不重复”是下标对不重复还是数值对不重复。排序加双指针便于跳过相同数值；哈希方案也可做，但去重规则必须明确。

### Q3：如果数据是一条不能全部放进内存的流呢？

精确回答通常仍需保存已经见过的相关值，最坏可能增长到 `O(n)`。若内存有硬上限，需要额外业务约束，例如值域有限、只看最近窗口，或允许概率性答案；不能凭空同时保证精确、单遍和常数空间。

### Q4：为什么不一开始就排序？

排序后可以双指针，但若要保留原下标，需要同时保存下标或建立副本；排序通常为 `O(n log n)`，还可能修改输入。它仍是合理替代方案，只是不是当前约束下时间最直接的选择。

## 13. 练习与完整参考答案

先独立完成，再展开答案。建议先写白话题意、暴力办法和至少三个边界样例。

### 练习 A：有序数组中的两数之和

给定一个从小到大排列的 32 位整数数组和 64 位目标值，判断是否存在两个不同位置之和等于目标值。要求 `O(n)` 时间、`O(1)` 额外空间。

<details>
<summary>思路、伪代码与完整 C++20 答案</summary>

关键观察：当前和太小时，右边已经是当前左端能配到的最大值，继续减小右端不可能让和变大，因此应增大左端；当前和太大时同理应减小右端。

不变量：若答案仍可能存在，则至少有一组答案的两个下标都在闭区间 `[left, right]` 内。

```text
left = 0
right = n - 1

当 left < right：
    sum = values[left] + values[right]
    如果 sum == target：返回 true
    如果 sum < target：left 增加 1
    否则：right 减少 1

返回 false
```

每轮至少移动一个指针，最多移动 `n - 1` 次，因此时间 `O(n)`、额外空间 `O(1)`。

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <vector>

[[nodiscard]] bool has_two_sum_sorted(
    const std::vector<std::int32_t>& values,
    std::int64_t target) {
    if (values.size() < 2) {
        return false;
    }

    std::size_t left = 0;
    std::size_t right = values.size() - 1;

    while (left < right) {
        const std::int64_t sum =
            std::int64_t{values[left]} + std::int64_t{values[right]};
        if (sum == target) {
            return true;
        }
        if (sum < target) {
            ++left;
        } else {
            --right;
        }
    }
    return false;
}

int main() {
    assert(!has_two_sum_sorted({}, 0));
    assert(!has_two_sum_sorted({3}, 6));
    assert(has_two_sum_sorted({1, 2, 4, 8}, 10));
    assert(has_two_sum_sorted({3, 3}, 6));
    assert(has_two_sum_sorted({-8, -3, 0, 7, 12}, 4));
    assert(!has_two_sum_sorted({1, 2, 4, 8}, 7));
    std::cout << "all sorted two-sum checks passed\n";
}
```

</details>

### 练习 B：第一个重复出现的值

按从左到右的扫描顺序，返回第一个“再次出现”的数值。例如 `[4, 2, 7, 2, 4]` 返回 `2`；没有重复值时返回空。

<details>
<summary>思路、伪代码与完整 C++20 答案</summary>

不变量：处理位置 `i` 前，集合 `seen` 恰好包含 `[0, i)` 中出现过的不同数值。因此当前值已在集合中，就说明这是扫描过程中遇到的第一次重复事件。

```text
创建空集合 seen
依次读取 value：
    如果 value 已在 seen 中：
        返回 value
    把 value 加入 seen
返回空
```

平均时间 `O(n)`，额外空间 `O(n)`；哈希操作的最坏情况需要单独说明。

```cpp
#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>
#include <unordered_set>
#include <vector>

[[nodiscard]] std::optional<std::int32_t> first_repeated_value(
    const std::vector<std::int32_t>& values) {
    std::unordered_set<std::int32_t> seen;
    seen.reserve(values.size());

    for (const std::int32_t value : values) {
        const auto [unused, inserted] = seen.insert(value);
        (void)unused;
        if (!inserted) {
            return value;
        }
    }
    return std::nullopt;
}

int main() {
    assert(!first_repeated_value({}).has_value());
    assert(!first_repeated_value({1}).has_value());
    assert(!first_repeated_value({1, 2, 3}).has_value());
    assert(first_repeated_value({4, 2, 7, 2, 4}) == 2);
    assert(first_repeated_value({0, 0}) == 0);
    assert(first_repeated_value({-1, 3, -1}) == -1);
    std::cout << "all repeated-value checks passed\n";
}
```

</details>

## 小结

这道题真正值得带走的不是“Two Sum 用哈希表”，而是一套稳定动作：先精确复述题意，补齐约束，写暴力基线；再找重复工作，用数据结构保存恰好需要的历史信息；写下不变量后再翻译成代码，最后用边界和差分测试主动找错。

当题目换成滑动窗口、树或动态规划时，数据结构会改变，但这套流程不会改变。

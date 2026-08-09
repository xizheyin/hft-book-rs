# 哈希、排序、区间与二分：从快速查找走向单调性

两数之和、区间合并和 `first true` 二分分别训练怎样保存已见信息、利用排序建立扫描不变量、利用单调谓词寻找第一处边界。

## 1. 先修回顾

哈希表在分布合理、负载因子受控时提供平均常数查找，但最坏可以退化到线性；有序树通常提供 `O(log n)` 查找；有序连续表可二分查找，但中间更新通常要移动元素。二分搜索成立的根本条件是候选空间能按某个谓词分成连续的两段，而不只是“数组看起来有序”。哈希、平衡树、B/B+ 树、二分和分块查找的完整定义与实现见[查找结构：二分、平衡树与哈希表](search_structures.md)。

## 2. 母题一：无序数组中的两数之和

### 2.1 白话题意

给定一个**没有排序**的整数数组和目标值 `target`，找两个不同位置，使对应元素之和等于目标值。找到一组即可；不存在时返回空结果。

```text
输入：[4, 7, 1, 5]，target = 6
输出：(2, 3)，因为 1 + 5 = 6
```

### 2.2 暴力解

枚举所有下标对：

```text
for i 从 0 到 n - 1：
    for j 从 i + 1 到 n - 1：
        如果 a[i] + a[j] == target：
            返回 (i, j)
返回“没有答案”
```

时间 `O(n²)`，额外空间 `O(1)`。暴力解很有价值：它容易验证，可以在随机测试中作为优化解的对照答案。

### 2.3 关键观察与不变量

扫描到值 `x` 时，需要知道前面是否出现过 `target - x`。如果把已经见过的“值 → 下标”保存到哈希表，就不必重新扫描前缀。

循环不变量是：**处理下标 `i` 之前，哈希表包含下标 `[0, i)` 中已经见过的值及其某个有效下标。**

先查再插很重要。这样不会把同一个位置同时当作两个数。

### 2.4 伪代码

```text
seen = 空映射

for i 从 0 到 n - 1：
    need = target - a[i]
    如果 seen 中存在 need：
        返回 (seen[need], i)
    如果 seen 中还没有 a[i]：
        seen[a[i]] = i

返回“没有答案”
```

只保留某个值第一次出现的下标，能让结果更稳定；本题只要求返回任意一组，因此保留最后一次也可以，但必须说清语义。

### 2.5 为什么正确

如果算法在下标 `i` 找到 `need`，根据不变量，`need` 来自某个更早下标 `j < i`。二者位置不同，而且 `a[j] + a[i] = target`，返回结果正确。

反过来，假设存在答案 `(p, q)` 且 `p < q`。扫描到 `q` 之前，`a[p]` 已经存入哈希表；处理 `q` 时，算法查询的补数正是 `target - a[q] = a[p]`，因此一定能找到某组答案。

### 2.6 复杂度

- 平均或期望时间：`O(n)`；
- 哈希表严重碰撞时的最坏时间：可能达到 `O(n²)`；
- 额外空间：`O(n)`。

如果场景要求确定的最坏复杂度，可以考虑排序后双指针 `O(n log n)`，或有序树映射 `O(n log n)`。

### 2.7 完整 C++20 实现

哈希键使用 `long long`，让 `target - value` 的计算不在 `int` 中溢出。

```cpp
#include <cassert>
#include <cstddef>
#include <optional>
#include <unordered_map>
#include <utility>
#include <vector>

using IndexPair = std::pair<std::size_t, std::size_t>;

std::optional<IndexPair> two_sum_unsorted(
    const std::vector<int>& values,
    int target) {
    std::unordered_map<long long, std::size_t> seen;
    seen.reserve(values.size());

    for (std::size_t i = 0; i < values.size(); ++i) {
        const long long value = values[i];
        const long long need = static_cast<long long>(target) - value;

        if (const auto it = seen.find(need); it != seen.end()) {
            return IndexPair{it->second, i};
        }
        seen.try_emplace(value, i);
    }
    return std::nullopt;
}

int main() {
    {
        const std::vector<int> values{4, 7, 1, 5};
        const auto answer = two_sum_unsorted(values, 6);
        assert(answer.has_value());
        assert(answer->first == 2);
        assert(answer->second == 3);
    }
    {
        const std::vector<int> values{3, 3};
        const auto answer = two_sum_unsorted(values, 6);
        assert(answer.has_value());
        assert(answer->first == 0);
        assert(answer->second == 1);
    }
    assert(!two_sum_unsorted({1, 2, 3}, 100).has_value());
    assert(!two_sum_unsorted({}, 0).has_value());
}
```

`reserve` 可以减少已知规模下的重复扩容，但不是正确性要求，也不能保证没有碰撞。

### 2.8 测试时还要想什么

- 空数组、一个元素；
- 两个相同的值恰好组成答案；
- 同一个值出现多次；
- 负数和零；
- 目标不存在；
- 接近整数上下界的输入。

### 2.9 常见追问

1. **为什么不能先插入当前值再查？** 当 `target == 2 * value` 时，可能错误地重复使用当前下标。
2. **需要返回全部下标对怎么办？** 映射值到下标列表，或在扫描时输出所有匹配的历史下标；结果本身可能有 `O(n²)` 个。
3. **内存只允许 `O(1)` 怎么办？** 若允许修改输入，可排序后双指针，但需要额外处理原下标。
4. **数据源是无限流呢？** 若不设窗口，保存历史值的内存会持续增长；必须定义时间窗口、容量或过期策略。

## 3. 母题二：合并重叠的半开区间

### 3.1 白话题意

给定若干半开区间 `[start, end)`，合并所有真正重叠的区间，返回按起点升序排列、互不重叠的结果。

```text
输入：[1, 4)、[2, 6)、[8, 10)、[9, 12)
输出：[1, 6)、[8, 12)
```

本章约定 `start < end`。由于采用半开区间，`[1, 3)` 和 `[3, 5)` 只是相邻，并没有共同元素，默认不合并。若业务把端点相接也视为连续，条件需要相应改变。

### 3.2 暴力思路

可以反复寻找任意一对重叠区间，合并后再从头检查，直到没有变化。这个过程难以维护，朴素实现可能达到 `O(n²)` 甚至做更多重复工作。

问题在于输入没有顺序。一个区间可能与列表中很远的位置重叠。

### 3.3 关键观察与不变量

先按 `start` 升序排序。排序后，如果下一个区间与当前合并区间都不重叠，那么它更不可能与更早已经输出的区间重叠。

扫描时维护 `current`。循环不变量是：

1. `output` 中的区间已经按起点排序且互不重叠；
2. `output` 加上 `current`，精确表示所有已处理输入区间的并集；
3. `current` 是已处理区间中最靠右、尚未最终输出的合并结果。

### 3.4 伪代码

```text
验证每个区间满足 start < end
按 start 升序排序；start 相同则按 end 升序

current = 第一个区间
output = 空列表

for next 遍历剩余区间：
    如果 next.start < current.end：
        current.end = max(current.end, next.end)
    否则：
        把 current 加入 output
        current = next

把最后的 current 加入 output
返回 output
```

### 3.5 为什么正确

排序保证后续区间的起点不会小于当前区间的起点。

- 若 `next.start < current.end`，两个半开区间存在重叠，它们的并集仍是一个区间；把右端更新为两者最大值完全保留了并集。
- 若 `next.start >= current.end`，`next` 以及之后所有区间的起点都不会早于 `current.end`，因此再也没有区间能与 `current` 重叠。此时输出 `current` 是安全的。

每一步都保持不变量，最后输出剩余的 `current`，结果恰好覆盖全部输入且没有重叠。

### 3.6 复杂度

- 排序时间：`O(n log n)`；
- 排序后的扫描：`O(n)`；
- 输出之外的额外空间取决于排序实现，通常为 `O(log n)` 级递归/辅助状态；本实现按值接收输入，因此还持有一份可修改副本。

总时间由排序主导，为 `O(n log n)`。

### 3.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <stdexcept>
#include <vector>

struct Interval {
    long long start;
    long long end;

    bool operator==(const Interval&) const = default;
};

std::vector<Interval> merge_overlapping(
    std::vector<Interval> intervals) {
    for (const Interval& interval : intervals) {
        if (interval.start >= interval.end) {
            throw std::invalid_argument("interval must satisfy start < end");
        }
    }
    if (intervals.empty()) {
        return {};
    }

    std::sort(intervals.begin(), intervals.end(),
              [](const Interval& lhs, const Interval& rhs) {
                  if (lhs.start != rhs.start) {
                      return lhs.start < rhs.start;
                  }
                  return lhs.end < rhs.end;
              });

    std::vector<Interval> merged;
    merged.reserve(intervals.size());
    Interval current = intervals.front();

    for (std::size_t i = 1; i < intervals.size(); ++i) {
        const Interval& next = intervals[i];
        if (next.start < current.end) {
            current.end = std::max(current.end, next.end);
        } else {
            merged.push_back(current);
            current = next;
        }
    }
    merged.push_back(current);
    return merged;
}

int main() {
    const std::vector<Interval> expected{{1, 6}, {8, 12}};
    assert(merge_overlapping(
               {{8, 10}, {1, 4}, {9, 12}, {2, 6}}) == expected);

    // 半开区间端点相接不算重叠。
    const std::vector<Interval> touching{{1, 3}, {3, 5}};
    assert(merge_overlapping(touching) == touching);

    const std::vector<Interval> nested{{1, 10}};
    assert(merge_overlapping({{1, 10}, {2, 3}}) == nested);
    assert(merge_overlapping({}).empty());

    bool rejected = false;
    try {
        static_cast<void>(merge_overlapping({{4, 4}}));
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);
}
```

比较器必须形成严格弱序。直观上，`comp(x, x)` 必须为假，不能写成 `lhs.start <= rhs.start`。错误比较器会破坏排序算法的前提。

### 3.8 测试时还要想什么

- 空输入和单个区间；
- 输入原本无序；
- 一个区间完全包含另一个；
- 多个区间连锁重叠；
- 端点刚好相接；
- 非法空区间或反向区间；
- 起点相同、终点不同。

### 3.9 常见追问

1. **闭区间 `[start, end]` 怎么改？** 若端点相等算重叠，判断改为 `next.start <= current.end`，同时重新确认离散/连续语义。
2. **怎样求最大同时重叠数量？** 把起点和终点变成事件并排序扫描；相同坐标的事件先后顺序由区间语义决定。
3. **区间持续在线到达怎么办？** 需要维护有序结构；若到达顺序本身按起点有序，就可以流式合并。
4. **为什么不直接使用哈希表？** 区间重叠依赖大小关系，不是精确键相等；排序更能暴露所需结构。

## 4. 母题三：第一个不小于目标值的位置

### 4.1 白话题意

给定一个非递减数组，返回第一个满足 `a[i] >= target` 的下标。如果所有元素都小于目标，返回 `n`。

```text
输入：[1, 2, 2, 2, 7]，target = 2
输出：1
```

这不是只找“有没有 2”，而是在找**第一个条件为真**的位置。把二分理解成 `first true`，比背许多 `+1/-1` 模板更稳定。

### 4.2 暴力解

从左到右扫描，第一个 `a[i] >= target` 就返回：

```text
for i 从 0 到 n - 1：
    如果 a[i] >= target：返回 i
返回 n
```

时间 `O(n)`，空间 `O(1)`。

### 4.3 关键观察与不变量

因为数组非递减，谓词 `a[i] >= target` 的结果形如：

```text
false false false true true true
```

一旦变成 `true`，后面不会重新变回 `false`。这就是二分需要的单调性。

维护半开搜索区间 `[left, right)`，不变量是：

- `[0, left)` 中的下标已经确认全部为 `false`；
- `[right, n)` 中的下标已经确认全部为 `true`；
- 第一个 `true` 若存在，一定在 `[left, right]` 的边界位置中。

`n` 被当作“虚拟的 true 哨兵”：当真实元素都不满足时，答案就是 `n`。

### 4.4 伪代码

```text
left = 0
right = n

while left < right：
    mid = left + (right - left) / 2
    如果 a[mid] >= target：
        right = mid
    否则：
        left = mid + 1

返回 left
```

使用 `left + (right - left) / 2`，避免 `left + right` 在固定宽度整数中溢出。

### 4.5 为什么正确

若 `a[mid] >= target`，`mid` 可能就是第一个真位置，不能排除它；但 `mid` 右侧不可能更早，所以令 `right = mid`。

若 `a[mid] < target`，根据有序性，`mid` 及其左侧都不可能满足条件，因此令 `left = mid + 1`。

每轮都保持不变量并缩小搜索范围。结束时 `left == right`，所有更小下标均为假，当前位置及其后均为真；所以 `left` 正是第一个真位置，或没有真实真位置时的 `n`。

### 4.6 复杂度

- 时间复杂度：`O(log n)`；
- 额外空间：`O(1)`。

二分减少的是**判断次数**。如果底层结构不支持常数时间随机访问，例如链表，即使写出二分形式，定位中点也可能很慢。

### 4.7 完整 C++20 实现

```cpp
#include <cassert>
#include <cstddef>
#include <vector>

std::size_t first_not_less(
    const std::vector<int>& values,
    int target) {
    std::size_t left = 0;
    std::size_t right = values.size();

    while (left < right) {
        const std::size_t mid = left + (right - left) / 2;
        if (values[mid] >= target) {
            right = mid;
        } else {
            left = mid + 1;
        }
    }
    return left;
}

int main() {
    const std::vector<int> values{1, 2, 2, 2, 7};
    assert(first_not_less(values, 2) == 1);
    assert(first_not_less(values, 3) == 4);
    assert(first_not_less(values, 0) == 0);
    assert(first_not_less(values, 8) == values.size());
    assert(first_not_less({}, 5) == 0);
}
```

标准库已经提供等价工具：`std::lower_bound(begin, end, target)`。面试中手写是为了展示边界推理，工程代码通常优先使用经过充分测试的标准算法。

### 4.8 测试时还要想什么

- 空数组；
- 目标小于所有元素或大于所有元素；
- 目标恰好存在且有重复；
- 单元素数组；
- 所有元素相同；
- 返回值允许等于 `n`，调用方不能直接无条件取 `values[index]`。

### 4.9 常见追问

1. **最后一个小于目标的位置呢？** `first_not_less(target) - 1`，但要先处理返回 `0`，否则无符号下标会下溢。
2. **第一个大于目标的位置呢？** 把谓词改为 `a[mid] > target`，等价标准工具是 `std::upper_bound`。
3. **能否二分答案而不是数组？** 可以，只要候选答案有序且“某答案是否可行”具有单调性。
4. **旋转数组还能直接用这个模板吗？** 整体谓词不再是简单的假后真，需要利用哪一半仍有序等额外结构。

## 5. `first true` 的通用检查表

写二分前先回答：

1. 候选答案的范围是什么？
2. 谓词为什么单调？是“假、假、真、真”，还是相反？
3. 没有真实答案时返回什么哨兵？
4. 循环中哪一侧已经被证明为假，哪一侧被证明为真？
5. `mid` 满足条件时是否仍可能是答案？如果可能，就不能用 `mid - 1` 随意排除。

若说不清这些问题，换一种模板只会暂时掩盖边界错误。

## 6. 变体练习

### 练习 1：第一个重复值

给定整数数组，返回按扫描顺序第一个“此前已经出现过”的值；没有重复则返回空。

<details>
<summary>思路与答案</summary>

维护 `unordered_set<int> seen`。从左到右扫描，插入返回失败时，当前值就是第一个重复值。循环不变量是 `seen` 恰好包含当前下标之前出现过的所有不同值。平均时间 `O(n)`、空间 `O(n)`；最坏时间仍可能退化。

</details>

### 练习 2：按交易品种聚合数量

输入若干 `(symbol, quantity)`，求每个 `symbol` 的总数量，并讨论输出顺序。

<details>
<summary>思路与答案</summary>

若不要求顺序，用 `unordered_map<string, long long>` 累加；若要求按品种字典序输出，可改用 `map`，或聚合后把键复制到数组并排序。数量使用足够宽的类型，并定义溢出策略。选择容器前必须先确认是否需要稳定或排序后的输出。

</details>

### 练习 3：插入新区间

已有按起点排序、互不重叠的半开区间，插入一个新区间并保持这些性质。

<details>
<summary>思路与答案</summary>

先输出所有结束位置不晚于新区间起点的区间；随后合并所有与新区间真正重叠的区间；最后输出剩余区间。因为原输入已经排序且互不重叠，不需要重新排序，时间 `O(n)`。端点相接是否合并仍取决于区间语义。

</details>

### 练习 4：整数平方根

给定非负整数 `x`，返回满足 `r² <= x` 的最大整数 `r`。要求避免乘法溢出。

<details>
<summary>思路与答案</summary>

可以寻找第一个满足 `m > x / m` 的正整数，再减一；除法形式避免直接计算 `m * m` 溢出。要单独处理 `m = 0`，并明确搜索区间和无答案哨兵。也可以使用足够宽的整数类型，但仍要证明该类型容得下平方。

</details>

### 练习 5：最小可行容量

有一串非负任务量，要按原顺序分到不超过 `d` 个批次。求每批容量的最小可行值。

<details>
<summary>思路与答案</summary>

候选容量范围从“最大单个任务量”到“全部任务量之和”。给定容量后贪心装批，可以在线性时间判断是否能在 `d` 批内完成。容量越大越容易可行，因此谓词呈“假后真”，可用 `first true` 二分。总时间 `O(n log S)`，其中 `S` 是容量搜索范围；累加要防溢出。

</details>

## 7. 章末做题方法：哈希、区间与二分边界

1. **读题判断信息来源**：需要按值反查历史元素用哈希；处理重叠范围先排序；在单调谓词上找边界才用二分。
2. **哈希题写键值语义**：键是什么、值保存计数还是下标、查询发生在插入前还是后；用重复元素手推避免自己配对自己。
3. **区间题统一端点**：明确闭区间还是半开区间，排序键和“可合并”条件写成数学不等式，再推演相邻、相交和包含。
4. **二分题先写谓词**：确定 `[lo,hi)` 中哪些位置为 false/true，循环保持答案仍在区间；每轮取中点后只保留含边界的一侧。
5. **验算**：空、单元素、全小于/大于目标、重复目标和答案位于首尾；返回位置应满足左侧不符合、当前位置符合。

常见陷阱：没有单调性硬二分；闭/开区间模板混用；`mid` 更新不缩区间；哈希下标被重复值错误覆盖；相邻半开区间误判重叠。

## 8. 面试复述清单

- `unordered_map` 的平均和最坏复杂度分别是什么？
- 两数之和为什么必须先查补数再插入当前值？
- 区间端点相接是否合并，为什么不是纯算法问题？
- 排序扫描时维护的合并不变量是什么？
- `first true` 中 `[0, left)` 和 `[right, n)` 分别代表什么？
- 为什么二分答案前必须证明可行性谓词单调？

能写出代码只是第一步；能主动讲清这些边界，才说明你掌握了方法。

# 排序与选择：不一定要把所有元素排好

排序题不只是“调用 `sort`”。在本书目标岗位中，更常见的追问是：

1. 题目需要完整顺序，还是只需要第 `k` 个或前 `k` 个？
2. 相等元素的原始顺序是否必须保留？
3. 比较器是否真的定义了一个合法顺序？
4. 快速排序或快速选择为什么会退化，随机化解决了什么、又没有保证什么？

本章从稳定性和比较器开始，再用归并排序、三路快速排序、Quickselect 解释库算法背后的不变量，并把它们与 `sort`、`stable_sort`、`nth_element`、`partial_sort` 放到同一张选择地图里。

> **本章目标**：P0 是会选择标准库算法、说明稳定性并写合法比较器；P1 是能手推归并和分区不变量；P2 才要求闭卷手写三路快排或随机化 Quickselect。普通系统/HFT 面试准备不应被 P2 阻塞。

本章题目是通用训练题，不代表任何公司的原题。所有完整示例均为独立 C++20 程序。

## 1. 先分清“排序”和“选择”

假设有 `n` 个数：

- **完整排序**：确定所有元素的先后关系；
- **第 `k` 小**：只确定目标排名上的元素；
- **最小的 `k` 个**：只确定哪些元素属于前 `k`，内部可能还需要排序；
- **Top-K 流式维护**：数据不断到达，只保留当前最优的 `k` 个。

若只要中位数，把所有元素完整排序当然正确，却额外确定了许多题目没有要求的关系。选择算法正是利用“答案要求更少”来减少平均工作。

C++20 常用工具：

| 需求 | 常用工具 | 典型复杂度 | 结果性质 |
|---|---|---|---|
| 完整排序，不要求稳定 | `std::sort` | `O(n log n)` 最坏比较量级 | 全部有序 |
| 完整排序，要求稳定 | `std::stable_sort` | 有足够辅助内存时 `O(n log n)`；否则比较次数可能到 `O(n log² n)` | 等价元素保留原顺序 |
| 第 `k` 小或无序前 `k` | `std::nth_element` | 平均 `O(n)` 比较 | 目标位置正确，两侧未完全排序 |
| 排好最小的 `k` 个 | `std::partial_sort` | 约 `O(n log k)` | 前 `k` 个有序 |
| `k` 很小或数据流式到达 | 大小为 `k` 的堆 | `O(n log k)` | 保存 Top-K，可再排序输出 |

复杂度只是第一层。还要看是否允许修改输入、是否要求稳定、内存限制、数据是否大量重复，以及最坏延迟是否重要。

## 2. 稳定排序到底保留什么

### 2.1 稳定不等于“结果更正确”

若两个元素在比较器看来等价，稳定排序保证它们在输出中的相对顺序与输入相同。

假设订单先按到达顺序排列：

```text
(A, priority=2), (B, priority=1), (C, priority=2)
```

只按 `priority` 降序稳定排序后，`A` 仍在 `C` 前：

```text
A, C, B
```

不稳定排序可能输出 `C, A, B`，但这不表示它排序错误；`A` 和 `C` 在比较器看来本来就没有先后要求。只有业务要求保留原顺序时，稳定性才是正确性的一部分。

还要注意，“等价”由比较器定义，不一定等于 `operator==`：

```text
a 与 b 等价 <=> comp(a,b) 为 false 且 comp(b,a) 也为 false
```

### 2.2 母题一：按优先级稳定排列任务

#### 白话题意

任务已经按到达顺序放在数组中。按优先级从高到低排列；优先级相同时必须保持到达顺序。

#### 伪代码

```text
对 tasks 做稳定排序
比较规则：只有 left.priority > right.priority 时，left 才排在 right 前
返回 tasks
```

#### 为什么正确

稳定排序保证不同优先级按照比较器降序排列。相同优先级时，两个方向的比较都为假，它们属于等价元素；稳定性保证这些元素的原始先后不变。因此两个业务要求同时满足。

#### 复杂度

`stable_sort` 的具体实现可能根据辅助内存采用不同算法。在通常能够取得线性辅助缓冲时，时间为 `O(n log n)`，额外缓冲为 `O(n)`；标准允许内存不足时使用比较次数更高的稳定方案。

#### 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <string>
#include <vector>

struct Task {
    std::string name;
    int priority{};

    bool operator==(const Task&) const = default;
};

std::vector<Task> stable_by_priority(std::vector<Task> tasks) {
    std::stable_sort(tasks.begin(), tasks.end(),
                     [](const Task& left, const Task& right) {
                         return left.priority > right.priority;
                     });
    return tasks;
}

int main() {
    const std::vector<Task> input{
        {"A", 2}, {"B", 1}, {"C", 2}, {"D", 1}, {"E", 3}};
    const std::vector<Task> expected{
        {"E", 3}, {"A", 2}, {"C", 2}, {"B", 1}, {"D", 1}};

    assert(stable_by_priority(input) == expected);
    assert(stable_by_priority({}).empty());
    assert((stable_by_priority({{"only", 7}}) ==
            std::vector<Task>{{"only", 7}}));
}
```

#### 测试

不要只检查优先级是否降序。还要特意放入多组相同优先级，检查每组内部的到达顺序。空输入、单元素、全部相等也要覆盖。

## 3. 比较器必须形成严格弱序

`std::sort`、`stable_sort`、`priority_queue` 和许多有序容器都依赖比较器。对排序算法，`comp(a,b)` 的意思是“`a` 应严格排在 `b` 前”，不是“`a` 不晚于 `b`”。

常见错误是使用 `<=`：

```cpp,ignore
// 错误：当 x == x 时返回 true，不是严格关系。
std::sort(values.begin(), values.end(),
          [](int left, int right) { return left <= right; });
```

合法比较器至少要满足以下直觉：

1. **非自反**：`comp(x,x)` 必须为假；
2. **不对称**：`comp(a,b)` 为真时，`comp(b,a)` 必须为假；
3. **传递**：`a` 在 `b` 前、`b` 在 `c` 前，则 `a` 必须在 `c` 前；
4. “互不在前”的等价关系也必须传递。

违反前置条件后，结果不只是“相等元素顺序不稳定”，而是整个标准算法的行为都不再可靠。

多字段规则应逐层写清：

```cpp,ignore
std::sort(candidates.begin(), candidates.end(),
          [](const Candidate& left, const Candidate& right) {
              if (left.score != right.score) {
                  return left.score > right.score; // 分数降序
              }
              return left.name < right.name;       // 姓名升序
          });
```

平局字段仍完全相同时返回 `false`。不要在最后写 `return true` 来“强行打破平局”。若浮点字段可能含 `NaN`，普通 `<` 未必形成你想要的全序；应先定义 `NaN` 排在何处，或在进入排序前拒绝它。

## 4. P1 原理题：手写稳定归并排序

### 4.1 白话题意

把整数数组从小到大稳定排序。虽然整数本身看不出相等元素身份，代码仍按稳定规则合并，以便将来换成记录类型时保持语义。

### 4.2 从分治到合并

归并排序分成三步：

1. 把 `[left,right)` 分成两个较小的半区间；
2. 分别把左右两半排好；
3. 线性合并两个有序区间。

真正需要证明的是第三步。两个区间已经有序时，全部未输出元素中的最小者一定是左半当前头部或右半当前头部。

### 4.3 伪代码

```text
merge_sort(left, right):
    如果区间长度 <= 1：返回
    mid = left + (right-left)/2
    merge_sort(left, mid)
    merge_sort(mid, right)

    i = left, j = mid
    当两边都还有元素：
        若 right[j] 严格小于 left[i]：取右边
        否则：取左边
    复制两边剩余元素
    把缓冲区结果复制回原区间
```

相等时先取左边，这一行决定了稳定性。如果相等时随意先取右边，数值仍有序，但跨越两个半区间的相等记录会改变原顺序。

### 4.4 不变量与正确性

合并循环开始每一轮时：

> 缓冲区已经包含两个输入区间已消费前缀的全部元素，且顺序正确；`i` 和 `j` 分别指向左右区间尚未消费的最小元素。

每轮取两个头部中较小者，因此新加入元素不大于任何尚未消费元素，缓冲区继续有序，也没有遗漏。某一边耗尽后，另一边本身已经有序，整体追加即可。

长度为零或一的区间天然有序。假设两个更短子区间递归后正确有序，合并证明说明当前区间也正确有序；由区间长度归纳，整个数组最终有序。相等时左半元素先出，而分割前左半元素原本就在右半元素之前，因此稳定性也逐层保持。

### 4.5 复杂度

每一层递归合计处理 `n` 个元素，递归层数为 `O(log n)`：

- 时间：`O(n log n)`，最好和最坏同阶；
- 合并缓冲：`O(n)`；
- 递归调用栈：`O(log n)`。

### 4.6 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <vector>

void merge_sort_range(std::vector<int>& values,
                      std::vector<int>& buffer,
                      std::size_t left,
                      std::size_t right) {
    if (right - left <= 1) {
        return;
    }
    const std::size_t middle = left + (right - left) / 2;
    merge_sort_range(values, buffer, left, middle);
    merge_sort_range(values, buffer, middle, right);

    std::size_t first = left;
    std::size_t second = middle;
    std::size_t output = left;

    while (first < middle && second < right) {
        if (values[second] < values[first]) {
            buffer[output++] = values[second++];
        } else {
            buffer[output++] = values[first++]; // 相等时先取左边
        }
    }
    while (first < middle) {
        buffer[output++] = values[first++];
    }
    while (second < right) {
        buffer[output++] = values[second++];
    }
    std::copy(buffer.begin() + static_cast<std::ptrdiff_t>(left),
              buffer.begin() + static_cast<std::ptrdiff_t>(right),
              values.begin() + static_cast<std::ptrdiff_t>(left));
}

void merge_sort(std::vector<int>& values) {
    std::vector<int> buffer(values.size());
    merge_sort_range(values, buffer, 0, values.size());
}

int main() {
    std::vector<int> values{5, 1, 4, 2, 2, -3, 9};
    merge_sort(values);
    assert((values == std::vector<int>{-3, 1, 2, 2, 4, 5, 9}));

    std::vector<int> empty;
    merge_sort(empty);
    assert(empty.empty());

    std::vector<int> equal{7, 7, 7, 7};
    merge_sort(equal);
    assert((equal == std::vector<int>{7, 7, 7, 7}));

    std::vector<int> sorted{-2, 0, 3, 8};
    merge_sort(sorted);
    assert((sorted == std::vector<int>{-2, 0, 3, 8}));
}
```

### 4.7 测试

- 空数组、单元素；
- 已升序、已降序；
- 大量重复；
- 正负混合；
- 奇数和偶数长度；
- 若元素是记录，显式验证相等键的原下标仍递增。

归并排序的性能较可预测，也容易稳定；代价是通常需要额外缓冲。链表归并可以通过改连接减少元素搬移，但随机访问和缓存局部性又不同，不能只比较一行大 O。

## 5. 快速排序为什么会快，又为什么会退化

快速排序选择一个枢轴 `pivot`，把元素按与枢轴的关系分开，再递归处理两侧。若每次大致均分，递归深度约为 `log n`，每层总扫描量为 `n`，期望时间为 `O(n log n)`。

若每次枢轴都是最小或最大值，问题规模可能只从 `n` 变成 `n-1`：

```text
n + (n-1) + ... + 1 = O(n²)
```

固定选择首元素或尾元素时，已经排序的输入很容易触发这种退化。随机选择枢轴让输入难以持续控制分割形状，使运行时间达到期望 `O(n log n)`；但随机化不把最坏情况从数学上消除，最坏时间仍是 `O(n²)`，递归栈最坏仍可能达到 `O(n)`。

工程中的 `std::sort` 不等同于教科书里最简单的快速排序。标准要求它满足最坏 `O(n log n)` 量级的比较复杂度；常见实现会组合快速排序、堆排序、小数组插入排序等策略。面试手写快速排序时，应说明自己的版本究竟保证什么。

## 6. P2 选读：三路快速排序

### 6.1 为什么不是只有“两边”

普通二路分区把元素分成“小于 pivot”和“其余”。输入含大量重复值时，等于枢轴的元素可能反复进入递归。

三路分区直接得到：

```text
[ 小于 pivot ][ 等于 pivot ][ 大于 pivot ]
```

中间区域已经处于最终正确的值域位置，不需要继续递归。全相等数组一次线性扫描即可结束。

### 6.2 伪代码

对半开区间 `[left,right)`：

```text
随机选择一个元素值作为 pivot
less = left
scan = left
greater = right

while scan < greater:
    如果 a[scan] < pivot:
        交换 a[less] 与 a[scan]
        less++, scan++
    否则如果 a[scan] > pivot:
        greater--
        交换 a[scan] 与 a[greater]
        scan 不动，继续检查刚换来的元素
    否则:
        scan++

递归排序 [left,less)
递归排序 [greater,right)
```

### 6.3 分区不变量

循环每轮开始时维护：

- `[left,less)` 全部小于 `pivot`；
- `[less,scan)` 全部等于 `pivot`；
- `[scan,greater)` 尚未分类；
- `[greater,right)` 全部大于 `pivot`。

遇到小值时把它放入左区，同时扩张小于区和已检查区；遇到大值时把它放入右区，但换到 `scan` 的元素还没分类，所以不能立刻增加 `scan`；遇到相等值只扩张等于区。

循环结束时未知区为空，三段分类完整。中间等值区无需排序，对左右更短区间递归，由归纳可得整个区间有序。

### 6.4 复杂度与稳定性

- 随机枢轴下期望时间：`O(n log n)`；
- 最坏时间：`O(n²)`；
- 期望递归栈：`O(log n)`，最坏 `O(n)`；
- 原地交换，除递归栈外额外空间 `O(1)`；
- 该实现**不稳定**，交换会改变相等元素的相对顺序。

### 6.5 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <random>
#include <utility>
#include <vector>

std::pair<std::size_t, std::size_t> partition_three_way(
    std::vector<int>& values,
    std::size_t left,
    std::size_t right,
    int pivot) {
    std::size_t less = left;
    std::size_t scan = left;
    std::size_t greater = right;

    while (scan < greater) {
        if (values[scan] < pivot) {
            std::swap(values[less], values[scan]);
            ++less;
            ++scan;
        } else if (pivot < values[scan]) {
            --greater;
            std::swap(values[scan], values[greater]);
        } else {
            ++scan;
        }
    }
    return {less, greater}; // 等于 pivot 的半开区间
}

void quick_sort_range(std::vector<int>& values,
                      std::size_t left,
                      std::size_t right,
                      std::mt19937& generator) {
    if (right - left <= 1) {
        return;
    }
    std::uniform_int_distribution<std::size_t> choose(left, right - 1);
    const int pivot = values[choose(generator)];
    const auto [equal_begin, equal_end] =
        partition_three_way(values, left, right, pivot);

    quick_sort_range(values, left, equal_begin, generator);
    quick_sort_range(values, equal_end, right, generator);
}

void quick_sort(std::vector<int>& values) {
    std::mt19937 generator{20260805U};
    quick_sort_range(values, 0, values.size(), generator);
}

int main() {
    std::vector<int> values{4, 1, 4, 2, 4, -1, 2, 9, 4};
    quick_sort(values);
    assert((values == std::vector<int>{-1, 1, 2, 2, 4, 4, 4, 4, 9}));

    std::vector<int> equal(100, 7);
    quick_sort(equal);
    assert((equal == std::vector<int>(100, 7)));

    std::vector<int> descending{5, 4, 3, 2, 1};
    quick_sort(descending);
    assert((descending == std::vector<int>{1, 2, 3, 4, 5}));

    std::vector<int> empty;
    quick_sort(empty);
    assert(empty.empty());
}
```

固定种子让测试可复现，算法仍按伪随机序列选枢轴。真实场景若输入可能由对手构造，需要结合威胁模型选择不可预测种子或直接使用具有最坏界保证的库算法；“换一个种子”不是最坏复杂度证明。

### 6.6 测试

重点覆盖全相等、只有两个不同值、已经升序/降序、枢轴最小或最大、空数组和大量重复。可以再用 `std::sort` 做 oracle，随机生成许多小数组比较完整结果。

## 7. P2 选读：Quickselect 找第 `k` 小

### 7.1 白话题意

给定整数数组和从零开始的排名 `k`，返回第 `k` 小元素。重复值分别占据排名。例如：

```text
values = [7, 2, 2, 9, 4], k = 2
排序后是 [2, 2, 4, 7, 9]
答案是 4
```

`k >= n` 时返回无答案。函数按值接收数组副本，因此不会修改调用者。

### 7.2 关键观察

三路分区后：

- 若 `k < equal_begin`，答案只可能在左边；
- 若 `k >= equal_end`，答案只可能在右边；
- 否则 `k` 落在等值区，答案就是 `pivot`。

与快速排序不同，Quickselect 每轮只继续一侧，不需要把另一侧也排好。

### 7.3 伪代码

```text
如果 k 越界：返回无答案
left = 0, right = n

循环：
    随机选 pivot
    三路分区 [left,right)，得到等值区 [a,b)
    如果 k < a：right = a
    否则如果 k >= b：left = b
    否则：返回 pivot
```

### 7.4 正确性

循环不变量是：原数组按排名为 `k` 的值一定存在于当前区间 `[left,right)`，而区间外元素已经根据分区关系排除。

三路分区后，左区所有值严格小于等值区，右区所有值严格大于等值区。若 `k` 位于某一侧，对侧和等值区都不可能包含该排名答案，可以安全丢弃；若 `k` 落入等值区，该排名上的值必为 `pivot`。每轮区间严格缩小，最终返回正确答案。

### 7.5 复杂度

随机枢轴下，期望处理量形成 `n + 较小子问题 + ...`，期望时间为 `O(n)`；连续选到极端枢轴时最坏为 `O(n²)`。下面使用迭代实现，选择过程本身除随机数状态外为 `O(1)` 额外空间；由于接口复制输入以保护调用者，总空间为 `O(n)`。

### 7.6 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <optional>
#include <random>
#include <utility>
#include <vector>

std::pair<std::size_t, std::size_t> partition_three_way(
    std::vector<int>& values,
    std::size_t left,
    std::size_t right,
    int pivot) {
    std::size_t less = left;
    std::size_t scan = left;
    std::size_t greater = right;
    while (scan < greater) {
        if (values[scan] < pivot) {
            std::swap(values[less++], values[scan++]);
        } else if (pivot < values[scan]) {
            std::swap(values[scan], values[--greater]);
        } else {
            ++scan;
        }
    }
    return {less, greater};
}

std::optional<int> kth_smallest(std::vector<int> values, std::size_t k) {
    if (k >= values.size()) {
        return std::nullopt;
    }

    std::mt19937 generator{20260805U};
    std::size_t left = 0;
    std::size_t right = values.size();

    while (left < right) {
        std::uniform_int_distribution<std::size_t> choose(left, right - 1);
        const int pivot = values[choose(generator)];
        const auto [equal_begin, equal_end] =
            partition_three_way(values, left, right, pivot);

        if (k < equal_begin) {
            right = equal_begin;
        } else if (k >= equal_end) {
            left = equal_end;
        } else {
            return pivot;
        }
    }
    return std::nullopt; // 对合法 k 不会到达
}

int main() {
    const std::vector<int> values{7, 2, 2, 9, 4};
    assert(kth_smallest(values, 0) == 2);
    assert(kth_smallest(values, 1) == 2);
    assert(kth_smallest(values, 2) == 4);
    assert(kth_smallest(values, 4) == 9);
    assert(!kth_smallest(values, 5).has_value());
    assert(!kth_smallest({}, 0).has_value());
    assert(kth_smallest({-1}, 0) == -1);
}
```

### 7.7 测试

- `k=0`、`k=n-1`、`k=n`；
- 空数组、单元素；
- 全相等；
- 重复值跨越目标排名；
- 升序、降序；
- 与“复制后完整排序并取下标 `k`”做随机差分测试。

## 8. 母题五：使用 `nth_element` 取得排好序的最小 K 个

### 8.1 `nth_element` 保证了什么

调用：

```cpp,ignore
std::nth_element(first, nth, last);
```

结束后：

- `nth` 位置拥有“完整排序后应该位于这里”的某个等价元素；
- `[first,nth)` 中没有元素应排在 `nth` 之后；
- `[nth,last)` 中没有元素应排在 `nth` 之前；
- 两侧内部**没有完整排序保证**；
- 算法会重排输入，也不稳定。

因此“调用 `nth_element` 后直接输出前 `k` 个”只适合题目不要求输出有序的情况。若前 `k` 个还需升序，再单独排序这一小段。

还有一个重要边界：`nth` 必须位于 `[first,last)`。当 `k == n` 时，不能把 `begin()+k == end()` 直接当作 `nth` 传入；此时所有元素都要保留，直接完整排序即可。

### 8.2 题意与伪代码

返回最小的 `min(k,n)` 个数，并按升序输出，重复值保留，调用者输入不修改。

```text
copy = values 的副本
keep = min(k, copy.size)
如果 keep == 0：返回空

如果 keep < copy.size：
    nth_element(copy.begin, copy.begin+keep, copy.end)
    删除下标 keep 及之后元素

排序保留下来的 keep 个元素
返回 copy
```

### 8.3 正确性与复杂度

当 `keep<n` 时，`nth_element` 的分区保证前 `keep` 个位置恰好由全局最小的 `keep` 个值占据；删除后面的元素不会丢掉更小值。随后排序只改变这些答案的内部顺序。当 `keep=n` 时保留全部元素并完整排序也显然正确。

- 复制：`O(n)` 时间和空间；
- `nth_element`：平均 `O(n)` 比较；标准接口不应被描述成最坏线性保证；
- 排序答案：`O(k log k)`；
- 总平均时间：`O(n + k log k)`，额外空间由副本 `O(n)` 主导。

### 8.4 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <vector>

std::vector<int> smallest_k_sorted(const std::vector<int>& values,
                                   std::size_t k) {
    std::vector<int> result = values;
    const std::size_t keep = std::min(k, result.size());
    if (keep == 0) {
        return {};
    }

    if (keep < result.size()) {
        std::nth_element(result.begin(),
                         result.begin() + static_cast<std::ptrdiff_t>(keep),
                         result.end());
        result.resize(keep);
    }
    std::sort(result.begin(), result.end());
    return result;
}

int main() {
    assert((smallest_k_sorted({7, 1, 5, 2, 2, 9}, 3) ==
            std::vector<int>{1, 2, 2}));
    assert(smallest_k_sorted({3, 1}, 0).empty());
    assert((smallest_k_sorted({3, 1}, 5) == std::vector<int>{1, 3}));
    assert((smallest_k_sorted({-1, -5, -3}, 1) == std::vector<int>{-5}));
    assert(smallest_k_sorted({}, 4).empty());
}
```

若允许修改输入，可省掉副本；若只要第 `k` 小，可直接读取 `values[k]` 对应的分区位置而不排序前缀；若 `k` 极小且输入来自流，大小为 `k` 的大顶堆可能更合适。

## 9. `partial_sort`、堆与 Quickselect 怎样选

假设需要最小的 `k` 个：

| 情况 | 合理起点 | 原因 |
|---|---|---|
| 必须完整排序 | `sort` / `stable_sort` | 题目确实需要全部顺序 |
| 只要第 `k` 小 | `nth_element` / Quickselect | 不必排序其余元素 |
| 要有序前 `k` | `partial_sort`，或 `nth_element` 后排序前缀 | 都避免完整排序全部元素 |
| 输入不能修改 | 复制后选择，或堆 | 先把修改权写清楚 |
| 数据是无限流 | 固定大小堆 | 不能等待完整输入再分区 |
| 需要稳定的前 `k` 条记录 | 完整复合键或带原序号选择 | `nth_element` 本身不稳定 |
| 强调最坏时间 | `sort` 或有最坏线性保证的专门选择算法 | 随机 Quickselect 只有期望线性 |

`std::partial_sort(first,middle,last)` 会让 `[first,middle)` 成为已经排序的最小元素，常见复杂度约为 `O(n log k)`。当 `k` 很小时，它比“先 `nth_element` 再排序前缀”谁更快，要看实现、元素移动成本和数据分布，不能只凭渐进式下结论。

## 10. P2 知识边界：比较排序下界与非比较排序

只通过两两比较来区分任意输入排列时，完整排序在最坏情况下需要 `Ω(n log n)` 次比较。直觉上，`n` 个不同元素有 `n!` 种可能顺序，而一次真假比较最多把候选情况分成两部分，需要足够深的决策树才能区分它们。

这不表示所有排序都永远不能线性：

- 计数排序利用值域小且离散；
- 基数排序利用数字位结构；
- 桶方法利用额外分布假设。

它们绕开的是“只能把元素当黑盒比较”的模型，同时付出值域、内存或表示方面的前提。面试中说“计数排序 `O(n)`”时，必须把值域大小 `U` 计入为 `O(n+U)`，也要说明负数、稳定性和内存上界。

## 11. 常见错误清单

- 题目只要第 `k` 小，却完整排序后声称这是唯一解；
- 把“不稳定”解释为“输出随机”或“排序错误”；
- 业务要求平局保持到达顺序，却使用不稳定排序且没有加入原序号；
- 比较器使用 `<=` 或在完全相同时仍返回真；
- 多字段比较忘记某个 tie-breaker，导致输出不满足题目规定；
- 浮点键含 `NaN`，却没有定义排序政策；
- 归并时相等元素先取右边，意外破坏稳定性；
- 快排对大量重复元素仍反复递归，没有考虑三路分区；
- 声称随机化“保证”不会退化；
- Quickselect 分区后仍递归两侧，退化成快速排序；
- 把 `nth_element` 后的整个数组当作已经有序；
- `k == n` 时把 `end()` 作为 `nth_element` 的 `nth`；
- 忘记 `k` 是从零还是从一开始；
- 选择算法修改了输入，却没有在接口中说明；
- 只写平均复杂度，不说明最坏情况和递归栈。

## 12. 面试表达模板

拿到排序或排名题，可以按这个顺序说：

1. “我先确认要完整顺序、第 `k` 个，还是有序 Top-K。”
2. “相等元素是否要保持原顺序？输入能否修改？”
3. “正确基线是复制后完整排序，时间 `O(n log n)`。”
4. “如果只要排名，可以用三路 Quickselect / `nth_element`，避免排序无关部分。”
5. “分区不变量是小于、等于、未知、大于四段。”
6. “随机枢轴给期望复杂度，不消除 `O(n²)` 最坏情况。”
7. “比较器必须是严格弱序；平局规则会写进比较器或通过稳定排序保留。”
8. “最后测试空数组、越界 `k`、全相等、重复跨排名、升降序和极值。”

## 13. 面试前自检

P0 主线只要求：

- [ ] 能用一句话解释稳定排序保留的是“比较器等价元素”的原顺序。
- [ ] 能写出严格比较器，并解释为什么不能用 `<=`。
- [ ] 知道 `nth_element` 保证分区但不保证两侧有序。
- [ ] 会根据完整排序、Top-K、稳定性、流式与最坏界选择工具。

学习 P1/P2 后再检查：

- [ ] 能证明归并时当前最小值只可能来自两个头部。
- [ ] 能写出三路分区的四段不变量。
- [ ] 知道大值换到 `scan` 后为什么不能立刻移动 `scan`。
- [ ] 能区分快排的期望、最坏时间和递归空间。
- [ ] 能解释 Quickselect 为什么只继续一侧。
- [ ] 能正确处理 `k=0`、`k=n-1`、`k=n` 和空输入。

排序是“建立全部顺序”，选择是“只回答排名所需的问题”。先确认题目究竟要多少信息，再决定要不要付出完整排序的成本；先定义等价和平局，再决定稳定性与比较器。这样即使题目换成订单、日志、模型候选或风险敞口，底层推理仍然不变。

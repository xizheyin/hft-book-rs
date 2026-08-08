# 排序基础：插入、交换、选择、归并与外部排序

**排序（sorting）**是按照一个确定规则重新排列记录，使关键字满足非递减、非递增或其他规定次序。它不只是把数字从小到大：数据库可以按时间排序日志，任务系统可以按优先级排序对象，相同关键字的先后是否保留也可能影响业务含义。

本章系统讲解教材中的排序方法、性质和计算推演。[排序、分区与选择](sorting_selection.md)集中训练比较器、Quickselect、Top-K 和标准库用法，不重复这里的基础算法主线。

## 1. 先明确排序对象和评价标准

待排序元素常称为**记录（record）**，决定次序的字段称为**关键字（key）**。记录可以还有不参与比较的其他字段。例如：

```text
{name="A", score=90, arrival=1}
```

若只按 `score` 排序，A 与另一个 90 分记录的关键字相等，但两条记录不是同一个对象。

### 1.1 内部排序与外部排序

- **内部排序（internal sorting）**：待排序数据能主要放在内存中，算法成本通常按比较、移动和额外内存分析；
- **外部排序（external sorting）**：数据大到不能同时放进内存，必须分批读写磁盘等外存，主要成本变成 I/O 次数与传输数据量。

“外部”不是指数据来自另一台机器，而是指排序过程必须借助容量更大、访问更慢的外存。

### 1.2 稳定性是什么

若两个记录关键字相等，排序后仍保持它们输入时的相对顺序，则算法是**稳定排序（stable sort）**。

```text
输入：(A, 2), (B, 1), (C, 2)
按第二字段升序的稳定结果：(B, 1), (A, 2), (C, 2)
```

A 与 C 的关键字都为 2，稳定排序保留 A 在 C 前。稳定不是“数值排得更正确”，而是额外保留一条顺序信息。算法的经典稳定性是指采用通常实现时能否保证；某种算法也可能通过增加记录下标或改写实现得到不同性质。

### 1.3 原地排序是什么

本章把只使用 `O(1)` 个与输入规模无关的辅助元素位置称为**原地（in-place）**。递归快速排序还使用调用栈，平均 `O(log n)`、最坏 `O(n)`；因此它常被称为“数组元素原地分区”，但严格统计总辅助空间时不能忽略递归栈。

### 1.4 还要比较哪些维度

| 维度 | 问的是什么 |
|---|---|
| 最好、平均、最坏时间 | 不同输入形状下要做多少比较和移动 |
| 额外空间 | 除输入和输出外还需要多少存储 |
| 稳定性 | 相等关键字记录是否保留原相对顺序 |
| 适应性 | 输入已经部分有序时能否少做工作 |
| 前提 | 是否要求小整数值域、均匀分布或可拆分数字位 |

不能只背一个 `O(n log n)`。同阶算法可能有不同最坏保证、内存需求和稳定性；非比较排序还会把值域大小计入成本。

## 2. 为什么比较排序有 `Ω(n log n)` 下界

如果算法只能通过“`a < b` 吗”这类两两比较获取顺序，可以把执行过程想成一棵**决策树**：

- 每次比较有两种结果，对应树的一次分叉；
- `n` 个互异元素有 `n!` 种可能输入排列；
- 为了区分它们，决策树至少要有 `n!` 个叶子；
- 高度为 `h` 的二叉树最多有 `2^h` 个叶子，所以 `2^h ≥ n!`。

于是：

```text
h ≥ log2(n!) = Ω(n log n)
```

这表示任何通用比较排序在最坏情况下都不能保证少于该数量级的比较。计数、桶和基数排序没有推翻下界，因为它们利用了“小整数值域、数字位或分布”等额外结构，不再把元素只当成可以比较的黑盒。

## 3. 直接插入排序：把新牌插进有序手牌

**直接插入排序（insertion sort）**维护一个已排序前缀。处理位置 `i` 时，先保存新元素，把前缀中较大的元素依次右移，再把新元素放进空位。

```text
初始：[5, 2, 4, 6, 1, 3]
插入 2：[2, 5 | 4, 6, 1, 3]
插入 4：[2, 4, 5 | 6, 1, 3]
插入 6：[2, 4, 5, 6 | 1, 3]
插入 1：[1, 2, 4, 5, 6 | 3]
插入 3：[1, 2, 3, 4, 5, 6]
```

竖线左侧表示已经有序的前缀。循环不变量是：开始处理 `i` 时，区间 `[0,i)` 已经有序，并且包含原输入前 `i` 个元素。

若移动条件只写“前一个关键字严格大于新关键字”，相等记录不会越过彼此，因此直接插入稳定。性质为：

- 最好：输入已有序，只比较一轮，`O(n)`；
- 平均和最坏：比较与移动为 `O(n²)`；
- 空间：`O(1)`；稳定、原地、对近乎有序输入适应性好。

它适合小数组或几乎有序的数据，也常作为复杂排序处理很短子区间的收尾算法。

## 4. 折半插入：少比较不等于少移动

**折半插入排序（binary insertion sort）**仍维护有序前缀，只把“从右向左寻找插入位置”改成二分查找。

有序前缀 `[2, 4, 5, 6]` 要插入 3：

```text
先与中间的 5 比：3 应在左半 [2,4]
再与 4 比：3 应在 4 前
再确定它在 2 后
插入位置为下标 1
右移 4、5、6，得到 [2,3,4,5,6]
```

查找位置只需 `O(log i)` 次比较，全部趟的比较次数为 `O(n log n)`；但插入到前部仍要右移 `O(i)` 个元素，总移动和总时间仍可能是 `O(n²)`。

要保持稳定，遇到相等关键字时应把新记录插到已有相等记录之后，也就是寻找“第一个严格大于新关键字的位置”。折半插入适合比较昂贵、移动相对便宜的记录，但不能把它误报成整体 `O(n log n)` 排序。

## 5. Shell 排序：先让相距较远的元素接近正确位置

直接插入每次只能把元素移动一个相邻位置，逆序很远的元素要移动很多次。**Shell 排序（希尔排序）**选择逐渐减小的间隔 `gap`，对每组下标相差 `gap` 的元素做插入排序，最后用 `gap=1` 完成普通插入。

以 `[9,8,3,7,5,6,4,1]`、间隔 `4,2,1` 为例：

```text
gap=4：分别整理 (9,5)、(8,6)、(3,4)、(7,1)
       [5,6,3,1,9,8,4,7]

gap=2：偶数下标组 [5,3,9,4] -> [3,4,5,9]
       奇数下标组 [6,1,8,7] -> [1,6,7,8]
       [3,1,4,6,5,7,9,8]

gap=1：对整体插入排序
       [1,3,4,5,6,7,8,9]
```

前几轮让元素跨越较大距离，最后数组已接近有序，`gap=1` 的移动较少。

Shell 排序的时间复杂度强烈依赖间隔序列。教材常见的每次折半序列最坏可到 `O(n²)`；更好的序列有更好的已知界和实际表现，但不能脱离具体序列只背一个精确复杂度。它使用 `O(1)` 额外空间；相等记录可能在不同间隔组中越过彼此，因此通常不稳定。

## 6. 冒泡排序：每一趟把当前最大者推到末尾

**冒泡排序（bubble sort）**反复比较相邻元素，若前者大于后者就交换。一趟从左到右后，未排序区间中的最大元素一定到达最右端。

```text
初始：[5,1,4,2,8]
第 1 趟：[1,4,2,5 | 8]
第 2 趟：[1,2,4 | 5,8]
第 3 趟没有交换，提前结束：[1,2,4,5,8]
```

每趟结束时，竖线右侧是已经就位的最大元素后缀。只有严格逆序时才交换，可以保持相等记录次序，因此经典冒泡稳定、原地。

带“本趟是否发生交换”标志时，已有序输入最好 `O(n)`；平均和最坏 `O(n²)`。它的教学价值是清楚展示相邻交换和循环不变量，工程排序通常不会把它作为大数组首选。

## 7. 快速排序：一次分区把基准放到最终位置

**快速排序（quicksort）**先选择一个**基准（pivot）**，执行**分区（partition）**，使较小元素在一侧、较大元素在另一侧，再递归排序两侧。

以 Lomuto 分区、最后一个元素 6 为基准：

```text
初始：[4,2,7,3,1,6]，store=0
看 4：放入 <=6 区，store=1
看 2：放入 <=6 区，store=2
看 7：留在右侧候选
看 3：与 store 处的 7 交换 -> [4,2,3,7,1,6]，store=3
看 1：与 7 交换 -> [4,2,3,1,7,6]，store=4
基准与 store 处交换 -> [4,2,3,1,6,7]
```

此时 6 已在最终位置；左边都不大于 6，右边都大于 6。左右内部尚未有序，必须继续递归。

若每次分区大致均衡，递归层数为 `O(log n)`，每层总扫描 `O(n)`，平均时间 `O(n log n)`。若每次基准都是最小或最大，例如对已有序输入始终选末尾，子问题规模变成 `n-1, n-2, ...`，最坏时间 `O(n²)`、递归栈 `O(n)`。

### 7.1 随机基准和三路分区解决什么

- **随机化基准**让固定输入模式更难持续制造极端分割，使期望时间为 `O(n log n)`；它降低坏分区概率，不把单次最坏界改成 `O(n log n)`；
- **三路分区**维护 `< pivot`、`== pivot`、`> pivot` 三段。大量重复值时，中间相等段不再进入递归，可避免反复处理同一关键字；
- **小区间改插入排序**可以减少递归和分区的固定开销。

经典原地快排通常不稳定，因为跨区交换会改变相等记录的相对次序。它的数组访问局部性好、平均常数小，但要求最坏保证时应考虑堆排序、归并排序或混合策略。

## 8. 简单选择排序：每趟选择剩余最小值

**简单选择排序（selection sort）**把数组分为已就位前缀和未排序后缀。每一趟扫描后缀找到最小元素，与后缀首元素交换。

```text
初始：[64,25,12,22,11]
选 11：[11 | 25,12,22,64]
选 12：[11,12 | 25,22,64]
选 22：[11,12,22 | 25,64]
选 25：[11,12,22,25,64]
```

无论输入是否有序，每趟仍要扫描剩余区间，因此比较次数都是 `Θ(n²)`；交换次数至多 `n-1`，适合“移动代价特别高但比较便宜”的小规模场景。

普通交换实现不稳定。例如 `[2A,2B,1]` 第一次找到 1，与 2A 交换得到 `[1,2B,2A]`，两个关键字为 2 的记录次序反转。空间为 `O(1)`，原地。

## 9. 堆排序：用大顶堆反复选择最大值

**堆排序（heap sort）**先把数组建成大顶堆，使最大值位于根；再把根与当前末尾交换，缩小堆范围并向下调整根。末尾逐渐形成有序后缀。

对 `[4,10,3,5,1]`：

```text
自底向上建大顶堆：[10,5,3,4,1]
10 与末尾交换，下滤：[5,4,3,1 | 10]
5 与堆尾交换，下滤：[4,1,3 | 5,10]
4 与堆尾交换，下滤：[3,1 | 4,5,10]
3 与堆尾交换：       [1,3,4,5,10]
```

建堆是 `O(n)`，随后 `n-1` 次删除堆顶各为 `O(log n)`，所以最好、平均、最坏都是 `O(n log n)`。数组内只需常数额外位置，但远距离交换会改变相等记录顺序，因此不稳定。

堆排序提供可靠最坏时间和小额外空间；与快排相比，访问位置跳跃较多，实际缓存局部性常较弱。堆结构、上滤、下滤与线性建堆推导见[树与二叉树：性质、遍历、Huffman 与堆](trees_foundations.md)。

## 10. 归并排序：把两个有序段线性合并

**归并排序（merge sort）**不断把区间分半，分别排好左右两段，再用两个指针合并。

```text
初始：[6,3,8,2]
分成：[6,3] 与 [8,2]
继续分：[6] [3] [8] [2]
两两合并：[3,6] 与 [2,8]
最终合并：先取 2，再取 3，再取 6，再取 8
结果：[2,3,6,8]
```

合并时，两个有序段尚未输出的最小值一定在两个段的当前头部。相等时先取左段记录，就能保持它在原数组中早于右段相等记录的顺序，因此经典归并稳定。

每层合并总共处理 `n` 个元素，共 `O(log n)` 层，所以最好、平均、最坏都是 `O(n log n)`。数组归并通常需要 `O(n)` 辅助缓冲，不是本章口径下的原地排序。链表归并可通过改连接减少元素缓冲，但仍要计算递归或迭代状态。

## 11. 完整 C++20：八种比较排序

下面程序实现直接/折半插入、Shell、冒泡、快速、简单选择、堆和归并排序。为让代码边界清楚，每个函数接收自己的数组副本；测试把结果与 `std::sort` 对照。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <random>
#include <utility>
#include <vector>

using Values = std::vector<int>;

Values insertion_sort(Values a) {
    for (std::size_t i = 1; i < a.size(); ++i) {
        const int value = a[i];
        std::size_t j = i;
        while (j > 0 && value < a[j - 1]) {
            a[j] = a[j - 1];
            --j;
        }
        a[j] = value;
    }
    return a;
}

Values binary_insertion_sort(Values a) {
    for (std::size_t i = 1; i < a.size(); ++i) {
        const int value = a[i];
        std::size_t low = 0;
        std::size_t high = i;
        while (low < high) {
            const std::size_t middle = low + (high - low) / 2;
            if (value < a[middle]) {
                high = middle;
            } else {
                low = middle + 1; // 插到已有相等元素之后，保持稳定。
            }
        }
        for (std::size_t j = i; j > low; --j) {
            a[j] = a[j - 1];
        }
        a[low] = value;
    }
    return a;
}

Values shell_sort(Values a) {
    for (std::size_t gap = a.size() / 2; gap > 0; gap /= 2) {
        for (std::size_t i = gap; i < a.size(); ++i) {
            const int value = a[i];
            std::size_t j = i;
            while (j >= gap && value < a[j - gap]) {
                a[j] = a[j - gap];
                j -= gap;
            }
            a[j] = value;
        }
    }
    return a;
}

Values bubble_sort(Values a) {
    for (std::size_t end = a.size(); end > 1; --end) {
        bool changed = false;
        for (std::size_t i = 1; i < end; ++i) {
            if (a[i] < a[i - 1]) {
                std::swap(a[i], a[i - 1]);
                changed = true;
            }
        }
        if (!changed) {
            break;
        }
    }
    return a;
}

void quick_sort_range(Values& a,
                      std::size_t left,
                      std::size_t right,
                      std::mt19937& random) {
    if (right - left <= 1) {
        return;
    }
    std::uniform_int_distribution<std::size_t> choose(left, right - 1);
    std::swap(a[choose(random)], a[right - 1]);
    const int pivot = a[right - 1];
    std::size_t store = left;
    for (std::size_t i = left; i + 1 < right; ++i) {
        if (a[i] <= pivot) {
            std::swap(a[i], a[store++]);
        }
    }
    std::swap(a[store], a[right - 1]);
    quick_sort_range(a, left, store, random);
    quick_sort_range(a, store + 1, right, random);
}

Values quick_sort(Values a) {
    std::mt19937 random(2025);
    quick_sort_range(a, 0, a.size(), random);
    return a;
}

Values selection_sort(Values a) {
    for (std::size_t i = 0; i < a.size(); ++i) {
        std::size_t smallest = i;
        for (std::size_t j = i + 1; j < a.size(); ++j) {
            if (a[j] < a[smallest]) {
                smallest = j;
            }
        }
        std::swap(a[i], a[smallest]);
    }
    return a;
}

void sift_down(Values& a, std::size_t root, std::size_t size) {
    while (2 * root + 1 < size) {
        std::size_t larger = 2 * root + 1;
        if (larger + 1 < size && a[larger] < a[larger + 1]) {
            ++larger;
        }
        if (a[larger] <= a[root]) {
            return;
        }
        std::swap(a[root], a[larger]);
        root = larger;
    }
}

Values heap_sort(Values a) {
    for (std::size_t i = a.size() / 2; i > 0; --i) {
        sift_down(a, i - 1, a.size());
    }
    for (std::size_t end = a.size(); end > 1; --end) {
        std::swap(a[0], a[end - 1]);
        sift_down(a, 0, end - 1);
    }
    return a;
}

void merge_range(Values& a,
                 Values& buffer,
                 std::size_t left,
                 std::size_t right) {
    if (right - left <= 1) {
        return;
    }
    const std::size_t middle = left + (right - left) / 2;
    merge_range(a, buffer, left, middle);
    merge_range(a, buffer, middle, right);
    std::size_t i = left;
    std::size_t j = middle;
    std::size_t out = left;
    while (i < middle && j < right) {
        if (a[j] < a[i]) {
            buffer[out++] = a[j++];
        } else {
            buffer[out++] = a[i++];
        }
    }
    while (i < middle) {
        buffer[out++] = a[i++];
    }
    while (j < right) {
        buffer[out++] = a[j++];
    }
    std::copy(buffer.begin() + static_cast<std::ptrdiff_t>(left),
              buffer.begin() + static_cast<std::ptrdiff_t>(right),
              a.begin() + static_cast<std::ptrdiff_t>(left));
}

Values merge_sort(Values a) {
    Values buffer(a.size());
    merge_range(a, buffer, 0, a.size());
    return a;
}

int main() {
    const std::vector<Values> cases{
        {}, {1}, {5, 2, 4, 6, 1, 3}, {3, 3, 2, 1, 2},
        {-4, 7, 0, -4, 9}, {1, 2, 3, 4}, {4, 3, 2, 1}};
    for (const Values& input : cases) {
        Values expected = input;
        std::sort(expected.begin(), expected.end());
        assert(insertion_sort(input) == expected);
        assert(binary_insertion_sort(input) == expected);
        assert(shell_sort(input) == expected);
        assert(bubble_sort(input) == expected);
        assert(quick_sort(input) == expected);
        assert(selection_sort(input) == expected);
        assert(heap_sort(input) == expected);
        assert(merge_sort(input) == expected);
    }
}
```

这些实现用于呈现基础不变量，不试图替代标准库经过长期优化的通用排序。生产代码通常先选择 `std::sort` 或 `std::stable_sort`，只有在接口、数据结构或教学目标要求时才手写。

## 12. 计数排序：值域小时直接统计每个值出现几次

**计数排序（counting sort）**不比较两个元素谁小，而是为值域中的每个整数维护出现次数。

```text
输入：[4,2,2,8,3,3,1]
计数：1->1，2->2，3->2，4->1，5/6/7->0，8->1
累加后可知：<=1 有1个，<=2 有3个，<=3 有5个……
稳定地放回：[1,2,2,3,3,4,8]
```

若值域从 `min` 到 `max`，大小 `U=max-min+1`，时间和空间为 `O(n+U)`。当 `U` 与 `n` 同阶或较小时很合适；若只有 100 个数却可能跨越几十亿整数，计数数组就不合理。

只按计数重复输出数值，看不出相同记录的身份。要稳定排序记录，应把计数改成前缀位置，再按输入逆序把记录放入输出数组，使相同键按原顺序落位。经典稳定实现需要 `O(n+U)` 辅助空间，不是原地。

## 13. 桶排序：先按范围分组，再分别排序

**桶排序（bucket sort）**把值域分成若干区间，每个元素进入对应桶；桶内排序后按桶顺序连接。

假设 `[0,1)` 均匀分成 10 个桶：

```text
输入：[0.78,0.17,0.39,0.26,0.72,0.94,0.21,0.12,0.23,0.68]
桶 1：[0.17,0.12]       -> [0.12,0.17]
桶 2：[0.26,0.21,0.23]  -> [0.21,0.23,0.26]
桶 3：[0.39]
桶 6：[0.68]
桶 7：[0.78,0.72]       -> [0.72,0.78]
桶 9：[0.94]
连接：[0.12,0.17,0.21,0.23,0.26,0.39,0.68,0.72,0.78,0.94]
```

若数据分布较均匀、桶数合适，每桶很短，期望时间可接近 `O(n+k)`，`k` 为桶数。若所有元素落入同一个桶，而桶内使用插入排序，最坏仍为 `O(n²)`。

桶边界必须保证“前一个桶的所有键不大于后一个桶”。稳定性取决于元素入桶顺序、桶内算法和连接方式是否都稳定。桶排序不是无条件线性；必须说明分布假设和桶内算法。

## 14. 基数排序：按数字位稳定地一轮轮整理

**基数排序（radix sort）**把关键字拆成个位、十位等数字位。最低位优先（LSD）版本从最低位开始，每一轮使用稳定的按位排序。

```text
输入：[170,45,75,90,802,24,2,66]
按个位稳定排序：[170,90,802,2,24,45,75,66]
按十位稳定排序：[802,2,24,45,66,170,75,90]
按百位稳定排序：[2,24,45,66,75,90,170,802]
```

为什么低位成果不会被下一轮破坏？因为按十位排序时，相同十位中的记录仍保持上一轮建立的个位次序。若按位排序不稳定，旧位次序会丢失，最终可能错误。

若有 `d` 位、每位基数为 `r`，使用计数分配时，时间为 `O(d(n+r))`，辅助空间为 `O(n+r)`。它适合固定位数整数、字符串片段等可拆位关键字。负数、变长字符串、字符集和符号位必须额外定义，不能直接套非负整数代码。

## 15. 外部排序：先生成有序段，再多路归并

当数据超过内存容量时，反复随机访问单个记录非常昂贵。外部排序通常分两阶段：

1. **生成初始归并段（run）**：每次读入一块能放进内存的数据，在内存排序后顺序写回一个有序文件段；
2. **多路归并**：同时为多个 run 保留输入缓冲，每次输出所有当前段首中的最小记录，直到生成更长 run；重复若干趟，最终只剩一个有序 run。

假设内存一次只能容纳 3 个数，输入为：

```text
7,2,9,1,5,8,3,6
```

分块内部排序后得到：

```text
R1=[2,7,9]，R2=[1,5,8]，R3=[3,6]
```

三路归并时只比较当前段首：

```text
(2,1,3) 取 1，R2 新段首为 5
(2,5,3) 取 2，R1 新段首为 7
(7,5,3) 取 3，R3 新段首为 6
(7,5,6) 取 5
(7,8,6) 取 6
随后取 7、8、9
结果：[1,2,3,5,6,7,8,9]
```

### 15.1 归并路数为什么重要

若有 `r` 个初始 run，每趟做 `k` 路归并，忽略不整除细节，归并趟数约为 `ceil(log_k r)`。每一趟通常都要读写全部数据，增加 `k` 能减少趟数，但每一路都需要输入缓冲和一个当前候选，打开文件数与管理成本也会上升。

真实系统会按块读写，而不是每输出一个记录就做一次磁盘 I/O。排序分析应区分“记录比较次数”和“整块 I/O 次数”。

### 15.2 败者树解决什么

直接扫描 `k` 个段首找最小值，每输出一个记录要 `O(k)` 次比较。小顶堆可降为 `O(log k)`。**败者树（loser tree）**是专为多路归并设计的锦标赛树：

- 叶子对应各路当前记录；
- 内部结点记录比较中的失败者；
- 总冠军位置给出当前最小者所在路；
- 某一路输出并补入新记录后，只需沿它到根的路径重新比赛，约 `O(log k)` 次比较。

记录失败者使更新路径和比较对象很固定，常数可能优于通用堆。败者树减少的是选择最小段首的比较工作，不减少必须读写的数据量；若 I/O 才是瓶颈，还要依靠大块缓冲和减少归并趟数。

<details>
<summary>扩展：置换选择怎样生成更长的初始 run</summary>

普通分块排序的 run 长度最多等于内存容量。置换选择在内存中维护候选最小值：能接在当前 run 后的输入继续参与本轮，比刚输出值更小的输入冻结到下一 run。在随机输入的理想模型中，它常生成长于内存容量的 run。

这会减少初始 run 数和后续归并趟数，但实现要管理冻结状态；它不保证所有输入都得到固定倍数的 run 长度。

</details>

## 16. 完整 C++20：非比较排序与多路归并

下面程序实现支持负数的稳定计数排序、`[0,1)` 浮点桶排序、非负 32 位整数 LSD 基数排序，以及模拟外部排序的分块 run 生成与优先队列多路归并。

```cpp
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <queue>
#include <stdexcept>
#include <tuple>
#include <utility>
#include <vector>

std::vector<int> counting_sort(const std::vector<int>& input) {
    if (input.empty()) {
        return {};
    }
    const auto [minimum_it, maximum_it] =
        std::minmax_element(input.begin(), input.end());
    const std::int64_t minimum = *minimum_it;
    const std::int64_t maximum = *maximum_it;
    const std::uint64_t range =
        static_cast<std::uint64_t>(maximum - minimum) + 1;
    if (range > 1'000'000) {
        throw std::length_error("value range too large for counting sort");
    }
    std::vector<std::size_t> counts(static_cast<std::size_t>(range), 0);
    for (int value : input) {
        ++counts[static_cast<std::size_t>(value - minimum)];
    }
    for (std::size_t i = 1; i < counts.size(); ++i) {
        counts[i] += counts[i - 1];
    }
    std::vector<int> output(input.size());
    for (auto it = input.rbegin(); it != input.rend(); ++it) {
        const std::size_t key = static_cast<std::size_t>(*it - minimum);
        output[--counts[key]] = *it;
    }
    return output;
}

std::vector<double> bucket_sort_unit(const std::vector<double>& input) {
    if (input.empty()) {
        return {};
    }
    std::vector<std::vector<double>> buckets(input.size());
    for (double value : input) {
        if (!std::isfinite(value) || value < 0.0 || value >= 1.0) {
            throw std::domain_error("bucket input must be finite in [0,1)");
        }
        const std::size_t index = static_cast<std::size_t>(
            value * static_cast<double>(buckets.size()));
        buckets[index].push_back(value);
    }
    std::vector<double> output;
    output.reserve(input.size());
    for (auto& bucket : buckets) {
        std::stable_sort(bucket.begin(), bucket.end());
        output.insert(output.end(), bucket.begin(), bucket.end());
    }
    return output;
}

std::vector<std::uint32_t> radix_sort(std::vector<std::uint32_t> a) {
    if (a.empty()) {
        return a;
    }
    const std::uint32_t maximum =
        *std::max_element(a.begin(), a.end());
    std::vector<std::uint32_t> output(a.size());
    for (std::uint64_t place = 1;
         static_cast<std::uint64_t>(maximum) / place > 0;
         place *= 10) {
        std::size_t counts[10]{};
        for (std::uint32_t value : a) {
            ++counts[(value / place) % 10];
        }
        for (std::size_t i = 1; i < 10; ++i) {
            counts[i] += counts[i - 1];
        }
        for (auto it = a.rbegin(); it != a.rend(); ++it) {
            const std::size_t digit = (*it / place) % 10;
            output[--counts[digit]] = *it;
        }
        a.swap(output);
    }
    return a;
}

std::vector<std::vector<int>> make_runs(const std::vector<int>& input,
                                        std::size_t capacity) {
    if (capacity == 0) {
        throw std::invalid_argument("run capacity must be positive");
    }
    std::vector<std::vector<int>> runs;
    for (std::size_t begin = 0; begin < input.size();) {
        const std::size_t chunk =
            std::min(capacity, input.size() - begin);
        const std::size_t end = begin + chunk;
        runs.emplace_back(input.begin() + static_cast<std::ptrdiff_t>(begin),
                          input.begin() + static_cast<std::ptrdiff_t>(end));
        std::sort(runs.back().begin(), runs.back().end());
        begin = end;
    }
    return runs;
}

std::vector<int> merge_runs(const std::vector<std::vector<int>>& runs) {
    using Entry = std::tuple<int, std::size_t, std::size_t>;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> next;
    std::size_t total = 0;
    for (std::size_t run = 0; run < runs.size(); ++run) {
        total += runs[run].size();
        if (!runs[run].empty()) {
            next.emplace(runs[run][0], run, 0);
        }
    }
    std::vector<int> output;
    output.reserve(total);
    while (!next.empty()) {
        const auto [value, run, index] = next.top();
        next.pop();
        output.push_back(value);
        if (index + 1 < runs[run].size()) {
            next.emplace(runs[run][index + 1], run, index + 1);
        }
    }
    return output;
}

int main() {
    assert((counting_sort({4, 2, 2, 8, 3, 3, 1}) ==
            std::vector<int>{1, 2, 2, 3, 3, 4, 8}));
    assert((counting_sort({-2, 3, -2, 0}) ==
            std::vector<int>{-2, -2, 0, 3}));

    const std::vector<double> decimals{
        0.78, 0.17, 0.39, 0.26, 0.72,
        0.94, 0.21, 0.12, 0.23, 0.68};
    auto bucketed = bucket_sort_unit(decimals);
    assert(std::is_sorted(bucketed.begin(), bucketed.end()));

    assert((radix_sort({170, 45, 75, 90, 802, 24, 2, 66}) ==
            std::vector<std::uint32_t>{2, 24, 45, 66, 75, 90, 170, 802}));
    assert((radix_sort({0, std::numeric_limits<std::uint32_t>::max(), 1}) ==
            std::vector<std::uint32_t>{0, 1,
                std::numeric_limits<std::uint32_t>::max()}));

    const std::vector<int> external_input{7, 2, 9, 1, 5, 8, 3, 6};
    const auto runs = make_runs(external_input, 3);
    assert((runs == std::vector<std::vector<int>>{
        {2, 7, 9}, {1, 5, 8}, {3, 6}}));
    assert((merge_runs(runs) ==
            std::vector<int>{1, 2, 3, 5, 6, 7, 8, 9}));
}
```

这里的 run 存在内存向量中，只是为了验证算法。真实外部排序会让每个 run 位于文件中，用有限大小的输入/输出缓冲分块读写，不能把所有 run 再一次性加载进内存。

## 17. 统一性质表

令 `n` 为元素数，`U` 为整数值域大小，`k` 为桶数，`d` 为数字位数，`r` 为每位基数。

| 算法 | 最好时间 | 平均时间 | 最坏时间 | 额外空间 | 稳定 | 原地 |
|---|---:|---:|---:|---:|:---:|:---:|
| 直接插入 | `O(n)` | `O(n²)` | `O(n²)` | `O(1)` | 是 | 是 |
| 折半插入 | 比较 `O(n log n)`、移动 `O(n)` | `O(n²)` | `O(n²)` | `O(1)` | 是 | 是 |
| Shell（折半间隔） | 依间隔而定 | 依间隔而定 | `O(n²)` | `O(1)` | 否 | 是 |
| 冒泡（提前停止） | `O(n)` | `O(n²)` | `O(n²)` | `O(1)` | 是 | 是 |
| 快速排序 | `O(n log n)` | `O(n log n)` | `O(n²)` | 栈平均 `O(log n)`、最坏 `O(n)` | 否 | 分区是 |
| 简单选择 | `O(n²)` | `O(n²)` | `O(n²)` | `O(1)` | 否 | 是 |
| 堆排序 | `O(n log n)` | `O(n log n)` | `O(n log n)` | `O(1)` | 否 | 是 |
| 归并排序（数组） | `O(n log n)` | `O(n log n)` | `O(n log n)` | `O(n)` | 是 | 否 |
| 计数排序 | `O(n+U)` | `O(n+U)` | `O(n+U)` | `O(n+U)` | 是 | 否 |
| 桶排序 | 分布合适时 `O(n+k)` | 依分布和桶内算法 | 可到 `O(n²)` | `O(n+k)` | 条件成立时 | 否 |
| LSD 基数排序 | `O(d(n+r))` | 同左 | 同左 | `O(n+r)` | 是 | 否 |

表中稳定性对应本章描述的经典实现。Shell 没有脱离间隔序列的单一通用时间式；桶排序没有脱离数据分布和桶内算法的单一时间式；外部排序还必须另算 run 数、归并路数和整块 I/O，不能只塞进 RAM 模型表。

## 18. 根据输入怎样选

| 输入与要求 | 优先考虑 | 原因与边界 |
|---|---|---|
| 很小或几乎有序 | 直接插入 | 自适应，代码短；大规模乱序会二次增长 |
| 只想少做记录交换 | 简单选择 | 交换至多 `n-1` 次；比较仍为 `n²` |
| 通用内存数组、平均效率重要 | 快速排序或标准库 `sort` | 局部性好；手写版本要处理退化 |
| 必须稳定、可提供线性缓冲 | 归并或稳定库排序 | 稳定且最坏 `n log n` |
| 辅助内存很紧、要求最坏 `n log n` | 堆排序 | 原地且最坏可靠；局部性通常弱 |
| 小范围整数键 | 计数排序 | 把 `U` 计入空间与时间 |
| 近似均匀分布且桶边界易定义 | 桶排序 | 分布偏斜会让单桶过大 |
| 固定位数非负整数/字符串位 | 基数排序 | 每位处理必须稳定，符号与变长需规则 |
| 数据远大于内存 | 外部多路归并 | 顺序生成 run，减少全量读写趟数 |

实际 C++ 代码优先使用标准库算法。手写基础排序的价值是理解性质、验证约束和回答原理题，不是用未经测试的实现替换成熟库。

## 19. 常见错误

- **把稳定理解成“结果总是一样”。** 它只约束比较器等价记录的原相对顺序。
- **说快速排序严格 `O(1)` 空间。** 原地分区仍可能使用递归栈。
- **把折半插入说成整体 `O(n log n)`。** 二分减少比较，数组移动仍可能为 `O(n²)`。
- **给 Shell 排序背一个不注明间隔序列的精确界。** 复杂度依赖 gap 选择。
- **冒泡每次都扫完整数组。** 已就位后缀无需再比较，且无交换可提前结束。
- **分区后认为两侧已经有序。** 只保证相对基准的区间关系，还要递归。
- **随机基准消除了最坏情况。** 它改善期望和输入鲁棒性，单次仍可能极端。
- **大量重复值仍用低效二路分区。** 三路分区能一次跳过等于基准的整段。
- **认为选择排序稳定。** 首元素与远处最小值交换可能跨越相等记录。
- **堆排序建小顶堆再把最小值换到数组末尾。** 升序原地堆排序通常建大顶堆。
- **归并相等时先取右边。** 会破坏跨左右段的稳定性。
- **说计数排序无条件 `O(n)`。** 正确式是 `O(n+U)`，巨大值域可能不可用。
- **桶排序无条件线性。** 全部数据进一个桶时可能退化。
- **基数排序每位使用不稳定算法。** 后一位排序会破坏已建立的低位顺序。
- **外部排序一次只读一个记录。** 应使用块缓冲；I/O 才是主成本。
- **败者树减少了数据读写量。** 它减少 k 路候选选择的比较，不能跳过输入输出。

## 20. 应用场景

- 数据库执行排序、归并连接或构建有序文件时，要先判断数据是否能进内存，并把外部 I/O 趟数纳入成本；
- Web/传统服务按时间或优先级整理记录时，要确认相同关键字是否必须保持到达顺序；
- AI 数据流水线可能按长度分桶以减少批内填充，但桶边界和分布偏斜会影响负载均衡；
- 日志、行情和其他持续数据可能只需要 Top-K、分位数或时间窗口，而不是完整排序，此时应回到[排序、分区与选择](sorting_selection.md)选择更少工作的算法。

不同行业共享同一组基础问题：排序键是什么、相等如何处理、数据有多大、能否修改输入、可用内存多少、最坏情况是否必须受控。

## 21. 本章小结

- 内部排序主要比较 CPU 与内存成本，外部排序主要比较 run 数、归并趟数和块 I/O；
- 稳定性保留相等关键字记录的原顺序，原地性描述辅助存储而不是时间；
- 通用比较排序的最坏比较下界是 `Ω(n log n)`，线性排序依赖额外键结构；
- 插入类扩大有序前缀，交换类通过局部交换推进，选择类每趟确定一个极值；
- 快排平均高效但可能退化，随机化改善期望，三路分区适合大量重复值；
- 堆排序原地且最坏 `n log n`，归并排序稳定且最坏 `n log n` 但数组版需要缓冲；
- 计数、桶、基数排序必须把值域、分布、数字位和稳定按位处理写进前提；
- 外部排序先生成 runs，再多路归并；败者树以 `O(log k)` 比较更新当前胜者。

## 22. 思考题、408 题与面试追问

1. 稳定排序保留的是什么？给出一个数值有序但业务上因不稳定而不合要求的例子。
2. 为什么 `n!` 个可能排列能推出比较排序最坏 `Ω(n log n)`？计数排序为什么不矛盾？
3. 对 `[5,2,4,6,1,3]` 写出每趟直接插入后的数组，并指出有序前缀。
4. 折半插入减少了什么、没有减少什么？为什么总时间仍可能是 `O(n²)`？
5. 使用间隔 `5,3,1` 手推 `[9,1,8,2,7,3,6,4,5]` 的 Shell 排序。
6. 冒泡排序怎样检测已有序？每趟结束后哪一段已经就位？
7. 用首元素 4 为基准，对 `[4,2,7,3,1,6]` 自选一种 partition 规则并完整推演；必须先声明规则。
8. 已有序输入为什么会让固定端点基准快排退化？随机化和三路分区分别解决什么问题？
9. 用 `[2A,2B,1]` 说明简单选择排序为何不稳定。
10. 从 `[4,10,3,5,1]` 建大顶堆并逐次取最大值，写出每轮有效堆和有序后缀。
11. 归并 `[2,4,7]` 与 `[1,4,6]` 时怎样保证两个关键字为 4 的记录稳定？
12. 值域 `[-5,5]` 的一百万个整数适合计数排序吗？若只有 20 个整数但值域跨度十亿呢？
13. 桶排序期望接近线性需要什么分布假设？所有元素落入同一桶会发生什么？
14. 对 `[329,457,657,839,436,720,355]` 手推十进制 LSD 基数排序三轮结果。
15. 2 GiB 数据、内存只能用于 256 MiB 数据块时，普通分块至少生成几个初始 run？若做 4 路归并，至少需要几趟归并？忽略缓冲保留和大小不整除。
16. k 路归并直接扫描、最小堆和败者树找当前最小段首的单次比较成本分别是什么？败者树为什么不降低 I/O 数据量？
17. 从统一表中分别选择：近乎有序小数组、稳定大数组、内存极紧且要最坏保证、小整数键、远大于内存的数据，并解释前提。

## 权威依据

- [2025 年 408 计算机学科专业基础考试大纲（高校公开附件）](https://www.uwh.edu.cn/uploads/article/20250609/660428d58334252302af691bf99e064e.pdf)
- 严蔚敏、吴伟民，《数据结构（C 语言版）》，内部排序与外部排序章节。
- [MIT Press：Introduction to Algorithms（CLRS）官方页面](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/)
- [Princeton Algorithms, 4th Edition 官方排序课程](https://algs4.cs.princeton.edu/20sorting/)
- [Princeton Algorithms, 4th Edition：Mergesort](https://algs4.cs.princeton.edu/22mergesort/)
- [Princeton Algorithms, 4th Edition：Quicksort](https://algs4.cs.princeton.edu/23quicksort/)
- [Princeton Algorithms, 4th Edition：Priority Queues](https://algs4.cs.princeton.edu/24pq/)

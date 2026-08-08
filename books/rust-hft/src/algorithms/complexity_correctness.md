# 复杂度、正确性与不变量：不仅要写出来，还要说明为什么对

算法题常有两种不完整答案：一种只说“时间复杂度是 `O(n)`”，却没有定义 `n`；另一种代码碰巧通过了样例，却解释不出为什么不会漏掉某些输入。本章用“在有序数组中找第一个不小于目标值的位置”连接这两个问题。

## 1. 复杂度到底在描述什么

复杂度描述的是：当输入规模增长时，算法使用的主要资源怎样增长。最常讨论两类资源：

- **时间复杂度**：主要操作次数的增长趋势；
- **空间复杂度**：算法额外申请的存储怎样增长。

它不直接等于运行时间。例如两个算法都是 `O(n)`，连续扫描数组通常比沿链表指针跳转更容易利用缓存；一个 `O(n log n)` 的紧凑排序也可能在小输入上快于分配很多节点的 `O(n)` 方案。复杂度先帮助排除增长过快的方案，最终性能仍需在明确输入与机器上测量。

### 1.1 先定义 `n`

回答“复杂度是多少”前，先说明规模变量：

- 数组题中，`n` 通常是元素数量；
- 图问题中，常同时使用顶点数 `V` 和边数 `E`；
- 字符串集合中，可能还需总字符数 `L`；
- 矩阵中，行数 `r` 和列数 `c` 不应无故都写成 `n`。

“遍历所有边”的复杂度通常是 `O(V + E)`，不是含糊的 `O(n)`。

### 1.2 常见增长趋势

| 量级 | 直觉 | 常见例子 |
|---|---|---|
| `O(1)` | 输入变大，操作数量级不随之增长 | 已知下标的数组访问 |
| `O(log n)` | 每一步排除固定比例 | 有序数组二分查找 |
| `O(n)` | 至多看一遍全部输入 | 求最大值 |
| `O(n log n)` | 线性层工作重复约 `log n` 层 | 常见比较排序 |
| `O(n²)` | 检查大量元素对 | 两层循环枚举下标对 |
| `O(2^n)` | 每个元素都产生选或不选分支 | 朴素枚举所有子集 |
| `O(n!)` | 枚举所有排列 | 朴素全排列搜索 |

这里忽略常数和低阶项，所以 `3n + 20` 写成 `O(n)`。但“忽略常数”只用于描述增长趋势，不表示常数在工程性能中不存在。

## 2. 最坏、平均与摊销不能混为一谈

### 2.1 最坏情况

最坏复杂度给定规模后，对所有合法输入取工作量上界。例如线性查找最坏要检查 `n` 个元素，因为目标可能不存在或位于最后。

### 2.2 平均情况

平均复杂度依赖输入分布或随机化假设。`std::unordered_map` 的查找通常按平均 `O(1)` 讨论，但最坏可能退化。若没有说明平均所依据的条件，就不要把它说成绝对承诺。

### 2.3 摊销分析

摊销分析把一串操作的总成本分摊到每次操作。例如 `vector::push_back` 通常称为摊销 `O(1)`：大多数尾插很便宜，偶尔扩容要移动许多元素，但足够长的一串尾插总成本仍为线性量级。

摊销 `O(1)` 不等于每次都是 `O(1)`。低延迟系统若关心单次尖峰，仍要处理扩容发生的那一次。

## 3. 额外空间：别忘了递归栈和数据结构

分析额外空间时，先说明是否把返回结果算进去。常见遗漏包括：

- 递归深度为 `h` 时，调用栈通常额外占用 `O(h)`；
- 原地排序也可能使用递归栈或小型缓冲；
- 哈希表保存 `n` 个键通常是 `O(n)`，即使函数中只写了一个变量名；
- 创建输入副本是额外 `O(n)`，不是“没有额外空间”。

面试中常说“除返回结果外的额外空间”。只要口径明确即可，不要在同一道题中前后改变口径。

## 4. 白话题意：找插入位置

题目如下：

> 给定一个从小到大排列的 64 位整数数组 `values` 和目标值 `target`，返回第一个满足 `values[index] >= target` 的下标。如果所有元素都小于 `target`，返回 `values.size()`。

例如：

| `values` | `target` | 返回值 | 解释 |
|---|---:|---:|---|
| `[1, 3, 3, 7]` | 3 | 1 | 第一个 `3` 在下标 1 |
| `[1, 3, 3, 7]` | 4 | 3 | `7` 是第一个不小于 4 的值 |
| `[1, 3, 3, 7]` | 9 | 4 | 可插在尾后位置 |
| `[]` | 5 | 0 | 空数组的尾后位置也是 0 |

这就是标准库 `lower_bound` 所表达的常见语义。本章手写它是为了学习边界推理；实际项目应优先使用经过测试的标准算法，并保证输入满足有序前置条件。

## 5. 暴力基线：从左到右找到第一处

```text
对于 index 从 0 到 n - 1：
    如果 values[index] >= target：
        返回 index
返回 n
```

只要数组有序或无序，这个线性扫描都能找到第一处满足条件的位置。最坏时间 `O(n)`，额外空间 `O(1)`。

它也是很好的测试参照：优化版的结果必须与它一致。

## 6. 关键观察：有序性让一次比较排除半个范围

若 `values[mid] < target`，那么 `mid` 以及它左边的所有位置都不可能是答案，可以把它们全部排除。

若 `values[mid] >= target`，`mid` 可能是答案，但它左边还可能有更早的合格位置，因此保留 `mid`，排除它右边的搜索范围。

这里查找的不是“某个等于目标值的位置”，而是满足谓词 `value >= target` 的第一个位置。把它理解成两段区域的分界线更稳定：

```text
[ 一定 < target ][ 一定 >= target ]
                  ^
                 答案
```

## 7. 不变量：给 `left` 和 `right` 明确含义

使用半开搜索区间 `[left, right)`，并维护两个事实：

1. 所有下标 `< left` 的元素都严格小于 `target`；
2. 所有有效下标 `>= right` 的元素都大于或等于 `target`。

尚未确定的区域正是 `[left, right)`。初始化为 `left = 0`、`right = n`：左侧和右侧已确认区域都为空，因此两个事实自然成立。

注意 `right` 可以等于 `n`。它是合法的尾后位置，但不能用来访问 `values[right]`。

## 8. 语言无关伪代码

```text
left = 0
right = n

当 left < right：
    mid = left + (right - left) / 2

    如果 values[mid] < target：
        left = mid + 1
    否则：
        right = mid

返回 left
```

写 `left + (right - left) / 2` 是常见的安全习惯，避免直接计算 `left + right` 时发生无符号回绕或有符号溢出。标准容器本身也不可能合法拥有超过其索引类型可表示范围的元素，但保持这个写法能让边界推理更清楚。

## 9. 正确性证明：初始化、保持、终止

### 9.1 初始化

开始时 `left = 0`，不存在下标 `< 0`；`right = n`，不存在有效下标 `>= n`。两个不变量都成立。

### 9.2 保持

令 `mid` 位于当前未确定区间：

- 若 `values[mid] < target`，由于数组有序，所有下标 `<= mid` 的元素都小于 `target`。令 `left = mid + 1` 后，第一个不变量继续成立；
- 若 `values[mid] >= target`，由于数组有序，所有下标 `>= mid` 的元素都大于或等于 `target`。令 `right = mid` 后，第二个不变量继续成立。

两种分支都严格缩小未确定区间，因此不会无限停留在同一状态。

### 9.3 终止

循环在 `left == right` 时结束，未确定区间为空。根据不变量：

- `left` 之前全部小于 `target`；
- 从 `left` 开始的有效元素全部大于或等于 `target`。

所以 `left` 正是第一个不小于目标值的位置；若 `left == n`，说明没有有效元素满足条件。

## 10. 复杂度：为什么是 `O(log n)`

每轮把长度为 `m` 的未确定区间缩小到至多大约 `m / 2`。经过 `k` 轮后，长度至多约为 `n / 2^k`。当它缩到 0 时，轮数与 `log₂ n` 同阶，因此：

- 最坏时间复杂度：`O(log n)`；
- 额外空间复杂度：`O(1)`。

这里是迭代实现。若改成递归二分，时间仍为 `O(log n)`，但调用栈通常额外使用 `O(log n)` 空间。

## 11. 完整 C++20：用线性基线做差分测试

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>

[[nodiscard]] std::size_t first_not_less_linear(
    const std::vector<std::int64_t>& values,
    std::int64_t target) {
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (values[index] >= target) {
            return index;
        }
    }
    return values.size();
}

[[nodiscard]] std::size_t first_not_less_binary(
    const std::vector<std::int64_t>& values,
    std::int64_t target) {
    std::size_t left = 0;
    std::size_t right = values.size();

    while (left < right) {
        const std::size_t mid = left + (right - left) / 2;
        if (values[mid] < target) {
            left = mid + 1;
        } else {
            right = mid;
        }
    }
    return left;
}

void check_case(const std::vector<std::int64_t>& values,
                std::int64_t target) {
    const std::size_t expected = first_not_less_linear(values, target);
    const std::size_t actual = first_not_less_binary(values, target);
    assert(actual == expected);

    const auto standard = std::lower_bound(values.begin(), values.end(), target);
    const auto standard_index =
        static_cast<std::size_t>(std::distance(values.begin(), standard));
    assert(actual == standard_index);

    // 结果左边都应小于 target；结果位置若存在，应不小于 target。
    for (std::size_t index = 0; index < actual; ++index) {
        assert(values[index] < target);
    }
    if (actual < values.size()) {
        assert(values[actual] >= target);
    }
}

int main() {
    check_case({}, 5);
    check_case({3}, 2);
    check_case({3}, 3);
    check_case({3}, 4);
    check_case({1, 3, 3, 7}, 0);
    check_case({1, 3, 3, 7}, 3);
    check_case({1, 3, 3, 7}, 4);
    check_case({1, 3, 3, 7}, 9);

    std::mt19937 generator{20260805U};
    std::uniform_int_distribution<int> length_distribution{0, 80};
    std::uniform_int_distribution<std::int64_t> value_distribution{-30, 30};
    std::uniform_int_distribution<std::int64_t> target_distribution{-40, 40};

    for (int round = 0; round < 3'000; ++round) {
        const auto length = static_cast<std::size_t>(length_distribution(generator));
        std::vector<std::int64_t> values(length);
        for (std::int64_t& value : values) {
            value = value_distribution(generator);
        }
        std::sort(values.begin(), values.end());
        check_case(values, target_distribution(generator));
    }

    std::cout << first_not_less_binary({1, 3, 3, 7}, 3) << '\n';
}
```

这个测试做了三层核对：与线性基线比较、与标准库比较、直接检查返回位置两侧的性质。三层都通过仍不是数学证明的替代品，但很适合发现边界实现错误。

## 12. 边界测试：二分最容易错在哪里

至少覆盖：

- 空数组；
- 单元素且目标分别小于、等于、大于该元素；
- 目标小于全部元素；
- 目标大于全部元素；
- 多个元素等于目标，必须返回第一个；
- 长度为偶数和奇数；
- 重复值很多。

不要访问 `values[right]`，因为 `right` 可以等于 `values.size()`。也不要把本模板中的 `[left, right)` 与另一份使用闭区间 `[left, right]` 的模板混合；两者都能正确，但循环条件和更新方式必须成套。

## 13. 正确性说明的四种常用工具

### 13.1 循环不变量

适合二分、双指针、滑动窗口和原地数组操作。给变量写一句稳定含义，通常比背更新公式可靠。

### 13.2 数学归纳

适合递归结构和动态规划：先证明最小规模成立，再证明较小问题正确能推出当前问题正确。

### 13.3 交换论证

常用于贪心：证明某个最优解可以把第一步替换为贪心选择而不会变差，再处理剩余问题。不能只说“每次选当前最好，所以整体最好”。

### 13.4 反证法

假设算法结果不是所需答案，再利用有序性、最短性或不变量推出矛盾。它常用于证明最短路径或分界位置，但不必为了显得正式而强行使用。

面试中的证明不要求写成论文。两三句说清“不会错报、不会漏报、循环会结束”通常已经很有价值。

## 14. 常见复杂度误区

### 14.1 两个连续循环不是自动 `O(n²)`

```cpp,ignore
for (std::size_t i = 0; i < n; ++i) {
    // O(1)
}
for (std::size_t j = 0; j < n; ++j) {
    // O(1)
}
```

总工作量是 `n + n`，所以仍为 `O(n)`。嵌套循环才常产生乘法，但还要看每层真实范围。

### 14.2 `while` 嵌套不一定是 `O(n²)`

双指针中，两个指针可能各自只单向移动 `n` 次。即使代码外观上有嵌套，只要总移动次数受线性上界约束，整体仍可能是 `O(n)`。

### 14.3 标准库调用也有成本

在循环内调用一次 `sort` 不能当作 `O(1)`。分析代码时要展开所调用操作的复杂度，而不是只数源码行数。

### 14.4 提前返回不改变最坏复杂度

线性查找最好情况可以第一步找到，但最坏仍可能检查全部输入。若题目问最坏复杂度，就不能只拿幸运输入回答。

### 14.5 整数运算也有正确性前提

复杂度合适不代表程序正确。中点、计数、距离和乘积都可能溢出；有符号溢出在 C++ 中可能造成未定义行为。应根据输入上界选择类型，并在运算前扩大或显式检查。

## 15. 面试追问与参考答法

### Q1：二分查找一定是 `O(log n)` 吗？

若每轮能把候选规模按固定比例缩小，才有对数级轮数。若“找中点”本身在线性链表上要走 `O(n)`，整体成本就不能只看轮数；二分通常依赖可高效随机访问的有序范围。

### Q2：为什么标准库有 `lower_bound`，还要会手写？

实际代码优先使用标准算法。手写训练用于理解半开区间、不变量和边界更新，也用于面试明确要求实现时。会手写不等于在生产中重复造轮子。

### Q3：测试很多随机输入，能代替证明吗？

不能。测试只能覆盖有限样本，证明说明所有满足前提的输入为何成立。工程上二者互补：证明可能遗漏实现细节，测试也可能遗漏输入区域。

### Q4：空间 `O(1)` 是否表示完全不使用内存？

不是。它表示额外内存不随输入规模增长，仍会有固定数量的局部变量、函数栈帧和程序运行开销。

## 16. 练习与完整参考答案

### 练习 A：统计有序数组中目标值出现次数

给定有序数组 `values` 和 `target`，要求在 `O(log n)` 时间内返回目标值出现次数。提示：分别寻找“第一个不小于目标的位置”和“第一个大于目标的位置”。

<details>
<summary>思路、伪代码与完整 C++20 答案</summary>

若 `lower` 是第一个 `>= target` 的位置，`upper` 是第一个 `> target` 的位置，那么所有等于目标的元素恰好位于 `[lower, upper)`，数量是 `upper - lower`。

```text
lower = 第一个满足 value >= target 的位置
upper = 第一个满足 value > target 的位置
返回 upper - lower
```

两个二分各需 `O(log n)`，总时间仍为 `O(log n)`；额外空间 `O(1)`。

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <vector>

[[nodiscard]] std::size_t first_not_less(
    const std::vector<std::int64_t>& values,
    std::int64_t target) {
    std::size_t left = 0;
    std::size_t right = values.size();
    while (left < right) {
        const std::size_t mid = left + (right - left) / 2;
        if (values[mid] < target) {
            left = mid + 1;
        } else {
            right = mid;
        }
    }
    return left;
}

[[nodiscard]] std::size_t first_greater(
    const std::vector<std::int64_t>& values,
    std::int64_t target) {
    std::size_t left = 0;
    std::size_t right = values.size();
    while (left < right) {
        const std::size_t mid = left + (right - left) / 2;
        if (values[mid] <= target) {
            left = mid + 1;
        } else {
            right = mid;
        }
    }
    return left;
}

[[nodiscard]] std::size_t count_equal(
    const std::vector<std::int64_t>& values,
    std::int64_t target) {
    return first_greater(values, target) - first_not_less(values, target);
}

int main() {
    assert(count_equal({}, 3) == 0);
    assert(count_equal({3}, 3) == 1);
    assert(count_equal({1, 2, 4}, 3) == 0);
    assert(count_equal({1, 3, 3, 3, 7}, 3) == 3);
    assert(count_equal({3, 3, 3}, 3) == 3);
    assert(count_equal({1, 1, 2, 2}, 1) == 2);
    assert(count_equal({1, 1, 2, 2}, 2) == 2);
    std::cout << count_equal({1, 3, 3, 3, 7}, 3) << '\n';
}
```

这个实现没有使用 `target + 1` 寻找右边界，因此即使 `target` 已是 64 位最大值，也不会因加一而溢出。

</details>

### 练习 B：判断复杂度

分别判断下面三种操作的时间和额外空间复杂度：

1. 扫描数组并维护最大值；
2. 先复制数组，再对副本排序；
3. 递归遍历一棵有 `n` 个节点、高度为 `h` 的二叉树，每个节点访问一次。

<details>
<summary>参考答案</summary>

1. 时间 `O(n)`，除返回值外额外空间 `O(1)`。
2. 复制 `O(n)`，常见比较排序 `O(n log n)`，合计由较大项主导为 `O(n log n)`；副本占额外 `O(n)`，排序自身还可能有实现相关栈或缓冲。
3. 时间 `O(n)`，因为每个节点访问一次；递归调用栈额外空间为 `O(h)`。平衡树中 `h` 常为 `O(log n)`，极度偏斜时可达 `O(n)`，不能不加前提直接写 `O(log n)`。

</details>

## 小结

复杂度回答“输入变大后工作怎样增长”，正确性回答“为什么所有合法输入都满足题意”。二分查找的核心不是三行模板，而是明确的搜索区间和不变量：左侧已经确定不合格，右侧已经确定合格，中间区域逐轮缩小。先给变量稳定含义，再写更新规则，边界错误会少很多。

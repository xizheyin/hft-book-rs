# 数组与字符串：双指针、滑动窗口和前缀和

数组与字符串题看起来千变万化，常见解法却大多在回答三个问题：

1. 能否利用已有顺序，只移动两个指针？
2. 能否维护一个连续窗口，而不是反复重新计算？
3. 能否先保存累计信息，让后面的区间查询变成一次减法？

本章从暴力解开始，找出重复工作，再依次建立双指针、滑动窗口和前缀和的不变量。重点是知道每个指针或累计量代表什么，并能由题目约束推导更新顺序。

## 1. 先认识 C++ 中的数组和字符串

算法题中最常见的三种连续序列是：

| 类型 | 长度 | 内存布局 | 常见用途 |
|---|---|---|---|
| `std::array<T, N>` | 编译期固定 | 连续 | 固定容量、小表格 |
| `std::vector<T>` | 运行时可变 | 连续 | 大多数动态数组题 |
| `std::string` | 运行时可变 | 连续字节 | 文本和协议字段 |

下标从 `0` 开始。长度为 `n` 时，有效下标是 `0` 到 `n - 1`；半开区间 `[left, right)` 包含 `left`，不包含 `right`，长度恰好是 `right - left`。

```cpp,ignore
// 教学片段：这些语句需要放进函数中。
std::vector<int> prices{101, 102, 103};
int first = prices[0];       // 不检查越界
int second = prices.at(1);   // 越界时抛出异常

std::string symbol = "AAPL";
char byte = symbol[0];
```

`std::string::size()` 返回的是**字节数**，不一定是人眼看到的字符数。ASCII 字符通常占一个字节，中文 UTF-8 字符通常占多个字节。本章的字符串练习会明确写出“输入只含 ASCII”这一前提；真实 Unicode 文本需要专门的分词和编码库。

还要记住两个 C++ 边界：

- `size()` 返回无符号的 `std::size_t`。写倒序循环时，`i >= 0` 对无符号数永远成立，容易死循环。
- `vector` 扩容后，原先指向元素的指针、引用和迭代器可能失效。算法中优先保存下标，而不是长期保存元素地址。

## 2. 母题一：判断 ASCII 字符串是否为回文

### 2.1 白话题意

给定一个只包含 ASCII 字节的字符串，判断它正着读和反着读是否完全相同。

```text
输入："level"
输出：true

输入："market"
输出：false
```

空字符串和单字节字符串都视为回文。本题比较原始字节，大小写不同也算不同；例如 `"Aa"` 不是回文。

### 2.2 暴力解

复制并反转字符串，再与原字符串比较：

```text
reversed = text 的副本
反转 reversed
返回 reversed == text
```

时间复杂度为 `O(n)`，但需要 `O(n)` 额外空间。它是完全正确的基线解，不应因为叫“暴力”就否定它；优化的目标只是避免不必要的副本，并能更早发现不匹配。

### 2.3 关键观察与不变量

回文要求第一个字节等于最后一个、第二个等于倒数第二个，以此类推。设置左右两个下标，比较后同时向中间移动。

循环不变量是：**每轮开始时，区间 `[left, right]` 外所有成对位置都已经确认相等。**

### 2.4 伪代码

```text
如果 text 为空：返回 true
left = 0
right = text.length - 1

while left < right：
    如果 text[left] != text[right]：
        返回 false
    left = left + 1
    right = right - 1

返回 true
```

空字符串必须在计算 `length - 1` 之前处理，否则无符号长度会下溢成一个很大的数。

### 2.5 为什么正确

如果某轮发现左右字节不同，那么字符串至少有一对镜像位置不相等，必定不是回文。

如果它们相等，向内移动后，区间外又多了一对已经确认相等的位置，不变量继续成立。指针相遇或交错时，所有镜像位置都已确认相等，因此返回 `true` 正确。

### 2.6 复杂度

- 时间复杂度：`O(n)`；最坏比较约 `n / 2` 对字节。
- 额外空间：`O(1)`。

### 2.7 完整 C++20 实现

`std::string_view` 只观察已有字符，不拥有内存。函数调用期间，调用方必须保证原字符串仍然存活。

```cpp
#include <cassert>
#include <string_view>

bool is_ascii_palindrome(std::string_view text) {
    if (text.empty()) {
        return true;
    }

    std::size_t left = 0;
    std::size_t right = text.size() - 1;
    while (left < right) {
        if (text[left] != text[right]) {
            return false;
        }
        ++left;
        --right;
    }
    return true;
}

int main() {
    assert(is_ascii_palindrome(""));
    assert(is_ascii_palindrome("a"));
    assert(is_ascii_palindrome("level"));
    assert(is_ascii_palindrome("abba"));
    assert(!is_ascii_palindrome("market"));
    assert(!is_ascii_palindrome("Aa"));
}
```

### 2.8 测试时还要想什么

- 空字符串和单字节字符串；
- 奇数、偶数长度；
- 第一次比较就失败，或直到中间才失败；
- 大小写是否敏感；
- 输入到底是 ASCII 字节、UTF-8 文本，还是已经解码的 Unicode 码点。

### 2.9 常见追问

1. **忽略大小写和标点怎么办？** 两端先跳过非字母数字 ASCII，再把大小写归一后比较；字符分类前应安全地转换为 `unsigned char`。
2. **UTF-8 中文字符串怎么办？** 不能逐字节反转或比较，必须先按 Unicode 码点或更符合产品定义的字素簇解码。
3. **最多删除一个字节后能否成为回文？** 第一次不匹配时，分别尝试跳过左侧或右侧，再检查剩余区间。
4. **输入来自单向流怎么办？** 两端随机访问不可用；需要缓存数据、使用外部存储，或接受概率型指纹方案及碰撞风险。

## 3. 母题二：有序数组中的两数之和

### 3.1 白话题意

给定一个**从小到大排列**的整数数组和目标值 `target`，找两个不同位置，使它们的元素之和等于 `target`。找到时返回两个下标，否则返回“没有答案”。

例如：

```text
输入：[1, 2, 4, 7, 11]，target = 9
输出：(1, 3)，因为 2 + 7 = 9
```

这里的“已经有序”不是装饰条件，它正是优化的依据。

### 3.2 先写暴力解

最直接的方法是枚举所有下标对：

```text
for i 从 0 到 n - 1：
    for j 从 i + 1 到 n - 1：
        如果 a[i] + a[j] == target：
            返回 (i, j)
返回“没有答案”
```

一共有大约 `n × (n - 1) / 2` 对，时间复杂度是 `O(n²)`，额外空间是 `O(1)`。

### 3.3 关键观察与不变量

把 `left` 放在最左端，`right` 放在最右端：

- 和太小：左边的数必须变大，所以 `left` 右移；
- 和太大：右边的数必须变小，所以 `right` 左移；
- 和刚好：找到答案。

循环不变量是：**如果仍存在尚未排除的答案，那么它一定在闭区间 `[left, right]` 中。**

### 3.4 伪代码

```text
left = 0
right = n - 1

while left < right：
    sum = a[left] + a[right]
    如果 sum == target：
        返回 (left, right)
    否则如果 sum < target：
        left = left + 1
    否则：
        right = right - 1

返回“没有答案”
```

### 3.5 为什么正确

假设当前 `a[left] + a[right] < target`。因为数组有序，对任何 `j <= right`，都有：

```text
a[left] + a[j] <= a[left] + a[right] < target
```

所以 `a[left]` 不可能和当前范围内任何数组成答案，排除它不会漏解。和太大时同理：任何 `i >= left` 与 `a[right]` 的和都更大，因此可以安全排除 `right`。

每轮要么返回答案，要么安全地排除一个不可能参与答案的位置。最终 `left >= right` 时已没有两个不同位置可选，因此返回无解是正确的。

### 3.6 复杂度

- 时间复杂度：`O(n)`。两个指针合计最多移动 `n - 1` 次。
- 额外空间：`O(1)`。

### 3.7 完整 C++20 实现

输入元素使用 `int`，求和先转成 `long long`，避免两个较大的 `int` 相加时溢出。

```cpp
#include <cassert>
#include <cstddef>
#include <optional>
#include <utility>
#include <vector>

using IndexPair = std::pair<std::size_t, std::size_t>;

std::optional<IndexPair> two_sum_sorted(
    const std::vector<int>& values,
    int target) {
    if (values.size() < 2) {
        return std::nullopt;
    }

    std::size_t left = 0;
    std::size_t right = values.size() - 1;

    while (left < right) {
        const long long sum =
            static_cast<long long>(values[left]) + values[right];

        if (sum == target) {
            return IndexPair{left, right};
        }
        if (sum < target) {
            ++left;
        } else {
            --right;
        }
    }
    return std::nullopt;
}

int main() {
    {
        const std::vector<int> values{1, 2, 4, 7, 11};
        const auto answer = two_sum_sorted(values, 9);
        assert(answer.has_value());
        assert(answer->first == 1);
        assert(answer->second == 3);
    }
    {
        const std::vector<int> values{2, 2, 3};
        const auto answer = two_sum_sorted(values, 4);
        assert(answer.has_value());
        assert(answer->first != answer->second);
    }
    {
        const std::vector<int> values{1, 3, 5};
        assert(!two_sum_sorted(values, 100).has_value());
    }
    assert(!two_sum_sorted({}, 1).has_value());
}
```

### 3.8 测试时还要想什么

- 空数组和只有一个元素的数组；
- 有重复值，而且答案需要使用两个不同位置；
- 含负数；
- 目标不存在；
- 元素接近 `int` 上下界，求和是否溢出。

### 3.9 常见追问

1. **数组没有排序怎么办？** 可以用哈希表做到平均 `O(n)`，下一章会实现。
2. **允许先排序吗？** 可以，但若要返回原始下标，需要把值和原下标一起排序；总时间为 `O(n log n)`。
3. **要找出所有不重复的数值对呢？** 找到一对后同时移动两端，并跳过相同值。
4. **输入是只读流怎么办？** 双指针需要随机访问和有序数据；单遍流通常要保存已经见过的值。

## 4. 母题三：最多翻转 K 个零的最长连续段

### 4.1 白话题意

给定只包含 `0` 和 `1` 的数组。你最多可以把 `k` 个 `0` 当成 `1`，求能够得到的最长连续 `1` 段长度。

```text
输入：[1, 1, 0, 0, 1, 1, 1, 0]，k = 2
输出：7
解释：区间 [0, 7) 内只有两个 0。
```

换一种说法：求“包含不超过 `k` 个零的最长连续子数组”。这种改写把“翻转”变成了容易维护的窗口条件。

### 4.2 暴力解

枚举每个起点，再向右扩展并统计零的数量：

```text
best = 0
for left 从 0 到 n - 1：
    zeros = 0
    for right 从 left 到 n - 1：
        如果 a[right] == 0：zeros += 1
        如果 zeros > k：停止扩展
        best = max(best, right - left + 1)
返回 best
```

最坏情况下每个起点都扫描到数组末尾，时间复杂度为 `O(n²)`。

### 4.3 关键观察与不变量

当右端加入新元素后，只有一种情况会让窗口非法：零的数量超过 `k`。此时不断右移左端，直到窗口重新合法即可。

窗口不变量是：**每次记录答案时，半开区间 `[left, right)` 中的零不超过 `k`。**

`left` 不会回头。虽然代码里有嵌套的 `while`，但它在整个程序中总共最多移动 `n` 次，因此不是 `O(n²)`。

### 4.4 伪代码

```text
left = 0
zeros = 0
best = 0

for right 从 0 到 n - 1：
    如果 a[right] == 0：
        zeros = zeros + 1

    while zeros > k：
        如果 a[left] == 0：
            zeros = zeros - 1
        left = left + 1

    best = max(best, right - left + 1)

返回 best
```

### 4.5 为什么正确

加入 `a[right]` 后，如果窗口合法，它就是当前右端能够保留的最长合法窗口；没有必要移动左端。

如果窗口非法，任何起点不晚于当前 `left` 的窗口都包含至少同样多的零，也不合法。循环逐个排除这些起点，直到零的数量重新不超过 `k`。此时得到以 `right` 结尾的最长合法窗口。

算法检查了每个右端对应的最长合法窗口，并取最大值，因此得到全局最优答案。

### 4.6 复杂度

- 时间复杂度：`O(n)`。每个元素最多被右端加入一次、被左端移出一次。
- 额外空间：`O(1)`。

### 4.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <vector>

std::size_t longest_ones_with_k_flips(
    const std::vector<int>& bits,
    int k) {
    if (k < 0) {
        return 0;
    }

    std::size_t left = 0;
    int zeros = 0;
    std::size_t best = 0;

    for (std::size_t right = 0; right < bits.size(); ++right) {
        if (bits[right] == 0) {
            ++zeros;
        }

        while (zeros > k) {
            if (bits[left] == 0) {
                --zeros;
            }
            ++left;
        }

        best = std::max(best, right - left + 1);
    }
    return best;
}

int main() {
    assert(longest_ones_with_k_flips(
               {1, 1, 0, 0, 1, 1, 1, 0}, 2) == 7);
    assert(longest_ones_with_k_flips({0, 0, 0}, 1) == 1);
    assert(longest_ones_with_k_flips({1, 1, 1}, 0) == 3);
    assert(longest_ones_with_k_flips({}, 2) == 0);
    assert(longest_ones_with_k_flips({1, 0}, -1) == 0);
}
```

函数的业务前提是数组只包含 `0` 和 `1`。面试时应主动说明这个前提；生产代码还可以验证输入并返回错误。

### 4.8 测试时还要想什么

- `k = 0`；
- `k` 大于数组中的零总数；
- 全是零、全是一、空数组；
- 最优窗口在开头、结尾或中间；
- 非法的负 `k` 如何处理。

### 4.9 常见追问

1. **为什么嵌套 `while` 仍是 `O(n)`？** 因为左指针一生只向右移动，总次数不超过 `n`。
2. **如果问“恰好包含 k 个零”呢？** 可以统计“至多 k 个”的子数组数量减去“至多 k-1 个”的数量；若只求最长长度，需要重新定义可接受状态。
3. **如果每个元素有不同翻转成本呢？** 把 `zeros` 换成窗口总成本，仍可在成本非负时使用相同窗口结构。
4. **为什么有负成本时不能直接套用？** 扩大窗口不再只会让总成本变大，单调性被破坏。

## 5. 母题四：静态数组的区间和查询

### 5.1 白话题意

给定一个之后不会修改的整数数组，需要多次查询半开区间 `[left, right)` 的元素之和。

```text
数组：[3, -1, 4, 2]
查询：[1, 4)
答案：-1 + 4 + 2 = 5
```

半开区间允许空区间 `[2, 2)`，它的和是 `0`，也让长度和边界计算更自然。

### 5.2 暴力解

每次查询都从 `left` 加到 `right - 1`：

```text
sum = 0
for i 从 left 到 right - 1：
    sum = sum + a[i]
返回 sum
```

单次查询为 `O(n)`。如果有 `q` 次查询，总时间可能达到 `O(nq)`，大量工作被重复计算。

### 5.3 关键观察与不变量

预先建立：

```text
prefix[i] = 前 i 个元素之和 = a[0] + ... + a[i - 1]
```

于是：

```text
sum(left, right) = prefix[right] - prefix[left]
```

前缀数组的不变量是：**处理完原数组前 `i` 个元素后，`prefix[i]` 精确等于这 `i` 个元素的和。**

### 5.4 伪代码

```text
prefix 创建为长度 n + 1，全部为 0
for i 从 0 到 n - 1：
    prefix[i + 1] = prefix[i] + a[i]

query(left, right)：
    如果 left > right 或 right > n：
        返回“非法范围”
    返回 prefix[right] - prefix[left]
```

多出来的 `prefix[0] = 0` 很重要：查询从下标 `0` 开始的区间时，不需要特殊分支。

### 5.5 为什么正确

根据定义，`prefix[right]` 包含下标 `0` 到 `right - 1` 的和；`prefix[left]` 包含下标 `0` 到 `left - 1` 的和。两者相减，前面的公共部分完全抵消，只剩 `[left, right)`。

构建阶段从 `prefix[0] = 0` 开始，每次把新元素 `a[i]` 加到已经正确的 `prefix[i]` 上，因此所有前缀值都正确。

### 5.6 复杂度

- 预处理：时间 `O(n)`，额外空间 `O(n)`。
- 每次查询：时间 `O(1)`。
- `q` 次查询总时间：`O(n + q)`。

这是用一次预处理和额外内存，换取大量查询加速。

### 5.7 完整 C++20 实现

`prefix` 使用 `long long`，因为许多 `int` 相加后可能超出 `int` 范围。

```cpp
#include <cassert>
#include <cstddef>
#include <optional>
#include <vector>

class RangeSum {
public:
    explicit RangeSum(const std::vector<int>& values)
        : prefix_(values.size() + 1, 0) {
        for (std::size_t i = 0; i < values.size(); ++i) {
            prefix_[i + 1] = prefix_[i] + values[i];
        }
    }

    [[nodiscard]] std::optional<long long> query(
        std::size_t left,
        std::size_t right) const {
        const std::size_t size = prefix_.size() - 1;
        if (left > right || right > size) {
            return std::nullopt;
        }
        return prefix_[right] - prefix_[left];
    }

private:
    std::vector<long long> prefix_;
};

int main() {
    const RangeSum sums({3, -1, 4, 2});

    assert(sums.query(1, 4).value() == 5);
    assert(sums.query(0, 4).value() == 8);
    assert(sums.query(2, 2).value() == 0);
    assert(!sums.query(3, 2).has_value());
    assert(!sums.query(0, 5).has_value());

    const RangeSum empty({});
    assert(empty.query(0, 0).value() == 0);
}
```

### 5.8 测试时还要想什么

- 空数组和空区间；
- 查询整个数组；
- 左右边界恰好等于数组长度；
- `left > right` 和 `right > n`；
- 含负数、零和较大累加结果。

### 5.9 常见追问

1. **数组会频繁修改怎么办？** 普通前缀和每次修改后可能要重建；可以根据操作需求学习树状数组或线段树。
2. **二维矩阵怎么做？** 建立二维前缀和，用四个矩形和通过容斥得到任意子矩形。
3. **只查询区间异或呢？** 把加法换成异或；相同前缀通过异或会抵消。
4. **为什么不用 `int` 存前缀和？** 单个元素合法不代表总和仍在 `int` 范围内。

## 6. 三种方法怎样选择

| 线索 | 首先考虑 | 必须确认的前提 |
|---|---|---|
| 有序序列、从两端收缩 | 双指针 | 排除一端时不会漏答案 |
| 连续区间、右端扩张后可通过左端恢复 | 滑动窗口 | 条件具有单调性 |
| 静态数组、大量区间聚合查询 | 前缀和 | 聚合结果可以由两个前缀相减或抵消 |

不要看到“连续”就机械使用滑动窗口。例如数组含负数时，“窗口和超过上限就缩小”未必正确，因为移走负数反而可能让和变大。模板成立依赖问题结构，不依赖题目长得像不像。

## 7. 变体练习

### 练习 1：原地去重

给定有序数组，把不同的值压到数组前部，返回不同值的数量。要求额外空间 `O(1)`。

<details>
<summary>思路与答案</summary>

使用 `read` 扫描所有元素，使用 `write` 指向下一个要写的位置。第一个元素直接保留；当 `a[read] != a[write - 1]` 时，把它写到 `a[write]` 并增加 `write`。不变量是 `[0, write)` 始终保存已经扫描部分的全部不同值，且顺序不变。时间 `O(n)`、空间 `O(1)`。

</details>

### 练习 2：长度固定的窗口最大和

给定整数数组和窗口长度 `k`，求所有长度恰好为 `k` 的连续区间中的最大和。非法 `k` 返回空结果。

<details>
<summary>思路与答案</summary>

先计算前 `k` 个元素的和。窗口每右移一步，只加入一个新元素并移走一个旧元素：`sum += a[right] - a[right-k]`。每步更新最大值。不变量是 `sum` 始终等于当前长度为 `k` 的窗口和。时间 `O(n)`、额外空间 `O(1)`；累加值应使用足够宽的整数类型。

</details>

### 练习 3：最长无重复 ASCII 子串

给定 ASCII 字符串，求没有重复字节的最长连续子串长度。

<details>
<summary>思路与答案</summary>

用长度 256 的计数数组维护窗口内每个字节的出现次数。右端加入字符后，如果它的计数大于 1，就不断移动左端并减少对应计数，直到窗口重新没有重复。记录最大窗口长度。将 `char` 转成 `unsigned char` 后再作为数组下标，避免有符号 `char` 产生负下标。时间 `O(n)`，额外空间对 ASCII 而言是 `O(1)`。

</details>

### 练习 4：差分数组

数组初始全为零，需要执行许多次“把 `[left, right)` 中每个元素加上 `delta`”，最后一次性输出所有值。

<details>
<summary>思路与答案</summary>

建立长度 `n + 1` 的差分数组。每次更新执行 `diff[left] += delta`、`diff[right] -= delta`；全部更新结束后，对 `diff` 求前缀和即可得到每个位置的最终值。每次更新 `O(1)`，最终恢复 `O(n)`。这适合离线批量更新；如果每次更新后都要立即查询，则要考虑其他数据结构。

</details>

## 8. 章末做题方法：窗口、双指针与前缀量

1. **读题找连续性**：确认答案是否要求连续子数组/子串、数组是否有序、窗口条件是否随右端扩张具有可恢复的单调性。
2. **画下标和区间语义**：统一使用 `[left,right)` 或闭区间，并在纸上标指针移动前后的有效范围；前缀和定义 `prefix[i]` 为前 `i` 个元素。
3. **逐步执行**：右指针加入元素，更新计数/和；条件不满足时移动左指针并撤销贡献；每一步只在窗口合法时更新答案。
4. **验算**：用空数组、单元素、全部相同、答案在两端和无解样例；前缀区间和检查是否为 `prefix[r]-prefix[l]`。

常见陷阱：无序数组硬套左右夹逼；含负数的“和不超过 K”窗口失去单调性；更新答案早于收缩；字符串按 byte 处理却声称支持任意 Unicode 字符。

## 9. 章末推演

尝试不看书回答：

1. 双指针移动一端时，为什么不会排除正确答案？

<details><summary>参考答案</summary>

必须依赖可证明的单调性。例如有序数组两数和中，若 `a[l]+a[r]` 太小，则固定 `l` 时任何 `r'≤r` 的和都不会更大，所以 `l` 不可能参与答案，可以右移。状态是不变量“尚未排除的候选都在 `[l,r]`”；每次移动都要给出同类排除证明。若数组无序，这个证明失效，不能硬套模板。

</details>

2. 嵌套 `while` 的滑动窗口为什么可能仍是 `O(n)`？

<details><summary>参考答案</summary>

虽然收缩循环写在扩张循环内部，但左右指针都只单调向右，每个元素最多被右指针加入一次、被左指针移出一次，总指针移动不超过 `2n`，故时间 `O(n)`。边界是左指针不得回退；若每个右端都从头重新扫描才会变为 `O(n²)`。

</details>

3. 哪类条件破坏滑动窗口需要的单调性？

<details><summary>参考答案</summary>

当扩张或收缩不再只朝一个方向改变“是否合法”时，朴素窗口失效。例如含负数数组中，移除左端负数反而会让窗口和变大，所以“和超过 K 就收缩”不能保证恢复且不漏解。应先构造反例 `[2,-5,4]` 再改用前缀和、哈希或有序结构。

</details>

4. 为什么前缀数组通常开成 `n + 1`？

<details><summary>参考答案</summary>

定义 `prefix[0]=0`、`prefix[i+1]=prefix[i]+a[i]` 后，任意半开区间 `[l,r)` 的和统一为 `prefix[r]-prefix[l]`，包括 `l=0`，无需特判。数组长度 `n+1` 恰好容纳“前 0 个”到“前 n 个”共 `n+1` 个状态。

</details>

5. `std::string::size()` 为什么不一定等于人眼字符数？

<details><summary>参考答案</summary>

`std::string` 保存字节，`size()` 返回 byte 数。UTF-8 中一个 Unicode 码点可占 1～4 byte，一个人眼字符还可能由多个码点组合，所以三种数量都可能不同。ASCII 输入时 byte 数才与字符数一致；算法必须先声明按 byte、码点还是字素簇处理。

</details>

6. 哪些测试能暴露下标、空输入和整数溢出问题？

<details><summary>参考答案</summary>

按状态覆盖：空数组、单元素、窗口 `k=0/1/n/n+1`、答案在首尾、全相等、严格增减、重复与无解；按数值覆盖：接近整数上下界、正负混合和长数组。用小规模 `O(n²)` 基线随机对拍结果，再开地址/未定义行为检查器；复杂度应为目标算法的 `O(n)` 时间和声明的空间。

</details>

如果只能背出代码，却解释不了不变量，说明这道题还没有真正掌握。

# 栈、队列、双端队列与堆：维护“下一位”和“最优候选”

单调栈、滑动窗口、Top-K、多路合并和表达式求值都在维护“仍可能成为答案的候选”，差别在于候选按什么顺序淘汰。

## 1. 先修回顾

栈按后进先出取元素，队列按先进先出取元素，双端队列允许两端进出，堆只保证堆顶是当前优先级最高的元素。C++ 中常用 `std::stack`、`std::queue`、`std::deque` 和 `std::priority_queue`，读取 `top()`、`front()` 或 `back()` 前必须确认容器非空。默认 `priority_queue<int>` 是大顶堆；需要小顶堆时要提供相反优先级的比较规则。单调栈和单调队列不是新容器，而是在栈或双端队列上维护值的单调不变量。完整的数组、栈、队列、循环队列、双端队列和堆基础见[栈、队列与数组](stacks_queues_arrays.md)。

## 2. 母题：每个位置右侧的第一个更大值

### 2.1 白话题意

给定整数数组。对每个位置，找到它右侧第一个严格更大的值；若不存在，结果为空。

```text
输入：[2, 1, 2, 4, 3]
输出：[4, 2, 4, 空, 空]
```

注意“第一个”和“严格更大”两个条件。相等值不能作为答案。

### 2.2 暴力解

对每个位置向右扫描，遇到第一个更大值就停止：

```text
for i 从 0 到 n - 1：
    answer[i] = 空
    for j 从 i + 1 到 n - 1：
        如果 a[j] > a[i]：
            answer[i] = a[j]
            break
```

严格递减数组中，每个位置都要一直扫到末尾，时间复杂度为 `O(n²)`。

### 2.3 关键观察与不变量

从左向右扫描时，栈中只保存“还没有找到右侧更大值”的下标。

新值 `a[i]` 比栈顶位置的值大时，它就是栈顶的第一个更大值：栈顶入栈以后，中间所有元素都没能让它弹出，而当前元素第一次满足条件。

不断弹出较小值后再压入 `i`。栈的不变量是：

1. 下标从栈底到栈顶递增；
2. 对应值从栈底到栈顶非递增；
3. 栈中每个下标在已扫描范围内都还没有更大值。

### 2.4 伪代码

```text
answer = 长度为 n 的空结果
stack = 空下标栈

for i 从 0 到 n - 1：
    while stack 非空 且 a[stack.top] < a[i]：
        old = stack.pop
        answer[old] = a[i]
    stack.push(i)

返回 answer
```

这里必须保存下标，而不是只保存值，因为答案要写回对应位置。

### 2.5 为什么正确

当下标 `j` 被当前下标 `i` 弹出时，`a[i] > a[j]`。从 `j + 1` 到 `i - 1` 的元素都已扫描，却没有让 `j` 弹出，所以它们都不严格大于 `a[j]`。因此 `a[i]` 正是 `j` 右侧第一个更大值。

扫描结束后仍留在栈中的位置，在其右侧从未遇到更大元素，所以保持空结果是正确的。每个位置最终要么在遇到第一个更大值时被弹出，要么一直留到结束。

### 2.6 复杂度

- 时间复杂度：`O(n)`；
- 额外空间：`O(n)`。

虽然有嵌套 `while`，每个下标只入栈一次、出栈至多一次，所以总栈操作为线性数量。

### 2.7 完整 C++20 实现

使用 `std::vector<std::size_t>` 作为栈，方便直接保存和访问下标。

```cpp
#include <cassert>
#include <cstddef>
#include <optional>
#include <vector>

std::vector<std::optional<int>> next_greater_value(
    const std::vector<int>& values) {
    std::vector<std::optional<int>> answer(values.size(), std::nullopt);
    std::vector<std::size_t> stack;
    stack.reserve(values.size());

    for (std::size_t i = 0; i < values.size(); ++i) {
        while (!stack.empty() && values[stack.back()] < values[i]) {
            answer[stack.back()] = values[i];
            stack.pop_back();
        }
        stack.push_back(i);
    }
    return answer;
}

int main() {
    const std::vector<std::optional<int>> expected{
        4, 2, 4, std::nullopt, std::nullopt};
    assert(next_greater_value({2, 1, 2, 4, 3}) == expected);

    const std::vector<std::optional<int>> decreasing{
        std::nullopt, std::nullopt, std::nullopt};
    assert(next_greater_value({3, 2, 1}) == decreasing);

    const std::vector<std::optional<int>> equal{
        std::nullopt, std::nullopt};
    assert(next_greater_value({5, 5}) == equal);
    assert(next_greater_value({}).empty());
}
```

### 2.8 测试时还要想什么

- 空数组、单个元素；
- 严格递增和严格递减；
- 相等值不算“更大”；
- 答案为负数时，不能用 `-1` 充当无解而产生歧义；
- 最后仍留在栈中的元素。

### 2.9 常见追问

1. **要返回距离而不是值呢？** 弹出 `j` 时写入 `i - j`。
2. **找右侧第一个大于等于呢？** 弹出条件改为 `<=`，同时重新推导相等值的处理。
3. **找左侧最近更大值呢？** 扫描方向和回答时机改变，但仍维护单调候选栈。
4. **数组首尾相连呢？** 可以逻辑上扫描两遍，用 `i % n` 访问；第二遍通常不再压入重复下标。

## 3. 母题：每个滑动窗口的最大值

### 3.1 白话题意

给定整数数组和窗口长度 `k`。窗口从左向右每次移动一格，输出每个窗口中的最大值。

```text
输入：[1, 3, -1, -3, 5, 3, 6, 7]，k = 3
窗口最大值：[3, 3, 5, 5, 6, 7]
```

`k = 0` 或 `k > n` 在本章定义为非法输入。

### 3.2 暴力解

每个窗口重新扫描 `k` 个元素：

```text
for 每个窗口起点 left：
    maximum = a[left]
    for i 遍历这个窗口：
        maximum = max(maximum, a[i])
    输出 maximum
```

共有约 `n - k + 1` 个窗口，时间为 `O(nk)`。

用大顶堆可以做到 `O(n log n)`，但删除已经离开窗口的旧元素需要额外记录。这里使用能在线性时间维护候选的单调双端队列。

### 3.3 关键观察与不变量

`deque` 保存下标，并保持对应值从队首到队尾**严格递减**：

- 队首始终是当前窗口最大值；
- 新元素进入前，弹出队尾所有不大于它的旧元素；
- 队首下标离开窗口时，从队首弹出。

为什么较小的旧元素可以永久删除？新元素更大或相等，而且位置更靠右。只要旧元素还在未来某个窗口中，新元素也会在；旧元素不可能再成为最大值。

### 3.4 伪代码

```text
如果 k 非法：返回“非法输入”
deque = 空下标双端队列
answer = 空列表

for i 从 0 到 n - 1：
    删除队首所有已经离开窗口的下标

    while deque 非空 且 a[deque.back] <= a[i]：
        deque.pop_back
    deque.push_back(i)

    如果第一个完整窗口已经形成：
        answer 加入 a[deque.front]

返回 answer
```

### 3.5 为什么正确

首先，过期下标在记录答案前被删除，因此队列只含当前窗口元素。

其次，从队尾删除不大于新值的元素是安全的：新元素更晚离开窗口且值不小于它们，所以这些旧元素以后不可能成为窗口最大值。

剩余下标按值严格递减，因此队首值不小于队列中其他值。所有没有进入队列或已从队尾删除的当前窗口元素，都被一个更晚且不小的候选支配。故队首就是当前窗口最大值。

### 3.6 复杂度

- 时间复杂度：`O(n)`；
- 额外空间：`O(k)`，答案数组除外。

每个下标入队一次，最多从队首或队尾弹出一次。

### 3.7 完整 C++20 实现

```cpp
#include <cassert>
#include <cstddef>
#include <deque>
#include <optional>
#include <vector>

std::optional<std::vector<int>> sliding_window_maximum(
    const std::vector<int>& values,
    std::size_t k) {
    if (k == 0 || k > values.size()) {
        return std::nullopt;
    }

    std::deque<std::size_t> candidates;
    std::vector<int> answer;
    answer.reserve(values.size() - k + 1);

    for (std::size_t i = 0; i < values.size(); ++i) {
        while (!candidates.empty() &&
               i >= k && candidates.front() <= i - k) {
            candidates.pop_front();
        }

        while (!candidates.empty() &&
               values[candidates.back()] <= values[i]) {
            candidates.pop_back();
        }
        candidates.push_back(i);

        if (i + 1 >= k) {
            answer.push_back(values[candidates.front()]);
        }
    }
    return answer;
}

int main() {
    const std::vector<int> expected{3, 3, 5, 5, 6, 7};
    assert(sliding_window_maximum(
               {1, 3, -1, -3, 5, 3, 6, 7}, 3).value() == expected);

    assert(sliding_window_maximum({4, 2}, 1).value() ==
           std::vector<int>({4, 2}));
    assert(sliding_window_maximum({4, 2}, 2).value() ==
           std::vector<int>({4}));
    assert(sliding_window_maximum({2, 2, 2}, 2).value() ==
           std::vector<int>({2, 2}));
    assert(!sliding_window_maximum({}, 1).has_value());
    assert(!sliding_window_maximum({1, 2}, 0).has_value());
    assert(!sliding_window_maximum({1, 2}, 3).has_value());
}
```

### 3.8 测试时还要想什么

- `k = 1` 和 `k = n`；
- `k = 0`、`k > n`、空数组；
- 所有值相同；
- 严格递增和严格递减；
- 最大值恰好在移动后过期；
- 负数。

### 3.9 常见追问

1. **窗口最小值怎么做？** 把单调递减改为单调递增。
2. **同时输出最大和最小呢？** 维护两个 `deque`，各自保持相反单调性。
3. **为什么队列中保存下标而不是值？** 需要判断候选何时离开窗口；只有值无法区分相同值的不同位置。
4. **流式数据可以做吗？** 可以，只需保存最近窗口的候选下标或递增序号，不必保存全部历史数据。

## 4. 母题三：找出最大的 K 个元素

### 4.1 白话题意

给定无序数组和整数 `k`，返回最大的 `k` 个元素，结果按从大到小排列。重复值分别计数。

```text
输入：[7, 1, 5, 9, 9, 2]，k = 3
输出：[9, 9, 7]
```

本章规定 `k = 0` 返回空数组，`k > n` 返回非法输入。

### 4.2 暴力思路

最简单的方法是把整个数组从大到小排序，再取前 `k` 个：时间 `O(n log n)`。这通常完全可用，但当 `n` 很大、`k` 很小时，我们为许多不需要的元素确定了完整次序。

### 4.3 关键观察与不变量

只维护目前见过的最大 `k` 个元素。用容量为 `k` 的**小顶堆**：

- 堆未满时直接加入；
- 堆满后，堆顶是这 `k` 个候选中最小的；
- 新值大于堆顶时，淘汰堆顶并加入新值；否则忽略新值。

循环不变量是：**处理完前 `i` 个输入后，堆中恰好保存这些输入中最大的 `min(i, k)` 个元素。**

### 4.4 伪代码

```text
如果 k > n：返回“非法输入”
如果 k == 0：返回空列表

heap = 空小顶堆
for x 遍历输入：
    如果 heap.size < k：
        heap.push(x)
    否则如果 x > heap.top：
        heap.pop
        heap.push(x)

依次弹出堆中元素，并整理成从大到小
返回结果
```

### 4.5 为什么正确

对已处理元素数量做归纳。堆未满时，保存全部已处理元素显然正确。堆满后：

- 若新值不大于堆顶，它也不大于当前第 `k` 大候选，不可能进入最大的 `k` 个；
- 若新值大于堆顶，新的 Top-K 必然包含新值，并淘汰旧 Top-K 中最小的堆顶。

因此每轮都保持不变量。扫描结束后，堆中就是全局最大的 `k` 个元素。最后排序只改变输出次序，不改变成员。

### 4.6 复杂度

- 扫描时间：`O(n log k)`；
- 提取并形成有序结果：`O(k log k)`；
- 额外空间：`O(k)`。

当 `k` 接近 `n` 时，完整排序可能更简单，常数也可能更好。算法复杂度是选择依据之一，不是唯一依据。

### 4.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <functional>
#include <optional>
#include <queue>
#include <vector>

std::optional<std::vector<int>> largest_k(
    const std::vector<int>& values,
    std::size_t k) {
    if (k > values.size()) {
        return std::nullopt;
    }
    if (k == 0) {
        return std::vector<int>{};
    }

    std::priority_queue<int, std::vector<int>, std::greater<int>> min_heap;

    for (int value : values) {
        if (min_heap.size() < k) {
            min_heap.push(value);
        } else if (value > min_heap.top()) {
            min_heap.pop();
            min_heap.push(value);
        }
    }

    std::vector<int> answer;
    answer.reserve(k);
    while (!min_heap.empty()) {
        answer.push_back(min_heap.top());
        min_heap.pop();
    }
    std::reverse(answer.begin(), answer.end());
    return answer;
}

int main() {
    assert(largest_k({7, 1, 5, 9, 9, 2}, 3).value() ==
           std::vector<int>({9, 9, 7}));
    assert(largest_k({-4, -2, -9}, 2).value() ==
           std::vector<int>({-2, -4}));
    assert(largest_k({3, 1}, 0).value().empty());
    assert(largest_k({}, 0).value().empty());
    assert(!largest_k({1, 2}, 3).has_value());
}
```

### 4.8 测试时还要想什么

- `k = 0`、`k = 1`、`k = n`、`k > n`；
- 空数组；
- 重复值是否重复计数；
- 全是负数；
- 输入已经升序或降序；
- 是否要求输出有序。如果不要求，可以省去最后的整理。

### 4.9 常见追问

1. **只求第 k 大，不要求 Top-K 列表呢？** 可以保留同样的小顶堆，最终堆顶就是第 `k` 大。
2. **允许修改数组，能否更快？** `std::nth_element` 平均线性时间把目标位置放对，但不保证两侧内部有序。
3. **数据是持续到达的流呢？** 固定 `k` 的小顶堆可以在线更新，内存仍为 `O(k)`。
4. **要按不同字段选 Top-K 对象呢？** 为堆定义清晰的比较器，并明确相等优先级时的稳定规则。

## 5. 母题四：合并 K 个有序数组

### 5.1 白话题意

给定 `k` 个分别从小到大排列的数组，把它们合并成一个有序数组。

```text
输入：[1, 4, 7]，[2, 2, 8]，[]，[3, 9]
输出：[1, 2, 2, 3, 4, 7, 8, 9]
```

设所有数组元素总数为 `N`。

### 5.2 暴力思路

把全部元素复制到一个数组，再整体排序：时间 `O(N log N)`。它没有利用每个输入数组已经有序这一条件。

也可以每次线性检查所有数组的当前首元素，取最小者。每输出一个元素检查 `k` 个候选，总时间 `O(Nk)`。

### 5.3 关键观察与不变量

全局最小的未输出元素，一定是某个数组当前尚未输出的第一个元素。我们只需在至多 `k` 个“数组头部候选”中找最小值。

用小顶堆维护候选节点 `(value, row, column)`。不变量是：**对每个仍有未输出元素的输入数组，堆中恰好保存它最靠前的未输出元素。**

### 5.4 伪代码

```text
heap = 空小顶堆
for 每个非空数组 row：
    把 (a[row][0], row, 0) 加入 heap

answer = 空列表
while heap 非空：
    node = heap.pop_min
    answer 加入 node.value

    next_column = node.column + 1
    如果同一数组还有元素：
        把下一个元素加入 heap

返回 answer
```

### 5.5 为什么正确

根据不变量，每个数组最小的未输出元素都在堆里。任何更靠后的元素都不小于它所在数组的头部候选，因此全局最小未输出元素必然就是堆顶。

弹出堆顶后，只需把同一数组的下一个元素加入堆，就重新为该数组保存了最靠前的未输出元素，其他数组的候选没有变化。不变量继续成立。

每次输出的都是当前全局最小值，所以最终结果有序；每个输入元素恰好输出一次，所以没有遗漏或重复制造元素。

### 5.6 复杂度

- 时间复杂度：`O(N log k)`，更精确地说是 `O(N log m)`，其中 `m` 是非空数组数；
- 除输出外额外空间：`O(k)`。

当 `k = 1` 时堆里只有一个候选，过程退化为线性复制。

### 5.7 完整 C++20 实现

`priority_queue` 默认把“比较器认为优先级最高”的元素放在顶部。下面的比较器用 `>` 构造小顶堆，并用行列下标让相等值的弹出顺序确定。

```cpp
#include <cassert>
#include <cstddef>
#include <queue>
#include <vector>

struct Node {
    int value;
    std::size_t row;
    std::size_t column;
};

struct NodeGreater {
    bool operator()(const Node& lhs, const Node& rhs) const {
        if (lhs.value != rhs.value) {
            return lhs.value > rhs.value;
        }
        if (lhs.row != rhs.row) {
            return lhs.row > rhs.row;
        }
        return lhs.column > rhs.column;
    }
};

std::vector<int> merge_sorted_arrays(
    const std::vector<std::vector<int>>& arrays) {
    std::priority_queue<Node, std::vector<Node>, NodeGreater> min_heap;
    std::size_t total_size = 0;

    for (std::size_t row = 0; row < arrays.size(); ++row) {
        total_size += arrays[row].size();
        if (!arrays[row].empty()) {
            min_heap.push(Node{arrays[row][0], row, 0});
        }
    }

    std::vector<int> answer;
    answer.reserve(total_size);

    while (!min_heap.empty()) {
        const Node node = min_heap.top();
        min_heap.pop();
        answer.push_back(node.value);

        const std::size_t next_column = node.column + 1;
        if (next_column < arrays[node.row].size()) {
            min_heap.push(Node{
                arrays[node.row][next_column], node.row, next_column});
        }
    }
    return answer;
}

int main() {
    const std::vector<std::vector<int>> arrays{
        {1, 4, 7}, {2, 2, 8}, {}, {3, 9}};
    const std::vector<int> expected{1, 2, 2, 3, 4, 7, 8, 9};
    assert(merge_sorted_arrays(arrays) == expected);

    assert(merge_sorted_arrays({}).empty());
    assert(merge_sorted_arrays({{}, {}}).empty());
    assert(merge_sorted_arrays({{-3, -1}, {-2, 0}}) ==
           std::vector<int>({-3, -2, -1, 0}));
    assert(merge_sorted_arrays({{1, 2, 3}}) ==
           std::vector<int>({1, 2, 3}));
}
```

真实输入若来自文件或网络流，堆节点可以保存迭代器或流编号，而不是把所有数组同时放在内存中。此时还要处理读取失败、背压和流生命周期。

### 5.8 测试时还要想什么

- `k = 0`；
- 存在空数组；
- 只有一个数组；
- 重复值和负数；
- 总元素数为零；
- 输入违反“各自有序”的前提时如何处理；
- `total_size` 累加在极端规模下是否溢出或无法分配。

### 5.9 常见追问

1. **怎样合并 k 个有序文件？** 堆中只保留每个文件当前记录，输出写入新文件；I/O 缓冲和失败恢复成为主要工程问题。
2. **怎样去重？** 输出前与上一个已输出值比较；但要明确是按值去重还是保留来源信息。
3. **怎样保持相等元素的来源稳定顺序？** 比较器加入输入流编号和流内序号作为次级键。
4. **为什么不两两合并？** 平衡地两两归并也能达到 `O(N log k)`；堆方案更自然地支持流式输入。

## 6. 进阶母题：用两个栈计算整数表达式

### 6.1 白话题意与语法

计算一个中缀整数表达式。为了让边界可验证，本题只接受下面的明确语法：

```text
expression = term (('+' | '-') term)*
term       = factor (('*' | '/') factor)*
factor     = 非负十进制整数 | '(' expression ')'
```

- 允许 ASCII 空白；
- 整数字面量范围是 `0..INT64_MAX`；
- `+ - * /` 都是二元运算，不支持一元 `-`，所以 `-3` 非法；
- 乘除优先于加减，同级运算从左向右；
- 整数除法向零截断；
- 括号必须匹配，不允许空括号或隐式乘法 `2(3)`；
- 除零、字面量溢出和任何中间结果溢出都报告错误。

例如 `2 + 3 * 4` 得到 14，`(2 + 3) * 4` 得到 20。

### 6.2 基线方法

如果表达式已经完全加上括号，可以递归寻找最外层运算符；但反复切分字符串容易达到 `O(n²)`，也很难正确处理优先级和错误位置。

递归下降解析器也是很好的线性解法，它直接对应上面的语法。本节选择两个栈，是为了集中练习“值栈保存什么、运算符何时可以安全执行”。

### 6.3 关键观察与不变量

维护：

- `values`：已经读到、但还没有被更外层运算消费的值；
- `operators`：尚未执行的运算符和左括号；
- `expect_value`：当前位置应该出现数字/左括号，还是运算符/右括号。

读到新运算符 `op` 时，先执行栈顶所有优先级更高或相同的运算符，再压入 `op`。相同优先级也先执行，保证二元运算左结合。

核心不变量是：**已经读过的合法前缀，其尚未归约部分被两个栈完整表示；运算符栈中任何本应在当前运算符之前执行的操作都已经完成。** 左括号是归约边界，右括号只归约到最近的左括号。

### 6.4 伪代码

```text
values = 空值栈
operators = 空运算符栈
expect_value = true

从左到右扫描：
    跳过空白

    如果 expect_value：
        若看到数字：带溢出检查地读取整个整数，压入 values
        若看到 '('：压入 operators
        否则：语法错误
        读取数字后 expect_value = false

    否则：
        若看到二元运算符 op：
            执行栈顶所有优先级 >= op 且不是 '(' 的运算
            压入 op
            expect_value = true
        若看到 ')'：
            执行到最近的 '('
            若没有 '('：语法错误
            弹出 '('
        否则：语法错误

如果结尾仍 expect_value：语法错误
执行剩余运算；若遇到未匹配 '('：语法错误
值栈必须恰好剩一个值，返回它
```

每次执行运算都先检查值栈至少有两个值，再检查除零与算术溢出。

### 6.5 为什么正确

对扫描前缀归纳。数字是一个完整因子，压入值栈后保持表示正确。左括号开始一个独立子表达式，阻止外层运算提前跨过它。

读到运算符时，所有优先级更高的栈顶运算都必须先算；相同优先级按左结合也必须先算。优先级更低的运算需要等待右侧因子，留在栈中正确。读到右括号时，括号内所有运算都已拥有右操作数，可以归约成一个值，再作为外层因子使用。

扫描结束后，按同样规则归约全部剩余运算。若语法合法，值栈最终恰好保存整棵表达式树的值。任何非法 token 顺序、括号或算术操作都会在对应检查处被拒绝，而不是产生一个猜测结果。

### 6.6 复杂度

- 时间复杂度：`O(n)`。每个 token 入栈、出栈至多一次；
- 额外空间：`O(n)`，最坏用于深括号和暂存值。

### 6.7 完整 C++20 实现

```cpp
#include <cassert>
#include <cctype>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <string_view>
#include <vector>

int precedence(char op) {
    if (op == '+' || op == '-') {
        return 1;
    }
    if (op == '*' || op == '/') {
        return 2;
    }
    return 0;
}

long long checked_add(long long lhs, long long rhs) {
    const long long min = std::numeric_limits<long long>::min();
    const long long max = std::numeric_limits<long long>::max();
    if ((rhs > 0 && lhs > max - rhs) ||
        (rhs < 0 && lhs < min - rhs)) {
        throw std::overflow_error("addition overflow");
    }
    return lhs + rhs;
}

long long checked_subtract(long long lhs, long long rhs) {
    const long long min = std::numeric_limits<long long>::min();
    const long long max = std::numeric_limits<long long>::max();
    if ((rhs > 0 && lhs < min + rhs) ||
        (rhs < 0 && lhs > max + rhs)) {
        throw std::overflow_error("subtraction overflow");
    }
    return lhs - rhs;
}

long long checked_multiply(long long lhs, long long rhs) {
    const long long min = std::numeric_limits<long long>::min();
    const long long max = std::numeric_limits<long long>::max();
    if (lhs == 0 || rhs == 0) {
        return 0;
    }

    bool overflow = false;
    if (lhs > 0) {
        overflow = (rhs > 0) ? (lhs > max / rhs) : (rhs < min / lhs);
    } else {
        overflow = (rhs > 0) ? (lhs < min / rhs) : (lhs < max / rhs);
    }
    if (overflow) {
        throw std::overflow_error("multiplication overflow");
    }
    return lhs * rhs;
}

long long checked_divide(long long lhs, long long rhs) {
    if (rhs == 0) {
        throw std::domain_error("division by zero");
    }
    if (lhs == std::numeric_limits<long long>::min() && rhs == -1) {
        throw std::overflow_error("division overflow");
    }
    return lhs / rhs;
}

long long apply_binary(char op, long long lhs, long long rhs) {
    switch (op) {
        case '+': return checked_add(lhs, rhs);
        case '-': return checked_subtract(lhs, rhs);
        case '*': return checked_multiply(lhs, rhs);
        case '/': return checked_divide(lhs, rhs);
        default: throw std::invalid_argument("unknown operator");
    }
}

void apply_top(std::vector<long long>& values, std::vector<char>& operators) {
    if (operators.empty() || operators.back() == '(' || values.size() < 2) {
        throw std::invalid_argument("malformed expression");
    }
    const char op = operators.back();
    operators.pop_back();
    const long long rhs = values.back();
    values.pop_back();
    const long long lhs = values.back();
    values.pop_back();
    values.push_back(apply_binary(op, lhs, rhs));
}

long long evaluate_integer_expression(std::string_view expression) {
    std::vector<long long> values;
    std::vector<char> operators;
    bool expect_value = true;
    std::size_t position = 0;

    while (position < expression.size()) {
        const unsigned char byte =
            static_cast<unsigned char>(expression[position]);
        if (std::isspace(byte) != 0) {
            ++position;
            continue;
        }

        if (expect_value) {
            if (std::isdigit(byte) != 0) {
                long long value = 0;
                const long long max = std::numeric_limits<long long>::max();
                while (position < expression.size()) {
                    const unsigned char digit_byte =
                        static_cast<unsigned char>(expression[position]);
                    if (std::isdigit(digit_byte) == 0) {
                        break;
                    }
                    const int digit = expression[position] - '0';
                    if (value > (max - digit) / 10) {
                        throw std::overflow_error("integer literal overflow");
                    }
                    value = value * 10 + digit;
                    ++position;
                }
                values.push_back(value);
                expect_value = false;
                continue;
            }
            if (expression[position] == '(') {
                operators.push_back('(');
                ++position;
                continue;
            }
            throw std::invalid_argument("expected an integer or '('");
        }

        const char token = expression[position];
        if (token == '+' || token == '-' || token == '*' || token == '/') {
            while (!operators.empty() && operators.back() != '(' &&
                   precedence(operators.back()) >= precedence(token)) {
                apply_top(values, operators);
            }
            operators.push_back(token);
            expect_value = true;
            ++position;
            continue;
        }
        if (token == ')') {
            while (!operators.empty() && operators.back() != '(') {
                apply_top(values, operators);
            }
            if (operators.empty()) {
                throw std::invalid_argument("unmatched ')'");
            }
            operators.pop_back();
            ++position;
            continue;
        }
        throw std::invalid_argument("expected an operator or ')'");
    }

    if (expect_value) {
        throw std::invalid_argument("expression ends before a value");
    }
    while (!operators.empty()) {
        if (operators.back() == '(') {
            throw std::invalid_argument("unmatched '('");
        }
        apply_top(values, operators);
    }
    if (values.size() != 1) {
        throw std::invalid_argument("malformed expression");
    }
    return values.back();
}

template <class Exception>
bool throws_as(std::string_view expression) {
    try {
        static_cast<void>(evaluate_integer_expression(expression));
    } catch (const Exception&) {
        return true;
    }
    return false;
}

int main() {
    assert(evaluate_integer_expression("2 + 3 * 4") == 14);
    assert(evaluate_integer_expression("(2 + 3) * 4") == 20);
    assert(evaluate_integer_expression("20 / 3") == 6);
    assert(evaluate_integer_expression("8 - 3 - 2") == 3);
    assert(evaluate_integer_expression(" 42 ") == 42);

    assert(throws_as<std::domain_error>("10 / (3 - 3)"));
    assert(throws_as<std::overflow_error>("9223372036854775807 + 1"));
    assert(throws_as<std::overflow_error>("9223372036854775808"));
    assert(throws_as<std::overflow_error>(
        "(0 - 9223372036854775807 - 1) - 1"));
    assert(throws_as<std::overflow_error>("9223372036854775807 * 2"));
    assert(throws_as<std::overflow_error>(
        "(0 - 9223372036854775807 - 1) / (0 - 1)"));
    assert(throws_as<std::invalid_argument>("1 +"));
    assert(throws_as<std::invalid_argument>("()"));
    assert(throws_as<std::invalid_argument>("2(3)"));
    assert(throws_as<std::invalid_argument>("-3"));
    assert(throws_as<std::invalid_argument>("(1 + 2"));
}
```

### 6.8 自测与边界

- 空输入、只有空白、单个数字；
- 多层括号、空括号、左右括号缺失；
- 同级左结合：`8-3-2`、`20/5/2`；
- 优先级：`2+3*4` 与 `(2+3)*4`；
- 相邻数字/括号造成的隐式乘法；
- 除零；
- 最大字面量、字面量超界，以及四种运算的正负溢出。

还可用一个独立递归下降实现随机生成小表达式，与本实现做差分测试。测试 oracle 必须独立，不能只是复制同一段归约逻辑。

### 6.9 常见追问

1. **怎样支持一元正负号？** 把语法增加 `unary = ('+'|'-') unary | factor`，或在 tokenizer 中区分一元和二元 token；不能简单在前面补 0，因为 `2*-3` 等上下文会出错。
2. **怎样输出逆波兰表达式？** 运算符被归约时输出它而不是立即计算，得到后缀序列。
3. **为什么 `std::isdigit(ch)` 前要转成 `unsigned char`？** 负的普通 `char` 直接传入字符分类函数不满足其参数前提。
4. **浮点、变量和函数调用怎么办？** 需要扩展 token、语法树和类型/错误规则；两个栈的核心思想仍可保留，但不能假装整数语义自动适用。

## 7. 怎样选择结构

| 题目中的信号 | 候选结构 | 先问一句 |
|---|---|---|
| 最近加入的未完成事项先处理 | 栈 | 是否需要匹配嵌套关系？ |
| 严格按到达顺序处理 | 队列 | 是否允许优先级插队？ |
| 窗口候选会从两端失效 | `deque` | 哪些旧候选可被永久支配？ |
| 只反复取当前最大或最小 | 堆 | 是否需要任意查找或删除？ |
| 每个位置找最近更大/更小 | 单调栈 | 相等元素如何处理？ |
| 每个窗口找最大/最小 | 单调队列 | 如何识别下标过期？ |
| 中缀表达式求值 | 值栈 + 运算符栈 | 语法、优先级、错误和数值边界是什么？ |

堆不适合查找任意元素；队列也不提供“中间删除”。结构的限制正是其操作成本可控的原因。

## 8. 变体练习

### 练习 1：有效括号

字符串只含 `()[]{}`，判断括号是否正确嵌套。

<details>
<summary>思路与答案</summary>

遇到左括号就入栈；遇到右括号时，栈必须非空且栈顶是对应左括号，然后弹出。扫描结束后栈必须为空。不变量是栈从底到顶保存已扫描前缀中尚未匹配的左括号。时间 `O(n)`、空间 `O(n)`。

</details>

### 练习 2：每日温度

对每天温度，求还要等待多少天才会遇到更高温度；不存在则为 `0`。

<details>
<summary>思路与答案</summary>

与“右侧第一个更大值”相同，维护温度非递增的下标栈。当前温度更高时弹出旧下标 `j`，答案写为 `i - j`。每个下标入栈、出栈至多一次，时间 `O(n)`、空间 `O(n)`。

</details>

### 练习 3：窗口内第一个负数

输出每个长度为 `k` 的窗口中第一个负数，不存在则返回空结果。

<details>
<summary>思路与答案</summary>

普通队列或 `deque` 中只保存负数的下标。右端加入负数下标；记录窗口答案前，弹出队首所有过期下标。队首就是当前窗口第一个负数。每个负数下标进出一次，时间 `O(n)`、空间 `O(k)`。

</details>

### 练习 4：持续数据流中的第 K 大值

构造一个对象，初始化后每收到一个新整数，就返回目前为止第 `k` 大的值。

<details>
<summary>思路与答案</summary>

维护容量不超过 `k` 的小顶堆。新值到达后按 Top-K 母题更新；当堆大小达到 `k` 时，堆顶就是第 `k` 大。如果目前元素少于 `k`，返回空结果。单次更新时间 `O(log k)`，空间 `O(k)`。

</details>

### 练习 5：最小的 K 个数

给定很长的数据流，只保存最小的 `k` 个数。

<details>
<summary>思路与答案</summary>

与最大 K 个相反，维护容量为 `k` 的大顶堆。堆满后，只有新值小于堆顶时才替换。堆顶始终是当前最小 `k` 个候选中最大的淘汰门槛。时间 `O(n log k)`，空间 `O(k)`。

</details>

### 练习 6：合并多个带时间戳的事件流

每个输入流内部按 `(timestamp, sequence)` 有序，输出全局确定顺序。

<details>
<summary>思路与答案</summary>

小顶堆中保存每个流当前事件，比较键依次为时间戳、序号和稳定的流编号。弹出后只从同一流读取下一条。若不同流的时间戳和序号都可能相同，必须定义最终平局规则；否则多次运行的输出顺序可能不稳定。算法结构为 `O(N log k)`，但在线系统还要定义某个流暂时没有数据时是否等待。

</details>

## 9. 面试复述清单

- 栈、队列、`deque` 和堆的取出规则分别是什么？
- 单调栈中一个下标弹出时，为什么当前值是它的第一个更大值？
- 单调队列为什么可以删除队尾较小的旧候选？
- 滑动窗口中为什么保存下标而不是只保存值？
- Top-K 为什么最大的 `k` 个元素要用小顶堆？
- 多路合并的堆里为什么每个输入只需保存一个候选？
- `priority_queue` 的比较器写反会产生大顶堆还是小顶堆？你能用一句话验证吗？
- 表达式求值中，栈在什么时候归约运算符，如何拒绝除零和溢出？

如果能画出容器中候选如何变化，并说清每次删除为何安全，就不需要死记代码。

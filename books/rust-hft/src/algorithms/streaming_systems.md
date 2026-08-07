# 流式与工程算法：数据不会一次全部到齐

许多算法题默认“完整数组已经放在内存里”。真实系统却更像传送带：日志、行情、任务和模型请求不断到来，你通常只能看一次，还必须限制内存。此时问题从“对一个数组求答案”变成了“每来一个事件，怎样只更新少量状态”。

> 本章目标：P0 会设计固定窗口和序号检测，P1 理解在线统计和事件时间；在线中位数与近似摘要只需按 P2 选读。所有实现都要能用不变量说明为什么正确，并用朴素算法做随机对拍。

对本书目标岗位，**P0** 是固定窗口、状态上限、重复/旧消息/序号缺口；它们直接对应行情和事件管线。在线均值/方差与事件时间是 **P1**；在线中位数、近似摘要和水库抽样是 **P2**。这里提到 P2 是为了告诉你方案入口，不表示都要实现。

本章中的场景是训练题，不代表任何公司的真实面试题。

## 1. 先问四个流式问题

拿到持续输入的问题，不要马上选容器。先问：

1. **答案针对全部历史，还是最近 `k` 个事件？** 全部历史可能只需几个累计量；固定窗口通常需要保存窗口状态。
2. **事件是否按顺序到达？** 若可能乱序，就要定义事件时间、到达时间以及迟到数据政策。
3. **内存是否有上限？** “把历史全部存起来”虽然简单，却可能不是合法答案。
4. **允许近似吗？** 精确去重、精确分位数可能需要大量状态；若允许误差，可以考虑采样或近似结构。

还要区分两种复杂度：

- **单次更新成本**：每来一个事件要做多少工作；
- **总成本**：处理 `n` 个事件共做多少工作。

“某次操作可能弹出很多元素”不一定意味着总成本是 `O(n²)`。若每个元素一生只入队、出队一次，总成本仍可能是 `O(n)`；这种分析叫**摊还分析**。

## 2. 母题一：最近 `k` 个数量的滚动和

### 2.1 白话题意

输入一串数量 `values` 和窗口长度 `k`。每当凑齐 `k` 个元素，就输出这 `k` 个元素的和。

例如：

```text
values = [2, 1, 4, 3], k = 3
窗口 [2, 1, 4] 的和是 7
窗口 [1, 4, 3] 的和是 8
答案是 [7, 8]
```

约定 `k == 0` 或 `k > values.size()` 时没有完整窗口，返回空结果。

### 2.2 最直接的办法

每移动一步，都重新遍历窗口里的 `k` 个元素。共有约 `n` 个窗口，因此时间复杂度是 `O(nk)`。

这个版本不丢人。它容易写对，正适合作为小规模输入上的 **oracle（参考答案）**。

### 2.3 关键观察与不变量

相邻窗口大部分元素相同：

```text
新窗口和 = 旧窗口和 - 离开的元素 + 新进入的元素
```

循环结束时保持下面的不变量：

> `sum` 等于当前下标结尾、长度不超过 `k` 的最近一段元素之和；一旦长度达到 `k`，它恰好就是当前完整窗口的和。

### 2.4 伪代码

```text
如果 k 为 0 或 k 大于输入长度：返回空
sum = 前 k 个元素之和
记录 sum
从下标 k 开始遍历：
    sum += 当前新元素
    sum -= 下标 i-k 的离开元素
    记录 sum
返回全部记录
```

### 2.5 为什么正确

第一个窗口直接求和，所以答案正确。之后每一步只删除旧窗口中唯一离开的元素，再加入新窗口中唯一新增的元素；其余 `k-1` 个元素没有变化。因此更新后的 `sum` 正好等于新窗口之和。由此逐步推出所有窗口都正确。

### 2.6 复杂度

- 时间：`O(n)`；
- 额外空间：若不计返回结果，为 `O(1)`；
- 若输入是真正的数据流，只需再保存最近 `k` 个值，状态空间为 `O(k)`。

### 2.7 C++20：优化解与随机对拍

下面同时保留朴素版和优化版。随机对拍的意思是：生成很多小输入，让两个实现给出完全相同的答案。它特别适合验证增量算法。

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <random>
#include <vector>

std::vector<std::int64_t> rolling_sums_brute(
    const std::vector<std::int32_t>& values,
    std::size_t k
) {
    std::vector<std::int64_t> result;
    if (k == 0 || k > values.size()) {
        return result;
    }

    for (std::size_t begin = 0; begin + k <= values.size(); ++begin) {
        std::int64_t sum{0};
        for (std::size_t i = begin; i < begin + k; ++i) {
            sum += values[i];
        }
        result.push_back(sum);
    }
    return result;
}

std::vector<std::int64_t> rolling_sums(
    const std::vector<std::int32_t>& values,
    std::size_t k
) {
    std::vector<std::int64_t> result;
    if (k == 0 || k > values.size()) {
        return result;
    }

    std::int64_t sum{0};
    for (std::size_t i = 0; i < k; ++i) {
        sum += values[i];
    }
    result.push_back(sum);

    for (std::size_t i = k; i < values.size(); ++i) {
        sum += values[i];
        sum -= values[i - k];
        result.push_back(sum);
    }
    return result;
}

int main() {
    assert((rolling_sums({2, 1, 4, 3}, 3) ==
            std::vector<std::int64_t>{7, 8}));
    assert(rolling_sums({}, 1).empty());
    assert(rolling_sums({1, 2}, 0).empty());
    assert(rolling_sums({1, 2}, 3).empty());
    assert((rolling_sums({-2, 5}, 1) ==
            std::vector<std::int64_t>{-2, 5}));

    std::mt19937 generator{20260805};
    std::uniform_int_distribution<int> length_dist{0, 20};
    std::uniform_int_distribution<int> value_dist{-20, 20};

    for (int trial = 0; trial < 2'000; ++trial) {
        const int length = length_dist(generator);
        std::vector<std::int32_t> values;
        for (int i = 0; i < length; ++i) {
            values.push_back(value_dist(generator));
        }
        for (std::size_t k = 0; k <= values.size() + 1; ++k) {
            assert(rolling_sums(values, k) ==
                   rolling_sums_brute(values, k));
        }
    }
}
```

这里把和保存在 `std::int64_t` 中，是因为多个 32 位数量相加可能超出 32 位范围。若输入规模仍可能让 64 位溢出，就必须继续限制输入或使用显式溢出检查。

### 2.8 面试追问

- 输入不是数组，而是无限数据流时怎样做？使用大小最多为 `k` 的环形缓冲或队列；加入新值，窗口超长时删除最旧值。
- 若要滚动最大值呢？普通的和公式不再够用，可使用单调双端队列。
- 若事件带时间戳，要求“最近五秒”呢？窗口不再按元素个数弹出，而是按时间阈值弹出；还要定义乱序政策。

## 3. P1 母题：一次扫描计算均值与样本方差

### 3.1 为什么不能只保存总和与平方和

数学上可以用 `E[x²] - E[x]²` 求方差，但当两个很大的近似数相减时，浮点误差可能被放大。Welford 算法在每个样本到来时更新均值和平方离差和，通常更稳定。

状态含义：

- `count`：已经看到的样本数；
- `mean`：这些样本的均值；
- `m2`：每个样本到均值的平方离差总量。

### 3.2 伪代码

```text
加入新值 x：
    count += 1
    delta = x - old_mean
    mean = old_mean + delta / count
    delta2 = x - new_mean
    m2 += delta * delta2

若 count == 0：均值不存在
若 count < 2：样本方差不存在
否则样本方差 = m2 / (count - 1)
```

### 3.3 正确性直觉

新均值等于“旧总量加上新样本”再除以新数量，只是公式被改写成增量形式。`delta * delta2` 则补上新样本加入后平方离差总量的变化。严格证明可用归纳法：假设旧状态准确，代入更新公式后得到包含新样本的定义式。

### 3.4 C++20 实现

```cpp
#include <cassert>
#include <cmath>
#include <cstddef>
#include <optional>

class RunningStats {
public:
    void add(double value) {
        ++count_;
        const double delta = value - mean_;
        mean_ += delta / static_cast<double>(count_);
        const double delta_after = value - mean_;
        m2_ += delta * delta_after;
    }

    [[nodiscard]] std::size_t count() const {
        return count_;
    }

    [[nodiscard]] std::optional<double> mean() const {
        if (count_ == 0) {
            return std::nullopt;
        }
        return mean_;
    }

    [[nodiscard]] std::optional<double> sample_variance() const {
        if (count_ < 2) {
            return std::nullopt;
        }
        return m2_ / static_cast<double>(count_ - 1);
    }

private:
    std::size_t count_{0};
    double mean_{0.0};
    double m2_{0.0};
};

bool close_to(double left, double right, double tolerance = 1e-12) {
    return std::abs(left - right) <= tolerance;
}

int main() {
    RunningStats stats;
    assert(!stats.mean().has_value());
    assert(!stats.sample_variance().has_value());

    stats.add(1.0);
    assert(close_to(*stats.mean(), 1.0));
    assert(!stats.sample_variance().has_value());

    stats.add(2.0);
    stats.add(3.0);
    stats.add(4.0);
    assert(stats.count() == 4);
    assert(close_to(*stats.mean(), 2.5));
    assert(close_to(*stats.sample_variance(), 5.0 / 3.0));
}
```

时间复杂度是每个样本 `O(1)`，状态空间是 `O(1)`。但这计算的是“从开始到现在”的统计，不是固定窗口统计；删除最旧样本需要另一套更新逻辑，并且数值误差要重新评估。

### 3.5 面试追问

- 为什么方差返回 `optional`？零个样本没有均值，少于两个样本没有样本方差；`0` 会把“没有答案”和“方差恰好为零”混在一起。
- 能否并行合并两个 `RunningStats`？可以，但需要推导两组数量、均值和 `m2` 的合并公式，不能简单平均两个均值。
- 遇到 `NaN` 或无穷怎么办？业务接口要明确拒绝、传播还是单独计数，不能悄悄混入状态。

## 4. 母题三：检测重复、旧消息与序号缺口

### 4.1 白话题意

消息带有严格递增的非负序号。第一条消息建立起点；之后：

- 恰好等于期待序号：正常；
- 大于期待序号：中间出现缺口；
- 小于期待序号：它是旧消息或重复消息。

下面的简化监控器发现缺口后会把当前较大序号视为新的进度。生产系统是否这样做，取决于恢复协议：有的系统必须暂停处理并请求快照。

### 4.2 不变量与伪代码

不变量：`expected` 始终等于“按本监控器已经接受的最大序号加一”。

```text
如果还没有 expected：
    expected = sequence + 1
    返回 First
如果 sequence < expected：返回 OldOrDuplicate
如果 sequence == expected：
    expected += 1
    返回 InOrder
否则：
    缺失范围是 [expected, sequence - 1]
    expected = sequence + 1
    返回 Gap
```

### 4.3 C++20 实现

```cpp
#include <cassert>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>

enum class ArrivalKind {
    First,
    InOrder,
    Gap,
    OldOrDuplicate
};

struct Arrival {
    ArrivalKind kind;
    std::optional<std::int64_t> missing_begin;
    std::optional<std::int64_t> missing_end;
};

class SequenceTracker {
public:
    Arrival observe(std::int64_t sequence) {
        if (sequence < 0 || sequence == std::numeric_limits<std::int64_t>::max()) {
            throw std::invalid_argument{"sequence is outside the supported range"};
        }

        if (!expected_.has_value()) {
            expected_ = sequence + 1;
            return {ArrivalKind::First, std::nullopt, std::nullopt};
        }

        if (sequence < *expected_) {
            return {ArrivalKind::OldOrDuplicate, std::nullopt, std::nullopt};
        }

        if (sequence == *expected_) {
            ++(*expected_);
            return {ArrivalKind::InOrder, std::nullopt, std::nullopt};
        }

        const std::int64_t missing_begin = *expected_;
        const std::int64_t missing_end = sequence - 1;
        expected_ = sequence + 1;
        return {ArrivalKind::Gap, missing_begin, missing_end};
    }

private:
    std::optional<std::int64_t> expected_;
};

int main() {
    SequenceTracker tracker;
    assert(tracker.observe(100).kind == ArrivalKind::First);
    assert(tracker.observe(101).kind == ArrivalKind::InOrder);

    const Arrival gap = tracker.observe(104);
    assert(gap.kind == ArrivalKind::Gap);
    assert(gap.missing_begin == 102);
    assert(gap.missing_end == 103);

    assert(tracker.observe(104).kind == ArrivalKind::OldOrDuplicate);
    assert(tracker.observe(103).kind == ArrivalKind::OldOrDuplicate);
    assert(tracker.observe(105).kind == ArrivalKind::InOrder);
}
```

单次更新时间和状态空间都是 `O(1)`。但它不能区分“重复消息”和“迟到旧消息”，也没有处理序号回绕。这正说明：算法正确性永远绑定在题目约束上。

### 4.4 面试追问

- 若要精确识别最近一分钟内的重复 ID 呢？可以用哈希集合加按时间排序的队列，过期时同时从两者删除；需要处理同一 ID 重复到来时的引用计数或版本。
- 发现缺口后能否继续更新订单簿？通常要根据协议暂停、缓冲后续消息并请求重传或快照，否则本地状态可能永久错误。
- 多线程同时调用怎么办？当前类不是线程安全的。先定义单写者还是多写者，再选择串行化、锁或消息队列。

## 5. P2 选读：在线中位数

### 5.1 从排序到两个堆

每来一个数就把全部历史排序，单次成本很高。我们真正需要的不是完整顺序，只是中间位置。

维护两个堆：

- `lower` 是最大堆，保存较小的一半；堆顶是较小一半的最大值；
- `upper` 是最小堆，保存较大的一半；堆顶是较大一半的最小值。

保持两个不变量：

1. `lower` 的每个元素都不大于 `upper` 的每个元素；
2. `lower` 的元素数量等于 `upper`，或只比它多一个。

### 5.2 伪代码

```text
加入 x：
    如果 lower 为空或 x <= lower 堆顶：放入 lower
    否则：放入 upper
    若 lower 比 upper 多两个：lower 堆顶移到 upper
    若 upper 比 lower 多：upper 堆顶移到 lower

查询中位数：
    两边一样多：两个堆顶的平均值
    否则：lower 堆顶
```

### 5.3 C++20 实现

```cpp
#include <cassert>
#include <cmath>
#include <functional>
#include <optional>
#include <queue>
#include <vector>

class OnlineMedian {
public:
    void add(double value) {
        if (lower_.empty() || value <= lower_.top()) {
            lower_.push(value);
        } else {
            upper_.push(value);
        }

        if (lower_.size() > upper_.size() + 1) {
            upper_.push(lower_.top());
            lower_.pop();
        } else if (upper_.size() > lower_.size()) {
            lower_.push(upper_.top());
            upper_.pop();
        }
    }

    [[nodiscard]] std::optional<double> median() const {
        if (lower_.empty()) {
            return std::nullopt;
        }
        if (lower_.size() == upper_.size()) {
            return lower_.top() / 2.0 + upper_.top() / 2.0;
        }
        return lower_.top();
    }

private:
    std::priority_queue<double> lower_;
    std::priority_queue<double, std::vector<double>, std::greater<>> upper_;
};

bool close_to(double left, double right) {
    return std::abs(left - right) < 1e-12;
}

int main() {
    OnlineMedian values;
    assert(!values.median().has_value());

    values.add(5.0);
    assert(close_to(*values.median(), 5.0));
    values.add(1.0);
    assert(close_to(*values.median(), 3.0));
    values.add(9.0);
    assert(close_to(*values.median(), 5.0));
    values.add(2.0);
    assert(close_to(*values.median(), 3.5));
}
```

每次插入最多进行常数次堆操作，时间为 `O(log n)`；查询中位数为 `O(1)`；保存全部历史，空间为 `O(n)`。

`lower_.top() / 2.0 + upper_.top() / 2.0` 避免先把两个很大的同号值相加，但浮点输入仍要定义 `NaN` 政策。若是 64 位整数，也不能先做可能溢出的整数加法。

### 5.4 固定窗口中位数为什么更难

两个堆很容易加入元素，却不能高效删除“恰好离开窗口的那个旧元素”。常见方案包括：

- 两个堆加延迟删除哈希表；
- 支持顺序统计的平衡树；
- 值域较小时用频次数组或 Fenwick Tree；
- 接受近似分位数算法。

面试时先说清约束，再选方案；不要把“在线全历史中位数”的代码直接冒充固定窗口答案。

## 6. P1 系统讨论：事件时间、到达时间与 watermark

假设事件内容写着 `10:00:03`，但网络延迟让它在 `10:00:08` 才到：

- **事件时间**是 `10:00:03`；
- **到达/处理时间**是 `10:00:08`。

若窗口按事件时间计算，就必须决定要等迟到事件多久。watermark 可以理解成系统的声明：“我认为早于这个时间的绝大多数事件已经到齐。”它不是自然真理；过早推进会漏掉迟到数据，过晚推进会增加状态和延迟。

算法题若没有乱序说明，可以先确认“输入是否按时间排序”。工程面试则还要主动问：

- 迟到事件丢弃、修正旧结果，还是触发补偿？
- 重放同一事件是否幂等？
- watermark 怎样生成，按分区还是全局？
- 状态如何做检查点并在失败后恢复？

## 7. P2 知识边界：精确、近似与内存下界

有些要求本身就意味着保存大量信息。例如，对无限值域的数据流做**绝对精确去重**，若又不允许过期，系统必须记住过去见过的 ID；状态会随不同 ID 数量增长。

当内存受限时，应明确改变承诺：

| 需求 | 可选思路 | 代价 |
|---|---|---|
| 固定时间内精确去重 | 哈希表 + 过期队列 | 内存随窗口内唯一 ID 增长 |
| 长期近似去重 | Bloom filter：用位数组回答“可能见过/一定没见过” | 可能把新 ID 误判为见过，普通版本不方便删除 |
| 近似分位数 | KLL、t-digest 等压缩分布摘要 | 不保存全部样本，答案存在可描述的误差 |
| 从未知长度流均匀抽样 | reservoir sampling（水库抽样）：以递减概率替换固定容量样本 | 只保留固定数量样本，不保存全部数据 |

面试中说“使用 Bloom filter”还不够，需要补上假阳性、容量、过期和重建策略。

## 8. 练习与参考思路

### 练习 1：固定窗口最大值

要求每来一个值，输出最近 `k` 个值的最大值。设计 `O(n)` 总时间算法。

<details>
<summary>参考思路</summary>

维护一个下标双端队列，使对应值从队首到队尾单调不增。加入新元素前，从队尾删除所有不大于新值的下标；再从队首删除已经离开窗口的下标。队首始终是当前最大值。每个下标最多入队、出队一次，所以总时间 `O(n)`，空间 `O(k)`。

</details>

### 练习 2：最近一分钟精确去重

事件包含 `id` 和单调不减的到达时间。同一 ID 在 60 秒内只处理一次。

<details>
<summary>参考思路</summary>

使用哈希表保存 ID 最近一次被接受的时间，并用队列按时间保存已接受记录。新事件到来时先弹出超过窗口的记录；弹出时只有当哈希表中的时间仍等于该记录时间，才能删除哈希项，避免误删同一 ID 的更新版本。然后查询当前 ID 决定接受或拒绝。

</details>

### 练习 3（P2）：水库抽样

输入长度事先未知，只保留一个样本，并保证处理完 `n` 个元素后每个元素被保留的概率都是 `1/n`。

<details>
<summary>参考思路</summary>

第一个元素必选。看到第 `i` 个元素时，以 `1/i` 的概率替换当前样本。对任意早期元素，它在第 `i` 步前被保留的概率是 `1/(i-1)`，再乘本步不被替换的概率 `(i-1)/i`，得到 `1/i`。最后每个元素概率相同。

</details>

### 练习 4：可恢复的序号检测

把本章 `SequenceTracker` 改成发现缺口后不推进 `expected`，并能在缺失消息补齐后继续。

<details>
<summary>参考思路</summary>

不能只保存一个未来序号。可以在有界范围内用有序集合缓冲已到达的未来序号；每补到 `expected`，就连续从集合中删除下一批相邻序号并推进。必须设置缓冲上限、超时和请求快照策略，否则攻击或长期缺口会让内存无限增长。

</details>

### 练习 5：如何验证增量算法

为固定窗口最大值写一个 `O(nk)` 朴素版本和随机对拍。至少生成哪些输入？

<details>
<summary>参考答案</summary>

空输入、`k=0`、`k=1`、`k=n`、`k>n`、全相等、严格递增、严格递减、正负混合和大量重复值都应覆盖。随机生成小数组与所有合法/非法 `k`，比较两个实现的完整输出；随机测试不能代替这些定向边界测试。

</details>

## 9. 本章自测

- [ ] 能解释批处理、全历史流式统计和固定窗口统计的区别。
- [ ] 能为滚动和写出朴素版、优化版和随机对拍。
- [ ] **P1**：若学习了 Welford 在线方差，能说清 `count`、`mean`、`m2` 的含义。
- [ ] 能指出简化序号监控器没有处理哪些生产语义。
- [ ] **P2**：若学习了在线中位数，能用两个不变量解释两个堆的关系。
- [ ] 知道摊还 `O(1)` 不代表每一次操作都严格只做一步。
- [ ] 遇到无限流时会主动确认内存上限、乱序、过期和近似误差。

下一章可进入[岗位场景综合题](company_scenarios.md)，把这些模式放进缓存、任务依赖、行情与风控问题中。

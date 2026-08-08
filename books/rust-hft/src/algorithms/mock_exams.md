# 限时模拟：笔试、白板编码与追问

看懂单独章节不等于能在时间压力下独立解题。模拟训练的价值，是在**看不到题型标签**时完成需求澄清、算法选择、C++ 实现和测试，并暴露自己究竟卡在哪一步。

> 本章包含两套 90 分钟模拟笔试和一套 45 分钟模拟面试。它们是本书根据岗位能力设计的训练题，不是 DeepSeek 或九坤真题，也不代表真实难度与流程。

## 1. 怎样使用模拟题

每套题先完整做一遍。只有错题、超时题或解释不清的题需要间隔重做：

1. **第一遍按真实时间做**：不看答案，可以查 C++ 标准库接口，但不能搜索题解；
2. **当天复盘失分题**：记录错误类别，读答案后关掉页面重写；
3. **第 7 天只重做失分模式**：从空白文件完成，不复制旧代码。已经稳定通过的题换成陌生变体，不机械抄第三遍。

建议保留以下证据：

```text
开始/结束时间：
每题第一次得到正确样例的时间：
是否写了暴力基线：
是否主动说出不变量：
失败用例：
错误类别：理解 / 算法 / 复杂度 / C++ / 边界 / 表达
下次只改变的一件事：
```

## 2. 统一评分表（100 分）

| 维度 | 分数 | 判断标准 |
|---|---:|---|
| 读题与约束 | 10 | 主动确认空输入、重复、范围、顺序和无解语义 |
| 正确基线 | 10 | 能先给一个正确的朴素解，不靠猜模板 |
| 关键观察与不变量 | 15 | 能说明优化依据，而非只背代码 |
| 正确性 | 15 | 样例和隐藏边界都正确，能用归纳/循环不变量解释 |
| 时间与空间复杂度 | 10 | 使用正确变量，区分平均、最坏与摊还 |
| C++ 实现 | 20 | 类型、STL、比较器、生命周期和溢出处理合理 |
| 测试 | 10 | 至少覆盖空、单元素、重复、无解与极值中的相关项 |
| 表达与追问 | 10 | 边写边解释，需求变化时能调整而不是推翻全部代码 |

分数解释：

- **85～100**：可以进入真实模拟面试，但仍需按具体岗位补系统、数学或业务；
- **70～84**：算法主线基本形成，优先重做边界和解释薄弱的题；
- **50～69**：常能认出题型，但还依赖答案；回到对应母题完成伪代码和对拍；
- **低于 50**：先恢复 C++ 与基础模式，不要用增加题量掩盖地基问题。

## 3. 模拟笔试 A：基础设施与数据处理（90 分钟）

建议分配：读题 5 分钟，A1 20 分钟，A2 25 分钟，A3 30 分钟，测试与回看 10 分钟。

### A1. 合并资源占用区间（20 分）

任务占用区间使用半开区间 `[start, end)`，满足 `0 <= start < end`；空区间不是有效任务。合并所有重叠或首尾相接的区间，返回按开始时间升序排列的不相交区间。

```text
输入：[(1, 4), (2, 5), (8, 10), (10, 12)]
输出：[(1, 5), (8, 12)]
```

要求说明为什么排序后只需与最后一个结果比较。

### A2. 最少需要多少个 worker（30 分）

每个任务给出半开执行区间 `[start, end)`，满足 `0 <= start < end`；空区间不是有效任务。同一 worker 上的任务不能重叠。求执行全部任务至少需要多少个 worker。结束时刻等于另一任务开始时刻时，可以复用 worker。

```text
输入：[(0, 10), (2, 6), (6, 9), (11, 12)]
输出：2
```

要求给出 `O(n log n)` 解法，并解释堆里应该保存什么。

### A3. 错误码 Top-K（40 分）

输入一批错误码字符串和整数 `k`，返回出现次数最多的 `k` 个不同错误码。次数相同时，字典序较小者在前。`k == 0` 返回空；`k` 大于不同错误码数量时返回全部。

```text
输入：codes = ["OOM", "IO", "OOM", "NET", "IO", "OOM"], k = 2
输出：["OOM", "IO"]
```

先给排序解，再讨论 `k` 很小而不同错误码很多时如何改用堆。

## 4. 模拟笔试 A 参考答案

做完三题后再展开。

<details>
<summary>A1 参考答案：区间合并</summary>

关键观察：按开始时间排序后，尚未处理的区间开始位置只会越来越大。若当前区间与结果最后一个区间不重叠，它也不可能与更早的结果区间重叠；若重叠，只需扩大最后结果的结束位置。

```text
按 (start, end) 排序
result = 空
依次处理 interval：
    若 result 为空或 interval.start > result.back.end：追加
    否则：result.back.end = max(result.back.end, interval.end)
```

时间 `O(n log n)`，排序之外的扫描为 `O(n)`；返回结果之外，取决于排序是否复制输入。

```cpp
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

using Interval = std::pair<std::int64_t, std::int64_t>;

std::vector<Interval> merge_intervals(std::vector<Interval> intervals) {
    for (const auto [start, end] : intervals) {
        if (start < 0 || end <= start) {
            throw std::invalid_argument{"invalid interval"};
        }
    }
    std::sort(intervals.begin(), intervals.end());

    std::vector<Interval> result;
    for (const auto [start, end] : intervals) {
        if (result.empty() || start > result.back().second) {
            result.emplace_back(start, end);
        } else {
            result.back().second = std::max(result.back().second, end);
        }
    }
    return result;
}

int main() {
    assert((merge_intervals({{1, 4}, {2, 5}, {8, 10}, {10, 12}}) ==
            std::vector<Interval>{{1, 5}, {8, 12}}));
    assert(merge_intervals({}).empty());
    assert((merge_intervals({{5, 7}, {1, 9}}) ==
            std::vector<Interval>{{1, 9}}));

    bool rejected_empty{false};
    try {
        (void)merge_intervals({{3, 3}});
    } catch (const std::invalid_argument&) {
        rejected_empty = true;
    }
    assert(rejected_empty);
}
```

</details>

<details>
<summary>A2 参考答案：最少 worker</summary>

按开始时间处理任务。最小堆保存每个正在使用的 worker 的结束时间；开始新任务前，释放所有结束时间 `<= start` 的 worker。加入当前结束时间后，堆的最大大小就是最大同时运行数，也就是最少 worker 数。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <queue>
#include <stdexcept>
#include <utility>
#include <vector>

using Interval = std::pair<std::int64_t, std::int64_t>;

std::size_t minimum_workers(std::vector<Interval> tasks) {
    for (const auto [start, end] : tasks) {
        if (start < 0 || end <= start) {
            throw std::invalid_argument{"invalid task interval"};
        }
    }
    std::sort(tasks.begin(), tasks.end());

    std::priority_queue<
        std::int64_t,
        std::vector<std::int64_t>,
        std::greater<>
    > ending_times;
    std::size_t answer{0};

    for (const auto [start, end] : tasks) {
        while (!ending_times.empty() && ending_times.top() <= start) {
            ending_times.pop();
        }
        ending_times.push(end);
        answer = std::max(answer, ending_times.size());
    }
    return answer;
}

int main() {
    assert(minimum_workers({{0, 10}, {2, 6}, {6, 9}, {11, 12}}) == 2);
    assert(minimum_workers({}) == 0);
    assert(minimum_workers({{0, 1}, {1, 2}, {2, 3}}) == 1);
    assert(minimum_workers({{0, 5}, {0, 5}, {0, 5}}) == 3);

    bool rejected_empty_task{false};
    try {
        (void)minimum_workers({{5, 5}});
    } catch (const std::invalid_argument&) {
        rejected_empty_task = true;
    }
    assert(rejected_empty_task);
}
```

每个任务排序一次、入堆出堆各至多一次，时间 `O(n log n)`，堆空间 `O(n)`。本题拒绝 `[t,t)` 空任务，避免把“不占用任何时间”误算成一个 worker；另一种合法契约是接受但忽略空区间，接口必须二选一说清楚。如果只在每次任务前弹出一个已结束 worker，在计算“当前活跃数”时也可能成立于某些写法，但弹出所有已结束项让堆不变量和后续扩展更清楚。

</details>

<details>
<summary>A3 参考答案：错误码 Top-K</summary>

先用哈希表统计频次，再把不同错误码放入数组排序。排序键是“次数降序，错误码升序”。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

std::vector<std::string> top_error_codes(
    const std::vector<std::string>& codes,
    std::size_t k
) {
    std::unordered_map<std::string, std::size_t> counts;
    for (const auto& code : codes) {
        ++counts[code];
    }

    std::vector<std::pair<std::string, std::size_t>> ranked;
    ranked.reserve(counts.size());
    for (const auto& [code, count] : counts) {
        ranked.emplace_back(code, count);
    }

    std::sort(ranked.begin(), ranked.end(), [](const auto& left, const auto& right) {
        if (left.second != right.second) {
            return left.second > right.second;
        }
        return left.first < right.first;
    });

    k = std::min(k, ranked.size());
    std::vector<std::string> result;
    result.reserve(k);
    for (std::size_t i = 0; i < k; ++i) {
        result.push_back(ranked[i].first);
    }
    return result;
}

int main() {
    assert((top_error_codes({"OOM", "IO", "OOM", "NET", "IO", "OOM"}, 2) ==
            std::vector<std::string>{"OOM", "IO"}));
    assert(top_error_codes({}, 3).empty());
    assert(top_error_codes({"B", "A"}, 0).empty());
    assert((top_error_codes({"B", "A"}, 5) ==
            std::vector<std::string>{"A", "B"}));
}
```

设输入数为 `n`、不同错误码数为 `u`，平均时间 `O(n + u log u)`，空间 `O(u)`。若 `k << u`，可以维护大小为 `k` 的堆，将排序阶段降为 `O(u log k)`；比较器必须同时编码频次和字典序，否则并列答案会错。

</details>

## 5. 模拟笔试 B：行情、窗口与风险（90 分钟）

建议分配：读题 5 分钟，B1 20 分钟，B2 30 分钟，B3 25 分钟，测试与回看 10 分钟。

### B1. 找出缺失序号区间（25 分）

给定按非递减顺序到达的非负序号，可能包含重复。再给闭区间 `[expected_begin, expected_end]`，满足 `expected_end < INT64_MAX`，返回区间内所有缺失序号的连续范围。

```text
sequences = [10, 11, 11, 14, 17]
expected = [10, 18]
missing = [(12, 13), (15, 16), (18, 18)]
```

输入若下降或序号在目标区间外，应明确处理政策。本题选择抛出异常。

### B2. 最近 `k` 笔成交的 VWAP（40 分）

VWAP 是 Volume-Weighted Average Price（成交量加权平均价）：把每笔价格按其成交数量加权，而不是把价格直接做算术平均。

每笔成交包含正整数价格 tick（用市场最小价格步长表示的整数价格）和正整数数量。每凑齐 `k` 笔，输出窗口成交额之和除以数量之和。`k == 0` 或 `k > n` 返回空。要求在相乘和相加前检查 64 位有符号整数溢出。

```text
trades = [(100, 2), (110, 1), (90, 1)], k = 2
输出 = [310/3, 200/2]
```

### B3. 绝对敞口 Top-K（35 分）

每个标的给出唯一 `symbol` 和有符号敞口 `exposure`。返回绝对敞口最大的 `k` 个标的；绝对值相同时按标的名升序。要正确处理最小 64 位整数，因为对它直接取负仍会溢出。

## 6. 模拟笔试 B 参考答案

<details>
<summary>B1 参考答案：缺失区间</summary>

维护 `next_expected`。跳过恰好等于上一项的重复；若当前序号大于 `next_expected`，缺口是 `[next_expected, sequence-1]`，然后把期待值推进到 `sequence+1`。扫描后若还没到终点，再补尾部缺口。

```cpp
#include <cassert>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

using Range = std::pair<std::int64_t, std::int64_t>;

std::vector<Range> missing_ranges(
    const std::vector<std::int64_t>& sequences,
    std::int64_t expected_begin,
    std::int64_t expected_end
) {
    if (expected_begin < 0 || expected_end < expected_begin ||
        expected_end == std::numeric_limits<std::int64_t>::max()) {
        throw std::invalid_argument{"invalid expected range"};
    }

    std::vector<Range> result;
    std::int64_t next_expected = expected_begin;
    std::int64_t previous = -1;

    for (const std::int64_t sequence : sequences) {
        if (sequence < expected_begin || sequence > expected_end) {
            throw std::out_of_range{"sequence outside expected range"};
        }
        if (previous > sequence) {
            throw std::invalid_argument{"sequences are not ordered"};
        }
        previous = sequence;

        if (sequence < next_expected) {
            continue;  // 已见过的重复
        }
        if (sequence > next_expected) {
            result.emplace_back(next_expected, sequence - 1);
        }
        next_expected = sequence + 1;
    }

    if (next_expected <= expected_end) {
        result.emplace_back(next_expected, expected_end);
    }
    return result;
}

int main() {
    assert((missing_ranges({10, 11, 11, 14, 17}, 10, 18) ==
            std::vector<Range>{{12, 13}, {15, 16}, {18, 18}}));
    assert(missing_ranges({1, 2, 3}, 1, 3).empty());
    assert((missing_ranges({}, 4, 6) == std::vector<Range>{{4, 6}}));
    assert((missing_ranges({5}, 5, 5).empty()));

    bool rejected_maximum{false};
    try {
        (void)missing_ranges({}, 0, std::numeric_limits<std::int64_t>::max());
    } catch (const std::invalid_argument&) {
        rejected_maximum = true;
    }
    assert(rejected_maximum);
}
```

时间 `O(n)`，返回结果之外空间 `O(1)`。代码显式执行 `expected_end < INT64_MAX` 的题目约束；若允许最大值，`sequence + 1` 需要 `optional` 或“已经越过终点”的独立状态，不能让有符号整数溢出。

</details>

<details>
<summary>B2 参考答案：滚动 VWAP</summary>

维护窗口成交额和数量。加入新成交、删除离开成交，每个窗口 `O(1)` 更新。由于数据均为正数，溢出检查可以在乘法前用 `price > MAX / quantity`，加法前用 `sum > MAX - value`。

```cpp
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

struct Trade {
    std::int64_t price_ticks;
    std::int64_t quantity;
};

std::int64_t checked_notional(Trade trade) {
    if (trade.price_ticks <= 0 || trade.quantity <= 0) {
        throw std::invalid_argument{"price and quantity must be positive"};
    }
    const auto maximum = std::numeric_limits<std::int64_t>::max();
    if (trade.price_ticks > maximum / trade.quantity) {
        throw std::overflow_error{"notional overflow"};
    }
    return trade.price_ticks * trade.quantity;
}

void checked_add_positive(std::int64_t& total, std::int64_t value) {
    if (total > std::numeric_limits<std::int64_t>::max() - value) {
        throw std::overflow_error{"sum overflow"};
    }
    total += value;
}

std::vector<long double> rolling_vwap(
    const std::vector<Trade>& trades,
    std::size_t k
) {
    if (k == 0 || k > trades.size()) {
        return {};
    }

    std::vector<std::int64_t> notionals;
    notionals.reserve(trades.size());
    for (const Trade trade : trades) {
        notionals.push_back(checked_notional(trade));
    }

    std::int64_t notional_sum{0};
    std::int64_t quantity_sum{0};
    for (std::size_t i = 0; i < k; ++i) {
        checked_add_positive(notional_sum, notionals[i]);
        checked_add_positive(quantity_sum, trades[i].quantity);
    }

    std::vector<long double> result;
    result.push_back(static_cast<long double>(notional_sum) /
                     static_cast<long double>(quantity_sum));

    for (std::size_t i = k; i < trades.size(); ++i) {
        notional_sum -= notionals[i - k];
        quantity_sum -= trades[i - k].quantity;
        checked_add_positive(notional_sum, notionals[i]);
        checked_add_positive(quantity_sum, trades[i].quantity);
        result.push_back(static_cast<long double>(notional_sum) /
                         static_cast<long double>(quantity_sum));
    }
    return result;
}

bool close_to(long double left, long double right) {
    return std::abs(left - right) < 1e-12L;
}

int main() {
    const auto result = rolling_vwap({{100, 2}, {110, 1}, {90, 1}}, 2);
    assert(result.size() == 2);
    assert(close_to(result[0], 310.0L / 3.0L));
    assert(close_to(result[1], 100.0L));
    assert(rolling_vwap({}, 1).empty());
    assert(rolling_vwap({{100, 1}}, 0).empty());
}
```

先计算每笔成交额再累加，让进入窗口前就完成单笔校验。窗口总和即使每笔合法仍可能溢出，所以还要检查加法。真实金融系统还要定义价格精度、舍入、成交修正和撤销语义。

</details>

<details>
<summary>B3 参考答案：绝对敞口 Top-K</summary>

最小有符号 64 位整数的绝对值无法放进 `int64_t`，但可以安全映射到 `uint64_t`：非负值直接转换；负数使用 `-(x + 1)` 后再加一，避免先对最小值取负。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <utility>
#include <vector>

struct Exposure {
    std::string symbol;
    std::int64_t value;
};

std::uint64_t magnitude(std::int64_t value) {
    if (value >= 0) {
        return static_cast<std::uint64_t>(value);
    }
    return static_cast<std::uint64_t>(-(value + 1)) + 1U;
}

std::vector<std::string> top_exposures(
    std::vector<Exposure> exposures,
    std::size_t k
) {
    std::sort(exposures.begin(), exposures.end(), [](const auto& left, const auto& right) {
        const auto left_magnitude = magnitude(left.value);
        const auto right_magnitude = magnitude(right.value);
        if (left_magnitude != right_magnitude) {
            return left_magnitude > right_magnitude;
        }
        return left.symbol < right.symbol;
    });

    k = std::min(k, exposures.size());
    std::vector<std::string> result;
    result.reserve(k);
    for (std::size_t i = 0; i < k; ++i) {
        result.push_back(exposures[i].symbol);
    }
    return result;
}

int main() {
    assert((top_exposures({{"A", -10}, {"C", 7}, {"B", 10}}, 2) ==
            std::vector<std::string>{"A", "B"}));
    assert((top_exposures({{"MIN", std::numeric_limits<std::int64_t>::min()},
                           {"MAX", std::numeric_limits<std::int64_t>::max()}}, 1) ==
            std::vector<std::string>{"MIN"}));
    assert(top_exposures({}, 3).empty());
}
```

若题目不保证标的唯一，应先说明是覆盖、求和还是拒绝重复。若敞口来自多笔相加，还必须在聚合时检查溢出。

</details>

## 7. 口述模拟面试：45 分钟边写边说

这一套不追求写三道完整程序，而是训练互动。

### M1. 10 分钟：需求澄清

面试官说：“实现一个请求限流器。”你应主动问什么？

最低覆盖：

- 限制按用户、租户、IP 还是全局？
- 是固定窗口、滑动窗口还是 token bucket 语义？
- 单机还是分布式？时钟是否单调？
- 超限返回什么？是否允许突发？
- 状态保存多久，容量上限多少？
- 并发调用和进程重启怎样处理？

### M2. 20 分钟：写出第一可行版本

约定单线程、到达时间单调不减、每个用户 60 秒内最多 `limit` 次请求。写出哈希表加时间队列的方案，分析平均复杂度，并覆盖 `limit == 0`。

合格答案应维护：每个用户一个请求时间双端队列；新请求前弹出 `<= now-60s` 的旧时间；若队列大小已达上限则拒绝，否则加入并接受。进一步追问总用户数和空队列何时从哈希表删除。

### M3. 15 分钟：连续追问

面试官依次改变需求：

1. 允许每秒补充 10 个 token、最多突发 50 个；
2. 多线程并发调用；
3. 服务有 100 个实例；
4. 时钟发生回拨；
5. 必须给出 p99 延迟证据。

好的回答不会声称一个容器解决全部问题，而会逐层说明：token bucket 状态、互斥/分片、集中式或一致性取舍、单调时钟、基准负载和观测指标。

## 8. 复盘答案，而不是收藏答案

每道错题只记题名没有用。建议按下面格式写错题卡：

| 字段 | 示例 |
|---|---|
| 触发信号 | “连续区间 + 最少资源” |
| 我当时的错误 | 只按结束时间排序，无法处理同时开始 |
| 正确不变量 | 堆中保存当前仍占用 worker 的结束时间 |
| 最小反例 | `[(0,10),(1,2),(2,3)]` |
| C++ 坑 | `priority_queue` 默认是最大堆 |
| 重写日期 | 第 0、2、7、21 天 |

最小反例尤其重要：它能证明你理解了旧方法为什么错，而不只是接受了新答案。

## 9. 模拟通过门槛

在把算法轮评为“较充分”前，至少达到：

- 本章 A/B 中任选一套，限时首次达到 75 分以上；
- 再从[追加盲测](mock_exams_extra.md)选择一套未看过答案的卷达到 75 分以上；
- 第 7 天只重做失分模式，不看答案达到 85 分以上；
- 每题能先口述伪代码和不变量，再写 C++；
- 能主动给出至少 5 类边界输入；
- 算法解完成后，能再谈容量、过期、并发、恢复和性能测量；
- 不把本书训练题描述成任何公司的真题。

若尚未达到，不要一次刷更多新题。先按错误类型回到对应基础章和训练题，能重新解释不变量并从空白写对后，再做下一套模拟。

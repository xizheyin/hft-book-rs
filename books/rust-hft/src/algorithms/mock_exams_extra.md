# 追加盲测与协作编码：陌生组合、需求演进与代码评审

前一章的模拟用于第一次验收；本章先提供两套不在标题中提示算法模式的盲测卷，再提供两道会逐轮增加需求的协作编码题。前者检查“函数会写，但到了在线评测不会读写”的断层；后者检查能否先澄清语义、写出最小正确版本，再在保留已有行为的前提下修改设计、补测试并接受代码评审。

> 这些题是本书训练题，不是公司真题。先只看题目区，限时结束后再展开答案。

卷 C 组合数组、队列、图和动态规划等基础结构；卷 D 的 D1、D3 训练滑动窗口，D2 训练线性字符串匹配。每题都要求先写清输入、输出和边界，再说明不变量与复杂度，最后用完整输入输出验证实现。

## 1. 使用规则与评分

- 每套 90 分钟，三题各 30 分；剩余 10 分来自完整编译、格式和自测。
- 可以查标准库签名，不搜索题解。
- 程序必须处理合法输入的边界；非法输入政策要写在注释或口头说明中。
- 每题先在草稿写暴力复杂度和一个不变量，再打开编辑器。
- 题目没有告诉你属于哪一章；认出结构本身就是考点。

单题 30 分拆分：题意/边界 4，基线 3，观察/不变量 5，算法正确 8，C++ 与 I/O 6，复杂度/测试 4。

## 2. 盲测卷 C：完整程序（90 分钟）

### C1. 机器占用总时长

第一行是测试组数 `T`。每组第一行是区间数 `n`，随后 `n` 行为 `start end`，表示半开区间 `[start,end)`，满足 `0 <= start <= end <= 10^18`。同一时刻被多个任务占用只计算一次，输出每组被占用的总时长。

```text
输入
2
4
1 4
2 5
8 10
10 12
2
3 3
5 7

输出
8
2
```

### C2. 最小单日容量

有 `n` 个正整数负载，必须保持原顺序，连续分配到不超过 `days` 天。每天负载之和不能超过容量。求能完成全部负载的最小整数容量。

第一行 `n days`，第二行 `n` 个负载。满足 `1 <= days <= n <= 200000`，单个负载不超过 `10^9`，所有负载之和不超过 `INT64_MAX`。

```text
输入
5 3
7 2 5 10 8

输出
14
```

### C3. 工作流最早完成时间

有 `n` 个任务，编号 `0..n-1`，任务 `i` 耗时 `duration[i]`。依赖边 `u v` 表示 `u` 完成后 `v` 才能开始。worker 数量无限，一个任务的所有依赖完成后立即开始。

第一行 `n m`，第二行 `n` 个正整数耗时，随后 `m` 行依赖。若有循环依赖输出 `-1`，否则输出全部任务完成的最早时间。`n,m <= 200000`；DAG（Directed Acyclic Graph，有向无环图）表示没有循环依赖，合法 DAG 的答案保证能放进 64 位有符号整数。

```text
输入
4 3
3 2 5 4
0 2
1 2
2 3

输出
12
```

## 3. 盲测卷 C 参考答案

<details>
<summary>C1 参考程序</summary>

按开始、结束排序，维护当前合并段。空区间没有长度；与当前段重叠或首尾相接时扩大结束位置，否则结算旧段。

```cpp
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <utility>
#include <vector>

using Interval = std::pair<std::int64_t, std::int64_t>;

std::int64_t occupied_length(std::vector<Interval> intervals) {
    for (const auto [start, end] : intervals) {
        if (start < 0 || end < start) {
            throw std::invalid_argument{"invalid interval"};
        }
    }
    std::sort(intervals.begin(), intervals.end());

    std::int64_t total{0};
    bool active{false};
    std::int64_t current_start{0};
    std::int64_t current_end{0};
    for (const auto [start, end] : intervals) {
        if (start == end) {
            continue;
        }
        if (!active) {
            current_start = start;
            current_end = end;
            active = true;
        } else if (start <= current_end) {
            current_end = std::max(current_end, end);
        } else {
            total += current_end - current_start;
            current_start = start;
            current_end = end;
        }
    }
    if (active) {
        total += current_end - current_start;
    }
    return total;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int test_count{0};
    if (!(std::cin >> test_count)) {
        assert(occupied_length({{1, 4}, {2, 5}, {8, 10}, {10, 12}}) == 8);
        assert(occupied_length({{3, 3}, {5, 7}}) == 2);
        return 0;
    }
    for (int test = 0; test < test_count; ++test) {
        std::size_t n{0};
        std::cin >> n;
        std::vector<Interval> intervals(n);
        for (auto& [start, end] : intervals) {
            std::cin >> start >> end;
        }
        std::cout << occupied_length(std::move(intervals)) << '\n';
    }
}
```

时间 `O(n log n)`，排序外扫描 `O(n)`；额外空间取决于是否计输入副本。

</details>

<details>
<summary>C2 参考程序</summary>

若给定容量 `C`，按顺序贪心地把尽可能多的负载放入当天，可以计算需要的最少天数。容量越大越容易在规定天数内完成，形成单调的 `false...true`，因此在 `[max(load), sum(load)]` 上找第一个可行容量。

```cpp
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <vector>

bool can_finish(const std::vector<std::int64_t>& loads,
                std::size_t days,
                std::int64_t capacity) {
    std::size_t used_days{1};
    std::int64_t today{0};
    for (const std::int64_t load : loads) {
        if (load <= 0 || load > capacity) {
            return false;
        }
        if (today > capacity - load) {
            ++used_days;
            today = 0;
        }
        today += load;
    }
    return used_days <= days;
}

std::int64_t minimum_capacity(const std::vector<std::int64_t>& loads,
                              std::size_t days) {
    if (loads.empty() || days == 0 || days > loads.size()) {
        throw std::invalid_argument{"invalid loads or days"};
    }
    std::int64_t left{0};
    std::int64_t right{0};
    for (const std::int64_t load : loads) {
        if (load <= 0) {
            throw std::invalid_argument{"load must be positive"};
        }
        left = std::max(left, load);
        if (right > std::numeric_limits<std::int64_t>::max() - load) {
            throw std::overflow_error{"total load overflow"};
        }
        right += load;
    }

    while (left < right) {
        const std::int64_t mid = left + (right - left) / 2;
        if (can_finish(loads, days, mid)) {
            right = mid;
        } else {
            left = mid + 1;
        }
    }
    return left;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::size_t n{0};
    std::size_t days{0};
    if (!(std::cin >> n >> days)) {
        assert(minimum_capacity({7, 2, 5, 10, 8}, 3) == 14);
        assert(minimum_capacity({5}, 1) == 5);
        return 0;
    }
    std::vector<std::int64_t> loads(n);
    for (auto& load : loads) {
        std::cin >> load;
    }
    std::cout << minimum_capacity(loads, days) << '\n';
}
```

设答案范围宽度为 `S`，每次可行性扫描 `O(n)`，总时间 `O(n log S)`，额外空间 `O(1)`（不计输入）。

</details>

<details>
<summary>C3 参考程序</summary>

先单独完成拓扑排序：若不能取出全部任务，立即报告有环，不在无效工作流上计算时间。确认是 DAG 后，再按拓扑序维护 `finish[v]`；它等于任务 `v` 自身耗时，加上所有前置任务完成时间的最大值。这样“有环输出 `-1`”的语义不会被无关的路径加法溢出抢先打断。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <optional>
#include <queue>
#include <stdexcept>
#include <utility>
#include <vector>

std::optional<std::int64_t> earliest_finish(
    const std::vector<std::int64_t>& duration,
    const std::vector<std::pair<std::size_t, std::size_t>>& edges
) {
    const std::size_t n = duration.size();
    std::vector<std::vector<std::size_t>> next(n);
    std::vector<std::size_t> indegree(n, 0);
    for (const auto [from, to] : edges) {
        if (from >= n || to >= n) {
            throw std::out_of_range{"task id outside range"};
        }
        next[from].push_back(to);
        ++indegree[to];
    }

    std::queue<std::size_t> ready;
    for (std::size_t i = 0; i < n; ++i) {
        if (duration[i] <= 0) {
            throw std::invalid_argument{"duration must be positive"};
        }
        if (indegree[i] == 0) {
            ready.push(i);
        }
    }

    std::vector<std::size_t> order;
    order.reserve(n);
    while (!ready.empty()) {
        const std::size_t current = ready.front();
        ready.pop();
        order.push_back(current);

        for (const std::size_t dependent : next[current]) {
            if (--indegree[dependent] == 0) {
                ready.push(dependent);
            }
        }
    }
    if (order.size() != n) {
        return std::nullopt;
    }

    std::vector<std::int64_t> finish = duration;
    std::int64_t answer{0};
    for (const std::size_t current : order) {
        answer = std::max(answer, finish[current]);
        for (const std::size_t dependent : next[current]) {
            if (finish[current] >
                std::numeric_limits<std::int64_t>::max() - duration[dependent]) {
                throw std::overflow_error{"finish time overflow"};
            }
            finish[dependent] = std::max(
                finish[dependent], finish[current] + duration[dependent]);
        }
    }
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::size_t n{0};
    std::size_t m{0};
    if (!(std::cin >> n >> m)) {
        assert(earliest_finish({3, 2, 5, 4}, {{0, 2}, {1, 2}, {2, 3}}) == 12);
        assert(!earliest_finish({1, 1}, {{0, 1}, {1, 0}}).has_value());
        const auto maximum = std::numeric_limits<std::int64_t>::max();
        assert(!earliest_finish(
                    {maximum, 1, 1}, {{0, 1}, {1, 2}, {2, 1}})
                    .has_value());
        return 0;
    }
    std::vector<std::int64_t> duration(n);
    for (auto& value : duration) {
        std::cin >> value;
    }
    std::vector<std::pair<std::size_t, std::size_t>> edges(m);
    for (auto& [from, to] : edges) {
        std::cin >> from >> to;
    }
    const auto answer = earliest_finish(duration, edges);
    std::cout << (answer.has_value() ? *answer : -1) << '\n';
}
```

时间 `O(V+E)`，空间 `O(V+E)`。题目若可能重复给同一条边，应确认它是重复输入还是两条独立约束；本程序把它们作为两条边，入度也对应增加两次。

</details>

## 4. 盲测卷 D：换皮组合（90 分钟）

### D1. 最短告警片段

给正整数数组 `values` 和正整数 `target`，返回和至少为 `target` 的最短连续片段长度；不存在则输出 `0`。

第一行输入 `n target`，第二行输入 `n` 个数组元素。满足 `1 <= n <= 200000`、`1 <= target <= INT64_MAX`，每个数组元素都是正整数，并且所有元素之和可以放进 64 位有符号整数。输出一个整数，表示最短片段长度。

```text
输入
6 7
2 3 1 2 4 3

输出
2
```

### D2. KMP 字符串匹配：查找所有出现位置

第一行输入文本 `text`，第二行输入非空模式 `pattern`。两者只包含 ASCII 可见字符和空格，因此空格也是待匹配内容，不应使用 `operator>>` 读取。满足 `0 <= |text| <= 1000000`、`1 <= |pattern| <= 1000000`；这里的长度和下标都按字节计算。

按从小到大的顺序输出模式在文本中所有出现的起始字节下标，相邻下标以一个空格分隔，匹配允许重叠。若没有匹配，输出一个空行。

```text
输入
aaaaa
aa

输出
0 1 2 3
```

### D3. 每个窗口有多少种事件

给整数数组和窗口长度 `k`，输出每个长度为 `k` 的连续窗口中不同整数的数量。

第一行输入 `n k`。当 `n > 0` 时，第二行输入 `n` 个整数；当 `n == 0` 时没有数组元素需要读取。满足 `0 <= n <= 200000`、`0 <= k <= 200000`，每个数组元素都在 32 位有符号整数范围内。输出各窗口的答案，相邻整数以一个空格分隔；若 `k == 0` 或 `k > n`，输出一个空行。

```text
输入
5 3
1 2 1 3 2

输出
2 3 3
```

## 5. 盲测卷 D 参考答案

<details>
<summary>D1 参考程序</summary>

由于元素全为正数，右端扩张时窗口和只增大；满足条件后移动左端只会减小。每个下标最多被左右指针各访问一次。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

std::size_t shortest_alert(const std::vector<std::int64_t>& values,
                           std::int64_t target) {
    if (target <= 0) {
        throw std::invalid_argument{"target must be positive"};
    }
    std::size_t left{0};
    std::int64_t sum{0};
    std::size_t best = std::numeric_limits<std::size_t>::max();

    for (std::size_t right = 0; right < values.size(); ++right) {
        if (values[right] <= 0 ||
            sum > std::numeric_limits<std::int64_t>::max() - values[right]) {
            throw std::invalid_argument{"values must be positive and sum must fit"};
        }
        sum += values[right];
        while (sum >= target) {
            best = std::min(best, right - left + 1);
            sum -= values[left++];
        }
    }
    return best == std::numeric_limits<std::size_t>::max() ? 0 : best;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    std::size_t n{0};
    std::int64_t target{0};
    if (!(std::cin >> n >> target)) {
        assert(shortest_alert({2, 3, 1, 2, 4, 3}, 7) == 2);
        assert(shortest_alert({1, 1}, 3) == 0);
        return 0;
    }
    std::vector<std::int64_t> values(n);
    for (auto& value : values) std::cin >> value;
    std::cout << shortest_alert(values, target) << '\n';
}
```

</details>

<details>
<summary>D2 参考程序</summary>

使用 KMP；完整推导见[字符串算法](string_algorithms.md)。前缀表让失配后复用已经匹配的前缀，不把文本指针退回。

```cpp
#include <cassert>
#include <cstddef>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

std::vector<std::size_t> find_all(std::string_view text,
                                  std::string_view pattern) {
    if (pattern.empty()) return {};
    std::vector<std::size_t> prefix(pattern.size(), 0);
    for (std::size_t i = 1, matched = 0; i < pattern.size(); ++i) {
        while (matched > 0 && pattern[i] != pattern[matched]) {
            matched = prefix[matched - 1];
        }
        if (pattern[i] == pattern[matched]) ++matched;
        prefix[i] = matched;
    }

    std::vector<std::size_t> result;
    for (std::size_t i = 0, matched = 0; i < text.size(); ++i) {
        while (matched > 0 && text[i] != pattern[matched]) {
            matched = prefix[matched - 1];
        }
        if (text[i] == pattern[matched]) ++matched;
        if (matched == pattern.size()) {
            result.push_back(i + 1 - pattern.size());
            matched = prefix[matched - 1];
        }
    }
    return result;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    std::string text;
    std::string pattern;
    if (!std::getline(std::cin, text) || !std::getline(std::cin, pattern)) {
        assert((find_all("aaaa", "aa") == std::vector<std::size_t>{0, 1, 2}));
        assert(find_all("abc", "z").empty());
        return 0;
    }
    const auto positions = find_all(text, pattern);
    for (std::size_t i = 0; i < positions.size(); ++i) {
        if (i != 0) std::cout << ' ';
        std::cout << positions[i];
    }
    std::cout << '\n';
}
```

</details>

<details>
<summary>D3 参考程序</summary>

哈希表保存当前窗口中每个值的频次；加入右端，移除离开的左端，频次归零时删除键。表的大小就是不同值数量。

```cpp
#include <cassert>
#include <cstddef>
#include <iostream>
#include <unordered_map>
#include <vector>

std::vector<std::size_t> distinct_per_window(const std::vector<int>& values,
                                             std::size_t k) {
    if (k == 0 || k > values.size()) return {};
    std::unordered_map<int, std::size_t> counts;
    for (std::size_t i = 0; i < k; ++i) ++counts[values[i]];

    std::vector<std::size_t> result{counts.size()};
    for (std::size_t i = k; i < values.size(); ++i) {
        auto leaving = counts.find(values[i - k]);
        if (--leaving->second == 0) counts.erase(leaving);
        ++counts[values[i]];
        result.push_back(counts.size());
    }
    return result;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    std::size_t n{0};
    std::size_t k{0};
    if (!(std::cin >> n >> k)) {
        assert((distinct_per_window({1, 2, 1, 3, 2}, 3) ==
                std::vector<std::size_t>{2, 3, 3}));
        assert(distinct_per_window({}, 1).empty());
        return 0;
    }
    std::vector<int> values(n);
    for (int& value : values) std::cin >> value;
    const auto result = distinct_per_window(values, k);
    for (std::size_t i = 0; i < result.size(); ++i) {
        if (i != 0) std::cout << ' ';
        std::cout << result[i];
    }
    std::cout << '\n';
}
```

</details>

## 6. 协作编码 E：需求会在实现过程中继续变化

这一组不是闭卷 OJ。面试官会先给最小需求，在你写出可工作的基线后再增加约束。每一轮都应先复述新语义，指出原接口哪里需要变化，再修改代码和测试。不要假装第一分钟就猜中了全部后续需求。

### E1. 版本化内存键值存储

**第一轮：**实现一个单线程内存存储，支持 `put(key, value)` 和 `get(key)`。

**第二轮：**每次成功写入获得全局单调递增版本号；增加 `get_at(key, version)`，返回该键在不晚于指定版本时的最新值。

**第三轮：**增加 `compare_and_set(key, expected_version, value)`。只有该键当前版本等于期望版本时才写入；不存在的键把当前版本视为 0。失败不能消耗版本号。

请在编码过程中说明：

1. 每个接口对不存在键返回什么；
2. 为什么每个键的历史可以二分；
3. 哪些整数边界会让版本号失去唯一性；
4. 这个“比较并写入”在多线程程序中是否已经原子；
5. 你会用哪些测试区分当前值、历史值和写入失败。

### E2. 可增量输入的长度前缀帧解码器

协议中的每个帧格式如下：

```text
2-byte big-endian payload_length | payload
```

**第一轮：**输入恰好是一帧完整字节，返回 payload。

**第二轮：**网络一次读取可能只有半个头、半个 payload，也可能同时包含多帧。改成 `feed(chunk)` 接口，跨调用保留未完成字节，并返回本次新完成的所有帧。

**第三轮：**构造函数给出最大 payload 长度。看到超长声明后，解码器进入终止错误状态，之后所有 `feed` 都失败，直到上层丢弃或重建解码器。

请在编码过程中说明：

1. 当前已消费位置和缓冲区分别表示什么；
2. 空 payload 是否合法；
3. 为什么不能按照尚未验证的长度直接分配；
4. 一次调用先解析出合法帧、随后遇到非法头时，已经产出的帧怎样处理；
5. 怎样系统测试每一种分包位置，而不是只测一次完整输入。

## 7. 协作编码 E 完整答案

### E1 参考答案：先固定接口语义和历史不变量

第一轮用 `unordered_map<string,string>` 就能完成当前值查询。第二轮出现历史查询后，不能再覆盖旧值；可以把每个键映射到按版本递增的 `vector<Entry>`。因为全局版本只增加，每个键追加进去的版本也严格增加，`get_at` 可以使用 `upper_bound` 找到“第一个大于目标版本”的条目，再退一格。

第三轮的关键不是先写代码，而是定义：

- 不存在键的当前版本为 0；
- 版本 0 永远不分配给真实写入；
- CAS 失败不修改状态，也不消耗版本；
- 本实现明确为单线程对象；在多线程环境中，“检查当前版本”和“追加新版本”必须处于同一临界区，函数名字不会自动提供线程原子性。

下面是完整实现和边界测试：

```cpp
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using Version = std::uint64_t;

struct VersionedValue {
    Version version;
    std::string value;
};

class VersionedStore {
public:
    Version put(std::string key, std::string value) {
        const Version version = allocate_version();
        history_[std::move(key)].push_back(
            VersionedValue{version, std::move(value)});
        return version;
    }

    std::optional<std::string> get(const std::string& key) const {
        const auto found = history_.find(key);
        if (found == history_.end() || found->second.empty()) {
            return std::nullopt;
        }
        return found->second.back().value;
    }

    std::optional<std::string> get_at(const std::string& key,
                                      Version version) const {
        const auto found = history_.find(key);
        if (found == history_.end()) {
            return std::nullopt;
        }

        const auto& entries = found->second;
        const auto after = std::upper_bound(
            entries.begin(), entries.end(), version,
            [](Version wanted, const VersionedValue& entry) {
                return wanted < entry.version;
            });
        if (after == entries.begin()) {
            return std::nullopt;
        }
        return std::prev(after)->value;
    }

    std::optional<Version> compare_and_set(std::string key,
                                           Version expected_version,
                                           std::string value) {
        const auto found = history_.find(key);
        const Version current = found == history_.end()
            ? 0
            : found->second.back().version;
        if (current != expected_version) {
            return std::nullopt;
        }
        return put(std::move(key), std::move(value));
    }

private:
    Version allocate_version() {
        if (next_version_ == 0) {
            throw std::overflow_error("version space exhausted");
        }
        const Version allocated = next_version_;
        next_version_ = allocated == std::numeric_limits<Version>::max()
            ? 0
            : allocated + 1;
        return allocated;
    }

    Version next_version_{1};
    std::unordered_map<std::string, std::vector<VersionedValue>> history_;
};

int main() {
    VersionedStore store;
    assert(!store.get("job"));
    assert(!store.get_at("job", 100));

    const Version v1 = store.put("job", "queued");
    const Version v2 = store.put("other", "ready");
    const Version v3 = store.put("job", "running");
    assert(v1 == 1 && v2 == 2 && v3 == 3);
    assert(store.get("job") == std::optional<std::string>{"running"});
    assert(store.get_at("job", 0) == std::nullopt);
    assert(store.get_at("job", v1) ==
           std::optional<std::string>{"queued"});
    assert(store.get_at("job", v2) ==
           std::optional<std::string>{"queued"});
    assert(store.get_at("job", v3) ==
           std::optional<std::string>{"running"});

    assert(!store.compare_and_set("job", v1, "wrong"));
    assert(store.get("job") == std::optional<std::string>{"running"});
    const auto v4 = store.compare_and_set("job", v3, "finished");
    assert(v4 == std::optional<Version>{4});
    assert(store.get("job") == std::optional<std::string>{"finished"});

    const auto v5 = store.compare_and_set("new", 0, "");
    assert(v5 == std::optional<Version>{5});
    assert(store.get("new") == std::optional<std::string>{""});
    std::cout << "latest version=" << *v5 << '\n';
}
```

**正确性不变量：**全局已分配版本唯一且递增；每个键的历史是全局写入序列的一个子序列，所以也严格递增；`get` 取末项；`get_at` 取最后一个 `entry.version≤wanted`；CAS 只有在比较成立后才调用分配函数。

**复杂度：**令某键有 h 个历史版本，`put` 摊还 `O(1)`，`get` 平均 `O(1)` 哈希定位后取末项，`get_at` 平均 `O(1)+O(log h)`，总空间与保留的全部历史版本数成正比。这里的平均 `O(1)` 依赖哈希分布，不是最坏保证。

**代码评审继续追问：**

- `get` 返回字符串副本，接口简单但可能复制；返回引用或 `string_view` 又会引入后续写入、rehash 和对象销毁导致的寿命问题，不能只为省复制就改；
- 历史会无限增长，生产设计要定义保留窗口、快照和旧 reader 语义；
- 全局版本溢出时显式失败，不能回绕后复用旧版本；
- 多线程版本应让 CAS 的检查与写入持同一 mutex，或重新设计成适合原子状态的数据结构；仅把 `next_version_` 改成 atomic 仍不能保护每个键的历史；
- 落盘、崩溃恢复和跨节点顺序都不在这个内存对象的承诺内。

### E2 参考答案：把输入流建模为可恢复解析状态

解析器保存“尚未完成解析的字节”和已消费下标。只有至少有 2 byte 时才能读长度；只有缓冲区达到 `2+length` 时才能产出完整 payload。长度必须先与上限比较，再复制或预留对应数据。

本答案规定：长度 0 的空 payload 合法；一次 `feed` 在非法头之前已经完成的帧仍返回给调用者；遇到非法头后解析器进入终止错误状态并丢弃内部剩余字节。调用者必须先处理返回的已完成帧，再关闭连接或重建解码器。把这个政策写进接口，比只返回一个含糊的 `false` 更重要。

```cpp
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <span>
#include <vector>

enum class FeedStatus { Ok, ProtocolError };

class FrameDecoder {
public:
    explicit FrameDecoder(std::size_t max_payload)
        : max_payload_(max_payload) {}

    FeedStatus feed(std::span<const std::uint8_t> chunk,
                    std::vector<std::vector<std::uint8_t>>& completed) {
        if (failed_) {
            return FeedStatus::ProtocolError;
        }
        buffer_.insert(buffer_.end(), chunk.begin(), chunk.end());

        while (available() >= header_size) {
            const std::size_t length =
                (static_cast<std::size_t>(buffer_[read_index_]) << 8U)
                | static_cast<std::size_t>(buffer_[read_index_ + 1]);
            if (length > max_payload_) {
                failed_ = true;
                buffer_.clear();
                read_index_ = 0;
                return FeedStatus::ProtocolError;
            }

            const std::size_t frame_size = header_size + length;
            if (available() < frame_size) {
                break;
            }
            const auto payload_begin =
                buffer_.begin() + static_cast<std::ptrdiff_t>(read_index_ + header_size);
            const auto payload_end =
                payload_begin + static_cast<std::ptrdiff_t>(length);
            completed.emplace_back(payload_begin, payload_end);
            read_index_ += frame_size;
        }

        compact_if_useful();
        return FeedStatus::Ok;
    }

    bool failed() const { return failed_; }

private:
    std::size_t available() const {
        return buffer_.size() - read_index_;
    }

    void compact_if_useful() {
        if (read_index_ == buffer_.size()) {
            buffer_.clear();
            read_index_ = 0;
        } else if (read_index_ >= 4096 && read_index_ * 2 >= buffer_.size()) {
            buffer_.erase(
                buffer_.begin(),
                buffer_.begin() + static_cast<std::ptrdiff_t>(read_index_));
            read_index_ = 0;
        }
    }

    static constexpr std::size_t header_size = 2;
    const std::size_t max_payload_;
    std::vector<std::uint8_t> buffer_;
    std::size_t read_index_{0};
    bool failed_{false};
};

void append_frame(std::vector<std::uint8_t>& output,
                  std::span<const std::uint8_t> payload) {
    assert(payload.size() <= 0xFFFFU);
    const auto length = static_cast<std::uint16_t>(payload.size());
    output.push_back(static_cast<std::uint8_t>(length >> 8U));
    output.push_back(static_cast<std::uint8_t>(length & 0xFFU));
    output.insert(output.end(), payload.begin(), payload.end());
}

int main() {
    const std::array<std::uint8_t, 3> abc{'a', 'b', 'c'};
    const std::array<std::uint8_t, 1> z{'z'};
    const std::array<std::uint8_t, 0> empty{};
    std::vector<std::uint8_t> wire;
    append_frame(wire, abc);
    append_frame(wire, empty);
    append_frame(wire, z);

    FrameDecoder decoder{8};
    std::vector<std::vector<std::uint8_t>> frames;
    for (const std::uint8_t byte : wire) {
        const std::array<std::uint8_t, 1> one{byte};
        assert(decoder.feed(one, frames) == FeedStatus::Ok);
    }
    assert((frames == std::vector<std::vector<std::uint8_t>>{
        {'a', 'b', 'c'}, {}, {'z'}}));

    FrameDecoder multiple{8};
    std::vector<std::vector<std::uint8_t>> all_at_once;
    assert(multiple.feed(wire, all_at_once) == FeedStatus::Ok);
    assert(all_at_once == frames);

    FrameDecoder limited{3};
    const std::array<std::uint8_t, 2> declares_four{0, 4};
    std::vector<std::vector<std::uint8_t>> none;
    assert(limited.feed(declares_four, none) == FeedStatus::ProtocolError);
    assert(limited.failed());
    assert(limited.feed(wire, none) == FeedStatus::ProtocolError);
    assert(none.empty());
    std::cout << "decoded frames=" << frames.size() << '\n';
}
```

**正确性不变量：**`read_index_≤buffer_.size()`；其前方字节都已属于已返回帧；从 `read_index_` 开始的字节要么不足一个头，要么声明了一个未收完整的合法长度帧；任何超过上限的长度都会使状态永久变成 failed。

**复杂度：**每个输入字节被追加一次、属于某个完整帧后被读取和复制一次；偶尔 compact 会移动未消费后缀。对总输入 N 和总输出 payload 大小 P，正常路径可按摊还 `O(N+P)` 理解。返回拥有数据的 `vector` 明确了生命周期，但会复制 payload；零拷贝视图需要固定底层缓冲寿命，并防止后续扩容或 compact 让视图悬空，不能直接把返回类型换成 `span`。

**系统化测试：**上面的逐 byte 测试覆盖所有头部和 payload 分割。进一步可以对同一 wire 枚举每个二分切点 `wire[0:i]`、`wire[i:n]`，再生成随机 chunk 序列，始终与一次完整 feed 的结果比较。还要测试空帧、最大合法长度、上限加一、连续多帧、只到一半就 EOF，以及合法帧后紧跟非法头的返回政策。

**代码评审继续追问：**单帧长度上限只限制一帧，不限制一次 `feed` 的 chunk、返回帧集合或连接总内存；上层仍需读取缓冲和每轮产出预算。真实 socket 还要处理 EOF 时残留半帧、连接级错误、背压与超时。协议若把长度定义为包含头部，或使用其他字节序，公式也必须随规范改变。

## 8. 盲测卷与协作题覆盖了什么

| 题 | 隐藏的核心 | 主要失分点 |
|---|---|---|
| C1 | 排序 + 区间 | 空区间、相接、64 位长度 |
| C2 | 单调答案 + 二分 | 上下界、加法溢出、保持顺序 |
| C3 | 拓扑 + DAG DP | 环、最大前驱、重复边语义 |
| D1 | 正数滑动窗口 | 把含负数版本误套进来 |
| D2 | KMP + 行读取 | 重叠匹配、空格、空模式政策 |
| D3 | 窗口 + 哈希频次 | 离开时不删零频键、非法 `k` |
| E1 | API 演进 + 版本化状态 + CAS 语义 | 覆盖历史、失败消耗版本、把函数名误当线程原子性 |
| E2 | 增量解析 + 有界输入 + 状态机测试 | 假定 read 等于一帧、先按不可信长度分配、忽略分包与寿命 |

若同一模式连续两次失分，回到对应基础章重新推演定义、操作和复杂度，再从训练章选择一道不同外形的题复测。

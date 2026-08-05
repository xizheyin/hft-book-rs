# 贪心与动态规划：局部选择什么时候能代表全局

贪心和动态规划都在避免暴力枚举，但理由完全不同：

- **贪心**现在就做一个不可撤销的选择，必须证明某个最优解可以接受这次选择；
- **动态规划**承认不同选择都可能重要，把重复子问题的最优答案保存下来，再组合成大问题答案。

“看起来应该选最大的”“先把眼前收益拿到”不是证明。相反，DP 也不是先创建二维数组再猜下标含义。本章会把证明和状态定义放在代码之前。

> 本章题目用于训练通用解题能力，不是任何公司的真题。

## 0. 一张决策表

| 看到的结构 | 先考虑 | 必须回答的问题 |
|---|---|---|
| 每次选一个局部最优项 | 贪心 | 为什么这个选择不会破坏某个全局最优解？ |
| 同一子问题反复出现 | 记忆化搜索 / DP | 状态是什么？不同状态是否足够区分未来？ |
| 当前决策只依赖少量前置状态 | 一维或滚动 DP | 初始化和遍历顺序能否保证依赖已计算？ |
| 要输出方案而非只输出最优值 | DP + 父状态 | 怎样从终点倒推选择？ |

先写暴力递归通常很有价值：它把“有哪些选择”说清楚。DP 只是把重复计算合并，不应该凭空出现。

## 1. 母题：区间调度的贪心选择

### 白话题意

给若干半开区间 `[start, end)`，选择尽可能多的互不重叠区间。半开区间允许 `[1,3)` 后紧接 `[3,5)`。本题要求 `start < end`。

### 暴力办法

枚举全部子集，检查每个子集是否互不重叠，再取区间数最多的一个。`n` 个区间有 `2^n` 个子集，最坏是指数时间。

### 关键观察与不变量

把区间按结束时间从早到晚排序。每次选择与已有结果不冲突、且结束最早的区间。

直觉是“给后面的区间留下最多时间”，但还需要交换论证：

> 设当前剩余问题中结束最早的区间是 `g`。任取一个最优方案，其第一个区间是 `o`。因为 `g.end <= o.end`，用 `g` 替换 `o` 后，原方案中所有能排在 `o` 后面的区间仍能排在 `g` 后面，所以方案数量不会减少。

因此至少存在一个最优解以 `g` 开头。选完 `g` 后，对剩余兼容区间重复同样论证。

### 伪代码

```text
按 end 升序排列区间
selected <- 空数组
last_end <- 无

for interval in 排序后的区间:
    如果 last_end 不存在 或 interval.start >= last_end:
        selected.push(interval)
        last_end <- interval.end

return selected
```

### 正确性说明

交换论证说明，第一步选择最早结束区间不会降低最优答案数量。删除所有与它冲突的区间后，剩余问题仍是同一种区间调度问题。对选择次数归纳，每一步都能与某个最优解保持一致，因此算法得到的区间数全局最优。

注意，这个证明优化的是“区间数量”。若每个区间有不同收益，最早结束贪心通常失效，应考虑加权区间 DP。

### 复杂度

- 排序：`O(n log n)`；
- 扫描：`O(n)`；
- 结果和排序所需额外空间依实现而定，下面的实现复制输入后排序，使用 `O(n)`。

### 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <optional>
#include <stdexcept>
#include <vector>

struct Interval {
    int start{};
    int end{};
    bool operator==(const Interval&) const = default;
};

std::vector<Interval> maximum_non_overlapping(std::vector<Interval> intervals) {
    for (const Interval interval : intervals) {
        if (interval.start >= interval.end) {
            throw std::invalid_argument("interval must satisfy start < end");
        }
    }

    std::sort(intervals.begin(), intervals.end(),
              [](const Interval& first, const Interval& second) {
                  if (first.end != second.end) {
                      return first.end < second.end;
                  }
                  return first.start < second.start;
              });

    std::vector<Interval> selected;
    std::optional<int> last_end;
    for (const Interval interval : intervals) {
        if (!last_end.has_value() || interval.start >= *last_end) {
            selected.push_back(interval);
            last_end = interval.end;
        }
    }
    return selected;
}

int main() {
    const std::vector<Interval> intervals{
        {1, 4}, {1, 3}, {3, 5}, {0, 7}, {5, 7}, {5, 9}, {8, 9}};
    const std::vector<Interval> expected{{1, 3}, {3, 5}, {5, 7}, {8, 9}};
    assert(maximum_non_overlapping(intervals) == expected);
    assert(maximum_non_overlapping({}).empty());
    assert((maximum_non_overlapping({{2, 6}}) ==
            std::vector<Interval>{{2, 6}}));
}
```

### 测试要点

覆盖空输入、单区间、首尾恰好相接、全部互相重叠、相同结束时间。必须先说清区间是闭区间还是半开区间；若 `[1,3]` 与 `[3,5]` 都含端点 `3`，兼容条件就不能写 `>=`。

### 常见追问

- **按开始时间最早选行吗？** 不行，例如 `[0,100)` 会挡住许多短区间。
- **按持续时间最短选行吗？** 也不总成立，短区间可能位于中间，同时挡住左右两个可兼容区间。
- **区间有收益怎么办？** 按结束时间排序，二分找前一个兼容区间，用 DP 比较选与不选。
- **怎样最少删除多少区间？** 总数减去最多可保留的不重叠区间数。

## 2. 贪心反例：一组数据就能推翻错误规则

考虑硬币 `{4,3,1}` 和金额 `6`。每次拿不超过余额的最大硬币，会得到 `4+1+1`，共三枚；最优解是 `3+3`，只要两枚。

这说明“每次拿最大”不是对所有硬币系统都正确。要推翻一个声称普遍成立的贪心规则，只需一个反例；要证明它正确，则需要覆盖所有合法输入的交换论证、领先不变量或其他严格理由。

下面的小程序同时运行错误贪心和正确 DP，帮助你亲眼看到差异：

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

std::vector<int> greedy_change(std::vector<int> coins, int amount) {
    std::sort(coins.rbegin(), coins.rend());
    std::vector<int> used;
    for (const int coin : coins) {
        while (coin > 0 && coin <= amount) {
            used.push_back(coin);
            amount -= coin;
        }
    }
    if (amount != 0) {
        return {};
    }
    return used;
}

std::int64_t minimum_coin_count(const std::vector<int>& coins, int amount) {
    if (amount < 0) {
        return -1;
    }
    const std::size_t target = static_cast<std::size_t>(amount);
    const auto infinity = std::numeric_limits<std::int64_t>::max() / 4;
    std::vector<std::int64_t> best(target + 1, infinity);
    best[0] = 0;
    for (std::size_t value = 1; value < best.size(); ++value) {
        for (const int coin : coins) {
            if (coin <= 0) {
                continue;
            }
            const std::size_t denomination = static_cast<std::size_t>(coin);
            if (denomination <= value && best[value - denomination] != infinity) {
                best[value] = std::min(
                    best[value], best[value - denomination] + 1);
            }
        }
    }
    return best[target] == infinity ? -1 : best[target];
}

int main() {
    const std::vector<int> coins{4, 3, 1};
    const auto greedy = greedy_change(coins, 6);
    assert((greedy == std::vector<int>{4, 1, 1}));
    assert(minimum_coin_count(coins, 6) == 2);
    assert(minimum_coin_count(coins, 0) == 0);
    assert(minimum_coin_count(coins, -1) == -1);
}
```

这里先把已确认非负的 `amount` 转成 `size_t`，再做 `+1` 和循环；不能先在 `int` 中计算 `amount + 1`，也不要用 `value <= amount` 让 `int` 循环变量在 `INT_MAX` 后继续自增。算法仍需 `O(amount)` 内存，因此真实题目还必须根据输入约束判断这张表是否可分配。

看到一道新题时，可以主动找小反例：零个元素、一个元素、两个选择互相冲突、局部最优挡住两个稍差选择、相等值和极端值。反例不仅用来否定算法，也能帮助你找出证明真正需要的前提。

## 3. DP 的五个问题

写任何 DP 前，先完整回答：

1. **状态**：`dp[...]` 的一句话含义是什么？
2. **选择**：到达这个状态的最后一步有哪些可能？
3. **转移**：如何从更小状态得到当前状态？
4. **初始化与顺序**：最小问题答案是什么，依赖计算好了吗？
5. **答案**：答案在哪个状态；若要方案，怎样恢复？

状态定义必须足够区分未来。例如只记“到当前位置的最大收益”，若未来合法性还取决于“上一项有没有选”，这个状态就可能不够。另一方面，状态越多，时间和空间通常越大。

## 4. 母题：一维 DP——不选相邻元素的最大和

### 白话题意

给一列收益，不能同时选择相邻位置，可以一个都不选。求最大总收益，并返回一组达到最大值的下标。

例如 `[2,7,9,3,1]` 的答案是下标 `[0,2,4]`，收益 `12`。

### 暴力办法

对每个位置做“选”或“不选”两种分支。选了位置 `i` 就跳到 `i+2`，不选就到 `i+1`。朴素递归会反复计算同一后缀，最坏约 `O(2^n)`。

### 关键观察与不变量

定义：

> `dp[i]` 表示只考虑前 `i` 个元素（下标 `0..i-1`）时，不选相邻元素能得到的最大收益。

处理第 `i-1` 个元素时只有两类完整情况：

- 不选它：答案是 `dp[i-1]`；
- 选它：不能选前一个，答案是 `dp[i-2] + value[i-1]`。

所以转移为二者较大值。

### 伪代码

```text
dp[0] <- 0
dp[1] <- max(0, value[0])

for i 从 2 到 n:
    skip <- dp[i-1]
    take <- dp[i-2] + value[i-1]
    dp[i] <- max(skip, take)

从 i=n 开始恢复:
    如果 dp[i] == dp[i-1]: 跳过 i-1，i <- i-1
    否则: 选择 i-1，i <- i-2
反转所选下标
```

### 正确性说明

`dp[0]=0` 表示没有元素只能取零；`dp[1]` 在选第一个和不选之间取优。对 `i>=2`，任何合法方案对最后元素要么选、要么不选，两类互斥且覆盖全部可能。不选时最多为 `dp[i-1]`；选时前一个不能选，前 `i-2` 项最多为 `dp[i-2]`。取二者最大，因此由归纳每个 `dp[i]` 都最优。

恢复时，若 `dp[i]==dp[i-1]`，存在一个最优方案不选最后元素；否则最优值只能来自选择它的转移。每次沿产生当前最优值的前置状态倒退，最终得到一组合法最优方案。

### 复杂度

- 计算并恢复方案：时间 `O(n)`、DP 表和结果空间 `O(n)`；
- 若只求最大值：只依赖前两个状态，可压缩为时间 `O(n)`、额外空间 `O(1)`。

### 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

struct Selection {
    std::int64_t best{};
    std::vector<std::size_t> indices;
};

Selection maximum_non_adjacent(const std::vector<int>& values) {
    const std::size_t count = values.size();
    std::vector<std::int64_t> dp(count + 1, 0);

    for (std::size_t i = 1; i <= count; ++i) {
        const std::int64_t skip = dp[i - 1];
        const std::int64_t take =
            static_cast<std::int64_t>(values[i - 1]) +
            (i >= 2 ? dp[i - 2] : 0);
        dp[i] = std::max(skip, take);
    }

    std::vector<std::size_t> selected;
    std::size_t i = count;
    while (i > 0) {
        if (dp[i] == dp[i - 1]) {
            --i; // 平局时选择跳过，仍然得到一个最优方案
        } else {
            selected.push_back(i - 1);
            i = (i >= 2) ? i - 2 : 0;
        }
    }
    std::reverse(selected.begin(), selected.end());
    return Selection{dp[count], std::move(selected)};
}

std::int64_t maximum_non_adjacent_compressed(const std::vector<int>& values) {
    std::int64_t two_back = 0;
    std::int64_t one_back = 0;
    for (const int value : values) {
        const std::int64_t current = std::max(
            one_back, two_back + static_cast<std::int64_t>(value));
        two_back = one_back;
        one_back = current;
    }
    return one_back;
}

int main() {
    const std::vector<int> values{2, 7, 9, 3, 1};
    const Selection answer = maximum_non_adjacent(values);
    assert(answer.best == 12);
    assert((answer.indices == std::vector<std::size_t>{0, 2, 4}));
    assert(maximum_non_adjacent_compressed(values) == answer.best);

    assert(maximum_non_adjacent({}).best == 0);
    assert(maximum_non_adjacent({-5, -2}).best == 0);
    assert(maximum_non_adjacent_compressed({10}) == 10);
}
```

### 测试要点

覆盖空数组、一个元素、全负数、相等最优解、很大的正收益。代码允许一个都不选，所以全负数答案为零；如果题目强制至少选一个，初始化和状态定义必须改变。还要明确收益总和是否保证落在 64 位范围内。

### 常见追问

- **为什么 `dp` 长度是 `n+1`？** `dp[i]` 表示前 `i` 项，`dp[0]` 自然表示空前缀，可减少边界分支。
- **空间压缩后还能恢复方案吗？** 仅保留两个值会丢掉选择历史；可保留决策位、重算部分状态，或接受 `O(n)` 表。
- **数组首尾也相邻怎么办？** 分别求“不含最后一个”和“不含第一个”两段的线性答案，再取较大者。
- **自顶向下怎么写？** 暴力递归加 `memo[index]`，每个下标只计算一次，也是 `O(n)`。

## 5. 一维空间压缩为什么成立

压缩不是把 `vector` 删除就算完成。必须先画出依赖：当前 `dp[i]` 只读取 `dp[i-1]` 和 `dp[i-2]`，更早状态永远不会再用，所以两个变量足够。

更新顺序也很重要：先用旧的 `one_back`、`two_back` 算 `current`，再整体向前滚动。如果先覆盖 `one_back`，后面的计算就会把“当前轮新值”误当作“上一轮旧值”。

## 6. 母题：二维 DP——编辑距离与操作恢复

### 白话题意

把字符串 `source` 变成 `target`，每次可以插入一个字符、删除一个字符或替换一个字符，每次成本为一。求最少操作数，并恢复一组操作。

例如 `kitten -> sitting` 最少三步：替换 `k->s`、替换 `e->i`、末尾插入 `g`。

### 暴力办法

从两个字符串的当前位置出发：若字符不同，可以尝试插入、删除、替换三个分支。许多分支会反复求解相同的前缀组合，朴素递归呈指数增长。

### 关键观察与不变量

定义二维状态：

> `dp[i][j]` 表示把 `source` 的前 `i` 个字符变成 `target` 的前 `j` 个字符所需的最少操作数。

最后一步只有四种情况：

- 末尾字符相同：无需操作，来自 `dp[i-1][j-1]`；
- 删除 `source[i-1]`：来自 `dp[i-1][j] + 1`；
- 插入 `target[j-1]`：来自 `dp[i][j-1] + 1`；
- 替换末尾字符：来自 `dp[i-1][j-1] + 1`。

初始化也有业务含义：非空前缀变空串只能全部删除，空串变非空前缀只能逐个插入。

### 伪代码

```text
dp[i][0] <- i
dp[0][j] <- j

for i 从 1 到 source.length:
    for j 从 1 到 target.length:
        如果 source[i-1] == target[j-1]:
            dp[i][j] <- dp[i-1][j-1]
        否则:
            dp[i][j] <- 1 + min(
                dp[i-1][j],     // 删除
                dp[i][j-1],     // 插入
                dp[i-1][j-1])   // 替换

从 dp[n][m] 沿等式成立的前置状态倒推操作，再反转
```

### 正确性说明

边界行列显然最优。对任意 `i,j>0`，一个最优编辑序列的最后一步必属于上述四类。去掉最后一步后，剩余操作必须是对应更小前缀问题的最优解；否则替换成更优子解就能改进原方案，产生矛盾。转移枚举并取遍全部可能最后一步，因此由二维前缀长度归纳，`dp[i][j]` 最优。

恢复过程每次选择一个满足当前 DP 等式的前置格子，等价于倒放某条最优路径。下标严格减小，最终到达 `(0,0)`，所以得到一组成本为 `dp[n][m]` 的操作。

### 复杂度

- 完整表和方案恢复：时间 `O(nm)`、空间 `O(nm)`；
- 只求距离时：当前行只依赖上一行和当前行左侧，可压缩为 `O(min(n,m))` 空间；
- 操作列表长度最多 `O(n+m)`。

### 完整 C++20

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <string_view>
#include <utility>
#include <vector>

enum class EditKind { match, replace, erase, insert };

struct EditOperation {
    EditKind kind{};
    char from{};
    char to{};
};

struct EditResult {
    std::size_t distance{};
    std::vector<EditOperation> operations;
};

EditResult edit_distance_with_path(std::string_view source,
                                   std::string_view target) {
    const std::size_t rows = source.size() + 1;
    const std::size_t columns = target.size() + 1;
    std::vector<std::vector<std::size_t>> dp(
        rows, std::vector<std::size_t>(columns, 0));

    for (std::size_t i = 0; i < rows; ++i) {
        dp[i][0] = i;
    }
    for (std::size_t j = 0; j < columns; ++j) {
        dp[0][j] = j;
    }

    for (std::size_t i = 1; i < rows; ++i) {
        for (std::size_t j = 1; j < columns; ++j) {
            if (source[i - 1] == target[j - 1]) {
                dp[i][j] = dp[i - 1][j - 1];
            } else {
                dp[i][j] = 1 + std::min(
                    {dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]});
            }
        }
    }

    std::vector<EditOperation> reversed;
    std::size_t i = source.size();
    std::size_t j = target.size();
    while (i > 0 || j > 0) {
        if (i > 0 && j > 0 &&
            source[i - 1] == target[j - 1] &&
            dp[i][j] == dp[i - 1][j - 1]) {
            reversed.push_back(
                EditOperation{EditKind::match, source[i - 1], target[j - 1]});
            --i;
            --j;
        } else if (i > 0 && j > 0 &&
                   dp[i][j] == dp[i - 1][j - 1] + 1) {
            reversed.push_back(
                EditOperation{EditKind::replace, source[i - 1], target[j - 1]});
            --i;
            --j;
        } else if (i > 0 && dp[i][j] == dp[i - 1][j] + 1) {
            reversed.push_back(
                EditOperation{EditKind::erase, source[i - 1], '\0'});
            --i;
        } else {
            assert(j > 0 && dp[i][j] == dp[i][j - 1] + 1);
            reversed.push_back(
                EditOperation{EditKind::insert, '\0', target[j - 1]});
            --j;
        }
    }

    std::reverse(reversed.begin(), reversed.end());
    return EditResult{dp.back().back(), std::move(reversed)};
}

std::size_t edit_distance_compressed(std::string_view source,
                                     std::string_view target) {
    if (target.size() > source.size()) {
        return edit_distance_compressed(target, source);
    }

    std::vector<std::size_t> previous(target.size() + 1);
    std::vector<std::size_t> current(target.size() + 1);
    for (std::size_t j = 0; j <= target.size(); ++j) {
        previous[j] = j;
    }

    for (std::size_t i = 1; i <= source.size(); ++i) {
        current[0] = i;
        for (std::size_t j = 1; j <= target.size(); ++j) {
            if (source[i - 1] == target[j - 1]) {
                current[j] = previous[j - 1];
            } else {
                current[j] = 1 + std::min(
                    {previous[j], current[j - 1], previous[j - 1]});
            }
        }
        std::swap(previous, current);
    }
    return previous.back();
}

int main() {
    const EditResult result = edit_distance_with_path("kitten", "sitting");
    assert(result.distance == 3);
    const auto changed = std::count_if(
        result.operations.begin(), result.operations.end(),
        [](const EditOperation& operation) {
            return operation.kind != EditKind::match;
        });
    assert(changed == 3);
    assert(edit_distance_compressed("kitten", "sitting") == 3);
    assert(edit_distance_compressed("", "abc") == 3);
    assert(edit_distance_compressed("same", "same") == 0);
}
```

### 测试要点

覆盖两个空串、只有一边为空、完全相同、全替换、插入和删除混合。距离相同的最优操作序列可能不唯一，所以不要只比较一套固定文字；应验证操作应用后确实得到目标，且非匹配操作数等于最优距离。

### 常见追问

- **为什么字符下标是 `i-1`？** `i` 表示前缀长度；长度为一的前缀最后字符下标是零。
- **怎样只用一行数组？** 还要保存左上角旧值；更新顺序必须保证“上、左、左上”分别来自正确轮次。
- **压缩后为什么难恢复路径？** 旧行被覆盖，无法知道每个格子来自哪个前驱；可保留父方向、分治恢复，或使用完整表。
- **替换成本不是一怎么办？** 把转移中的常数换成对应成本；若成本与字符相关，状态结构仍可能不变。

## 7. 二维空间压缩：先看依赖方向

编辑距离的 `dp[i][j]` 读取：

- 上方 `dp[i-1][j]`；
- 左方 `dp[i][j-1]`；
- 左上 `dp[i-1][j-1]`。

使用两行时，`previous` 是上一行，`current` 是本行；从左到右计算保证 `current[j-1]` 已存在。若压成一行，覆盖一个格子前要先保存它作为下一格的“左上”。

并不是所有二维 DP 都能轻易压缩。即使能压缩，也要权衡：内存变少，但调试更难，而且可能失去答案恢复所需的信息。面试中先给清楚正确的完整表，再讨论压缩，通常比一上来写难懂的滚动数组更稳。

## 8. 贪心与 DP 的分界练习

看到下面的问题，先判断更像贪心还是 DP，并说理由：

- 最多选择多少个互不重叠区间：贪心，最早结束有交换论证；
- 互不重叠区间的最大总收益：DP，局部最早结束可能放弃高收益组合；
- 任意硬币系统的最少硬币数：DP，最大硬币贪心存在反例；
- 所有任务耗时相同、每次选最早截止任务：仍需看目标和约束，不能只凭关键词；
- 网格最小路径和：通常二维 DP，但若可移动方向或存在环改变，需要重新建模。

算法名称不是由故事中的“选择”“收益”“最短”决定，而是由可证明的结构决定。

## 9. 常见错误清单

- 用“直觉上更好”代替贪心正确性证明；
- 只试几个样例就断言贪心普遍正确；
- `dp[i]` 没有一句准确含义，代码写到一半才改定义；
- 初始化为零，却把“不可达”也误当成收益零；
- 遍历顺序让转移读取了本轮尚未计算或已被错误覆盖的状态；
- 忘记题目是否允许一个都不选；
- 只求出最优值，却没有为“输出具体方案”保存父状态；
- 空间压缩后仍试图直接使用已经覆盖的历史；
- 把 `int` 的多个值相加，不检查总和范围；
- 用浮点数直接做相等判断作为状态条件。

## 10. 练习

1. 加权区间调度：每个区间有收益，求最大总收益并恢复选择。
2. 兑换零钱：给任意正整数硬币，求组成金额的最少硬币数并恢复硬币。
3. 经典 0/1 背包：每件物品最多选一次，求容量内最大价值。
4. 网格最小路径和：只能向右或向下，并恢复一条最优路径。
5. 最长递增子序列：先写 `O(n^2)` DP，再解释 `O(n log n)` 方法维护的数组含义。
6. 股票至多交易两次的最大收益：明确持有状态和交易次数。

## 11. 练习答案与思路

### 练习 1

按结束时间排序。令 `previous[i]` 是第 `i` 个区间之前最后一个与它兼容的区间，可用二分预处理。定义 `dp[i]` 为前 `i` 个区间最大收益：

```text
dp[i] = max(dp[i-1], profit[i-1] + dp[previous[i-1] + 1])
```

恢复时比较当前值来自“不选”还是“选”。这正是普通区间贪心失效后增加状态的做法。

### 练习 2

`dp[amount]` 表示组成该金额的最少枚数，不可达初始化为无穷，`dp[0]=0`。对每个金额尝试最后一枚硬币；成功改进时记录该硬币。若硬币包含零或负数，必须拒绝输入。

### 练习 3

二维定义 `dp[i][capacity]` 为前 `i` 件物品在容量限制下的最大价值。选第 `i-1` 件时读取 `dp[i-1][capacity-weight]`，不选读取 `dp[i-1][capacity]`。压成一维后容量必须从大到小遍历，否则同一物品可能在本轮被重复使用，变成完全背包。

### 练习 4

`dp[row][column]` 为到该格子的最小路径和，只能来自上方或左方。首行和首列只有一条方向，需单独初始化。恢复时从终点选择产生当前值的上方或左方前驱。若格子值可能让总和溢出，使用更宽类型并检查约束。

### 练习 5

`O(n^2)` 定义 `dp[i]` 为“以 `i` 结尾”的最长递增子序列长度，枚举所有更早且值更小的 `j`。`O(n log n)` 方法维护 `tails[len]`：长度为 `len+1` 的递增子序列能够取得的最小结尾值；它不是最终序列本身，恢复方案还需额外前驱信息。

### 练习 6

可把每天的状态分为：完成零次交易且未持有、第一次持有、完成一次卖出、第二次持有、完成第二次卖出。每天用“保持原状态”或“今天买/卖”更新。必须明确同一天更新能否读取本轮新状态；使用旧状态副本最容易避免顺序歧义。

## 12. 面试前自检

你应该能不看代码回答：

1. 区间调度为何按最早结束选择，而不是最早开始？
2. 交换论证究竟交换了哪两个选择？
3. 一个反例能证明什么，不能证明什么？
4. `dp[i]` 与数组下标 `i` 的关系是什么？
5. DP 初始化为什么属于状态定义的一部分？
6. 如何从最优值恢复一组具体选择？
7. 空间压缩需要检查哪些依赖和更新顺序？
8. 为什么完整二维表正确后，再压缩通常更稳？

当你能先写出状态含义和证明，再写出循环，DP 就不再是“背公式”；当你会主动找反例和做交换论证，贪心也不再是“凭感觉”。

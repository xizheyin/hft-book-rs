# 动态规划：状态、遍历方向、不可达与答案恢复

动态规划（Dynamic Programming，DP）常被误解成“背状态转移方程”。真正稳定的做法是先回答六个问题：

1. `dp[...]` 用一句白话到底表示什么？
2. 当前状态从哪些更小状态转移而来？
3. 哪些状态一开始可达，哪些不可达？
4. 按什么顺序计算，才能保证依赖已经准备好？
5. 最终答案存在哪里？
6. 只要最优值，还是还要恢复具体选择？

本章用四道母题把这些问题串起来。不要先背代码；先把状态定义写在纸上，再检查循环顺序是否真的符合定义。

> **本章目标**：会从暴力递归中识别重复子问题；能解释 0/1 背包容量为何倒序；能表示不可达状态；能恢复网格最优路径；能从 `O(n²)` 的最长递增子序列推导出 `O(n log n)` 方法。

## 1. 一张 DP 检查表

| 步骤 | 必须说清的内容 | 常见错误 |
|---|---|---|
| 状态 | 下标各代表什么，值代表“恰好”还是“至多” | 状态含义随代码变化 |
| 转移 | 最后一步做了什么 | 漏掉一种选择 |
| 初始值 | 空问题的答案和不可达哨兵 | 把不可达错误地初始化为 0 |
| 遍历顺序 | 当前读取的是上一轮还是本轮状态 | 0/1 物品被重复使用 |
| 答案 | 是 `dp[n]`、最大值还是最小值 | 取错状态 |
| 恢复 | 保存父指针、选择，或重新推导 | 压缩后才发现路径丢了 |

空间压缩不是自动收益。它会减少内存，有时也改善缓存局部性；但覆盖旧状态后，恢复具体方案通常更困难。先满足题目输出，再决定是否压缩。

## 2. 母题一：0/1 背包与容量倒序

### 2.1 白话题意

有 `n` 件物品。第 `i` 件物品重量为 `weight[i]`，价值为 `value[i]`；背包容量为 `capacity`。每件物品只能选零次或一次，求不超过容量时的最大总价值。

```text
重量：[2, 3, 4]
价值：[4, 5, 7]
容量：5
答案：9，选择重量 2 和 3 的物品
```

本题假设重量为正整数、价值为非负整数。

### 2.2 基线：枚举选或不选

对每件物品都有“选”和“不选”两种选择。递归枚举所有子集，最坏会产生 `2^n` 个方案：

```text
solve(i, remaining)：
    如果 i == n：返回 0
    best = solve(i + 1, remaining)              // 不选
    如果 weight[i] <= remaining：
        best = max(best,
                   value[i] + solve(i + 1, remaining - weight[i]))
    返回 best
```

许多不同选择会重复到达相同的 `(i, remaining)`，这就是可以复用的子问题。

### 2.3 状态、转移与不变量

先定义二维状态：

```text
dp[i][c] = 只看前 i 件物品、容量至多为 c 时的最大价值
```

第 `i` 件物品不选，答案来自 `dp[i-1][c]`；能选时，也可以来自 `dp[i-1][c-weight] + value`。

二维表的当前行只依赖上一行，因此可以压成一维：

```text
dp[c] = 已处理物品在容量至多为 c 时的最大价值
```

处理一件新物品时，容量必须**从大到小**遍历。这样读取的 `dp[c-weight]` 仍是处理这件物品之前的旧值。若从小到大，刚更新的状态会再次使用同一物品，悄悄变成“每件可选无限次”的完全背包。

循环不变量是：处理完前 `i` 件物品后，每个 `dp[c]` 都等于只使用这 `i` 件物品、容量至多为 `c` 的最优价值。

### 2.4 伪代码

```text
dp[0 ... capacity] = 0

for 每件物品 (weight, value)：
    for c 从 capacity 递减到 weight：
        dp[c] = max(dp[c], dp[c - weight] + value)

返回 dp[capacity]
```

### 2.5 为什么正确

对处理过的物品数量做归纳。没有物品时，任何容量的最大价值都是 0。

处理当前物品时，对容量 `c`，合法最优方案只有两类：

- 不选当前物品，价值为旧的 `dp[c]`；
- 选一次当前物品，剩余容量使用之前物品的最优值，即旧的 `dp[c-weight] + value`。

倒序遍历保证两项都来自“尚未重复使用当前物品”的状态。取两者最大值覆盖了全部合法方案，因此不变量保持。最终 `dp[capacity]` 即为答案。

### 2.6 复杂度

- 时间复杂度：`O(n × capacity)`；
- 额外空间：`O(capacity)`。

这是**伪多项式**复杂度：它依赖容量的数值，而不仅是表示容量所需的位数。容量极大时不能只看到 `O(nC)` 中的字母就认为可行。

### 2.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <vector>

long long knapsack_01(
    const std::vector<int>& weights,
    const std::vector<int>& values,
    std::size_t capacity) {
    if (weights.size() != values.size()) {
        throw std::invalid_argument("weights and values must have equal length");
    }
    for (std::size_t i = 0; i < weights.size(); ++i) {
        if (weights[i] <= 0 || values[i] < 0) {
            throw std::invalid_argument("weight must be positive and value non-negative");
        }
    }

    if (capacity == std::numeric_limits<std::size_t>::max()) {
        throw std::length_error("capacity is too large");
    }
    const std::size_t state_count = capacity + 1;
    if (state_count > std::vector<long long>{}.max_size()) {
        throw std::length_error("DP table cannot represent this capacity");
    }
    std::vector<long long> dp(state_count, 0);
    for (std::size_t i = 0; i < weights.size(); ++i) {
        const std::size_t weight = static_cast<std::size_t>(weights[i]);
        if (weight > capacity) {
            continue;
        }

        for (std::size_t c = capacity; c >= weight; --c) {
            const long long item_value = static_cast<long long>(values[i]);
            if (dp[c - weight] >
                std::numeric_limits<long long>::max() - item_value) {
                throw std::overflow_error("knapsack value exceeds long long");
            }
            dp[c] = std::max(dp[c], dp[c - weight] + item_value);
        }
    }
    return dp[capacity];
}

int main() {
    assert(knapsack_01({2, 3, 4}, {4, 5, 7}, 5) == 9);
    assert(knapsack_01({}, {}, 10) == 0);
    assert(knapsack_01({2}, {3}, 0) == 0);
    assert(knapsack_01({8}, {100}, 7) == 0);

    // 同一件重量 2、价值 3 的物品不能在容量 4 中使用两次。
    assert(knapsack_01({2}, {3}, 4) == 3);

    bool rejected = false;
    try {
        static_cast<void>(knapsack_01({0}, {1}, 3));
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    bool rejected_capacity = false;
    try {
        static_cast<void>(knapsack_01(
            {}, {}, std::numeric_limits<std::size_t>::max()));
    } catch (const std::length_error&) {
        rejected_capacity = true;
    }
    assert(rejected_capacity);
}
```

正重量前提也保证了无符号倒序循环能够在 `c < weight` 时结束。代码还在执行 `capacity + 1` 前拒绝 `SIZE_MAX`，并检查容器的理论上限，避免无符号回绕；即使通过这两项，实际内存仍可能不足，所以面试时必须先用题目约束估算状态表大小。若允许零重量，除了业务语义要重新定义，循环边界也必须重写。

### 2.8 测试时还要想什么

- 空物品、零容量；
- 所有物品都太重；
- 最优方案只选一件或组合多件；
- 单件物品不能被重复选择；
- 重量与价值数组长度不一致；
- 非法零/负重量，以及总价值是否会溢出。

### 2.9 常见追问

1. **为什么必须倒序？** 为了让转移读取上一轮状态，防止当前物品在同一轮重复使用。
2. **每件物品可以无限次使用呢？** 完全背包通常把容量改为从小到大，让当前物品更新后的状态可以继续参与。
3. **要恢复选了哪些物品怎么办？** 保留二维表或父选择信息，再从 `(n, capacity)` 逆推；仅保留一维最优值不够直接恢复。
4. **容量是十亿怎么办？** `O(nC)` 不可行，需要利用物品数量、价值总和、特殊结构或近似算法等其他约束。

## 3. 母题二：凑出金额所需的最少硬币

### 3.1 白话题意

给定若干正整数面额，每种硬币可以使用无限次。求恰好凑出 `amount` 所需的最少硬币数；无法凑出时返回空结果。

```text
面额：[1, 3, 4]，amount = 6
答案：2，使用 3 + 3
```

“恰好凑出”很重要。不能把无法到达的状态错误地当作 0 枚硬币。

### 3.2 基线：递归尝试最后一枚硬币

可以枚举最后使用哪种硬币：

```text
solve(x)：
    如果 x == 0：返回 0
    如果 x < 0：返回“不可达”
    answer = “不可达”
    for coin 遍历所有面额：
        previous = solve(x - coin)
        如果 previous 可达：
            answer = min(answer, previous + 1)
    返回 answer
```

不做记忆化时，同一个金额会被反复计算，递归树可能指数增长。

### 3.3 状态、不可达与不变量

定义：

```text
dp[x] = 恰好凑出金额 x 的最少硬币数
```

`dp[0] = 0`。其他金额一开始不可达，必须使用明确哨兵 `INF`，而不是 0。

若 `x - coin` 可达，则可以在其方案末尾再加一枚 `coin`：

```text
dp[x] = min(dp[x], dp[x - coin] + 1)
```

循环不变量是：开始计算 `x` 时，所有更小金额的最优答案已经正确；完成后，`dp[x]` 考虑了所有可能的最后一枚硬币。

### 3.4 伪代码

```text
dp[0] = 0
dp[1 ... amount] = INF

for x 从 1 到 amount：
    for coin 遍历面额：
        如果 coin <= x 且 dp[x - coin] 可达：
            dp[x] = min(dp[x], dp[x - coin] + 1)

如果 dp[amount] 仍为 INF：返回“不可达”
否则返回 dp[amount]
```

### 3.5 为什么正确

对金额 `x` 归纳。`x = 0` 不需要硬币，答案为 0。

任何凑出正金额 `x` 的方案都有最后一枚硬币 `coin`；移走它后，剩余方案恰好凑出 `x - coin`。根据归纳假设，`dp[x-coin]` 已是该剩余金额的最少硬币数。算法枚举每种可能的最后硬币并取最小，因此不会漏掉更优方案。

只有前一状态可达时才转移，所以不可达状态不会凭空产生方案。

### 3.6 复杂度

设面额数量为 `m`：

- 时间复杂度：`O(amount × m)`；
- 额外空间：`O(amount)`。

它同样依赖金额数值，是伪多项式算法。

### 3.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <optional>
#include <stdexcept>
#include <vector>

std::optional<long long> minimum_coin_count(
    const std::vector<int>& coins,
    int amount) {
    if (amount < 0) {
        throw std::invalid_argument("amount must be non-negative");
    }
    for (int coin : coins) {
        if (coin <= 0) {
            throw std::invalid_argument("coin value must be positive");
        }
    }

    const std::size_t target = static_cast<std::size_t>(amount);
    const long long unreachable = -1;
    std::vector<long long> dp(target + 1, unreachable);
    dp[0] = 0;

    for (std::size_t current = 1; current <= target; ++current) {
        for (int coin : coins) {
            const std::size_t denomination = static_cast<std::size_t>(coin);
            if (denomination <= current &&
                dp[current - denomination] != unreachable) {
                const long long candidate = dp[current - denomination] + 1;
                if (dp[current] == unreachable || candidate < dp[current]) {
                    dp[current] = candidate;
                }
            }
        }
    }

    if (dp[target] == unreachable) {
        return std::nullopt;
    }
    return dp[target];
}

int main() {
    assert(minimum_coin_count({1, 3, 4}, 6).value() == 2);
    assert(minimum_coin_count({2}, 3) == std::nullopt);
    assert(minimum_coin_count({}, 0).value() == 0);
    assert(minimum_coin_count({}, 5) == std::nullopt);
    assert(minimum_coin_count({2, 5}, 10).value() == 2);

    bool rejected = false;
    try {
        static_cast<void>(minimum_coin_count({0, 2}, 4));
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);
}
```

硬币数量不可能为负，因此实现用 `-1` 明确表示不可达，并且只从非负状态转移。实际工程还应在分配 `amount + 1` 个状态前设置输入规模上限。

### 3.8 测试时还要想什么

- `amount = 0`；
- 空面额、无法凑出；
- 某一枚硬币直接等于目标；
- 贪心选最大面额不是最优的情况，如 `[1, 3, 4]` 与金额 6；
- 零或负面额；
- 极大金额导致时间或内存不可接受。

### 3.9 常见追问

1. **为什么不能把不可达初始化成 0？** 0 表示一个真实答案，会让后续状态从不存在的方案转移。
2. **要返回具体硬币组合呢？** 每次改善 `dp[x]` 时记录选择的硬币，再从 `amount` 不断减去它。
3. **要计算组合数量呢？** 状态含义和循环顺序都会改变；还要区分 `[1,2]` 与 `[2,1]` 是否算同一种。
4. **硬币数量有限呢？** 变成有数量约束的背包，不能继续无条件复用当前面额。

## 4. 母题三：网格最小路径与答案恢复

### 4.1 白话题意

给定一个非空矩形网格，每格是非负成本。从左上角出发，每步只能向右或向下，直到右下角。求最小总成本，并返回一条达到该成本的完整坐标路径。起点和终点成本都计入。

```text
网格：
1  3  1
1  5  1
4  2  1

最小成本：7
一条路径：(0,0) → (0,1) → (0,2) → (1,2) → (2,2)
```

### 4.2 基线：枚举所有路径

从每格递归尝试向右和向下。一个 `r × c` 网格可能有组合数量级的路径，许多路径会重复求同一格到终点的最优成本。

### 4.3 状态、父指针与不变量

定义：

```text
dp[r][c] = 从左上角走到 (r,c) 的最小总成本
```

进入 `(r,c)` 的最后一步只可能来自上方或左方：

```text
dp[r][c] = grid[r][c] + min(dp[r-1][c], dp[r][c-1])
```

同时保存 `parent[r][c]`：最优转移来自上方记为 `U`，来自左方记为 `L`。从终点沿父指针逆走，再反转即可恢复路径。

扫描不变量是：按行从左到右处理时，当前格上方和左方的最优成本与父指针都已经正确。

### 4.4 伪代码

```text
dp[0][0] = grid[0][0]

按行扫描每个其他格子 (r,c)：
    如果只有上方可达：从上方转移，parent = U
    如果只有左方可达：从左方转移，parent = L
    如果两者都可达：选择成本较小者，并记录 parent

path = 空列表
从右下角开始：
    把当前坐标加入 path
    根据 parent 走到上方或左方
直到到达左上角
加入左上角并反转 path

返回 dp[rows-1][cols-1] 和 path
```

### 4.5 为什么正确

网格移动只向右或向下，所以不存在回到尚未计算位置的环。对处理顺序归纳：起点成本显然正确；任何其他格子的所有合法路径，最后一步必来自上方或左方。根据归纳假设，这两个前驱的最优成本已知，选择较小者再加当前成本，得到当前格最优值。

父指针记录了每次实际采用的等式分支。逆向跟随父指针每步都回到一个合法前驱，最终到达起点；反转后就是一条成本等于 DP 最优值的合法路径。

### 4.6 复杂度

- 时间复杂度：`O(rows × cols)`；
- `dp` 与父指针空间：`O(rows × cols)`；
- 恢复路径长度：`O(rows + cols)`。

如果只求成本，可以把 `dp` 压缩到一行 `O(cols)`；但父信息被覆盖后，不能再直接恢复路径。这就是输出需求影响空间优化的例子。

### 4.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

using Coordinate = std::pair<std::size_t, std::size_t>;

struct PathResult {
    long long cost;
    std::vector<Coordinate> path;
};

std::optional<PathResult> minimum_grid_path(
    const std::vector<std::vector<int>>& grid) {
    if (grid.empty()) {
        return std::nullopt;
    }
    const std::size_t rows = grid.size();
    const std::size_t columns = grid.front().size();
    for (const auto& row : grid) {
        if (row.size() != columns) {
            throw std::invalid_argument("grid must be rectangular");
        }
        for (int cost : row) {
            if (cost < 0) {
                throw std::invalid_argument("grid costs must be non-negative");
            }
        }
    }
    if (columns == 0) {
        return std::nullopt;
    }

    std::vector<std::vector<long long>> dp(
        rows, std::vector<long long>(columns, 0));
    std::vector<std::vector<char>> parent(
        rows, std::vector<char>(columns, 'S'));
    dp[0][0] = grid[0][0];

    for (std::size_t row = 0; row < rows; ++row) {
        for (std::size_t column = 0; column < columns; ++column) {
            if (row == 0 && column == 0) {
                continue;
            }

            if (row == 0) {
                dp[row][column] = dp[row][column - 1] + grid[row][column];
                parent[row][column] = 'L';
            } else if (column == 0) {
                dp[row][column] = dp[row - 1][column] + grid[row][column];
                parent[row][column] = 'U';
            } else if (dp[row - 1][column] <= dp[row][column - 1]) {
                dp[row][column] = dp[row - 1][column] + grid[row][column];
                parent[row][column] = 'U';
            } else {
                dp[row][column] = dp[row][column - 1] + grid[row][column];
                parent[row][column] = 'L';
            }
        }
    }

    std::vector<Coordinate> path;
    std::size_t row = rows - 1;
    std::size_t column = columns - 1;
    while (row != 0 || column != 0) {
        path.emplace_back(row, column);
        if (parent[row][column] == 'U') {
            --row;
        } else {
            --column;
        }
    }
    path.emplace_back(0, 0);
    std::reverse(path.begin(), path.end());

    return PathResult{dp[rows - 1][columns - 1], std::move(path)};
}

int main() {
    const auto result = minimum_grid_path({
        {1, 3, 1},
        {1, 5, 1},
        {4, 2, 1},
    });
    assert(result.has_value());
    assert(result->cost == 7);
    assert(result->path.front() == Coordinate(0, 0));
    assert(result->path.back() == Coordinate(2, 2));
    assert(result->path.size() == 5);

    const auto single = minimum_grid_path({{8}});
    assert(single->cost == 8);
    assert(single->path == std::vector<Coordinate>({{0, 0}}));
    assert(!minimum_grid_path({}).has_value());
    assert(!minimum_grid_path({{}}).has_value());

    bool rejected = false;
    try {
        static_cast<void>(minimum_grid_path({{1, 2}, {3}}));
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    bool rejected_empty_ragged = false;
    try {
        static_cast<void>(minimum_grid_path({{}, {1}}));
    } catch (const std::invalid_argument&) {
        rejected_empty_ragged = true;
    }
    assert(rejected_empty_ragged);
}
```

### 4.8 测试时还要想什么

- 空网格、空行、非矩形网格；
- 单格、单行、单列；
- 多条最优路径并列时采用什么稳定规则；
- 恢复路径是否从起点到终点、每步是否合法；
- 路径上的成本和是否等于返回成本；
- 成本之和是否会超过所用整数类型。

### 4.9 常见追问

1. **加入障碍格怎么办？** 把障碍和无法从前驱到达的格子标成不可达，只从可达前驱转移。
2. **允许上下左右移动呢？** 图中出现环，简单的行扫描 DP 不再成立；非负边权可转成最短路问题。
3. **只要成本怎样压缩？** 当前行只依赖上一行和当前行左侧，可用一维数组原地更新。
4. **既要低内存又要路径呢？** 需要分治重算、检查点或其他恢复策略，不能假装一维值数组仍保留全部父信息。

## 5. 母题四：最长严格递增子序列

### 5.1 白话题意

给定整数数组，求最长**严格递增子序列**的长度。子序列保持原下标顺序，但不要求元素连续。

```text
输入：[10, 9, 2, 5, 3, 7, 101, 18]
答案：4，例如 [2, 3, 7, 18]
```

“严格递增”意味着相等元素不能接在后面增加长度。

### 5.2 基线：枚举子序列，再到 `O(n²)` DP

每个元素都有选或不选两种可能，枚举所有子序列需要指数时间。

先定义一个容易证明的二次 DP：

```text
length[i] = 以 a[i] 结尾的最长严格递增子序列长度
```

枚举所有 `j < i`；若 `a[j] < a[i]`，就能把 `a[i]` 接到以 `j` 结尾的序列后。总时间 `O(n²)`。

### 5.3 从状态到更强不变量

二次 DP 保存“每个位置结尾的最优长度”。若只求总长度，可以改存：

```text
tails[len - 1] = 当前已扫描前缀中，长度为 len 的递增子序列
                 所能达到的最小结尾值
```

结尾越小，越容易被未来元素接上。`tails` 始终严格递增。处理新值 `x` 时，找到第一个 `>= x` 的位置并替换：

- 找到位置 `p`：`x` 能成为长度 `p + 1` 的更小或相等结尾；
- 没找到：`x` 大于全部结尾，可以把最长长度增加一。

这里使用 `lower_bound`。若题目改成最长**非递减**子序列，相等值允许延长，需要改用 `upper_bound`。

### 5.4 伪代码

```text
tails = 空列表

for x 遍历数组：
    p = tails 中第一个大于等于 x 的位置
    如果 p 不存在：
        tails 末尾加入 x
    否则：
        tails[p] = x

返回 tails.length
```

`tails` 的内容不保证本身就是原数组中的某条最终子序列；它维护的是每个长度的最优结尾值。

### 5.5 为什么正确

处理 `x` 前，假设 `tails[p-1] < x`，而 `tails[p] >= x`。那么存在一条长度为 `p`、结尾为 `tails[p-1]` 的递增子序列，可以接上 `x` 得到长度 `p+1`。用 `x` 替换 `tails[p]` 不改变已知可达长度，只让该长度的结尾不更大，未来扩展机会不会变差。

若 `x` 大于所有结尾，它能接在当前最长序列之后，最长长度增加一。反之，`x` 不可能凭空产生更长序列，因为它不能接在长度更长且结尾不小于它的候选之后。

因此 `tails.size()` 始终等于已扫描前缀的 LIS 长度。

### 5.6 复杂度

- 二次 DP：时间 `O(n²)`、空间 `O(n)`；
- `tails` 方法：时间 `O(n log n)`、空间 `O(n)`。

### 5.7 完整 C++20 实现

示例同时保留 `O(n²)` 基线，并用随机小输入对拍优化实现。基线不仅用于教学，也是很好的测试 oracle。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <random>
#include <vector>

std::size_t lis_length_quadratic(const std::vector<int>& values) {
    if (values.empty()) {
        return 0;
    }

    std::vector<std::size_t> length(values.size(), 1);
    std::size_t best = 1;
    for (std::size_t i = 0; i < values.size(); ++i) {
        for (std::size_t j = 0; j < i; ++j) {
            if (values[j] < values[i]) {
                length[i] = std::max(length[i], length[j] + 1);
            }
        }
        best = std::max(best, length[i]);
    }
    return best;
}

std::size_t lis_length_nlogn(const std::vector<int>& values) {
    std::vector<int> tails;
    tails.reserve(values.size());

    for (int value : values) {
        const auto position =
            std::lower_bound(tails.begin(), tails.end(), value);
        if (position == tails.end()) {
            tails.push_back(value);
        } else {
            *position = value;
        }
    }
    return tails.size();
}

int main() {
    assert(lis_length_nlogn({10, 9, 2, 5, 3, 7, 101, 18}) == 4);
    assert(lis_length_nlogn({}) == 0);
    assert(lis_length_nlogn({5, 4, 3, 2}) == 1);
    assert(lis_length_nlogn({2, 2, 2}) == 1);
    assert(lis_length_nlogn({1, 2, 3, 4}) == 4);

    std::mt19937 generator(20260805);
    std::uniform_int_distribution<int> length_distribution(0, 20);
    std::uniform_int_distribution<int> value_distribution(-10, 10);
    for (int test = 0; test < 500; ++test) {
        std::vector<int> values(
            static_cast<std::size_t>(length_distribution(generator)));
        for (int& value : values) {
            value = value_distribution(generator);
        }
        assert(lis_length_nlogn(values) == lis_length_quadratic(values));
    }
}
```

### 5.8 测试时还要想什么

- 空数组、单元素；
- 严格递增、严格递减；
- 全部相等，确认“严格”语义；
- 多条不同 LIS；
- 负数和重复值；
- 用 `O(n²)` 基线对随机小输入做差分测试。

### 5.9 常见追问

1. **怎样恢复一条 LIS？** 除 `tails` 值外，再保存每个长度对应的原下标和每个元素的前驱下标，最后从最长结尾逆推。
2. **为什么 `tails` 本身不一定是一条答案？** 不同位置的替换可能来自彼此不兼容的历史子序列；它只保证每个长度的最小结尾值存在。
3. **最长非递减子序列怎么改？** 使用第一个 `> x` 的位置，即 `upper_bound`。
4. **为什么优化不是普通 DP 数组压缩？** 它更换了状态表示，用“长度对应最小结尾”获得单调数组，再通过二分加速转移。

## 6. 母题五：相邻石堆合并的区间 DP

### 6.1 白话题意

有一排非负重量的石堆。一次操作只能选择**相邻的两组**，把它们合成一组；本次成本等于新组的总重量。不断合并，直到只剩一组，求最小总成本。

```text
石堆：[4, 3, 3, 4]
一种最优顺序：
4+3，成本 7；3+4，成本 7；最后 7+7，成本 14
总成本：28
```

“只能合并相邻组”让每个中间结果始终对应原数组的一个连续区间，这正是区间 DP 的结构。

### 6.2 基线：枚举所有括号方案

可以递归枚举最后一次合并从哪里切开：

```text
solve(left, right)：
    如果区间只有一堆：返回 0
    answer = INF
    for split 从 left + 1 到 right - 1：
        answer = min(answer,
                     solve(left, split)
                     + solve(split, right)
                     + sum(left, right))
    返回 answer
```

不做记忆化时，同一区间会被不同括号方案反复求解，递归规模呈指数增长。

### 6.3 状态、转移与不变量

使用半开区间：

```text
dp[left][right] = 把原数组区间 [left, right) 合成一堆的最小成本
```

单堆不需要合并，所以 `dp[i][i+1] = 0`。

考虑 `[left, right)` 的**最后一次**操作。此前它一定已经变成相邻的两组 `[left, split)` 和 `[split, right)`；最后把两组合并，成本是整个区间重量。因此：

```text
dp[left][right] = min over split (
    dp[left][split] + dp[split][right] + range_sum(left, right))
```

外层按区间长度从小到大计算。不变量是：开始计算长度 `length` 时，所有更短非空区间的最优成本已经正确。

区间和用前缀和在 `O(1)` 得到，否则每次转移再扫描区间会多出一层成本。

### 6.4 伪代码

```text
prefix[0] = 0
for i 从 0 到 n - 1：
    prefix[i+1] = prefix[i] + weight[i]

for i 从 0 到 n - 1：
    dp[i][i+1] = 0

for length 从 2 到 n：
    for left 从 0 到 n - length：
        right = left + length
        total_weight = prefix[right] - prefix[left]
        dp[left][right] = INF

        for split 从 left + 1 到 right - 1：
            candidate = dp[left][split]
                      + dp[split][right]
                      + total_weight
            dp[left][right] = min(dp[left][right], candidate)

返回 dp[0][n]
```

### 6.5 为什么正确

对区间长度归纳。长度为 1 时没有操作，成本 0 正确。

对任意更长区间，任何合法完整方案都有唯一的最后一次合并；它把区间分成某个 `split` 两侧的连续子区间。根据归纳假设，算法已经知道两侧各自最小成本，再加最后合并的固定区间总重量，就得到这个切分下的最优方案。

算法枚举所有可能 `split` 并取最小，因此不会漏掉全局最优方案。反过来，每个候选都由两个合法子方案再做一次相邻合并构成，所以不会产生非法答案。

### 6.6 复杂度

- 区间数量：`O(n²)`；
- 每个区间枚举 `O(n)` 个切分点；
- 总时间：`O(n³)`；
- DP 与前缀和空间：`O(n²)`。

这是“真正的 `dp[left][right]` 区间 DP”：状态两端都是原序列边界，计算顺序由区间长度决定。

### 6.7 完整 C++20 实现

代码拒绝负重量，并对前缀和、转移加法和状态表维度做检查。前面 0/1 背包中对 `capacity + 1` 的检查保持不变；这里同样不能先溢出、再试图分配。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <limits>
#include <optional>
#include <stdexcept>
#include <vector>

std::optional<long long> try_nonnegative_add(long long lhs, long long rhs) {
    if (lhs < 0 || rhs < 0) {
        throw std::invalid_argument("expected non-negative values");
    }
    if (lhs > std::numeric_limits<long long>::max() - rhs) {
        return std::nullopt;
    }
    return lhs + rhs;
}

long long minimum_adjacent_merge_cost(
    const std::vector<long long>& weights) {
    const std::size_t size = weights.size();
    if (size <= 1) {
        if (size == 1 && weights[0] < 0) {
            throw std::invalid_argument("weights must be non-negative");
        }
        return 0;
    }
    if (size == std::numeric_limits<std::size_t>::max()) {
        throw std::length_error("too many piles");
    }

    std::vector<long long> prefix(size + 1, 0);
    for (std::size_t i = 0; i < size; ++i) {
        if (weights[i] < 0) {
            throw std::invalid_argument("weights must be non-negative");
        }
        const auto next_prefix = try_nonnegative_add(prefix[i], weights[i]);
        if (!next_prefix.has_value()) {
            throw std::overflow_error("total pile weight exceeds long long");
        }
        prefix[i + 1] = *next_prefix;
    }

    // nullopt 表示这个区间的最优成本超出 long long；它不会与合法的
    // LLONG_MAX 混用同一个哨兵。
    std::vector<std::vector<std::optional<long long>>> dp(
        size, std::vector<std::optional<long long>>(size + 1));
    for (std::size_t i = 0; i < size; ++i) {
        dp[i][i + 1] = 0;
    }

    for (std::size_t length = 2; length <= size; ++length) {
        for (std::size_t left = 0; left + length <= size; ++left) {
            const std::size_t right = left + length;
            const long long total_weight = prefix[right] - prefix[left];

            for (std::size_t split = left + 1; split < right; ++split) {
                if (!dp[left][split].has_value() ||
                    !dp[split][right].has_value()) {
                    continue;
                }
                const auto children = try_nonnegative_add(
                    *dp[left][split], *dp[split][right]);
                if (!children.has_value()) {
                    continue;
                }
                const auto candidate = try_nonnegative_add(
                    *children, total_weight);
                if (!candidate.has_value()) {
                    continue;  // 此切分溢出，其他切分仍可能可表示。
                }
                if (!dp[left][right].has_value() ||
                    *candidate < *dp[left][right]) {
                    dp[left][right] = *candidate;
                }
            }
        }
    }
    if (!dp[0][size].has_value()) {
        throw std::overflow_error("minimum merge cost exceeds long long");
    }
    return *dp[0][size];
}

template <class Exception>
bool merge_throws(const std::vector<long long>& weights) {
    try {
        static_cast<void>(minimum_adjacent_merge_cost(weights));
    } catch (const Exception&) {
        return true;
    }
    return false;
}

int main() {
    assert(minimum_adjacent_merge_cost({4, 3, 3, 4}) == 28);
    assert(minimum_adjacent_merge_cost({1, 2, 3}) == 9);
    assert(minimum_adjacent_merge_cost({5, 5}) == 10);
    assert(minimum_adjacent_merge_cost({7}) == 0);
    assert(minimum_adjacent_merge_cost({}) == 0);
    assert(minimum_adjacent_merge_cost({
        std::numeric_limits<long long>::max(), 0, 0}) ==
        std::numeric_limits<long long>::max());

    assert(merge_throws<std::invalid_argument>({1, -1, 2}));
    assert(merge_throws<std::overflow_error>({
        std::numeric_limits<long long>::max(), 1}));
}
```

一个切分点溢出时，代码只跳过这个候选，因为其他切分仍可能得到可表示的最优值。`optional` 独立表示“这个区间的最优成本不可表示”，所以合法答案 `LLONG_MAX` 不会与哨兵混淆。只有最终区间的所有切分都不可表示时，函数才报告溢出。

### 6.8 自测与边界

- 空数组、单堆、两堆；
- 所有重量为 0；
- 对称输入与明显不对称输入；
- 负重量的失败政策；
- 前缀和与总成本溢出；
- 用指数递归或记忆化版本对随机小 `n` 做差分测试；
- 若保存切分点，恢复出的每一步是否只合并相邻组，累计成本是否等于 DP 值。

### 6.9 常见追问

1. **怎样恢复具体合并顺序？** 每次改善 `dp[left][right]` 时保存最佳 `split`，再递归恢复左右子区间，最后输出当前区间的合并。
2. **为什么外层必须按长度递增？** 当前区间依赖两段严格更短的区间；长度顺序保证读取前已经算完。
3. **如果任意两堆都能合并呢？** 连续区间结构消失；若每次成本仍是两堆重量和，会转向 Huffman/最小堆式贪心问题。
4. **能否优化到 `O(n²)`？** 某些满足额外单调性或四边形不等式的区间 DP 可以优化，但必须证明条件，本题基础实现不能凭模板宣称。

## 7. 五道题放在一起比较

| 问题 | 状态核心 | 最容易错的地方 | 是否直接恢复答案 |
|---|---|---|---|
| 0/1 背包 | 前若干物品、容量 | 一维容量遍历方向 | 需额外父信息或二维表 |
| 最少硬币 | 恰好凑出金额 | 不可达不能初始化为 0 | 记录最后一枚硬币 |
| 网格路径 | 到达当前格的最优成本 | 转移前驱和边界 | 本章保存父指针恢复 |
| LIS | 各长度的最小结尾 | 严格/非严格与二分边界 | 需保存下标和前驱 |
| 相邻合并 | 连续区间合成一组的最小成本 | 区间长度顺序、最后切分点 | 保存最佳 `split` |

## 8. 变体练习

### 练习 1：分割等和子集

判断一组非负整数能否分成两个和相等的子集。

<details>
<summary>思路与答案</summary>

总和为奇数时直接失败；否则问题变为“每个数最多使用一次，能否恰好凑出 `sum/2`”。使用布尔 0/1 背包，`dp[0] = true`，容量倒序更新 `dp[c] = dp[c] || dp[c-value]`。倒序仍是为了避免同一元素重复使用。时间 `O(n × sum)`，空间 `O(sum)`。

</details>

### 练习 2：恢复最少硬币组合

在最少硬币母题中返回具体使用了哪些面额。

<details>
<summary>思路与答案</summary>

增加 `choice[x]`。当 `dp[x-coin] + 1` 严格改善 `dp[x]` 时，记录 `choice[x] = coin`。若目标可达，从 `amount` 开始反复输出 `choice[current]` 并减去该面额，直到 0。并列最优时要定义稳定规则，例如偏好较小面额。

</details>

### 练习 3：带障碍的网格路径数量

网格中某些格子不可进入，求从左上到右下的路径数量。

<details>
<summary>思路与答案</summary>

定义 `dp[c]` 为当前扫描到的行中，到达该列的路径数。障碍格把 `dp[c]` 设为 0；普通格执行 `dp[c] += dp[c-1]`，分别代表从上方和左方到达。先处理起点是否为障碍，并考虑路径数溢出或取模要求。时间 `O(rows × cols)`、空间 `O(cols)`。

</details>

### 练习 4：最长递增子序列计数

不仅求 LIS 长度，还求达到最长长度的子序列数量。

<details>
<summary>思路与答案</summary>

使用 `O(n²)` DP：`length[i]` 表示以 `i` 结尾的最长长度，`count[i]` 表示达到该长度的方案数。遇到更长转移时覆盖长度和计数；遇到同长转移时累加计数。最终累加所有达到全局最长长度的位置。要明确按下标不同是否算不同序列，并处理计数溢出。

</details>

## 9. 面试复述清单

- 你的 `dp` 状态表示“恰好”还是“至多”？
- 哪些状态不可达，哨兵参与运算前是否检查？
- 0/1 背包一维压缩为什么倒序，完全背包为什么常顺序？
- 只保留最优值后，恢复具体方案还缺什么信息？
- LIS 的 `tails` 为什么保持有序，它为什么不一定是一条真实 LIS？
- 区间 DP 为什么按长度计算，最后一次操作怎样导出切分转移？
- 能否保留小规模暴力或二次算法作为随机对拍 oracle？

能用自己的话回答这些问题，比记住四段循环更重要。

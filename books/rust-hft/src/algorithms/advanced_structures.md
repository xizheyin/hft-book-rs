# 进阶数据结构与图算法

本章讲坐标压缩、Fenwick Tree（树状数组）、Segment Tree（线段树）、最小生成树、强连通分量和含负边的最短路。它们解决动态区间查询、网络连接和更复杂路径约束；共同难点是适用前提比基础结构更容易被忽略。

这里的“高级”不表示代码一定很长，而是使用前提更容易被忽略：

- 坐标压缩通常需要提前看见全部键，是离线方法；
- Fenwick Tree 很轻量，但只适合能通过前缀结果组合的操作；
- Segment Tree 更通用，也带来更多内存和实现复杂度；
- MST、最短路和 SCC 回答的是不同问题，不能看到“图”就互换算法；
- Dijkstra 遇到负边会失去正确性，不能靠加一个 `visited` 修复。

`MST` 是最小生成树，目标是以最小总边权连接全部点；`SCC` 是强连通分量，指有向图中彼此都可到达的一组点；`Fenwick Tree` 也叫树状数组，用紧凑数组维护可组合的前缀结果。先懂它们解决什么问题，再决定是否学习实现。

## 1. 母题一：坐标压缩

### 1.1 白话题意

给定一组可能很大、很稀疏、含重复的整数键，把每个键映射为从 `0` 开始的稠密排名，同时保持：

- 相等原值映射到相同排名；
- `x < y` 时，`rank(x) < rank(y)`；
- 排名中间没有空洞。

```text
输入：[10000, -5, 10000, 42]
有序不同值：[-5, 42, 10000]
排名：[2, 0, 2, 1]
```

压缩只保留相等关系和大小顺序，不保留数值距离。`100` 与 `101` 相邻、`100` 与 `1000000` 也可能映射为相邻排名。

### 1.2 基线方法

对每个值，扫描全部输入，收集所有比它小的不同值，再计数。直接实现容易达到 `O(n²)`，还要反复处理重复值。

也可以把键范围大小为 `M` 的数组直接开出来，但键可能为负或接近十亿，空间 `O(M)` 往往不可接受。

### 1.3 关键观察与不变量

复制输入，排序并去重，得到字典 `dictionary`。一个值在字典中的下标就是它的排名。

不变量是：

```text
dictionary 严格递增，且恰好包含输入中所有不同值。
```

因此可以用二分搜索 `lower_bound` 找每个值的位置。

### 1.4 伪代码

```text
dictionary = values 的副本
排序 dictionary
删除相邻重复值

ranks = 空列表
for value 遍历原输入：
    position = dictionary 中第一个不小于 value 的位置
    ranks 加入 position

返回 dictionary 和 ranks
```

保留字典很重要：它既能把原值编码成排名，也能通过 `dictionary[rank]` 解码。

### 1.5 为什么正确

排序去重后，字典包含每个不同输入值恰好一次，并严格递增。对输入值 `x`，`lower_bound(x)` 必然指向字典中唯一的 `x`。

若 `x < y`，严格递增字典中 `x` 的位置必然早于 `y`；相等值查到同一位置。字典下标从 `0` 连续到 `m-1`，所以排名没有空洞。

### 1.6 复杂度

- 排序：`O(n log n)`；
- 对每个输入二分：`O(n log n)`；
- 额外空间：`O(n)`。

若后续查询很多，可以再构建哈希映射，把已知值到排名的平均查询降为 `O(1)`；代价是额外内存和哈希最坏情况。

### 1.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <vector>

struct Compression {
    std::vector<long long> dictionary;
    std::vector<std::size_t> ranks;
};

Compression coordinate_compress(const std::vector<long long>& values) {
    Compression result;
    result.dictionary = values;
    std::sort(result.dictionary.begin(), result.dictionary.end());
    result.dictionary.erase(
        std::unique(result.dictionary.begin(), result.dictionary.end()),
        result.dictionary.end());

    result.ranks.reserve(values.size());
    for (long long value : values) {
        const auto position = std::lower_bound(
            result.dictionary.begin(), result.dictionary.end(), value);
        result.ranks.push_back(static_cast<std::size_t>(
            position - result.dictionary.begin()));
    }
    return result;
}

int main() {
    const std::vector<long long> values{10000, -5, 10000, 42};
    const Compression compressed = coordinate_compress(values);

    assert(compressed.dictionary ==
           std::vector<long long>({-5, 42, 10000}));
    assert(compressed.ranks == std::vector<std::size_t>({2, 0, 2, 1}));

    for (std::size_t i = 0; i < values.size(); ++i) {
        assert(compressed.dictionary[compressed.ranks[i]] == values[i]);
    }

    const Compression empty = coordinate_compress({});
    assert(empty.dictionary.empty());
    assert(empty.ranks.empty());

    const Compression equal = coordinate_compress({7, 7, 7});
    assert(equal.dictionary == std::vector<long long>({7}));
    assert(equal.ranks == std::vector<std::size_t>({0, 0, 0}));
}
```

### 1.8 测试时还要想什么

- 空输入、全部相等；
- 负数、零、很大的键；
- 原输入无序且有重复；
- 解码是否恢复原值；
- 任意 `x < y` 的排名是否也严格更小；
- 后续是否会出现字典中没有的新键。

### 1.9 常见追问

1. **新键持续在线到达怎么办？** 固定压缩排名可能整体变化；可使用有序树、分段映射、预留范围，或周期性重建，取决于业务语义。
2. **压缩后能做加减距离吗？** 不能。排名差表示中间有多少种已知键，不是原数值距离。
3. **为什么常与 Fenwick Tree 配合？** Fenwick 需要稠密整数下标；压缩把稀疏有序键转换成这样的下标。
4. **只需判断相等还要排序吗？** 不一定，哈希编号也能给相等值相同 ID；只有需要保序时才必须建立有序排名。

## 2. 母题二：Fenwick Tree 的单点增加与区间和

Fenwick Tree 也称 Binary Indexed Tree（BIT）。名称中的 `bit` 来自下标二进制分块，不表示它只能存布尔值。

### 2.1 白话题意

维护一个整数数组，支持两种操作：

1. `add(index, delta)`：某个位置增加 `delta`；
2. `range_sum(left, right)`：查询半开区间 `[left, right)` 的和。

要求两种操作都比线性扫描快。

### 2.2 基线方法

- 只存原数组：单点更新 `O(1)`，区间求和 `O(n)`；
- 存普通前缀和：区间查询 `O(1)`，但一个位置改变后，后面所有前缀都可能更新，成本 `O(n)`。

Fenwick Tree 在两者之间取得平衡，让更新和查询都是 `O(log n)`。

### 2.3 关键观察与不变量

内部使用从 `1` 开始的下标。定义：

```text
lowbit(i) = i 的二进制表示中最低位的 1 所代表的值
tree[i] = 原数组区间 (i - lowbit(i), i] 的和
```

例如 `i = 12` 的二进制是 `1100`，`lowbit(12) = 4`，所以 `tree[12]` 覆盖 1-based 下标 `9..12`。

不变量是：每个 `tree[i]` 始终等于它所负责区间的和。单点更新沿 `i += lowbit(i)` 访问所有包含该点的块；前缀查询沿 `i -= lowbit(i)` 把前缀拆成互不重叠的块。

### 2.4 伪代码

```text
add(index, delta)：
    i = index + 1
    while i <= n：
        tree[i] += delta
        i += lowbit(i)

prefix_sum(end)：                 // [0, end)
    result = 0
    i = end
    while i > 0：
        result += tree[i]
        i -= lowbit(i)
    返回 result

range_sum(left, right)：
    返回 prefix_sum(right) - prefix_sum(left)
```

### 2.5 为什么正确

更新时，`index + 1` 是包含该元素的最小 Fenwick 块；每次加上 `lowbit(i)` 都跳到下一个同样包含该点的父块。其他块不包含该位置，无需改变，所以区间和不变量保持。

查询时，`tree[i]` 恰好覆盖以 `i` 结尾、长度为 `lowbit(i)` 的后缀块。减去 `lowbit(i)` 后继续查询剩余前缀。这些块互不重叠且并集正好是 `[0, end)`，所以相加得到正确前缀和。两个前缀相减得到 `[left, right)`。

### 2.6 复杂度

- 单点增加：`O(log n)`；
- 前缀和、区间和：`O(log n)`；
- 额外空间：`O(n)`；
- 本章构造函数逐点加入，构建时间 `O(n log n)`；还存在 `O(n)` 构建方法。

### 2.7 完整 C++20 实现

公开接口使用 0-based 下标，只有内部转换为 1-based。

```cpp
#include <cassert>
#include <cstddef>
#include <optional>
#include <vector>

class FenwickTree {
public:
    explicit FenwickTree(const std::vector<long long>& values)
        : tree_(values.size() + 1, 0) {
        for (std::size_t i = 0; i < values.size(); ++i) {
            static_cast<void>(add(i, values[i]));
        }
    }

    [[nodiscard]] std::size_t size() const {
        return tree_.size() - 1;
    }

    bool add(std::size_t index, long long delta) {
        if (index >= size()) {
            return false;
        }
        for (std::size_t i = index + 1; i < tree_.size(); i += lowbit(i)) {
            tree_[i] += delta;
        }
        return true;
    }

    [[nodiscard]] std::optional<long long> range_sum(
        std::size_t left,
        std::size_t right) const {
        if (left > right || right > size()) {
            return std::nullopt;
        }
        return prefix_sum(right) - prefix_sum(left);
    }

private:
    static std::size_t lowbit(std::size_t value) {
        return value & (~value + 1);
    }

    [[nodiscard]] long long prefix_sum(std::size_t end) const {
        long long result = 0;
        for (std::size_t i = end; i > 0; i -= lowbit(i)) {
            result += tree_[i];
        }
        return result;
    }

    std::vector<long long> tree_;
};

int main() {
    FenwickTree tree({5, 1, 4, 2});
    assert(tree.range_sum(0, 4).value() == 12);
    assert(tree.range_sum(1, 3).value() == 5);
    assert(tree.range_sum(2, 2).value() == 0);

    assert(tree.add(1, 10));
    assert(tree.range_sum(0, 2).value() == 16);
    assert(tree.range_sum(1, 4).value() == 17);
    assert(!tree.add(4, 1));
    assert(!tree.range_sum(3, 2).has_value());
    assert(!tree.range_sum(0, 5).has_value());

    FenwickTree empty({});
    assert(empty.range_sum(0, 0).value() == 0);
    assert(!empty.add(0, 1));
}
```

这里假设所有累计结果都能放进 `long long`。若输入来自不可信来源，需要定义溢出检查或更宽表示，而不是让有符号溢出变成未定义行为。

### 2.8 测试时还要想什么

- 空数组、单元素；
- 空区间和整个数组；
- 第一位、最后一位更新；
- 正负 `delta`；
- `left > right`、越界更新和查询；
- 与朴素数组在随机操作序列上对拍；
- 累加是否可能溢出。

### 2.9 常见追问

1. **能做区间最小值吗？** 一般不能像区间和那样用两个前缀相减；普通 Fenwick 依赖操作可组合且能消去前缀，范围最小值更适合线段树等结构。
2. **怎样支持区间增加、单点查询？** 在差分数组上使用 Fenwick；区间 `[l,r)` 增加可转成 `add(l, delta)` 与 `add(r, -delta)`。
3. **怎样支持区间增加、区间和？** 常用两个 Fenwick Tree 组合，推导前缀和公式；不要只复制公式而不验证端点。
4. **怎样统计逆序对？** 坐标压缩后从右向左扫描，用 Fenwick 查询更小排名的已见数量，再更新当前排名。

## 3. 母题三：Segment Tree 的单点赋值与区间最小值

Segment Tree（线段树）把数组递归分成区间。每个节点保存一个区间的聚合结果。本节用区间最小值说明它比 Fenwick 更通用的地方。

### 3.1 白话题意

维护整数数组，支持：

1. `assign(index, value)`：把某位置改成新值；
2. `range_min(left, right)`：查询非空半开区间 `[left, right)` 的最小值。

### 3.2 基线方法

直接数组赋值为 `O(1)`，但每次区间最小值要扫描 `O(n)`。如果保存所有区间答案，空间和更新成本又会非常大。

线段树只保存约 `O(n)` 个层次化区间；一次更新或查询只接触每层少数节点。

### 3.3 关键观察与不变量

把叶子放在大小为 2 的幂的底层数组中，父节点保存两个子节点的最小值：

```text
tree[node] = min(tree[2*node], tree[2*node+1])
```

不变量是：**每个节点的值都等于它所代表数组区间的最小值。**

点更新先改叶子，再一路重算祖先。区间查询把目标 `[left, right)` 拆成若干互不重叠的树节点区间，并对它们取最小值。

### 3.4 伪代码

```text
assign(index, value)：
    p = index 对应叶子
    tree[p] = value
    while p 不是根：
        p = p / 2
        tree[p] = min(tree[2*p], tree[2*p+1])

range_min(left, right)：
    left  移到叶子层
    right 移到叶子层
    answer = INF

    while left < right：
        如果 left 是右孩子：纳入 tree[left]，left += 1
        如果 right 是右边界：right -= 1，纳入 tree[right]
        left /= 2
        right /= 2

    返回 answer
```

### 3.5 为什么正确

构建时，叶子等于原元素，内部节点由两个正确子区间合并，因此节点不变量自底向上成立。

单点赋值只影响包含该位置的祖先区间；逐层重算这些祖先后，所有受影响节点恢复正确，其他节点无需改变。

查询过程中，被纳入答案的节点区间互不重叠；移动左右边界并上升一层后，它们与尚未处理部分一起始终精确覆盖原查询区间。最终边界相遇，所有部分都已纳入，因此返回整个区间最小值。

### 3.6 复杂度

- 构建：`O(n)`；
- 单点赋值：`O(log n)`；
- 区间最小值：`O(log n)`；
- 空间：`O(n)`，本实现底层容量取下一个 2 的幂，数组长度小于 `4n`。

### 3.7 完整 C++20 实现

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <limits>
#include <optional>
#include <vector>

class RangeMinimumTree {
public:
    explicit RangeMinimumTree(const std::vector<long long>& values)
        : size_(values.size()), base_(1) {
        while (base_ < size_) {
            base_ *= 2;
        }

        tree_.assign(base_ * 2, infinity());
        for (std::size_t i = 0; i < size_; ++i) {
            tree_[base_ + i] = values[i];
        }
        for (std::size_t node = base_; node-- > 1;) {
            tree_[node] = std::min(tree_[node * 2], tree_[node * 2 + 1]);
        }
    }

    bool assign(std::size_t index, long long value) {
        if (index >= size_) {
            return false;
        }

        std::size_t node = base_ + index;
        tree_[node] = value;
        while (node > 1) {
            node /= 2;
            tree_[node] = std::min(tree_[node * 2], tree_[node * 2 + 1]);
        }
        return true;
    }

    [[nodiscard]] std::optional<long long> range_min(
        std::size_t left,
        std::size_t right) const {
        if (left >= right || right > size_) {
            return std::nullopt;
        }

        left += base_;
        right += base_;
        long long answer = infinity();

        while (left < right) {
            if ((left & 1U) != 0U) {
                answer = std::min(answer, tree_[left]);
                ++left;
            }
            if ((right & 1U) != 0U) {
                --right;
                answer = std::min(answer, tree_[right]);
            }
            left /= 2;
            right /= 2;
        }
        return answer;
    }

private:
    static constexpr long long infinity() {
        return std::numeric_limits<long long>::max();
    }

    std::size_t size_;
    std::size_t base_;
    std::vector<long long> tree_;
};

int main() {
    RangeMinimumTree tree({5, 1, 4, 2, 9});
    assert(tree.range_min(0, 5).value() == 1);
    assert(tree.range_min(2, 5).value() == 2);
    assert(tree.range_min(4, 5).value() == 9);

    assert(tree.assign(1, 8));
    assert(tree.range_min(0, 5).value() == 2);
    assert(tree.assign(3, -7));
    assert(tree.range_min(1, 4).value() == -7);

    assert(!tree.assign(5, 0));
    assert(!tree.range_min(2, 2).has_value());
    assert(!tree.range_min(0, 6).has_value());

    RangeMinimumTree empty({});
    assert(!empty.range_min(0, 0).has_value());
    assert(!empty.assign(0, 1));
}
```

### 3.8 测试时还要想什么

- 空数组和单元素；
- 查询完整范围、单元素范围、非法空范围；
- 更新最小值所在位置；
- 数组长度不是 2 的幂；
- 重复最小值和负数；
- 与朴素扫描在随机更新/查询序列上对拍。

### 3.9 常见追问

1. **为什么范围最小值适合线段树？** `min` 可以从左右子区间合并，但不能像和那样通过两个前缀相减。
2. **怎样支持区间整体增加？** 使用 lazy propagation，把尚未下推的区间更新标记保存在节点；实现和测试复杂度明显增加。
3. **Fenwick 和线段树怎么选？** 前缀和与单点增量优先考虑更简单的 Fenwick；需要多种区间操作、最小/最大或 lazy 更新时再考虑线段树。
4. **必须把容量补到 2 的幂吗？** 不必须；这是让迭代实现和节点区间更容易推理的一种布局。

## 4. 最小生成树：Kruskal 与问题边界

### 4.1 白话题意

给定一个带权**无向图**，希望选择一些边，把所有顶点连通，同时总边权最小。这样的边集称为最小生成树（Minimum Spanning Tree，MST）。若图不连通，只能得到最小生成森林。

MST 不是“从某个起点到其他点的最短路径树”。它最小化整棵连接网络的总成本，不保证任意两点间路径最短。

### 4.2 基线方法

可以枚举所有包含 `V-1` 条边的子集，检查是否连通且无环，再取最小总权重。组合数量很快爆炸，无法用于一般规模。

### 4.3 关键观察与不变量

Kruskal 从权重最小的边开始考虑，只在连接两个不同连通分量时选择它。DSU（Disjoint Set Union，并查集）用于快速判断两个端点是否已经连通。

不变量是：

1. 已选边始终无环；
2. 已选边可以扩展成某棵最小生成树。

### 4.4 严格伪代码

```text
KRUSKAL(vertices, edges)：
    按 (weight, stable_edge_id) 升序排序 edges
    dsu = 每个顶点各自一个集合
    chosen = 空列表
    total = 0

    for edge(u, v, weight) 遍历排序后的 edges：
        如果 dsu.find(u) != dsu.find(v)：
            dsu.union(u, v)
            chosen 加入 edge
            total += weight
            如果 chosen.size == vertices - 1：
                break

    如果 vertices > 0 且 chosen.size != vertices - 1：
        返回“图不连通”，以及按需返回最小生成森林
    返回 (total, chosen)
```

### 4.5 为什么正确

当算法选择连接两个分量的当前最轻边时，这两个分量形成一个割。根据割性质，跨越该割的最轻边可以出现在某棵 MST 中；若现有 MST 使用另一条跨割边，可以用当前边替换而不增加总权重。

并查集只允许连接不同分量，因此不会形成环。反复应用交换论证后，不变量保持；选满 `V-1` 条边时得到连通无环的生成树，且总权重最小。

### 4.6 复杂度与测试边界

- 排序：`O(E log E)`；
- 并查集配合路径压缩与按秩合并，总成本近似线性；
- 总时间由排序主导。

应测试单顶点、平行边、自环、相同权重、负权边和不连通图。负权边对 MST 没有问题；它与 Dijkstra 的负边限制是两回事。

### 4.7 完整 C++20 实现

接口对连通图返回 MST；不连通图返回空结果。空图和单顶点图的成本定义为 0。自环会被并查集自然跳过，平行边按权重竞争。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <limits>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

struct Edge {
    std::size_t from;
    std::size_t to;
    long long weight;
};

struct MstResult {
    long long total_weight{};
    std::vector<Edge> edges;
};

class DisjointSet {
public:
    explicit DisjointSet(std::size_t size)
        : parent_(size), rank_(size, 0) {
        for (std::size_t i = 0; i < size; ++i) {
            parent_[i] = i;
        }
    }

    std::size_t find(std::size_t value) {
        if (parent_[value] != value) {
            parent_[value] = find(parent_[value]);
        }
        return parent_[value];
    }

    bool unite(std::size_t first, std::size_t second) {
        first = find(first);
        second = find(second);
        if (first == second) {
            return false;
        }
        if (rank_[first] < rank_[second]) {
            std::swap(first, second);
        }
        parent_[second] = first;
        if (rank_[first] == rank_[second]) {
            ++rank_[first];
        }
        return true;
    }

private:
    std::vector<std::size_t> parent_;
    std::vector<unsigned char> rank_;
};

long long checked_weight_add(long long lhs, long long rhs) {
    const long long min = std::numeric_limits<long long>::min();
    const long long max = std::numeric_limits<long long>::max();
    if ((rhs > 0 && lhs > max - rhs) ||
        (rhs < 0 && lhs < min - rhs)) {
        throw std::overflow_error("MST total weight exceeds long long");
    }
    return lhs + rhs;
}

long long sum_selected_weights(const std::vector<Edge>& edges) {
    std::vector<long long> non_negative;
    std::vector<long long> negative;
    non_negative.reserve(edges.size());
    negative.reserve(edges.size());
    for (const Edge& edge : edges) {
        if (edge.weight >= 0) {
            non_negative.push_back(edge.weight);
        } else {
            negative.push_back(edge.weight);
        }
    }

    // 当前和非负时优先加负数，当前和为负时优先加非负数。
    // 异号相加的结果位于两个操作数之间，不会溢出。某一侧用完后，
    // 剩余同号项让部分和单调走向最终和；此时 checked add 的失败
    // 恰好表示最终数学总和也超出 long long。
    long long total = 0;
    std::size_t positive_index = 0;
    std::size_t negative_index = 0;
    while (positive_index < non_negative.size() &&
           negative_index < negative.size()) {
        if (total >= 0) {
            total = checked_weight_add(total, negative[negative_index++]);
        } else {
            total = checked_weight_add(total, non_negative[positive_index++]);
        }
    }
    while (positive_index < non_negative.size()) {
        total = checked_weight_add(total, non_negative[positive_index++]);
    }
    while (negative_index < negative.size()) {
        total = checked_weight_add(total, negative[negative_index++]);
    }
    return total;
}

std::optional<MstResult> kruskal_mst(
    std::size_t vertex_count,
    std::vector<Edge> edges) {
    for (const Edge& edge : edges) {
        if (edge.from >= vertex_count || edge.to >= vertex_count) {
            throw std::invalid_argument("edge endpoint is out of range");
        }
    }
    if (vertex_count == 0) {
        return MstResult{};
    }

    std::sort(edges.begin(), edges.end(),
              [](const Edge& lhs, const Edge& rhs) {
                  if (lhs.weight != rhs.weight) {
                      return lhs.weight < rhs.weight;
                  }
                  if (lhs.from != rhs.from) {
                      return lhs.from < rhs.from;
                  }
                  return lhs.to < rhs.to;
              });

    DisjointSet sets(vertex_count);
    MstResult result;
    result.edges.reserve(vertex_count - 1);

    for (const Edge& edge : edges) {
        if (!sets.unite(edge.from, edge.to)) {
            continue;
        }
        result.edges.push_back(edge);
        if (result.edges.size() == vertex_count - 1) {
            result.total_weight = sum_selected_weights(result.edges);
            return result;
        }
    }

    if (vertex_count == 1) {
        return result;
    }
    return std::nullopt;
}

int main() {
    const auto mst = kruskal_mst(4, {
        {0, 1, 4},
        {0, 1, 1},   // 平行边中选择更轻者。
        {1, 2, -2},  // MST 允许负边。
        {2, 3, 3},
        {0, 3, 10},
        {2, 2, -100} // 自环不能连接两个分量。
    });
    assert(mst.has_value());
    assert(mst->total_weight == 2);
    assert(mst->edges.size() == 3);

    assert(!kruskal_mst(3, {{0, 1, 5}}).has_value());
    assert(kruskal_mst(1, {}).value().total_weight == 0);
    assert(kruskal_mst(0, {}).value().edges.empty());

    // 选边顺序中前两项会下溢，但最终数学总和 -2 可以表示。
    const auto cancellation = kruskal_mst(4, {
        {0, 1, std::numeric_limits<long long>::min()},
        {1, 2, -1},
        {2, 3, std::numeric_limits<long long>::max()}});
    assert(cancellation.has_value());
    assert(cancellation->total_weight == -2);

    bool invalid_endpoint = false;
    try {
        static_cast<void>(kruskal_mst(2, {{0, 2, 1}}));
    } catch (const std::invalid_argument&) {
        invalid_endpoint = true;
    }
    assert(invalid_endpoint);

    bool overflow = false;
    try {
        static_cast<void>(kruskal_mst(3, {
            {0, 1, std::numeric_limits<long long>::max()},
            {1, 2, std::numeric_limits<long long>::max()}}));
    } catch (const std::overflow_error&) {
        overflow = true;
    }
    assert(overflow);

    bool underflow = false;
    try {
        static_cast<void>(kruskal_mst(3, {
            {0, 1, std::numeric_limits<long long>::min()},
            {1, 2, -1}}));
    } catch (const std::overflow_error&) {
        underflow = true;
    }
    assert(underflow);
}
```

### 4.8 自测与边界

- 空图、单顶点、已经是一棵树；
- 不连通图返回空结果；
- 平行边、自环、相同权重与负权边；
- 非法顶点编号；
- 选中边数应为 `V-1`，且重新用 DSU 检查无环和连通；
- 小图可枚举全部生成树，与 Kruskal 做随机差分测试；
- 总权重的正向和负向溢出。

### 4.9 什么时候考虑 Prim

Prim 从一个连通集合向外扩张，适合直接使用邻接结构和优先队列；稠密图还可使用不同实现。Kruskal 常适合边列表和并查集。选择应看输入表示、图密度和是否本来就要处理连通分量，而不是背“谁更快”。

## 5. 强连通分量：Kosaraju 与有向图压缩

### 5.1 白话题意

在有向图中，如果顶点 `u` 能到 `v`，同时 `v` 也能到 `u`，它们属于同一个强连通分量（Strongly Connected Component，SCC）。把每个 SCC 缩成一个点后，得到的凝聚图一定是 DAG。

SCC 不是无向图连通分量；只从一边可达不够。

### 5.2 基线方法

从每个顶点分别做一次 DFS/BFS，得到任意两点的可达性，再按互相可达分组。时间可能达到 `O(V(V+E))`，也保存了远多于所需的信息。

### 5.3 关键观察与不变量

Kosaraju 做两轮 DFS：

1. 在原图上 DFS，按退出时间记录顶点；
2. 把所有边反向，按退出时间从晚到早启动 DFS；每次搜索得到一个 SCC。

凝聚图是 DAG。对本节“第一轮走原图、第二轮走转置图”的版本，逆退出序下一项属于**原凝聚 DAG 当前的源分量**；边反向后，它就是**转置凝聚 DAG 当前的汇分量**。因此第二轮从它出发，不能沿转置边跑进另一个尚未处理的分量，却仍能遍历本 SCC 内全部顶点。

### 5.4 严格伪代码

```text
KOSARAJU(graph)：
    visited = 全 false
    finish_order = 空列表

    DFS1(u)：
        visited[u] = true
        for v in graph[u]：
            如果未访问 v：DFS1(v)
        finish_order 加入 u

    对每个顶点 u：
        如果未访问 u：DFS1(u)

    reversed = graph 的所有边反向
    visited = 全 false
    components = 空列表

    按 finish_order 的逆序遍历 u：
        如果未访问 u：
            component = 空列表
            在 reversed 上 DFS2(u)，把到达顶点加入 component
            components 加入 component

    返回 components
```

### 5.5 为什么正确

一个 SCC 内任意两点互相可达，反转全部边后仍互相可达，所以第二轮不会拆散一个 SCC。

把 SCC 缩点后得到 DAG。第一轮退出顺序保证第二轮按逆序选择的起点位于原凝聚图当前的源分量；在转置图中它是汇分量，没有指向其他未处理 SCC 的出边。因此搜索不会合并两个不同 SCC。每个顶点只会归入一次，最终分组恰好是全部 SCC。

### 5.6 复杂度与测试边界

- 两轮 DFS 加建反图：时间 `O(V + E)`；
- 邻接表、反图、访问和顺序：空间 `O(V + E)`。

应测试孤立点、单向链、完整环、多个 SCC 之间单向连接、自环和平行边。递归 DFS 在很深图上可能耗尽调用栈，生产实现可改为显式栈。

### 5.7 完整 C++20 实现

图用邻接表表示。实现返回 SCC 列表；分量之间以及分量内部的输出顺序不是接口语义，测试会先规范化再比较集合。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <stdexcept>
#include <vector>

using Graph = std::vector<std::vector<std::size_t>>;

void validate_graph(const Graph& graph) {
    for (const auto& neighbors : graph) {
        for (std::size_t vertex : neighbors) {
            if (vertex >= graph.size()) {
                throw std::invalid_argument("edge endpoint is out of range");
            }
        }
    }
}

void dfs_finish(const Graph& graph,
                std::size_t vertex,
                std::vector<bool>& visited,
                std::vector<std::size_t>& finish_order) {
    visited[vertex] = true;
    for (std::size_t next : graph[vertex]) {
        if (!visited[next]) {
            dfs_finish(graph, next, visited, finish_order);
        }
    }
    finish_order.push_back(vertex);
}

void dfs_collect(const Graph& graph,
                 std::size_t vertex,
                 std::vector<bool>& visited,
                 std::vector<std::size_t>& component) {
    visited[vertex] = true;
    component.push_back(vertex);
    for (std::size_t next : graph[vertex]) {
        if (!visited[next]) {
            dfs_collect(graph, next, visited, component);
        }
    }
}

std::vector<std::vector<std::size_t>> kosaraju_scc(const Graph& graph) {
    validate_graph(graph);
    std::vector<bool> visited(graph.size(), false);
    std::vector<std::size_t> finish_order;
    finish_order.reserve(graph.size());

    for (std::size_t vertex = 0; vertex < graph.size(); ++vertex) {
        if (!visited[vertex]) {
            dfs_finish(graph, vertex, visited, finish_order);
        }
    }

    Graph transposed(graph.size());
    for (std::size_t from = 0; from < graph.size(); ++from) {
        for (std::size_t to : graph[from]) {
            transposed[to].push_back(from);
        }
    }

    std::fill(visited.begin(), visited.end(), false);
    std::vector<std::vector<std::size_t>> components;
    for (auto it = finish_order.rbegin(); it != finish_order.rend(); ++it) {
        if (visited[*it]) {
            continue;
        }
        components.emplace_back();
        dfs_collect(transposed, *it, visited, components.back());
    }
    return components;
}

std::vector<std::vector<std::size_t>> normalized(
    std::vector<std::vector<std::size_t>> components) {
    for (auto& component : components) {
        std::sort(component.begin(), component.end());
    }
    std::sort(components.begin(), components.end());
    return components;
}

int main() {
    // SCC 为 {0,1} -> {2,3} -> {4}。
    const Graph graph{
        {1},       // 0 -> 1
        {0, 2},    // 1 -> 0,2
        {3},       // 2 -> 3
        {2, 4},    // 3 -> 2,4
        {4},       // 自环
        {}         // 孤立点 5
    };
    assert(normalized(kosaraju_scc(graph)) ==
           std::vector<std::vector<std::size_t>>({
               {0, 1}, {2, 3}, {4}, {5}}));

    assert(kosaraju_scc({}).empty());
    assert(normalized(kosaraju_scc({{1}, {2}, {0}})) ==
           std::vector<std::vector<std::size_t>>({{0, 1, 2}}));
    assert(normalized(kosaraju_scc({{}, {}, {}})) ==
           std::vector<std::vector<std::size_t>>({{0}, {1}, {2}}));

    bool rejected = false;
    try {
        static_cast<void>(kosaraju_scc({{1}, {2}}));
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);
}
```

### 5.8 自测与边界

- 空图、孤立点、自环；
- 一条有向链与一个完整大环；
- 多个 SCC 之间形成单向 DAG；
- 平行边和非法顶点编号；
- 每个顶点恰好出现在一个返回分量；
- 同一分量内任意两点互相可达，不同分量不能互相可达；
- 很深的链应使用显式栈版本做压力测试，避免递归栈溢出。

### 5.9 Tarjan 的位置

Tarjan 算法只需一轮 DFS 且不需要显式转置图，但 `discovery/low-link/on-stack` 不变量更精细。两者复杂度同为 `O(V+E)`，应根据自己能否可靠维护状态以及现有图表示选择。

## 6. 负边最短路：先选算法，再写代码

### 6.1 选择边界

| 图的条件 | 常见选择 | 关键限制 |
|---|---|---|
| 无权图或所有边同成本 | BFS | 按层扩张 |
| 边权全部非负，单源 | Dijkstra | 任何可达负边都会破坏贪心定点依据 |
| DAG，可含负边 | 拓扑序 DP | 必须确实无环 |
| 一般图，可含负边，单源 | Bellman-Ford | `O(VE)`，可检测源可达负环 |
| 小规模图的全源最短路 | Floyd-Warshall | `O(V³)` 时间、`O(V²)` 空间 |

Dijkstra 的核心不变量是“取出的最小暂定距离以后不会再被改善”，它依赖边权非负。出现负边时，这个证明失效；某些测试碰巧通过不代表算法正确。

### 6.2 Bellman-Ford 的白话思路与基线

枚举所有可能路径会遇到环，路径数量无限。若不存在从源点可达的负环，最短路径可以取为简单路径，最多使用 `V-1` 条边。

Bellman-Ford 重复放松所有边。为得到最清楚的不变量，下面伪代码每轮从上一轮距离复制到 `next`：

```text
dist[source] = 0
其他 dist = INF

重复最多 V - 1 轮：
    next = dist
    changed = false
    for 每条有向边 (u, v, weight)：
        如果 dist[u] 可达 且 dist[u] + weight < next[v]：
            next[v] = dist[u] + weight
            changed = true
    dist = next
    如果没有变化：提前结束

for 每条边 (u, v, weight)：
    如果 dist[u] 可达 且 dist[u] + weight < dist[v]：
        报告存在从 source 可达、还能继续降低距离的负环影响

返回 dist
```

进行完第 `i` 轮后，`dist[v]` 等于从源点到 `v`、最多使用 `i` 条边的最短距离。证明对轮数归纳：一条至多 `i` 边的路径要么本来至多 `i-1` 边，要么最后一条边 `(u,v)` 前是至多 `i-1` 边的最短前缀；一轮枚举覆盖这两类。

没有负环时，最短简单路径至多 `V-1` 条边，所以这些轮次足够。再做一轮仍能改善，说明存在可达的负权循环能让某些距离继续下降。

时间复杂度 `O(VE)`，使用两个距离数组的空间为 `O(V)`。实现时必须先检查 `dist[u]` 可达，再做加法，并处理距离类型溢出。

### 6.3 负环结果意味着什么

检测到源可达负环，不表示图中每个顶点的最短距离都不存在。只有从源能到该负环、再从负环能到达的顶点会受到“可以无限降低”影响。若题目要求逐顶点标记，还要从可继续放松的顶点沿图传播影响。

### 6.4 完整 C++20 实现

返回值分别保存暂定距离和“受源可达负环影响”标记。对标记为真的顶点，有限 `distance` 已没有最短路含义，调用方必须忽略它。接口约定所有从源点实际尝试的路径加法都必须能放入 `long long`，否则抛出溢出错误。

```cpp
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <limits>
#include <optional>
#include <queue>
#include <stdexcept>
#include <utility>
#include <vector>

struct DirectedEdge {
    std::size_t from;
    std::size_t to;
    long long weight;
};

struct BellmanFordResult {
    std::vector<std::optional<long long>> distance;
    std::vector<bool> negative_cycle_affected;
};

long long checked_distance_add(long long lhs, long long rhs) {
    const long long min = std::numeric_limits<long long>::min();
    const long long max = std::numeric_limits<long long>::max();
    if ((rhs > 0 && lhs > max - rhs) ||
        (rhs < 0 && lhs < min - rhs)) {
        throw std::overflow_error("path distance exceeds long long");
    }
    return lhs + rhs;
}

BellmanFordResult bellman_ford(
    std::size_t vertex_count,
    const std::vector<DirectedEdge>& edges,
    std::size_t source) {
    if (source >= vertex_count) {
        throw std::invalid_argument("source is out of range");
    }
    std::vector<std::vector<std::size_t>> adjacency(vertex_count);
    for (const DirectedEdge& edge : edges) {
        if (edge.from >= vertex_count || edge.to >= vertex_count) {
            throw std::invalid_argument("edge endpoint is out of range");
        }
        adjacency[edge.from].push_back(edge.to);
    }

    std::vector<std::optional<long long>> distance(vertex_count);
    distance[source] = 0;

    // 使用上一轮的 distance 写入 next：第 i 轮后恰好覆盖至多 i 条边。
    for (std::size_t round = 1; round < vertex_count; ++round) {
        auto next = distance;
        bool changed = false;
        for (const DirectedEdge& edge : edges) {
            if (!distance[edge.from].has_value()) {
                continue;
            }
            const long long candidate = checked_distance_add(
                *distance[edge.from], edge.weight);
            if (!next[edge.to].has_value() || candidate < *next[edge.to]) {
                next[edge.to] = candidate;
                changed = true;
            }
        }
        distance = std::move(next);
        if (!changed) {
            break;
        }
    }

    std::vector<bool> affected(vertex_count, false);
    std::queue<std::size_t> pending;
    for (const DirectedEdge& edge : edges) {
        if (!distance[edge.from].has_value()) {
            continue;  // 源点不可达的负环不影响本次单源结果。
        }
        const long long candidate = checked_distance_add(
            *distance[edge.from], edge.weight);
        if ((!distance[edge.to].has_value() ||
             candidate < *distance[edge.to]) &&
            !affected[edge.to]) {
            affected[edge.to] = true;
            pending.push(edge.to);
        }
    }

    // 负环可以继续影响所有从种子顶点可达的下游顶点。
    while (!pending.empty()) {
        const std::size_t vertex = pending.front();
        pending.pop();
        for (std::size_t next : adjacency[vertex]) {
            if (!affected[next]) {
                affected[next] = true;
                pending.push(next);
            }
        }
    }
    return BellmanFordResult{std::move(distance), std::move(affected)};
}

int main() {
    const auto normal = bellman_ford(3, {
        {0, 1, 4}, {0, 2, 5}, {1, 2, -2}}, 0);
    assert(normal.distance[0] == 0);
    assert(normal.distance[1] == 4);
    assert(normal.distance[2] == 2);
    assert(std::none_of(normal.negative_cycle_affected.begin(),
                        normal.negative_cycle_affected.end(),
                        [](bool value) { return value; }));

    const auto negative_cycle = bellman_ford(5, {
        {0, 1, 1}, {1, 2, -2}, {2, 1, -2},
        {2, 3, 5}, {0, 4, 10}}, 0);
    assert(!negative_cycle.negative_cycle_affected[0]);
    assert(negative_cycle.negative_cycle_affected[1]);
    assert(negative_cycle.negative_cycle_affected[2]);
    assert(negative_cycle.negative_cycle_affected[3]);
    assert(!negative_cycle.negative_cycle_affected[4]);
    assert(negative_cycle.distance[4] == 10);

    // 顶点 3、4 的负环从源点 0 不可达，不应报告影响。
    const auto unreachable_cycle = bellman_ford(5, {
        {0, 1, 2}, {3, 4, -1}, {4, 3, -1}}, 0);
    assert(!unreachable_cycle.distance[3].has_value());
    assert(!unreachable_cycle.distance[4].has_value());
    assert(std::none_of(unreachable_cycle.negative_cycle_affected.begin(),
                        unreachable_cycle.negative_cycle_affected.end(),
                        [](bool value) { return value; }));

    bool overflow = false;
    try {
        static_cast<void>(bellman_ford(3, {
            {0, 1, std::numeric_limits<long long>::max()},
            {1, 2, 1}}, 0));
    } catch (const std::overflow_error&) {
        overflow = true;
    }
    assert(overflow);

    bool invalid_source = false;
    try {
        static_cast<void>(bellman_ford(0, {}, 0));
    } catch (const std::invalid_argument&) {
        invalid_source = true;
    }
    assert(invalid_source);

    bool invalid_endpoint = false;
    try {
        static_cast<void>(bellman_ford(2, {{0, 2, 1}}, 0));
    } catch (const std::invalid_argument&) {
        invalid_endpoint = true;
    }
    assert(invalid_endpoint);
}
```

### 6.5 自测与边界

- 只有源点、不可达顶点、平行边和自环；
- 有负边但没有负环；
- 源可达负环，以及从负环可达的下游顶点；
- 图中存在但从源不可达的负环；
- 非法源点和非法边端点；
- 距离正向/负向溢出；
- 无负边小图可与 Dijkstra 对拍，DAG 可与拓扑序 DP 对拍。

本例为了保持“第 `i` 轮最多 `i` 条边”的精确定义，每轮复制距离数组。常见原地放松实现可能在一轮沿边顺序传播多步，仍可正确求解，但不能再原封不动使用这个精确轮次等式作证明。

## 7. 结构与算法选择表

| 需求 | 候选 | 不应忽略的条件 |
|---|---|---|
| 稀疏有序键映射到数组下标 | 坐标压缩 | 是否能离线看见全部键 |
| 单点增量 + 前缀/区间和 | Fenwick Tree | 聚合能否由前缀组合/消去 |
| 点更新 + 区间最小/最大/和 | Segment Tree | 更高内存与实现成本 |
| 无向图最低总连接成本 | MST | 不是点对最短路径 |
| 有向图互相可达分组 | SCC | 与无向连通分量不同 |
| 非负边单源最短路 | Dijkstra | 不能含可达负边 |
| 一般负边单源最短路 | Bellman-Ford | 成本较高，要定义负环语义 |

## 8. 变体练习

### 练习 1：逆序对数量

给定数组，统计下标 `i < j` 且 `a[i] > a[j]` 的对数。

<details>
<summary>思路与答案</summary>

先保序坐标压缩。从右向左扫描，用 Fenwick 查询排名严格小于当前值的已见元素数量，再把当前排名计数加一。相等值不能计入，查询区间应为 `[0, rank)`。时间 `O(n log n)`、空间 `O(n)`；答案最多约为 `n(n-1)/2`，需要足够宽的整数。

</details>

### 练习 2：动态区间和该选哪个结构

需要单点赋值和区间和，Fenwick 与 Segment Tree 怎样选择？

<details>
<summary>思路与答案</summary>

Fenwick 的原生更新是增量。若要赋值，可额外保存当前数组，把 `new_value - old_value` 作为增量更新；它更短、更省内存。若未来还要区间最小值、复杂区间更新或多种聚合，可考虑 Segment Tree。先按真实操作集合选最简单结构。

</details>

### 练习 3：离散价格档位统计

已知当天所有可能价格，订单更新到来时要维护“价格不高于 `p` 的总数量”。

<details>
<summary>思路与答案</summary>

先把所有已知价格保序压缩，再用 Fenwick 在对应排名做数量增量。查询 `p` 时用 `upper_bound` 找到最后一个不大于 `p` 的排名边界，再做前缀和。若价格集合不能提前知道，这个离线方案需要改成有序树、分批重建或其他在线索引。

</details>

### 练习 4：MST 与最短路辨析

要铺设总成本最低的网络，使所有机房互通；又要保证总部到每个机房的路径最短。是否是同一个问题？

<details>
<summary>思路与答案</summary>

不是。前者是 MST，最小化所选网络边权总和；后者是单源最短路，分别最小化总部到各点的路径。MST 中的总部到某点路径可能不是原图最短路径。需求同时存在时要明确优先级或做带约束的网络设计，不能把一棵树同时宣布为两个问题的最优解。

</details>

### 练习 5：把 SCC 缩成 DAG

求出 SCC 后，怎样构造凝聚图，重复边怎么办？

<details>
<summary>思路与答案</summary>

先得到每个顶点的 `component_id`。遍历原图每条边 `(u,v)`；若两个 ID 不同，就添加分量边。可排序去重或用集合避免重复，选择取决于规模和是否要求稳定顺序。凝聚图必为 DAG，可以继续做拓扑排序和分量级 DP。

</details>

### 练习 6：有负边但图是 DAG

是否一定要使用 Bellman-Ford？

<details>
<summary>思路与答案</summary>

不一定。DAG 先做拓扑排序，再按拓扑序放松出边即可；每条边只处理一次，时间 `O(V+E)`，负边也不会形成环。只有确认图确实无环，这个选择才成立。

</details>

## 9. 面试复述清单

- 坐标压缩保留了什么，又丢失了什么？
- Fenwick 的 `tree[i]` 究竟覆盖哪个区间？
- 为什么区间和能由两个前缀相减，而区间最小值通常不能？
- Segment Tree 查询时被选节点为何恰好覆盖原区间？
- MST 和单源最短路分别优化什么目标？
- SCC 与普通连通分量有什么区别？
- Dijkstra 的证明在哪一步使用了“边权非负”？
- Bellman-Ford 的第 `i` 轮代表最多多少条边？负环影响哪些顶点？

这些结构和图算法不能只靠名称选择；使用时必须同时说清不变量、复杂度和适用边界。

# 图搜索：把“走迷宫”变成可证明的步骤

图不一定长得像地图。任务依赖、社交关系、网络连接、状态转换，都可以抽象成“点”和“边”。图题真正难的地方通常不是语法，而是先回答三个问题：

1. 点表示什么，边表示什么？
2. 边有方向吗，有权重吗？
3. 一个点能否重复访问，什么时候标记为已访问？

本章从 DFS（Depth-First Search，沿一条路尽量走深再回退）和 BFS（Breadth-First Search，按距离一层层扩展）开始，再学习拓扑排序、并查集、Dijkstra 与回溯剪枝。所有母题都沿用同一个表达模板，帮助你在面试中先说清思路，再写代码。

> 本章题目是通用算法训练，不是任何公司的真题。真实面试范围以当次岗位说明和通知为准。

对本书目标岗位，图不是“竞赛图论”的代名词。**P0** 是 DFS/BFS、访问标记和任务依赖的拓扑排序；它们直接对应依赖图、连通性和无权路径。并查集与非负权最短路是 **P1**；组合回溯是 **P1/P2**，只在算法轮或岗位要求时深入。最小生成树、强连通分量和负边最短路已放到[进阶选学](advanced_structures.md)，不进入通用门槛。

## 0. 图的最小词汇表

- **顶点（vertex）**：图中的对象，本章常用整数 `0..n-1` 编号；
- **边（edge）**：两个顶点之间的关系；
- **无向边**：`u` 与 `v` 可以互相到达；
- **有向边**：只能按 `u -> v` 的方向走；
- **权重**：走过一条边的成本；
- **路径**：首尾相接的一串边；
- **环**：从某点出发又回到它；
- **连通分量**：无向图中彼此可达的一组点。
- **DAG（Directed Acyclic Graph，有向无环图）**：不存在有向环，因此可以安排满足全部依赖的拓扑顺序。

稀疏图常用邻接表：`graph[u]` 保存从 `u` 能一步到达的邻居。空间是 `O(V+E)`。邻接矩阵查询一条边很快，但空间是 `O(V^2)`；只有点数小或图很密时才常用。

```cpp,ignore
std::vector<std::vector<int>> graph(vertex_count);
graph[u].push_back(v); // 有向边 u -> v
```

## 1. 母题：用 DFS 统计无向图连通分量

### 白话题意

有 `n` 个点和若干无向边。统计图被分成多少个互不连通的“岛”。孤立点本身也是一个连通分量。

### 暴力办法

先给每个点不同标签，再反复扫描所有边：若一条边两端标签不同，就把其中一类标签全部改成另一类，直到没有变化。朴素实现可能反复扫描顶点和边，成本可到 `O(VE)` 甚至更差。

### 关键观察与不变量

从一个尚未访问的点出发，沿边不断走，恰好能访问它所在的整个连通分量。一次搜索结束后，再找下一个未访问点，就发现了一个新分量。

这里用显式栈写 DFS。循环中的不变量是：

> `visited` 中的点已经被某次搜索发现；栈中的点已经发现但邻边可能尚未全部检查。一个点第一次发现时就标记，保证它最多入栈一次。

### 伪代码

```text
components <- 0
visited <- 全 false

for start 从 0 到 n-1:
    如果 visited[start]: continue
    components <- components + 1
    visited[start] <- true
    stack.push(start)

    while stack 不空:
        u <- stack.pop()
        for v in graph[u]:
            如果 not visited[v]:
                visited[v] <- true
                stack.push(v)

return components
```

### 正确性说明

一次 DFS 只沿真实边移动，因此不会走出起点所在的连通分量。反过来，分量内任一点都存在一条从起点出发的路径；沿路径长度归纳，DFS 会发现路径上的每个点，所以不会漏掉同一分量中的节点。

外层循环只在遇到未访问点时增加计数。已经完整访问过的分量不会重复计数，每个尚未访问的起点代表一个新分量，因此最终计数正确。

### 复杂度

- 时间：`O(V+E)`，无向边在邻接表中出现两次，数量级不变；
- 空间：`O(V+E)` 存图，另有 `O(V)` 的访问数组和栈。

### 完整 C++20

```cpp
#include <cassert>
#include <cstddef>
#include <vector>

using Graph = std::vector<std::vector<std::size_t>>;

void add_undirected_edge(Graph& graph, std::size_t first, std::size_t second) {
    assert(first < graph.size() && second < graph.size());
    graph[first].push_back(second);
    graph[second].push_back(first);
}

std::size_t count_components(const Graph& graph) {
    std::vector<bool> visited(graph.size(), false);
    std::vector<std::size_t> stack;
    std::size_t components = 0;

    for (std::size_t start = 0; start < graph.size(); ++start) {
        if (visited[start]) {
            continue;
        }

        ++components;
        visited[start] = true;
        stack.push_back(start);

        while (!stack.empty()) {
            const std::size_t current = stack.back();
            stack.pop_back();

            for (const std::size_t next : graph[current]) {
                assert(next < graph.size());
                if (!visited[next]) {
                    visited[next] = true;
                    stack.push_back(next);
                }
            }
        }
    }
    return components;
}

int main() {
    Graph graph(7);
    add_undirected_edge(graph, 0, 1);
    add_undirected_edge(graph, 1, 2);
    add_undirected_edge(graph, 3, 4);
    add_undirected_edge(graph, 4, 5);
    assert(count_components(graph) == 3); // {0,1,2}, {3,4,5}, {6}

    assert(count_components(Graph{}) == 0);
    assert(count_components(Graph(1)) == 1);
}
```

### 测试要点

覆盖空图、全是孤立点、只有一个分量、含环的分量。邻接表来自不可信输入时，不能只靠 `assert` 检查编号；应在解析边时返回错误，因为发布构建可能关闭断言。

### 常见追问

- **递归 DFS 可以吗？** 可以，但深链图的递归深度是 `O(V)`，可能栈溢出。
- **何时标记已访问？** 入栈时。若等出栈才标记，同一点可能被多个邻居重复压栈。
- **有向图的“连通”一样吗？** 不一样，还要区分弱连通与强连通，先问清定义。

## 2. 母题：BFS 求无权网格最短路

### 白话题意

网格中 `.` 可以走、`#` 是障碍。每步只能上下左右移动一格，每步成本都为一。求起点到终点的最少步数；不可达时返回“没有答案”。

### 暴力办法

枚举所有不重复格子的路径，计算每条到终点的长度，再取最小值。一个格子常有多个选择，路径数会指数增长。

DFS 能找到一条路，但第一次找到的不一定最短。如果把所有路径都搜完，它仍然退化到暴力枚举。

### 关键观察与不变量

所有边成本相同，BFS 按距离一层一层扩展：先处理距离 `0`，再处理距离 `1`，然后是距离 `2`。

> 一个格子第一次入队时，记录的就是起点到它的最短距离；入队即标记，之后无需重复进入队列。

为什么？若还存在更短路径，它的前驱应位于更早的一层，早就会先把该格子入队，和“第一次”矛盾。

### 伪代码

```text
如果起点或终点越界/被阻挡: return 无答案
distance 全部设为 -1
distance[start] <- 0
queue.push(start)

while queue 不空:
    current <- queue.pop()
    如果 current == target: return distance[current]

    for next in current 的四个邻居:
        如果 next 在边界内、可走、尚未访问:
            distance[next] <- distance[current] + 1
            queue.push(next)

return 无答案
```

### 正确性说明

起点距离为零，正确。假设队列已经正确处理到距离 `d` 的所有格子，从它们第一次发现的未访问邻居都有一条长度 `d+1` 的路径。任何长度小于 `d+1` 的路径都应从更早层发现该邻居，因此不存在。由归纳，首次记录的距离均为最短；终点出队或首次发现时即可得到最短答案。

### 复杂度

设网格有 `R*C` 个格子：

- 时间：`O(RC)`，每个格子最多入队一次；
- 空间：`O(RC)`，用于距离和队列。

### 完整 C++20

```cpp
#include <array>
#include <cassert>
#include <optional>
#include <queue>
#include <string>
#include <utility>
#include <vector>

using Position = std::pair<int, int>;

bool inside(const std::vector<std::string>& grid, int row, int column) {
    return row >= 0 && column >= 0 &&
           row < static_cast<int>(grid.size()) &&
           column < static_cast<int>(grid[row].size());
}

std::optional<int> shortest_path(const std::vector<std::string>& grid,
                                 Position start,
                                 Position target) {
    if (grid.empty()) {
        return std::nullopt;
    }
    const std::size_t columns = grid.front().size();
    for (const std::string& row : grid) {
        if (row.size() != columns) {
            return std::nullopt;
        }
    }

    if (!inside(grid, start.first, start.second) ||
        !inside(grid, target.first, target.second) ||
        grid[start.first][start.second] == '#' ||
        grid[target.first][target.second] == '#') {
        return std::nullopt;
    }

    std::vector<std::vector<int>> distance(
        grid.size(), std::vector<int>(columns, -1));
    std::queue<Position> pending;
    distance[start.first][start.second] = 0;
    pending.push(start);

    constexpr std::array<Position, 4> directions{
        Position{-1, 0}, Position{1, 0}, Position{0, -1}, Position{0, 1}};

    while (!pending.empty()) {
        const Position current = pending.front();
        pending.pop();

        if (current == target) {
            return distance[current.first][current.second];
        }

        for (const auto [row_step, column_step] : directions) {
            const int next_row = current.first + row_step;
            const int next_column = current.second + column_step;
            if (inside(grid, next_row, next_column) &&
                grid[next_row][next_column] == '.' &&
                distance[next_row][next_column] == -1) {
                distance[next_row][next_column] =
                    distance[current.first][current.second] + 1;
                pending.emplace(next_row, next_column);
            }
        }
    }
    return std::nullopt;
}

int main() {
    const std::vector<std::string> grid{"....", ".##.", "...."};
    assert(shortest_path(grid, {0, 0}, {2, 3}) == 5);
    assert(shortest_path(grid, {2, 0}, {2, 0}) == 0);
    assert(!shortest_path(grid, {0, 0}, {1, 1}).has_value());

    const std::vector<std::string> blocked{".#", "#."};
    assert(!shortest_path(blocked, {0, 0}, {1, 1}).has_value());
}
```

### 测试要点

覆盖起点等于终点、起点/终点是障碍、不可达、只有一行、非矩形输入。实际题目若允许八方向、传送门或不同移动成本，必须重新定义邻边，不能机械套四方向 BFS。

### 常见追问

- **何时可以提前返回？** 终点首次入队时距离已经最短；出队时返回也正确。
- **要恢复具体路径怎么办？** 记录 `parent[next] = current`，从终点倒推到起点后反转。
- **边权是 0 或 1 怎么办？** 可用双端队列做 0-1 BFS；一般非负权用 Dijkstra。

## 3. 母题：拓扑排序与依赖环检测

### 白话题意

有一组任务和有向依赖 `u -> v`，表示必须先完成 `u` 才能做 `v`。输出一个合法执行顺序；若依赖中有环，返回无答案。

### 暴力办法

枚举所有 `V!` 种任务排列，逐条检查依赖是否满足。点数稍大就不可用。

### 关键观察与不变量

入度是指向某点的边数。入度为零的任务没有尚未完成的前置依赖，可以安全地作为下一项。

Kahn 算法维护：

> 队列中的点在“删除所有已输出点及其出边”之后入度为零；`indegree[v]` 始终等于尚未删除的前置依赖数量。

若最后输出不足 `V` 个点，剩下部分每个点都仍有前驱，只可能包含有向环。

### 伪代码

```text
计算每个点的 indegree
把所有 indegree == 0 的点入队
order <- 空数组

while queue 不空:
    u <- queue.pop()
    order.push(u)
    for v in graph[u]:
        indegree[v] <- indegree[v] - 1
        如果 indegree[v] == 0: queue.push(v)

如果 order.size != 顶点数: return 无答案
return order
```

### 正确性说明

每次输出的点当前入度为零，所以它没有未输出的前置依赖，输出顺序始终合法。删除它的出边后，更新后的入度仍准确。

若算法输出全部点，就得到合法拓扑序。若提前停住，剩余每个点入度都大于零；从任一点不断沿尚存前驱逆向走，有限个点中必然重复某点，形成有向环。存在环时也不可能有拓扑序，因此返回无答案正确。

### 复杂度

- 时间：`O(V+E)`；
- 空间：`O(V+E)` 存图，另有 `O(V)` 入度、队列和结果。

### 完整 C++20

```cpp
#include <cassert>
#include <cstddef>
#include <optional>
#include <queue>
#include <vector>

using Graph = std::vector<std::vector<std::size_t>>;

std::optional<std::vector<std::size_t>> topological_order(const Graph& graph) {
    std::vector<std::size_t> indegree(graph.size(), 0);
    for (const auto& neighbours : graph) {
        for (const std::size_t next : neighbours) {
            if (next >= graph.size()) {
                return std::nullopt;
            }
            ++indegree[next];
        }
    }

    std::queue<std::size_t> ready;
    for (std::size_t vertex = 0; vertex < graph.size(); ++vertex) {
        if (indegree[vertex] == 0) {
            ready.push(vertex);
        }
    }

    std::vector<std::size_t> order;
    while (!ready.empty()) {
        const std::size_t current = ready.front();
        ready.pop();
        order.push_back(current);

        for (const std::size_t next : graph[current]) {
            --indegree[next];
            if (indegree[next] == 0) {
                ready.push(next);
            }
        }
    }

    if (order.size() != graph.size()) {
        return std::nullopt;
    }
    return order;
}

bool respects_edges(const Graph& graph,
                    const std::vector<std::size_t>& order) {
    if (order.size() != graph.size()) {
        return false;
    }
    std::vector<std::size_t> position(graph.size());
    std::vector<bool> seen(graph.size(), false);
    for (std::size_t index = 0; index < order.size(); ++index) {
        if (order[index] >= graph.size() || seen[order[index]]) {
            return false;
        }
        seen[order[index]] = true;
        position[order[index]] = index;
    }
    for (std::size_t from = 0; from < graph.size(); ++from) {
        for (const std::size_t to : graph[from]) {
            if (position[from] >= position[to]) {
                return false;
            }
        }
    }
    return true;
}

int main() {
    Graph graph(6);
    graph[5] = {2, 0};
    graph[4] = {0, 1};
    graph[2] = {3};
    graph[3] = {1};
    const auto order = topological_order(graph);
    assert(order.has_value());
    assert(respects_edges(graph, *order));

    Graph cycle(3);
    cycle[0] = {1};
    cycle[1] = {2};
    cycle[2] = {0};
    assert(!topological_order(cycle).has_value());
}
```

### 测试要点

不要只断言一个固定顺序，因为同一张图可能有多个合法拓扑序。应验证每个点恰好出现一次，且每条边的起点排在终点之前。还要测空图、孤立点和自环。

### 常见追问

- **如何判断拓扑序是否唯一？** Kahn 算法每一步若可选的零入度点不止一个，顺序就不唯一。
- **DFS 也能拓扑排序吗？** 能，用三色状态发现回边，并按完成时间逆序输出。
- **拓扑排序能处理无向图吗？** 这个定义针对有向无环图；无向边没有“先后依赖”的含义。

## 4. P1 母题：并查集发现冗余连接

### 白话题意

按顺序加入无向边。返回第一条“加入前两端已经连通”的边；加入它会在当前图中形成环。若没有这种边，返回无答案。

### 暴力办法

每加一条边前，都从一端做一次 DFS/BFS，看能否到达另一端。最坏每条边都搜索整张图，约为 `O(E(V+E))`。

### 关键观察与不变量

这里不需要知道具体路径，只要快速回答“两个点是否属于同一连通分量”。并查集为每个分量维护一个代表根：

- `find(x)` 找代表；
- `unite(a,b)` 合并两个不同分量；
- 路径压缩让查找过的节点直接靠近根；
- 按大小合并，避免小树接管大树导致过深。

不变量是：

> 处理完前 `i` 条非冗余边后，两个顶点的代表相同，当且仅当它们由这些边连通。

### 伪代码

```text
初始化：每个点各自成为一个集合

for (u, v) in edges:
    如果 find(u) == find(v):
        return (u, v)
    合并 u 和 v 的集合

return 无答案
```

### 正确性说明

初始没有边，每个点只与自己连通，并查集表示正确。若新边连接两个不同集合，图中原本不存在两端路径，合并后这两个分量恰好成为一个，表示仍正确。若代表已经相同，根据不变量，两端已有路径；再加新边必然闭合成环，因此第一条被拒绝的边就是第一条冗余连接。

### 复杂度

路径压缩和按大小合并后，`E` 次操作总时间为 `O(E α(V))`，`α` 是增长极慢的反阿克曼函数，实践中可近似看作常数。空间 `O(V)`。

### 完整 C++20

```cpp
#include <cassert>
#include <cstddef>
#include <numeric>
#include <optional>
#include <utility>
#include <vector>

class DisjointSet {
public:
    explicit DisjointSet(std::size_t count)
        : parent_(count), size_(count, 1) {
        std::iota(parent_.begin(), parent_.end(), std::size_t{0});
    }

    std::size_t find(std::size_t value) {
        assert(value < parent_.size());
        if (parent_[value] != value) {
            parent_[value] = find(parent_[value]);
        }
        return parent_[value];
    }

    bool unite(std::size_t first, std::size_t second) {
        std::size_t first_root = find(first);
        std::size_t second_root = find(second);
        if (first_root == second_root) {
            return false;
        }
        if (size_[first_root] < size_[second_root]) {
            std::swap(first_root, second_root);
        }
        parent_[second_root] = first_root;
        size_[first_root] += size_[second_root];
        return true;
    }

private:
    std::vector<std::size_t> parent_;
    std::vector<std::size_t> size_;
};

using Edge = std::pair<std::size_t, std::size_t>;

std::optional<Edge> first_redundant_edge(std::size_t vertex_count,
                                         const std::vector<Edge>& edges) {
    DisjointSet sets(vertex_count);
    for (const auto [first, second] : edges) {
        if (first >= vertex_count || second >= vertex_count) {
            return std::nullopt;
        }
        if (!sets.unite(first, second)) {
            return Edge{first, second};
        }
    }
    return std::nullopt;
}

int main() {
    const std::vector<Edge> edges{{0, 1}, {1, 2}, {2, 3}, {0, 3}, {3, 4}};
    assert(first_redundant_edge(5, edges) == Edge(0, 3));

    const std::vector<Edge> tree{{0, 1}, {1, 2}, {2, 3}};
    assert(!first_redundant_edge(4, tree).has_value());
}
```

### 测试要点

覆盖无冗余边、第一条就是自环、多个环但只返回第一条、重复边。上例把非法顶点和“没有冗余边”都表示成 `nullopt`，真实接口最好使用独立错误类型区分无答案与坏输入。

### 常见追问

- **并查集能给出两点间具体路径吗？** 不能，它只高效维护分组；需要路径时保留图再搜索。
- **能删除边吗？** 普通并查集不擅长在线删除，需要离线倒序、可回滚并查集或更复杂动态连通结构。
- **为什么按大小合并？** 让较小树挂到较大树下，控制高度。

## 5. P1 母题：Dijkstra 求非负权最短路

### 白话题意

在有向加权图中，从起点出发求到每个顶点的最小总成本。所有边权必须非负，不可达点保留为无穷。

### 暴力办法

枚举从起点出发的所有简单路径并取最小值，路径数量可能指数级。

Bellman-Ford 可以反复松弛全部边，在存在负边时仍适用，时间 `O(VE)`。当边权保证非负时，Dijkstra 能更快。

### 关键观察与不变量

“松弛”一条边 `u -> v`，就是尝试用 `distance[u] + weight` 改进 `distance[v]`。

Dijkstra 每次从小根堆取当前暂定距离最小的点。非负权保证：

> 当一条堆记录 `(d,u)` 仍等于当前 `distance[u]` 时，不可能以后再通过尚未处理的更远顶点找到小于 `d` 的路线。

实现常把改进后的新记录直接压堆，而不删除旧记录；弹出时若 `d != distance[u]`，它就是过期记录，跳过即可。

### 伪代码

```text
distance 全设为“无值”（表示不可达）
distance[source] <- 0
min_heap.push((0, source))

while heap 不空:
    (d, u) <- heap.pop_min()
    如果 d != distance[u]: continue

    for (v, weight) in graph[u]:
        如果 d + weight 超出距离类型：报告输入超出支持范围
        如果 distance[v] 无值或 d + weight < distance[v]:
            distance[v] <- d + weight
            heap.push((distance[v], v))

return distance
```

### 正确性说明

假设弹出当前有效最小记录 `(d,u)`。若存在一条更短的起点到 `u` 路径，沿该路径找到第一个尚未确定的点 `x`，它的前驱已经处理。松弛前驱边后，`x` 的暂定距离不大于那条更短路径到 `x` 的长度；因为后续边非负，这个值不大于到 `u` 的路径总长，也就小于 `d`。那么堆应该先弹出 `x`，与 `u` 是当前最小记录矛盾。因此 `d` 已是最短距离。不断应用该结论，所有可达点答案正确。

### 复杂度

使用邻接表和二叉堆：

- 时间：严格写作 `O((V+E) log E)`，因为允许平行边且惰性堆中可有 `O(E)` 条记录；若图是简单图，则 `E <= V²`，可化为常见的 `O((V+E) log V)`；
- 空间：`O(V+E)`，堆中可能存在过期记录。

### 完整 C++20

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <optional>
#include <queue>
#include <stdexcept>
#include <utility>
#include <vector>

struct Edge {
    std::size_t to{};
    std::int64_t weight{};
};

using WeightedGraph = std::vector<std::vector<Edge>>;

std::vector<std::optional<std::int64_t>> dijkstra(
    const WeightedGraph& graph,
    std::size_t source
) {
    if (source >= graph.size()) {
        throw std::out_of_range("source is outside graph");
    }
    for (const auto& neighbours : graph) {
        for (const Edge& edge : neighbours) {
            if (edge.to >= graph.size()) {
                throw std::out_of_range("edge endpoint is outside graph");
            }
            if (edge.weight < 0) {
                throw std::invalid_argument(
                    "Dijkstra requires non-negative weights");
            }
        }
    }

    using QueueItem = std::pair<std::int64_t, std::size_t>;
    std::priority_queue<QueueItem,
                        std::vector<QueueItem>,
                        std::greater<QueueItem>> pending;
    std::vector<std::optional<std::int64_t>> distance(graph.size());
    distance[source] = 0;
    pending.emplace(0, source);

    while (!pending.empty()) {
        const auto [current_distance, current] = pending.top();
        pending.pop();
        if (!distance[current].has_value() ||
            current_distance != *distance[current]) {
            continue;
        }

        for (const Edge& edge : graph[current]) {
            const auto maximum = std::numeric_limits<std::int64_t>::max();
            if (current_distance > maximum - edge.weight) {
                throw std::overflow_error{"path cost exceeds int64_t"};
            }
            const std::int64_t candidate = current_distance + edge.weight;
            if (!distance[edge.to].has_value() ||
                candidate < *distance[edge.to]) {
                distance[edge.to] = candidate;
                pending.emplace(candidate, edge.to);
            }
        }
    }
    return distance;
}

int main() {
    WeightedGraph graph(6);
    graph[0] = {{1, 7}, {2, 9}, {5, 14}};
    graph[1] = {{2, 10}, {3, 15}};
    graph[2] = {{3, 11}, {5, 2}};
    graph[3] = {{4, 6}};
    graph[5] = {{4, 9}};

    const auto distance = dijkstra(graph, 0);
    assert(distance[0].value() == 0);
    assert(distance[1].value() == 7);
    assert(distance[2].value() == 9);
    assert(distance[5].value() == 11);
    assert(distance[4].value() == 20);

    WeightedGraph disconnected(2);
    assert(!dijkstra(disconnected, 0)[1].has_value());

    WeightedGraph large(2);
    large[0] = {{1, std::numeric_limits<std::int64_t>::max()}};
    assert(dijkstra(large, 0)[1].value() ==
           std::numeric_limits<std::int64_t>::max());

    WeightedGraph invalid_disconnected(2);
    invalid_disconnected[1] = {{1, -1}};
    bool rejected_negative{false};
    try {
        (void)dijkstra(invalid_disconnected, 0);
    } catch (const std::invalid_argument&) {
        rejected_negative = true;
    }
    assert(rejected_negative);

    invalid_disconnected[1] = {{2, 0}};
    bool rejected_endpoint{false};
    try {
        (void)dijkstra(invalid_disconnected, 0);
    } catch (const std::out_of_range&) {
        rejected_endpoint = true;
    }
    assert(rejected_endpoint);
}
```

### 测试要点

覆盖起点到自己、不可达点、多条边竞争、权重为零、大权重，以及不可达分量中的非法端点或负边。这里用 `optional` 区分“不可达”和“距离恰好等于最大整数”，并在路径加法无法表示时显式报错。整个输入图都必须验证；Dijkstra 在负边下的证明失效，即使某些小例子碰巧得到正确结果也不能使用。

### 常见追问

- **如何恢复路径？** 每次成功松弛时记录 `parent[v] = u`，从目标倒推。
- **只求一个目标能提前结束吗？** 目标的有效最小记录弹出时可以结束。
- **为什么用 64 位距离？** 路径是多条边权之和，可能超过单条边或 32 位范围；仍要做加法上界检查。

## 6. P1/P2 选学：回溯与剪枝——从 1 到 9 选数

### 白话题意

从数字 `1..9` 中选出恰好 `k` 个互不重复的数，使它们的和等于 `target`。每组答案内部升序，组合之间不考虑排列差异。

例如 `k=3, target=7`，答案只有 `[1,2,4]`。

### 暴力办法

枚举 `1..9` 的全部子集，共 `2^9` 个，再筛选长度和总和。范围扩大到 `1..n` 后是指数级。

更糟的写法会枚举排列，例如把 `[1,2,4]`、`[2,1,4]` 当成不同分支，造成大量重复。

### 关键观察与不变量

回溯是对“选择树”做 DFS：选一个数，递归探索，再撤销选择。

让下一次只能选择比当前更大的数，可保证每个组合只生成一次。不变量是：

> `path` 严格递增，里面已有 `chosen` 个数，总和与原目标的差是 `need`；后续只允许从 `next..9` 选择。

剪枝来自上下界：

- 剩余可选数字数量不足，停止；
- 选择最小的若干数仍超过 `need`，停止；
- 选择最大的若干数仍达不到 `need`，停止。

### 伪代码

```text
search(next, remaining, need):
    如果 remaining == 0:
        如果 need == 0: 保存 path
        return

    如果可选数量不足: return
    如果 remaining 个最小数之和 > need: return
    如果 remaining 个最大数之和 < need: return

    for candidate 从 next 到 9:
        path.push(candidate)
        search(candidate + 1, remaining - 1, need - candidate)
        path.pop()
```

### 正确性说明

任何合法组合都有唯一升序表示。搜索第一层枚举它的第一个数，下一层只枚举更大的第二个数，依次可沿唯一分支生成整个组合，因此不漏解也不重复。

三类剪枝只在数学上已经不可能完成时停止：数量不足无法选满；最小可能和都太大，任何选择只会更大；最大可能和都太小，任何选择只会更小。因此剪枝不会删除合法答案。

### 复杂度

本题固定只有 9 个数字，上界很小。推广到 `1..n` 时，未剪枝搜索最多考察 `O(2^n)` 个子集；递归深度 `O(k)`，答案存储另计。剪枝改善实际运行时间，但通常不改变指数级最坏上界。

### 完整 C++20

```cpp
#include <cassert>
#include <vector>

using Combinations = std::vector<std::vector<int>>;

void search(int next,
            int remaining,
            int need,
            std::vector<int>& path,
            Combinations& answers) {
    if (remaining == 0) {
        if (need == 0) {
            answers.push_back(path);
        }
        return;
    }
    if (next > 9 || 10 - next < remaining) {
        return;
    }

    int minimum_sum = 0;
    for (int offset = 0; offset < remaining; ++offset) {
        minimum_sum += next + offset;
    }
    int maximum_sum = 0;
    for (int offset = 0; offset < remaining; ++offset) {
        maximum_sum += 9 - offset;
    }
    if (need < minimum_sum || need > maximum_sum) {
        return;
    }

    for (int candidate = next; candidate <= 9; ++candidate) {
        if (candidate > need) {
            break;
        }
        path.push_back(candidate);
        search(candidate + 1,
               remaining - 1,
               need - candidate,
               path,
               answers);
        path.pop_back();
    }
}

Combinations choose_numbers(int count, int target) {
    Combinations answers;
    if (count < 0 || target < 0) {
        return answers;
    }
    std::vector<int> path;
    search(1, count, target, path, answers);
    return answers;
}

int main() {
    assert((choose_numbers(3, 7) == Combinations{{1, 2, 4}}));
    assert((choose_numbers(3, 9) ==
            Combinations{{1, 2, 6}, {1, 3, 5}, {2, 3, 4}}));
    assert(choose_numbers(4, 2).empty());
    assert((choose_numbers(0, 0) == Combinations{{}}));
}
```

### 测试要点

覆盖唯一答案、多个答案、无答案、`k=0`、目标太小或太大。测试还应确认每组严格递增、元素无重复、和正确，而不只比较答案数量。

### 常见追问

- **回溯和 DFS 是什么关系？** 回溯通常是状态空间树上的 DFS，并在返回时撤销选择。
- **为什么要 `pop_back`？** 同一个 `path` 被各兄弟分支复用；不撤销会把上一分支选择带入下一分支。
- **若候选数字可以重复使用？** 递归参数继续传 `candidate`，而不是 `candidate+1`，同时处理零或负数导致的无限递归风险。

## 7. 怎样选择搜索工具

| 问题特征 | 常用工具 | 关键前提 |
|---|---|---|
| 可达性、连通分量 | DFS 或 BFS | 标记访问，避免环中重复 |
| 无权最短路 | BFS | 每条边成本相同 |
| 有向依赖顺序 | 拓扑排序 | 只有 DAG 才有完整顺序 |
| 动态合并连通分量 | 并查集 | 擅长合并与查询，不擅长删除和路径 |
| 非负权最短路 | Dijkstra | 不能有负边 |
| 枚举所有可行选择 | 回溯 | 明确选择、撤销和可证明剪枝 |

工具选择来自题目性质，不来自题目表面故事。网格可以是 BFS，也可以是 Dijkstra；依赖图可以做拓扑，也可能要求强连通分量。

## 8. 常见错误清单

- 没问有向/无向，把无向边只加入一次；
- 访问数组大小和顶点编号范围不一致；
- BFS/DFS 出队或出栈时才标记，导致重复加入；
- 用 DFS 第一次到达结果冒充无权最短路；
- 拓扑排序没有检查输出数量，漏报依赖环；
- 并查集只改父节点却没有先找根；
- Dijkstra 忘记跳过堆中过期记录；
- 对负边使用 Dijkstra；
- 距离相加发生整数溢出；
- 回溯忘记撤销选择，或剪枝只有直觉、没有上下界证明。

## 9. 练习

1. 用 BFS 返回无权图从起点到所有点的距离，并恢复一条到指定终点的路径。
2. 判断一张无向图是否为二分图。
3. 给定课程依赖，除了返回一个拓扑序，还要判断顺序是否唯一。
4. 岛屿会按天新增，实时返回岛屿数量。
5. 在有向非负权图中返回从起点到终点的具体最短路径。
6. 求 `n` 皇后所有摆放方案，并写出至少两条剪枝条件。

## 10. 练习答案与思路

### 练习 1

距离初始化为 `-1`，起点为 `0`；邻居第一次入队时设置距离和父节点。终点不可达时父节点无意义；可达时从终点沿父指针倒推到起点，再反转。时间 `O(V+E)`。

### 练习 2

对每个未访问分量做 BFS/DFS，给起点染色 `0`，每条边另一端染相反颜色。若发现一条边两端同色，返回假。无向图可二分当且仅当不存在奇数长度环。

### 练习 3

使用 Kahn 算法。每轮处理前若零入度队列大小大于一，说明当前有多个合法选择，拓扑序不唯一；仍要继续处理并检查是否存在环。

### 练习 4

每个陆地格子映射为并查集节点。新增陆地时分量数先加一，再与四周已有陆地逐一合并；每次成功合并，分量数减一。重复新增同一格不能再次计数。

### 练习 5

Dijkstra 成功松弛 `v` 时记录 `parent[v]=u`。目标有效记录弹出后即可停止。从目标倒推；若其距离仍为无穷则不可达。注意起点的父节点可设为自己或空状态。

### 练习 6

逐行放皇后。用集合或布尔数组记录已占用的列、主对角线 `row-column`、副对角线 `row+column`；冲突位置直接剪枝。每行只放一个皇后已经消除了大量无效排列。

## 11. 面试前自检

你应该能解释：

1. DFS 栈和 BFS 队列分别改变了什么访问顺序？
2. 为什么无权 BFS 第一次访问就是最短距离？
3. 拓扑排序输出不足 `V` 个点说明什么？
4. **P1**：若学习了并查集，它能回答什么，不能回答什么？
5. **P1**：若学习了 Dijkstra，非负权前提用在证明的哪里？
6. **P1/P2**：若学习了回溯，“选择—递归—撤销”分别改变什么状态？
7. **P1/P2**：一条剪枝为什么不会漏掉合法答案？

如果只能默写代码，却说不出这些前提，换一个题目故事就容易失手。先建立模型和不变量，代码只是最后的翻译。

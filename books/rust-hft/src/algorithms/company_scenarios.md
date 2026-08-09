# 岗位场景综合题：把算法放进系统与交易语境

缓存、调度、日志和行情问题看起来不同，底层往往仍是哈希、链表、堆、图、滑动窗口和有序映射。本章练习把模糊场景变成明确接口，并继续处理容量、重复、乱序、失败语义和整数边界。

这里的 **Agent Infra** 指承载模型或智能体运行的基础设施，例如请求调度、缓存、日志和任务依赖；**HFT** 指高频交易系统。场景代码是便于推演的算法模型，生产系统还要补充并发、持久化、监控和故障恢复。

本章首次会用到几个缩写：LRU（Least Recently Used，淘汰最久未使用项的缓存策略）、DAG（Directed Acyclic Graph，有向无环图）、Top-K（只保留排名最前的 `k` 项）和 PnL（Profit and Loss，盈亏）。遇到业务词时先用一句白话定义，再选择结构。

## 1. 从算法模型到生产约束

算法模型故意只保留决定数据结构的核心状态。例如 LRU 只保留容量、键值和访问次序，简化订单簿只保留价格与数量。模型可以证明核心操作是否正确，却不能自动代表真实系统已经解决并发、持久化、审计、权限和灾难恢复。每道题都会先完成可验证模型，再列出进入生产环境必须补充的约束。

## 2. 同一个算法，换一层业务外衣

| 通用结构 | Agent/基础设施训练场景 | 量化/HFT 训练场景 |
|---|---|---|
| 哈希表 | 请求去重、缓存索引、日志计数 | 订单 ID 查找、标的状态表 |
| 堆 | Top-K 错误、优先级调度、多路日志合并 | 多路行情合并、最优价候选 |
| 图与拓扑排序 | 任务依赖、构建 DAG、工作流调度 | 策略依赖、数据管线依赖 |
| 双端队列 | 滑动限流、窗口最大负载 | 滚动高低价、窗口信号 |
| 有序映射 | 时间索引、范围查询 | 价格档位与最优买卖价 |
| 链表 + 哈希 | LRU 缓存 | 有界状态缓存、订单索引辅助结构 |
| 前缀和/差分 | 时间区间资源占用 | 区间成交量、PnL 聚合 |

面试时可以先说：“我把业务名词暂时翻译成一个数据结构问题。”然后再补回业务边界。这样既不会被陌生词吓住，也不会只写出脱离需求的 LeetCode 模板。

## 3. Agent/基础设施母题一：实现有容量上限的 LRU 缓存

### 3.1 白话题意

缓存最多保存 `capacity` 个键值对：

- `get(key)`：存在则返回值，并把该键标为“最近使用”；
- `put(key, value)`：插入或更新，并标为“最近使用”；
- 超过容量时，删除最久没有使用的键。

要求两个操作平均 `O(1)`。

### 3.2 为什么单一容器不够

- 只用哈希表：能平均 `O(1)` 找键，却不知道谁最久未使用；
- 只用链表：能从尾部淘汰，却要 `O(n)` 找键；
- 哈希表 + 双向链表：哈希表负责定位，链表负责使用顺序。

这里不是为了炫耀组合，而是因为题目同时要求了两种访问方式。

### 3.3 不变量

1. 链表从前到后按“最近使用 → 最久未使用”排列；
2. 哈希表中的每个键都指向链表中同一个键的节点；
3. 哈希表大小等于链表大小，且不超过容量。

### 3.4 伪代码

```text
get(key):
    若哈希表没有 key：返回无值
    把对应链表节点移动到表头
    返回节点中的 value

put(key, value):
    若容量为 0：什么也不保存
    若 key 已存在：更新 value，节点移到表头
    否则：在表头插入节点，并在哈希表登记迭代器
    若超容量：删除链表尾节点，并从哈希表删除其 key
```

### 3.5 C++20 实现

```cpp
#include <cassert>
#include <cstddef>
#include <list>
#include <optional>
#include <unordered_map>
#include <utility>

class LruCache {
public:
    explicit LruCache(std::size_t capacity) : capacity_{capacity} {}

    std::optional<int> get(int key) {
        const auto found = index_.find(key);
        if (found == index_.end()) {
            return std::nullopt;
        }
        touch(found->second);
        return found->second->second;
    }

    void put(int key, int value) {
        if (capacity_ == 0) {
            return;
        }

        const auto found = index_.find(key);
        if (found != index_.end()) {
            found->second->second = value;
            touch(found->second);
            return;
        }

        entries_.emplace_front(key, value);
        index_[key] = entries_.begin();

        if (entries_.size() > capacity_) {
            const int expired_key = entries_.back().first;
            index_.erase(expired_key);
            entries_.pop_back();
        }
    }

    [[nodiscard]] std::size_t size() const {
        return entries_.size();
    }

private:
    using Entry = std::pair<int, int>;
    using Iterator = std::list<Entry>::iterator;

    void touch(Iterator entry) {
        entries_.splice(entries_.begin(), entries_, entry);
    }

    std::size_t capacity_;
    std::list<Entry> entries_;
    std::unordered_map<int, Iterator> index_;
};

int main() {
    LruCache cache{2};
    cache.put(1, 10);
    cache.put(2, 20);
    assert(cache.get(1) == 10);  // 1 变成最近使用

    cache.put(3, 30);            // 淘汰 2
    assert(!cache.get(2).has_value());
    assert(cache.get(1) == 10);
    assert(cache.get(3) == 30);

    cache.put(1, 11);
    assert(cache.get(1) == 11);
    assert(cache.size() == 2);

    LruCache disabled{0};
    disabled.put(7, 70);
    assert(!disabled.get(7).has_value());
}
```

`std::list::splice` 在这里移动现有节点，不复制键值，也不会让该节点迭代器失效。平均时间是 `O(1)`，空间是 `O(capacity)`；“平均”来自 `unordered_map` 的哈希假设。

### 3.6 从算法答案追问到生产设计

- 缓存键和值是谁拥有？值很大时是否复制？
- 多线程访问怎样同步？一把全局锁是否够用，是否要分片？
- 淘汰是否需要异步释放，避免析构阻塞关键路径？
- 除容量外是否还有 TTL、字节上限、租户配额？
- 缓存穿透、击穿和同时回源怎样处理？

算法题的 LRU 只解决“顺序和定位”，没有自动解决这些系统问题。

## 4. Agent/基础设施母题二：任务依赖能否完成

### 4.1 白话题意

任务编号为 `0..n-1`。依赖 `(before, after)` 表示 `before` 完成后才能执行 `after`。要求返回一个合法执行顺序；若存在循环依赖，返回无解。

这就是有向图的拓扑排序。

### 4.2 关键观察

入度为零的任务当前没有未完成前置依赖，可以执行。每执行一个任务，就删除它发出的边；新的入度零任务继续进入候选集合。

不变量：

> 候选集合中的任务，其所有前置任务都已经放入结果；结果序列始终满足已处理边的依赖顺序。

### 4.3 伪代码

```text
构建邻接表和每个点的入度
把所有入度为 0 的任务放入候选堆
当候选堆非空：
    取出一个任务，加入结果
    对它指向的每个后继：
        后继入度减一
        若变为 0：加入候选堆
若结果数量小于 n：存在环，返回无解
否则返回结果
```

使用最小堆不是正确性必需，只是让多个合法答案中总返回编号较小的任务，方便测试与复现。

### 4.4 C++20 实现

```cpp
#include <cassert>
#include <cstddef>
#include <functional>
#include <optional>
#include <queue>
#include <stdexcept>
#include <utility>
#include <vector>

std::optional<std::vector<int>> schedule_tasks(
    int task_count,
    const std::vector<std::pair<int, int>>& dependencies
) {
    if (task_count < 0) {
        throw std::invalid_argument{"negative task count"};
    }

    std::vector<std::vector<int>> next(static_cast<std::size_t>(task_count));
    std::vector<int> indegree(static_cast<std::size_t>(task_count), 0);

    for (const auto [before, after] : dependencies) {
        if (before < 0 || before >= task_count ||
            after < 0 || after >= task_count) {
            throw std::out_of_range{"task id outside range"};
        }
        next[static_cast<std::size_t>(before)].push_back(after);
        ++indegree[static_cast<std::size_t>(after)];
    }

    std::priority_queue<int, std::vector<int>, std::greater<>> ready;
    for (int task = 0; task < task_count; ++task) {
        if (indegree[static_cast<std::size_t>(task)] == 0) {
            ready.push(task);
        }
    }

    std::vector<int> order;
    while (!ready.empty()) {
        const int task = ready.top();
        ready.pop();
        order.push_back(task);

        for (const int dependent : next[static_cast<std::size_t>(task)]) {
            int& degree = indegree[static_cast<std::size_t>(dependent)];
            --degree;
            if (degree == 0) {
                ready.push(dependent);
            }
        }
    }

    if (order.size() != static_cast<std::size_t>(task_count)) {
        return std::nullopt;
    }
    return order;
}

int main() {
    const auto order = schedule_tasks(4, {{0, 2}, {1, 2}, {2, 3}});
    assert(order.has_value());
    assert((*order == std::vector<int>{0, 1, 2, 3}));

    assert(!schedule_tasks(2, {{0, 1}, {1, 0}}).has_value());
    assert((schedule_tasks(0, {}).value() == std::vector<int>{}));
    assert((schedule_tasks(3, {}).value() == std::vector<int>{0, 1, 2}));
}
```

设任务数为 `V`、依赖数为 `E`。邻接表构建为 `O(V+E)`；使用最小堆后总时间为 `O((V+E) log V)`，空间为 `O(V+E)`。若只用普通队列，可达到 `O(V+E)`，但合法顺序不一定按编号稳定。

### 4.5 工程追问

- 两条完全相同的依赖边会让入度重复增加；题目是否保证去重？若不保证，应使用边集合或明确重复边语义。
- 任务有资源需求、优先级和预计时长时，拓扑排序只解决“能否开始”，没有解决最优调度。
- 分布式执行还要处理重试、幂等、租约、失联 worker 和结果提交原子性。
- 若要求返回具体环，可以在 DFS 中记录颜色与父指针，重建一条环路径。

## 5. 量化/HFT 母题一：合并多路有序行情

### 5.1 白话题意

有 `k` 路行情，每一路内部已经按时间戳非递减排列。把它们合成一条全局有序序列；时间戳相同时，先按输入流编号，再按流内顺序输出，使结果可复现。

把全部事件拼接后排序需要 `O(N log N)`。利用每一路已经有序，可以用大小最多为 `k` 的最小堆做到 `O(N log k)`。

### 5.2 不变量

堆中只保存每个尚未耗尽数据流的“当前头部”。任何流后面的事件都不会早于它的头部，因此全局最小未输出事件一定在这些头部之中。

### 5.3 伪代码

```text
检查每一路内部有序
把每个非空流的第 0 个事件放入最小堆
当堆非空：
    弹出最早事件并输出
    若它所在流还有下一个事件：把下一个放入堆
```

### 5.4 C++20 实现

```cpp
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <queue>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

struct MarketEvent {
    std::int64_t timestamp_ns;
    std::string payload;

    bool operator==(const MarketEvent&) const = default;
};

struct Cursor {
    std::int64_t timestamp_ns;
    std::size_t stream;
    std::size_t offset;
};

struct EarlierCursor {
    bool operator()(const Cursor& left, const Cursor& right) const {
        return std::tie(left.timestamp_ns, left.stream, left.offset) >
               std::tie(right.timestamp_ns, right.stream, right.offset);
    }
};

std::vector<MarketEvent> merge_streams(
    const std::vector<std::vector<MarketEvent>>& streams
) {
    std::size_t total{0};
    for (const auto& stream : streams) {
        total += stream.size();
        for (std::size_t i = 1; i < stream.size(); ++i) {
            if (stream[i].timestamp_ns < stream[i - 1].timestamp_ns) {
                throw std::invalid_argument{"an input stream is not sorted"};
            }
        }
    }

    std::priority_queue<Cursor, std::vector<Cursor>, EarlierCursor> heap;
    for (std::size_t stream = 0; stream < streams.size(); ++stream) {
        if (!streams[stream].empty()) {
            heap.push({streams[stream][0].timestamp_ns, stream, 0});
        }
    }

    std::vector<MarketEvent> result;
    result.reserve(total);
    while (!heap.empty()) {
        const Cursor current = heap.top();
        heap.pop();
        result.push_back(streams[current.stream][current.offset]);

        const std::size_t next_offset = current.offset + 1;
        if (next_offset < streams[current.stream].size()) {
            heap.push({streams[current.stream][next_offset].timestamp_ns,
                       current.stream,
                       next_offset});
        }
    }
    return result;
}

int main() {
    const std::vector<std::vector<MarketEvent>> streams{
        {{1, "a"}, {4, "d"}},
        {{1, "b"}, {3, "c"}},
        {},
        {{5, "e"}}
    };
    const std::vector<MarketEvent> expected{
        {1, "a"}, {1, "b"}, {3, "c"}, {4, "d"}, {5, "e"}
    };
    assert(merge_streams(streams) == expected);
    assert(merge_streams({}).empty());
    assert(merge_streams({{}, {}}).empty());
}
```

其中 `N` 是事件总数，时间为 `O(N log k)`，堆空间为 `O(k)`，返回结果为 `O(N)`。

### 5.5 业务追问

- 时间戳相同的真实先后关系是什么？只靠本地接收时间可能无法恢复交易所顺序，还需要通道、分区和序号规则。
- 某一路暂时没有新事件时，是否可以继续输出其他流？若必须保证事件时间全局有序，就需要 watermark 或等待上界。
- 输入来自网络时不能提前知道全部数据；堆算法仍可用，但流结束、超时和背压必须定义。
- 回放要稳定，因此相同时间戳必须有明确 tie-breaker，不能依赖未规定的容器行为。

## 6. 量化/HFT 母题二：维护简化订单簿最优价

### 6.1 白话题意

每次更新包含买卖方向、整数价格和该档更新后的总数量：

- 数量大于零：插入或覆盖该价格档；
- 数量等于零：删除该价格档；
- 查询最高买价与最低卖价；
- 判断订单簿是否交叉，即最高买价大于等于最低卖价。

这是教学模型，不含逐订单队列、价格时间优先、成交、快照恢复和并发。

### 6.2 结构选择

买盘需要快速得到最大键，卖盘需要快速得到最小键。有序映射能让更新、删除为 `O(log n)`，最优价从 `begin()` 取得。

若价格范围小且固定，数组加 best 指针可能更合适；若只用堆，删除或覆盖任意价格档需要延迟删除等额外逻辑。

### 6.3 C++20 实现

```cpp
#include <cassert>
#include <cstdint>
#include <functional>
#include <map>
#include <optional>
#include <stdexcept>

enum class Side { Buy, Sell };

class TopOfBook {
public:
    void update(Side side, std::int64_t price, std::int64_t quantity) {
        if (price <= 0 || quantity < 0) {
            throw std::invalid_argument{"invalid price or quantity"};
        }

        if (side == Side::Buy) {
            update_level(bids_, price, quantity);
        } else {
            update_level(asks_, price, quantity);
        }
    }

    [[nodiscard]] std::optional<std::int64_t> best_bid() const {
        if (bids_.empty()) {
            return std::nullopt;
        }
        return bids_.begin()->first;
    }

    [[nodiscard]] std::optional<std::int64_t> best_ask() const {
        if (asks_.empty()) {
            return std::nullopt;
        }
        return asks_.begin()->first;
    }

    [[nodiscard]] bool crossed() const {
        const auto bid = best_bid();
        const auto ask = best_ask();
        return bid.has_value() && ask.has_value() && *bid >= *ask;
    }

private:
    template <class Map>
    static void update_level(Map& levels,
                             std::int64_t price,
                             std::int64_t quantity) {
        if (quantity == 0) {
            levels.erase(price);
        } else {
            levels[price] = quantity;
        }
    }

    std::map<std::int64_t, std::int64_t, std::greater<>> bids_;
    std::map<std::int64_t, std::int64_t> asks_;
};

int main() {
    TopOfBook book;
    assert(!book.best_bid().has_value());
    assert(!book.best_ask().has_value());

    book.update(Side::Buy, 100, 5);
    book.update(Side::Buy, 101, 2);
    book.update(Side::Sell, 103, 7);
    book.update(Side::Sell, 102, 4);
    assert(book.best_bid() == 101);
    assert(book.best_ask() == 102);
    assert(!book.crossed());

    book.update(Side::Sell, 101, 1);
    assert(book.crossed());
    book.update(Side::Sell, 101, 0);
    assert(!book.crossed());

    book.update(Side::Buy, 101, 0);
    assert(book.best_bid() == 100);
}
```

设一侧有 `L` 个价格档，更新和删除为 `O(log L)`，查询最优价为 `O(1)`（标准库未用 Big-O 文字逐项承诺所有实现细节时，面试表达可说“从树首迭代器取得，通常为常数操作”），空间为 `O(L)`。

### 6.4 工程追问

- 更新是绝对数量还是增量数量？两种协议不能混用。
- 重复、乱序、缺口和快照切换怎样处理？
- 为什么价格用整数 tick，而不是 `double`？整数更容易定义精确比较和档位。
- `std::map` 的节点分配、指针跳转和缓存局部性是否满足延迟目标？只有压测后才能回答；密集价格空间可比较数组结构。
- 交叉簿是正常成交前状态、数据错误，还是不同市场来源造成？业务语义必须说明。

## 7. 继续训练的场景题库

下面每题先识别底层模式，再写伪代码。不要一看到业务词就开始堆类。

### 7.1 Agent/系统方向

1. **最近五分钟错误 Top-K**：日志含时间与错误码，输出窗口内频率最高的 `k` 个错误。考虑过期、并列和高基数。

<details><summary>参考思路</summary>

按到达时间有序时，用队列保存窗口事件、哈希表保存码→频次；新事件加入，队首时间早于 `now-5min` 就逐个过期并减频。查询可把当前频次排序 `O(u log u)` 作为基线；频繁查询再维护有序集合/堆并处理旧版本。并列规则必须写进比较器。不变量是哈希频次恰等于队列窗口内计数；用边界时刻、同码过期和 `k>u` 验算。

</details>

2. **滑动窗口限流器**：同一租户 60 秒内最多 100 次请求。比较精确时间戳队列、固定桶和 token bucket 的语义。

<details><summary>参考思路</summary>

精确窗口为每租户保存已接受时间队列，先删 `≤now-60s` 再在 size<100 时接受，精确但空间随租户×请求增长。固定桶合并小时间段计数，省空间但边界有近似误差。Token bucket 按速率补 token、请求消耗 token，控制长期平均并允许容量大小的突发，不等价于“任意 60 秒严格≤100”。画时间轴用第 0 秒 100 次、第 59.9 秒再来请求验证语义。

</details>

3. **区间资源峰值**：每个任务给出开始、结束和 GPU 数量，求任意时刻最大 GPU 需求。提示：排序事件或差分扫描。

<details><summary>参考思路</summary>

把半开区间 `[s,e)` 变为事件 `(s,+g),(e,-g)`，按时间排序；同一时刻必须先应用结束再应用开始，或把同刻增量合并后再更新。扫描 `current+=delta`，维护最大值。不变量是处理完时刻 t 的全部事件后，current 等于 t 之后仍活跃的资源；时间 `O(n log n)`、空间 `O(n)`。用 `[0,1)` 与 `[1,2)` 验算它们不重叠。

</details>

4. **幂等请求表**：相同请求 ID 重试时返回旧结果；记录有 TTL。考虑“正在执行”和“已经完成”两种状态。

<details><summary>参考思路</summary>

表项是 `request_id→{IN_PROGRESS|DONE,result,expiry,payload_hash}`。首次请求原子创建 IN_PROGRESS，完成业务写入与 DONE 结果应处于可恢复事务边界；重复请求若 payload 不同则拒绝，DONE 返回旧结果，IN_PROGRESS 等待/查询而不是再执行。TTL 只能在业务保证不会再重试后过期。状态机验算“提交成功但响应丢失”只能产生一次业务效果。

</details>

5. **最小 worker 数**：任务有起止时间，求不重叠执行所需最少 worker。提示：按开始时间排序 + 结束时间最小堆。

<details><summary>参考思路</summary>

按开始时刻排序，最小堆保存当前占用 worker 的结束时刻。处理 `[s,e)` 前弹出全部 `end≤s`，再压入 e，记录堆最大尺寸。堆大小是不变量“当前活跃任务数”，最大重叠数既是必要下界，也可由该分配达到，所以是最少 worker。时间 `O(n log n)`；空输入 0，同刻结束可复用。

</details>

6. **有界优先级队列**：容量满时拒绝谁？相同优先级怎样保持公平？算法答案必须先定义业务政策。

<details><summary>参考思路</summary>

先选政策，例如容量满时仅当新任务优先级高于当前最低项才替换，否则拒绝；同优先级按递增 sequence 保持 FIFO。可用能取得“下一最高”和“当前最低”的有序集合，键为 `(priority,sequence)`；或双堆加惰性删除。状态不变量是 size≤capacity、每个任务唯一、弹出顺序符合优先级/FIFO。逐步推容量 2 的高低同级事件验证替换边界。

</details>

7. **失败域放置**：副本不能放在同一机架。先给贪心启发式，再构造它可能失败的反例。

<details><summary>参考思路</summary>

基线把每个副本放到当前负载最低且未使用的机架，再在机架内选节点。它是启发式，不自动最优：若后续对象只允许某两个机架，先前无限制对象贪心占满这两个机架，会导致后续无位置，而把前者放第三机架本可成功。严格问题可建二分匹配/最大流或带约束搜索。验算必须检查同对象副本的机架集合无重复及节点容量。

</details>

8. **依赖图增量更新**：新增一条依赖后快速判断是否产生环。先给完整重算基线，再讨论动态算法是否值得。

<details><summary>参考思路</summary>

加入 `u→v` 会成环当且仅当旧图中存在 `v→...→u` 路径。正确基线是暂加边后做全图拓扑 `O(V+E)`，或从 v DFS/BFS 查 u `O(V+E)`；无环才提交更新。若更新非常频繁且图大，可维护拓扑序：若 `pos[u]<pos[v]` 立即安全，否则只搜索受影响区并重排，但实现复杂。用自环、平行边、已有路径和不连通图验算。

</details>

### 7.2 量化/HFT 方向

1. **最近 `k` 笔成交的 VWAP**：维护成交额与成交量；数量为零和乘法溢出怎样处理？

<details><summary>参考思路</summary>

队列保存最近 k 笔，维护 `notional=Σprice×qty` 与 `volume=Σqty`；加入新笔、超过 k 时减去队首贡献，窗口满后输出 `notional/volume`。乘法和加减前用更宽整数或显式溢出检查，数量必须为正；若契约允许 0 数量则不计并确保分母非零。不变量两项和与队列逐项重算一致，时间 `O(n)`、空间 `O(k)`。

</details>

2. **行情序号缺口**：检测缺失范围，决定暂停、缓冲还是继续；参见[流式算法](streaming_systems.md)。

<details><summary>参考思路</summary>

维护 `expected`。`seq==expected` 应用并推进；`seq<expected` 按协议判重复/旧包；`seq>expected` 记录缺口 `[expected,seq-1]` 并进入 RECOVERING。策略必须由场所规则决定：可暂停应用并有界缓存未来消息、请求重传，超限/超时转快照；不能默认跳过。状态表用 10、12、11 推演，恢复后应用顺序应为 10、11、12，且同一 seq 只应用一次。

</details>

3. **价格窗口最大回撤**：先明确回撤定义以及是否限制时间窗口，再选择前缀最大值或双端结构。

<details><summary>参考思路</summary>

无限历史常定义 `max_{i<j}(price[i]-price[j])` 或百分比，扫描时维护此前最高价 peak，当前回撤 `peak-price`，再更新答案，`O(n)`。若只看最近 W 个时刻，过期 peak 必须移除，可用按值递减的下标双端队列维护窗口最大。先固定“峰必须早于谷”、百分比分母和无下跌返回值；用峰恰好过期的样例验算。

</details>

4. **订单 ID 去重**：哈希表能检查重复，但何时安全过期？交易日、会话重连与序号重置怎样影响键？

<details><summary>参考思路</summary>

键不能盲目只用 ID，应按协议定义组合会话/业务日/发送方等作用域。哈希表存处理状态与结果，重复返回相同结果或拒绝；只有当协议重放窗口、客户端重试上限和审计/恢复需求都已过去后才安全过期。会话重连若 ID 可能复用必须换 epoch，序号重置不等于订单 ID 可复用。重放“过期前的旧请求”应验证不会创建第二笔订单。

</details>

5. **多标的风险 Top-K**：按绝对敞口找最大的 `k` 个标的；全量批处理与持续更新分别怎样做？

<details><summary>参考思路</summary>

批处理先算每项安全绝对值（`INT_MIN` 用无符号幅值/更宽类型），全部排序 `O(n log n)` 或大小 k 堆 `O(n log k)`；并列按 symbol。持续更新可用 `symbol→当前值` 哈希加按 `(abs, symbol)` 的有序集合，每次先删旧键再插新键，Top-K 从末端取。验算更新前后每 symbol 只出现一次且符号翻转不改变绝对排序。

</details>

6. **简化撮合**：买单按价格高优先、同价时间早优先；卖单相反。需要两个优先队列或有序档位加 FIFO。

<details><summary>参考思路</summary>

买侧按价格降序、卖侧按价格升序，每个价格档内部 FIFO 保存订单剩余量。新买单在 `buy_price≥best_ask` 时与最优卖档队首成交，取双方剩余量最小值，归零者移除；卖单对称。队列保证同价时间优先。不变量是非空档位无零量、best bid/ask 来自端点、成交不超剩余量；取消/修改语义与交易所规则另定。

</details>

7. **区间成交量查询**：静态历史可用前缀和；持续更新且要修改历史时，可比较 Fenwick Tree、segment tree 和重新计算。

<details><summary>参考思路</summary>

静态数组建 `prefix[i+1]=prefix[i]+a[i]`，`[l,r)` 查询 `prefix[r]-prefix[l]`，预处理 `O(n)`、查询 `O(1)`。有点更新时，Fenwick 支持点加与前缀/区间和 `O(log n)`；segment tree 同为 `O(log n)` 且易扩展其他聚合；修改很少、查询也少可直接更新后扫描。用单点、全区间和更新后总和验算，累加类型需防溢出。

</details>

8. **固定窗口异常波动**：滚动均值/方差只是第一步，还要定义样本不足、零方差、异常值和浮点比较。

<details><summary>参考思路</summary>

先规定窗口 W、总体/样本方差和异常阈值。队列保存窗口值，可维护和与平方和作基线，但大数相减可能不稳定；工程上可用可删除的稳定统计或定期重算校正。样本不足时不报警或标未知；方差 0 时只有偏离常量的值才按专门规则处理，不能除 0。用全相等、大数量级小波动、异常正好过期和 NaN 输入验证。

</details>

## 8. 一道场景题的回答骨架

面对“设计一个每秒处理百万事件的去重器”，可以按以下顺序说：

1. **澄清语义**：“重复”的键是什么？保留多久？能否误判？输入是否有序？
2. **给正确基线**：哈希集合保存所有仍有效的 ID。
3. **写不变量**：集合恰好包含有效时间窗内已经接受的 ID。
4. **分析上界**：峰值速率乘保留时间，估算条目数和内存。
5. **再优化**：分片、批处理、过期队列、Bloom filter 或持久化层。
6. **定义失败**：状态丢失、时钟回拨、重放、分区和恢复后会发生什么。
7. **说明验证**：定向边界、随机对拍、回放、容量与尾延迟压测。

这比直接回答“用 `unordered_set`，平均 `O(1)`”完整得多。

## 9. 章末做题方法：剥掉业务名词后再选算法

1. **读题做名词映射**：把“任务”“行情”“订单”“缓存”改写成节点、边、有序流、键值和容量，另列真正的业务约束，如稳定顺序、重复事件和删除语义。
2. **画状态转移**：LRU 画哈希表与双向链表同步更新；依赖任务画有向图和入度；多路行情画每路游标与堆；订单簿画价格到数量的映射。
3. **用事件序列推演**：至少覆盖新增、更新、删除、重复、无效输入与容量边界，逐步写出数据结构状态，不只跑 happy path。
4. **验算业务不变量**：LRU 容量不超限且最近使用顺序正确；拓扑结果覆盖全部节点；合并输出有序且每项一次；最优价始终来自非空档位。

常见陷阱：被 HFT/Agent 名词诱导去设计完整系统；忽略同键更新；用值相等代替事件身份；只给算法复杂度不说明状态在异常事件后是否仍可信。

## 10. 自测清单

1. 能否从业务名词识别哈希、堆、图、窗口或有序结构？

<details><summary>验收参考</summary>

把“按 ID 找对象”映射为哈希等值查询，“持续取最高/最早”映射为堆，“依赖/可达”映射为图，“最近一段时间”映射为窗口，“前驱后继/范围”映射为有序结构。合格回答还要列更新、删除、顺序和最坏界，不能只凭名词选模板。

</details>

2. 能否解释 LRU 为什么需要哈希表和双向链表配合？

<details><summary>验收参考</summary>

哈希表平均 `O(1)` 找到 key 对应节点；双链表 `O(1)` 把已知节点移到最前并从尾部淘汰。每次操作同步两者，不变量是 key 与节点一一对应、链顺序等于新近使用次序、size 不超容量。只用链表查找慢，只用哈希无法得到最旧项。

</details>

3. 能否写拓扑排序并检测循环依赖？

<details><summary>验收参考</summary>

计算入度，把所有零入度点入队；反复弹出、输出并减少出邻居入度，新变 0 的入队。最终输出数等于 V 才是合法拓扑序，小于 V 表示剩余点在环中或依赖环。邻接表时间 `O(V+E)`、空间 `O(V+E)`。

</details>

4. 能否证明多路合并的全局最小值一定在各流头部？

<details><summary>验收参考</summary>

每一路自身有序，所以该路任何未输出元素都不小于其头部；全局最小若来自某一路，就不可能越过该路更小或相等的头部。因此只需在 k 个头部中选最小，输出后推进对应游标。最小堆实现时间 `O(N log k)`、空间 `O(k)`，空流和并列顺序要定义。

</details>

5. 能否维护简化订单簿的最优买卖价，并说明模型缺失了什么？

<details><summary>验收参考</summary>

买侧用降序价格档、卖侧升序价格档，数量变 0 时删除档位；best bid/ask 取两侧首项。每次更新后不变量是档位量为正且最优价来自当前非空端点。简化模型通常没覆盖订单级 FIFO、成交、取消优先级、快照/gap、场所特殊订单和并发一致性，必须明确边界。

</details>

6. 算法写完后，是否继续检查容量、过期、乱序、重复、并发和恢复？

<details><summary>验收参考</summary>

给同一实现列状态表：容量满时拒绝/淘汰谁；状态何时过期；乱序是否缓存；重复是否幂等；并发更新怎样原子化；崩溃后从何重建。至少为每项给一个失败样例并说明不变量是否保持。若只能报时间复杂度而答不出这些状态转移，方案还不是完整系统答案。

</details>

接下来进入[限时模拟笔试与面试](mock_exams.md)，在看不到解题标签的情况下完成整套训练。

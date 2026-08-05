# 岗位场景综合题：把算法放进系统与交易语境

经典算法题训练“能不能找到结构”，岗位场景题还会检查“能不能把模糊需求变成明确接口”。缓存、调度、日志和行情问题看起来不同，底层往往仍是哈希、链表、堆、图、滑动窗口和有序映射。

> 本章目标：把通用算法迁移到 Agent Infra 与 HFT 场景；学会区分算法模型和生产系统；能处理容量、重复、乱序、失败语义和整数边界。

## 1. 先划清事实边界

截至 2026-08-05，公开岗位信息能支持以下判断：

- DeepSeek 的[服务端开发岗位](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/2eb2e75d-29f3-47b5-bb10-39f12547d398)明确要求常用数据结构与算法；[AI 搜索架构岗位](https://app.mokahr.com/social-recruitment/high-flyer/140576#/job/1df4597d-6039-4392-9954-0df72510f415)要求熟练 C++ 或 Rust，并强调数据密集型系统与性能优化。其他训练/推理框架、数据基建和高性能算子岗位也反复出现 C++、系统基础与算法竞赛经历。
- 九坤[官方招贤纳士页](https://www.ubiquant.com/website/career)和[2026 校招报名页](https://www.wjx.cn/vm/mObzJHr.aspx)列出量化实现、AI 算法、AI Infra、高性能计算与系统优化、Linux 内核等方向；[公司介绍](https://www.ubiquant.com/website/about)强调大数据与数学算法。

这些资料**没有**公开确认具体笔试流程、固定题型、难度分布或所谓“原题”。因此，本章只称为“岗位能力导向的训练题”，不冒充公司真题，也不承诺某家公司一定这样考。

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
2. **滑动窗口限流器**：同一租户 60 秒内最多 100 次请求。比较精确时间戳队列、固定桶和 token bucket 的语义。
3. **区间资源峰值**：每个任务给出开始、结束和 GPU 数量，求任意时刻最大 GPU 需求。提示：排序事件或差分扫描。
4. **幂等请求表**：相同请求 ID 重试时返回旧结果；记录有 TTL。考虑“正在执行”和“已经完成”两种状态。
5. **最小 worker 数**：任务有起止时间，求不重叠执行所需最少 worker。提示：按开始时间排序 + 结束时间最小堆。
6. **有界优先级队列**：容量满时拒绝谁？相同优先级怎样保持公平？算法答案必须先定义业务政策。
7. **失败域放置**：副本不能放在同一机架。先给贪心启发式，再构造它可能失败的反例。
8. **依赖图增量更新**：新增一条依赖后快速判断是否产生环。先给完整重算基线，再讨论动态算法是否值得。

### 7.2 量化/HFT 方向

1. **最近 `k` 笔成交的 VWAP**：维护成交额与成交量；数量为零和乘法溢出怎样处理？
2. **行情序号缺口**：检测缺失范围，决定暂停、缓冲还是继续；参见[流式算法](streaming_systems.md)。
3. **价格窗口最大回撤**：先明确回撤定义以及是否限制时间窗口，再选择前缀最大值或双端结构。
4. **订单 ID 去重**：哈希表能检查重复，但何时安全过期？交易日、会话重连与序号重置怎样影响键？
5. **多标的风险 Top-K**：按绝对敞口找最大的 `k` 个标的；全量批处理与持续更新分别怎样做？
6. **简化撮合**：买单按价格高优先、同价时间早优先；卖单相反。需要两个优先队列或有序档位加 FIFO。
7. **区间成交量查询**：静态历史可用前缀和；持续更新且要修改历史时，可比较 Fenwick Tree、segment tree 和重新计算。
8. **固定窗口异常波动**：滚动均值/方差只是第一步，还要定义样本不足、零方差、异常值和浮点比较。

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

## 9. 自测清单

- [ ] 能从业务名词识别哈希、堆、图、窗口或有序结构。
- [ ] 能解释 LRU 为什么需要哈希表和双向链表配合。
- [ ] 能写拓扑排序并检测循环依赖。
- [ ] 能证明多路合并的全局最小值一定在各流头部。
- [ ] 能维护简化订单簿的最优买卖价，并说明模型缺失了什么。
- [ ] 不把岗位训练场景说成公司真题。
- [ ] 算法写完后，会继续问容量、过期、乱序、重复、并发和恢复。

接下来进入[限时模拟笔试与面试](mock_exams.md)，在看不到解题标签的情况下完成整套训练。

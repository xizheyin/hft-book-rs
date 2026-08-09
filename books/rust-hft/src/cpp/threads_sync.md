# C++ 线程与同步：从生命周期到条件变量

一个程序可以创建多个线程，让它们同时执行不同任务。真正困难的不是“同时运行”，而是三个更具体的问题：

1. 线程使用的数据是否仍然活着；
2. 多个线程修改共享状态时，谁有权在什么时候修改；
3. 没有工作可做的线程怎样等待，并在状态改变后重新检查条件。

操作系统层面的临界区、锁、信号量和条件变量已经在[操作系统同步](../foundations/os_synchronization.md)中解释。本章不重复那些定义，而是把它们落实为 C++20 接口和可检查的并发协议。原子变量、内存顺序和无锁算法分别放在后续的[原子操作与 C++ 内存模型](atomics_memory_model.md)和[无锁结构](lock_free.md)中。

## 1. 线程对象不是后台任务的所有权证明

`std::thread` 构造成功时，新线程通常已经可以开始执行。创建者与新线程随后谁先运行，由调度器决定，不能依赖源码中的上下顺序。

```cpp,ignore
int value = 42;
std::thread worker([&value] {
    use(value);
});
worker.join();
```

这是语法片段，不是独立程序。lambda 按引用捕获 `value`，所以必须保证 `worker` 最后一次访问它时，`value` 仍然存在。这里的 `join()` 不只是“等一下”：它也让外层作用域在子线程结束前不会销毁 `value`。

需要分清两种生命周期：

- **线程的执行生命周期**：入口函数从开始运行到返回；
- **C++ 线程对象的生命周期**：`std::thread` 或 `std::jthread` 对象从构造到析构。

线程对象只是一个控制句柄。把句柄移动、销毁或放进容器，并不会自动证明入口函数捕获的引用安全。

## 2. `std::thread`：必须明确 join 或 detach

`std::thread` 是只移动类型，因为两个普通对象不能同时声称自己负责同一个可 join 线程。可以用 `joinable()` 检查对象当前是否关联着一个尚未 join 或 detach 的线程。

### 2.1 `join()` 等待线程结束

调用 `join()` 后，调用者等待目标线程返回，随后该 `std::thread` 对象不再 joinable。对同一个对象重复 `join()` 是错误。

如果入口函数已经执行完，但还没有调用 `join()`，线程对象仍然是 joinable：操作系统执行结束与 C++ 句柄是否已经回收，是两个不同状态。

### 2.2 `detach()` 不是“让程序更异步”

`detach()` 让线程独立继续运行，当前 `std::thread` 对象放弃等待它的能力。此后很难统一处理：

- 引用捕获对象何时销毁；
- 程序退出前任务是否完成；
- 线程抛出异常、卡住或需要取消时由谁收尾；
- 测试怎样确定后台工作已经停止。

因此业务程序通常应让线程属于一个明确的组件，并在组件关闭时 join。只有整个进程生命周期都能覆盖线程访问的数据，而且退出与错误政策已经另行解决时，才考虑 detach；“我不想等待”本身不是充分理由。

### 2.3 析构 joinable 的 `std::thread` 会终止程序

若一个 joinable 的 `std::thread` 对象直接析构，标准要求调用 `std::terminate`，而不是悄悄 detach。这样做是为了避免程序在不知情时留下仍会访问外部对象的线程。

这意味着异常路径也必须收尾。C++20 的 `std::jthread` 为常见情况提供了更安全的 RAII 默认值。

## 3. `std::jthread`：自动 join 与协作式停止

`std::jthread` 析构时会先请求停止，再在仍 joinable 时 join。它减少了“某条返回或异常路径忘记 join”的风险，但不等于可以随时强杀线程。

入口函数如果接收 `std::stop_token`，就可以主动检查停止请求：

```cpp,ignore
std::jthread worker([](std::stop_token token) {
    while (!token.stop_requested()) {
        do_one_bounded_piece_of_work();
    }
});

worker.request_stop();
```

这是展示接口的片段。`request_stop()` 只把停止请求发布出去；线程必须在有限时间内检查 token，或者让它正在等待的阻塞原语同时被唤醒。若线程永远阻塞在不响应停止的系统调用、条件变量或第三方库中，`jthread` 析构时的 join 仍可能一直等。

协作式停止通常要回答四件事：

1. 从哪里开始不再领取新工作；
2. 当前工作是完成、回滚还是记录为结果未知；
3. 哪些等待点会因停止请求而醒来；
4. 线程返回前由谁释放资源、通知上游并保存状态。

## 4. Mutex 保护的是不变量

下面是一个包含两个字段的账户状态：

```text
available + reserved = total
```

如果两个字段必须一起变化，只给它们分别套一个原子操作，并不能保证其他线程看见一致组合。更直接的设计是用同一把 mutex 保护整条不变量：持锁者可以读取和更新这组状态，其他线程只能在取得同一把锁后访问。

### 4.1 `lock_guard`：只需要作用域加锁

```cpp,ignore
void reserve(std::int64_t amount) {
    std::lock_guard<std::mutex> guard{mutex_};
    if (amount <= available_) {
        available_ -= amount;
        reserved_ += amount;
    }
}
```

`lock_guard` 构造时加锁，离开作用域时解锁，包括普通返回和异常展开。它适合“进入作用域后一直持锁，直到离开”的简单临界区。

### 4.2 `unique_lock`：需要临时解锁或交给条件变量

`std::unique_lock` 也是 RAII 锁所有者，但它可以延迟加锁、显式解锁、重新加锁和移动。条件变量的 `wait` 需要在睡眠时暂时释放 mutex，并在返回前重新取得它，因此通常接收 `unique_lock`。

灵活性也意味着更多状态：一个 `unique_lock` 可能暂时不拥有锁，代码评审时要检查 `owns_lock()` 对应的控制流。只是作用域加锁时优先使用更简单的 `lock_guard`。

### 4.3 多把锁使用统一顺序或 `scoped_lock`

两个线程若分别先锁 A、先锁 B，再等待对方的锁，就可能形成死锁。可采用全局锁顺序；需要同时取得多把 mutex 时，也可以用 `std::scoped_lock`，让标准库使用避免死锁的加锁算法。

即使没有死锁，仍要缩小持锁范围。不要在不知道耗时上限的网络 I/O、磁盘 I/O、日志格式化或外部回调期间持有共享锁，否则一个慢操作会把所有等待者串起来。

## 5. 条件变量等待的是“状态成立”

条件变量本身不保存“现在有几个任务”，也不会把每次通知排队供未来线程消费。真实状态必须保存在 mutex 保护的数据中，例如：

```text
队列非空，或者队列已经关闭
```

等待者的标准写法是：

```cpp,ignore
std::unique_lock<std::mutex> lock{mutex};
not_empty.wait(lock, [&] {
    return closed || !queue.empty();
});
```

带谓词的 `wait` 可以理解为：

```text
while (!predicate()) {
    原子地释放 mutex 并进入等待；
    被唤醒后重新取得 mutex；
}
```

这里的“原子地”指释放 mutex 与加入条件变量等待之间不会留下一个让通知永久丢失的可观察空窗。`wait` 返回时，调用线程重新持有 mutex，随后才能安全读取被保护状态。

### 5.1 为什么只写 `if` 会错

线程被唤醒不等于条件必然仍成立：

- 可能发生**虚假唤醒**，即没有对应业务状态变化也返回；
- `notify_all` 会唤醒多个等待者，第一个线程可能已经取走唯一任务；
- 从通知到重新取得 mutex 之间，其他线程可能再次改变状态。

因此每次醒来都要在持锁状态下重查谓词。谓词重载或显式 `while` 都满足这一点，单独的 `if` 不满足。

### 5.2 丢失唤醒怎样发生

考虑错误协议：消费者先在**没有同一把锁保护**的情况下看见队列为空；此时生产者加入任务并调用 `notify_one()`；消费者随后才调用 `wait()`。通知已经发生，而条件变量不会保存通知，消费者可能一直睡眠。

正确协议把“检查谓词”和“进入等待”连接到同一把 mutex：

1. 生产者持锁修改队列状态；
2. 消费者持同一把锁检查谓词；
3. 谓词为假时，`wait` 原子地解锁并等待；
4. 生产者修改状态后通知；
5. 消费者醒来、重新加锁并再次检查。

即使通知早于消费者开始等待，消费者取得锁后也会看见“队列非空”，于是根本不会睡。防止丢失的核心是持久化的状态和统一互斥协议，不是“多发几次 notify”。

### 5.3 `notify_one` 还是 `notify_all`

- 一个新任务通常只允许一个消费者取得，可先考虑 `notify_one`；
- 关闭队列、配置代际变化或多个等待条件都可能成立时，常需 `notify_all`；
- 唤醒所有线程会制造锁竞争，不能把它当默认修复按钮。

状态必须先在锁保护下完成修改，再发通知。很多实现会先解锁再 notify，避免被唤醒者立即阻塞在同一 mutex 上；这项调整只有在状态发布协议已经正确后才讨论，不能用来弥补无锁修改共享状态。

## 6. 完整例子：可关闭的有界阻塞队列

有界队列同时需要两个等待条件：

- 队列满时，生产者等待“有空位或已经关闭”；
- 队列空时，消费者等待“有元素或已经关闭”。

`close()` 表示不再接受新元素，并唤醒所有等待者。消费者仍会取完关闭前已经入队的元素；队列关闭且为空后，`pop()` 返回 `nullopt`。

```cpp
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <iostream>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>
#include <utility>

template <class T>
class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t capacity) : capacity_(capacity) {
        if (capacity_ == 0) {
            throw std::invalid_argument("capacity must be positive");
        }
    }

    BoundedQueue(const BoundedQueue&) = delete;
    BoundedQueue& operator=(const BoundedQueue&) = delete;

    bool push(T value) {
        std::unique_lock<std::mutex> lock{mutex_};
        not_full_.wait(lock, [this] {
            return closed_ || queue_.size() < capacity_;
        });
        if (closed_) {
            return false;
        }

        queue_.push_back(std::move(value));
        lock.unlock();
        not_empty_.notify_one();
        return true;
    }

    std::optional<T> pop() {
        std::unique_lock<std::mutex> lock{mutex_};
        not_empty_.wait(lock, [this] {
            return closed_ || !queue_.empty();
        });
        if (queue_.empty()) {
            return std::nullopt;
        }

        T value = std::move(queue_.front());
        queue_.pop_front();
        lock.unlock();
        not_full_.notify_one();
        return value;
    }

    void close() {
        {
            std::lock_guard<std::mutex> guard{mutex_};
            closed_ = true;
        }
        not_empty_.notify_all();
        not_full_.notify_all();
    }

private:
    const std::size_t capacity_;
    std::mutex mutex_;
    std::condition_variable not_empty_;
    std::condition_variable not_full_;
    std::deque<T> queue_;
    bool closed_{false};
};

int main() {
    BoundedQueue<int> queue{4};
    std::atomic<int> sum{0};

    std::jthread first_consumer([&] {
        while (const auto value = queue.pop()) {
            sum.fetch_add(*value, std::memory_order_relaxed);
        }
    });
    std::jthread second_consumer([&] {
        while (const auto value = queue.pop()) {
            sum.fetch_add(*value, std::memory_order_relaxed);
        }
    });

    for (int value = 1; value <= 100; ++value) {
        assert(queue.push(value));
    }
    queue.close();

    first_consumer.join();
    second_consumer.join();
    assert(sum.load(std::memory_order_relaxed) == 5'050);
    assert(!queue.push(101));
    std::cout << "sum=" << sum.load(std::memory_order_relaxed) << '\n';
}
```

这段程序需要注意七条不变量：

1. `queue_` 和 `closed_` 的每次访问都持有同一个 `mutex_`；
2. `queue_.size()` 从不超过 `capacity_`；
3. 只有真正弹出一个元素后才通知 `not_full_`；
4. 只有真正加入一个元素后才通知 `not_empty_`；
5. `close()` 以后所有 `push` 都失败；
6. 关闭不丢弃已经入队的元素；
7. 关闭时通知两类等待者，否则满队列中的生产者或空队列中的消费者可能永远不醒。

这里的 `sum` 是一个独立统计量，不负责发布其他数据，所以 `Relaxed` 足够。队列元素的可见性由 mutex 的解锁与随后加锁建立，不需要再给元素字段加原子变量。

### 6.1 这个教学实现还没有承诺什么

- `push`/`pop` 没有 deadline 或 `stop_token` 重载；
- 公平性由 mutex 与调度器实现决定，不保证严格 FIFO 唤醒线程；
- `deque` 分配失败时会抛异常；
- 多个生产者都能调用 `close`，结果保持关闭，但没有区分“谁有关闭权”；
- 对极低延迟路径，应先测锁竞争、调度和分配，再决定是否需要预分配或改变所有权拓扑。

把这些边界说清楚，比直接宣称“线程安全队列已经生产可用”更重要。

## 7. 取消、关闭和超时不是同一个动作

**取消请求**表示调用者不再需要某项工作；**关闭队列**表示不再接收新工作；**超时**表示等待者在自己的 deadline 前没有观察到结果。三者可能同时出现，却不能互相替代。

例如消费者收到停止请求时，设计可以选择：

- 立即停止领取新任务，完成手上的任务后退出；
- 把未完成任务放回队列；
- 将可能已经产生外部副作用的任务标记为结果未知，稍后对账。

不能用 C++ 线程停止机制撤销已经发送到远端服务的请求。线程只能停止继续执行本地代码；数据库写入、文件提交或订单是否已经生效，需要各自的幂等键、查询或补偿协议。

对阻塞等待，常见实现选择包括：

- 条件变量的定时等待，并在每次醒来后检查 deadline、关闭状态和谓词；
- `condition_variable_any` 与支持的 `stop_token` 等待接口；
- 把停止状态并入受 mutex 保护的谓词，再在停止时 `notify_all`。

无论选择哪一种，都要保证停止状态与业务状态之间没有丢失唤醒窗口。

## 8. 怎样选择同步手段

| 问题形状 | 优先考虑 | 原因 |
|---|---|---|
| 多字段必须一起满足不变量 | mutex + RAII guard | 最容易把临界区和证明边界写清楚 |
| 等待某个共享状态成立 | mutex + condition variable + predicate | 不忙等，并能处理虚假/竞争唤醒 |
| 一次性交付任务结果 | `promise/future` 或更高层任务接口 | 结果和完成状态是一对一关系 |
| 独立计数，不携带其他数据 | atomic + Relaxed | 不必为了一个数字建立大临界区 |
| 单写者可以拥有全部状态 | 消息传递/有界队列 | 从结构上减少共享写入 |
| 已证明锁竞争是瓶颈且能写出进展与回收证明 | 成熟无锁结构 | 无锁是专门约束，不是默认升级 |

先选最容易证明正确、最符合所有权的结构，再用目标负载测量。mutex 可能在无竞争时只走很短的用户态路径；高竞争的原子读改写也会让缓存行反复迁移。

## 9. 高频错误

- `std::thread` 还 joinable 就离开作用域；
- detach 一个捕获局部引用或 `this` 的线程；
- 多个线程访问同一普通对象，误以为“只有很短时间”就不算数据竞争；
- 用两个 mutex 分别保护必须原子变化的两个字段；
- 条件变量没有持久化谓词，只把 notify 当消息；
- 用 `if` 包住 wait，不处理虚假唤醒和竞争消费者；
- 修改谓词时未持同一把 mutex；
- 关闭时只唤醒消费者，忘记可能正在等空位的生产者；
- 持锁调用未知回调、阻塞 I/O 或另一个可能反向加锁的组件；
- 认为 `jthread` 析构能强制终止任何阻塞线程。

## 做题方法

并发题不要只盯着某一行加锁。按下面顺序画协议：

1. **列共享状态**：哪些字段共同组成一条不变量；
2. **标所有访问者**：每个线程读什么、写什么，数据活到什么时候；
3. **画锁范围**：哪把锁保护哪些字段，是否出现嵌套和反向顺序；
4. **写等待谓词**：线程究竟在等哪个布尔条件，不要只写“等通知”；
5. **枚举三个时刻**：通知发生在 wait 之前、等待期间、被唤醒后重新抢锁之前；
6. **加入关闭与异常**：谁唤醒等待者，谁 join，外部副作用处于什么状态；
7. **最后才谈优化**：记录竞争、等待、上下文切换和队列深度，再比较分片、单写者或原子方案。

## 10. 练习与参考答案

### 练习 1：判断生命周期错误

函数创建局部字符串，启动线程并按引用捕获它，然后 detach 并返回。问题是什么？怎样修复？

<details>
<summary>参考答案与解答</summary>

**解答过程：**函数返回后局部字符串被销毁，detached 线程仍可能解引用它，形成悬垂引用和未定义行为。优先让组件拥有线程并在字符串销毁前 join；若任务确实独立，也可以把所需数据按值移动进线程，但仍需定义任务完成、错误和进程退出政策。只把 `&text` 改成裸指针不能解决寿命问题。

</details>

### 练习 2：推演一次丢失唤醒

消费者无锁检查 `queue.empty()`，为空便准备等待；生产者此时入队并 notify；消费者随后调用 wait。为什么会永久睡眠？正确协议怎样避免？

<details>
<summary>参考答案与解答</summary>

**解答过程：**条件变量不保存历史通知。消费者检查状态与真正进入等待之间存在空窗，通知恰好落在空窗中。正确做法是由同一把 mutex 保护队列，消费者用 `wait(lock, predicate)`；生产者也在持锁时修改队列。这样消费者要么先看见非空而不睡，要么已经原子地释放锁并进入等待，生产者随后才能入队和通知。

</details>

### 练习 3：为什么必须重查谓词

队列只有一个元素，`notify_all` 唤醒三个消费者。每个消费者都用 `if (empty) wait()`，可能发生什么？

<details>
<summary>参考答案与解答</summary>

**解答过程：**三个线程醒来后依次竞争 mutex。第一个取得锁并取走元素；第二、第三个取得锁时队列已经再次为空，但 `if` 已经执行过，它们会继续访问空队列。用谓词重载或 `while` 后，每个线程重新取得锁都会再次检查，后两个发现条件为假并继续等待。虚假唤醒也由同一重查处理。

</details>

### 练习 4：计算有界队列的业务容量

队列容量为 4096，每个元素对象占 64 byte。只计算元素有效载荷，满队列至少对应多少 KiB？为什么这不是进程真实内存上限？

<details>
<summary>参考答案与解答</summary>

**解答过程：**有效载荷为 `4096 × 64 = 262144 byte = 256 KiB`。真实内存还包括 `deque` 分块与元数据、mutex/条件变量、分配器开销、线程栈、消费者已经取走但仍在处理的元素，以及对象内部可能指向的动态内存。容量限制了队列中的元素数，却不能单独限制整个进程 RSS。

</details>

### 练习 5：检查两把锁的死锁

线程 A 先锁账户再锁订单，线程 B 先锁订单再锁账户。写出死锁时间线和两种修复方式。

<details>
<summary>参考答案与解答</summary>

**解答过程：**A 取得账户锁，B 取得订单锁；A 等订单锁，B 等账户锁，形成循环等待。可规定所有路径都按“账户→订单”的统一顺序；需要同时取得两把锁时也可用 `std::scoped_lock{account_mutex, order_mutex}`。修复后还要检查回调或下层函数是否暗中再次加锁，否则表面顺序一致仍可能自锁或形成更长环。

</details>

### 练习 6：`jthread` 为什么仍可能卡在析构

worker 正阻塞在一个永不返回、也不观察 stop token 的第三方调用中。外层 `jthread` 离开作用域会怎样？

<details>
<summary>参考答案与解答</summary>

**解答过程：**析构会请求停止，但第三方调用不观察请求；随后析构 join，等待入口函数返回，因此仍可能无限阻塞。需要为调用提供 deadline、可取消句柄、独立故障域或可安全关闭的资源，使阻塞点能够结束。`stop_token` 是协作协议，不是操作系统级强杀。

</details>

## 11. 面试复述

> `std::thread` 必须明确 join 或 detach，joinable 对象直接析构会 terminate；`std::jthread` 提供请求停止和自动 join，但停止仍需线程协作。mutex 应保护一组不变量，锁由 RAII guard 管理。条件变量不保存业务状态，等待者必须在同一 mutex 下使用谓词循环；这样才能同时处理通知早到、虚假唤醒和多个消费者竞争。设计还要覆盖关闭、异常、引用生命周期和所有等待者的退出，再根据竞争证据决定是否需要分片或原子结构。

## 一手资料与延伸阅读

- [C++ 工作草案：thread 类](https://eel.is/c++draft/thread.thread.class)、[jthread](https://eel.is/c++draft/thread.jthread.class)：joinable、析构、停止源与 token 的语言规则。
- [C++ 工作草案：mutex 要求](https://eel.is/c++draft/thread.mutex.requirements)与[条件变量](https://eel.is/c++draft/thread.condition)：加锁同步和 wait/notify 的标准语义。
- [C++ Core Guidelines 并发规则](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#S-concurrency)：锁守卫、条件变量谓词、持锁范围和线程生命周期的工程规则。
- 本书[操作系统同步](../foundations/os_synchronization.md)：互斥、信号量、管程、生产者—消费者和死锁的机制基础。

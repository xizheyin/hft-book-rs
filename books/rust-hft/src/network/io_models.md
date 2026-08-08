# I/O 模型：等待就绪、提交操作与忙轮询

网络程序经常不是“算得慢”，而是在**等数据**。I/O 模型要解决的问题是：数据暂时没到时，线程应该睡眠、检查别的连接，还是一直轮询？

判断一个 I/O 接口，需要先回答三件事：

1. 一个线程怎样管理很多连接；
2. “可读”为什么不等于“一定读到完整消息”；
3. 更低延迟为什么往往要付出更多 CPU、复杂度和隔离成本。

## 1. 先分清四个概念

### 1.1 文件描述符

**文件描述符**（file descriptor，FD）是进程用来引用一个已打开内核对象的小整数。TCP socket、UDP socket、文件和管道都可以由 FD 表示。

“Linux 一切皆文件”只是帮助理解接口统一性，不能理解成这些对象的内部实现完全相同。例如 socket 收发不会走普通文件的页缓存写回路径。

### 1.2 阻塞与非阻塞

- **阻塞 FD**：当前没有数据时，`read`/`recv` 可以让调用线程睡眠；
- **非阻塞 FD**：当前无法继续时，调用立即返回 `EAGAIN`/`EWOULDBLOCK`，线程自己决定下一步。

非阻塞只改变“现在做不了时怎么办”，并不会自动把程序变成异步程序。

### 1.3 就绪与完成

- **就绪（readiness）**：现在尝试读或写，预计不会因为“完全没有进展”而长时间阻塞；
- **完成（completion）**：先提交一个具体操作，系统稍后告诉你它完成了多少字节以及是否出错。

`epoll` 主要报告**就绪**；`io_uring` 主要交付已提交操作的**完成结果**。这是 Reactor 与 Completion 风格最重要的区别。

### 1.4 一次通知不等于一次完整应用操作

一次“可读”通知只表示当前值得尝试读取：

- 可能只读到消息头的一部分；
- 可能一次读到多条消息；
- 另一个线程可能抢先读走数据；
- 非阻塞读取仍可能得到 `EAGAIN`。

所以应用仍要根据读取返回值处理部分结果、关闭和错误；流式消息定界由 [TCP Socket 工程](tcp_optimization.md) 主讲。

## 2. 阻塞 I/O：简单不等于不能并发

阻塞读取在没有数据时让线程睡眠：

```rust,no_run
use std::io::{self, Read};
use std::net::TcpStream;

fn receive_once(stream: &mut TcpStream) -> io::Result<Vec<u8>> {
    let mut buffer = vec![0_u8; 4096];
    let received = stream.read(&mut buffer)?;
    if received == 0 {
        return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "peer closed"));
    }
    buffer.truncate(received);
    Ok(buffer)
}
```

它的优点是控制流直观，特别适合连接数少、每个连接都很重要的程序。它**可以并发**：可以使用线程池或每连接一个线程；问题是连接很多而活跃连接很少时，大量线程会增加栈内存、调度和唤醒成本。

因此准确的结论是：阻塞 I/O 不适合用“无限增加线程”的方式扩展到大量空闲连接，而不是“阻塞 I/O 无法并发”。

## 3. 非阻塞 I/O：立即返回，但谁来通知？

非阻塞 socket 暂时没有数据时会立即返回 `WouldBlock`：

```rust,no_run
use std::io::{self, Read};
use std::net::TcpStream;

enum ReadStatus {
    Data(usize),
    WouldBlock,
    Closed,
}

fn try_read_once(stream: &mut TcpStream, buffer: &mut [u8]) -> io::Result<ReadStatus> {
    assert!(!buffer.is_empty());
    loop {
        match stream.read(buffer) {
            Ok(0) => return Ok(ReadStatus::Closed),
            Ok(n) => return Ok(ReadStatus::Data(n)),
            Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                return Ok(ReadStatus::WouldBlock);
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(error) => return Err(error),
        }
    }
}
```

连接初始化时只需设置一次 non-blocking。收到 ET 通知后，调用者要反复执行 `try_read_once`：每次 `Data(n)` 都先处理或保存这 `n` 字节，`WouldBlock` 才表示本轮已经 drain；`Closed` 或其他错误则进入关闭/错误处理。不能因为一个固定用户缓冲区恰好装满就假装 socket 已经 drain 完。

程序若不停遍历全部 FD，就是**忙轮询**：响应可能很快，但空闲时也会占满 CPU。若在每轮后 `sleep`，又会把睡眠时间直接加到尾延迟上。

`select`、`poll` 和 `epoll` 的价值，就是让线程在没有事件时睡眠，并在某些 FD 就绪后只处理相应对象。

## 4. 多路复用：一个等待点管理多个 FD

### 4.1 `select`

调用者每次传入 FD 位图，内核检查它们并返回修改后的集合。主要限制是：

- 每次调用都要传递并扫描集合；
- 通常受 `FD_SETSIZE` 限制；Linux/glibc 常见值是 1024，但不要把它当作跨平台常量；
- 返回后，应用还要扫描位图找出就绪项。

### 4.2 `poll`

`poll` 使用 `pollfd` 数组，没有 `select` 那种固定大小位图限制，但每次仍要把数组交给内核并线性检查。监控对象很多、活跃对象很少时，这份工作浪费明显。

### 4.3 `epoll`

`epoll` 把“关注哪些 FD”和“本次等待结果”拆开：

1. `epoll_ctl` 持久地添加、修改或删除关注项；
2. 被监控对象的状态变化通过等待队列回调进入就绪集合；
3. `epoll_wait` 睡眠或返回本轮可处理的事件。

内核实现会用树等结构管理关注项，并维护就绪链表。**不是网卡中断处理程序去红黑树里搜索 socket**：网卡、协议栈、socket 等层处理数据，相关等待队列的回调再把事件传播给 `epoll`。

也不要把 `epoll` 简化成“绝对 O(1)”：它避免了每次扫描全部关注 FD，但 `epoll_ctl`、事件入队、锁竞争、把结果复制给用户空间，以及处理本轮 `K` 个就绪事件都仍有成本。更稳妥的面试说法是：

> `select`/`poll` 的一次等待工作更容易随监控总数 `N` 增长；`epoll` 持久保存关注集合，等待与返回路径主要围绕本轮就绪事件 `K` 工作，因此在 `K ≪ N` 时通常更合适。

### 4.4 LT 与 ET

`epoll` 常见两种触发方式：

- **水平触发（LT）**：只要状态仍满足条件，就可能再次通知，容易写对；
- **边缘触发（ET）**：主要在状态发生变化时通知，可减少重复通知，但必须配合非阻塞 FD，并一直处理到 `EAGAIN`。

ET 不是自动的“高速模式”。如果每次本来就能处理干净，收益可能很小；如果忘记 drain 到 `EAGAIN`，则可能让已有数据长时间得不到处理。

## 5. Reactor 与完成式接口

下面这张表只比较编程契约，不把实现细节说成永远不变的保证：

| 风格 | 应用先得到什么 | 随后做什么 | 常见接口 |
| --- | --- | --- | --- |
| 阻塞调用 | 调用返回时的结果 | 处理结果 | blocking `read`/`write` |
| Reactor / 就绪 | “这个 FD 现在可尝试操作” | 应用再调用 `read`/`write` | Linux `epoll` |
| Completion / 完成 | “此前提交的操作已完成” | 读取完成结果并继续 | Linux `io_uring` |
| 忙轮询 | 应用主动检查状态 | 立即处理或继续转圈 | 专用低延迟线程、部分 bypass 方案 |

`io_uring` 用共享的提交队列（SQ）和完成队列（CQ）批量交换请求，但这不代表所有操作都“零系统调用”或“零拷贝”：

- 普通模式仍需进入内核提交或等待；
- SQPOLL 可在满足配置和权限条件时减少提交系统调用；
- 是否发生数据复制取决于操作、缓冲区注册和内核支持；
- 完成通知也不天然等于数据已经持久化到磁盘。

## 6. 延迟来自哪里

不要背“系统调用固定几百纳秒”。真实代价会随 CPU、内核缓解措施、缓存冷热、批量大小和竞争改变。应沿路径分析：

| 成本 | 为什么出现 | 常见缓解方式 | 代价 |
| --- | --- | --- | --- |
| 系统调用与状态切换 | 请求内核服务 | 批量提交、减少无效调用 | 批量可能增加等待时间 |
| 睡眠与唤醒 | 空闲时节省 CPU | 忙轮询、固定核心 | 持续占用核心和电力 |
| 数据复制 | 内核与用户缓冲区边界 | 注册缓冲区、mmap、bypass | 生命周期和安全更复杂 |
| 调度与跨核迁移 | 线程或中断换核 | affinity、队列分片 | 降低系统调度弹性 |

低延迟系统追求的不是“技术名词最多”，而是让关键路径的工作更少、更可预测。

## 7. 怎么选

1. 连接少、逻辑简单：先用阻塞 I/O，易验证通常比复杂接口更重要；
2. 大量连接、事件驱动服务：`epoll`/`mio`/Tokio 是成熟基线；
3. 需要统一批量处理网络和文件 I/O：测量后再评估 `io_uring`；
Rust 中，标准库适合阻塞接口，`mio` 暴露较薄的就绪抽象，Tokio 提供 runtime、任务和生态集成，底层 `io-uring` crate 更接近内核接口。不要只凭框架榜单选型；用连接数、消息率、尾延迟、CPU 预算和运维约束做基准测试。

## 8. 一分钟面试回答

> 阻塞 I/O 在暂时无数据时让线程睡眠；非阻塞 I/O 立即返回 `EAGAIN`，但单独使用会迫使应用扫描或忙轮询。`select` 和 `poll` 每次传入并检查整个集合；`epoll` 持久保存关注集合，并返回就绪事件，所以大量连接但少量活跃时更合适。`epoll` 给的是 readiness，应用仍要非阻塞读到 `EAGAIN`；`io_uring` 更接近提交操作后接收 completion。两种接口都必须按返回值处理部分完成、关闭和错误。

## 9. 高频追问

### `epoll` 为什么不能简单说成 O(1)？

因为注册、删除、唤醒回调、锁、结果复制和处理 `K` 个就绪事件都有成本。它的关键优势是避免每次等待都扫描全部 `N` 个关注项。

### “可读”后为什么还会 `EAGAIN`？

就绪状态可能在通知与读取之间改变，例如另一个线程先读走了数据。就绪是提示，不是为当前线程预留数据。

### ET 为什么必须非阻塞并读到 `EAGAIN`？

阻塞 FD 可能在 drain 循环中卡住；若没有把当前可读数据处理干净，ET 又可能不重复提醒同一状态。

### 非阻塞是否等于异步？

不等于。非阻塞只规定一次调用无法立即推进时应返回；异步程序还需要事件来源、任务状态和调度方式。可以写一个不停扫描非阻塞 FD 的同步循环，也可以由运行时把非阻塞 FD 组合成异步任务。

## 10. 延伸阅读

- [epoll(7)](https://man7.org/linux/man-pages/man7/epoll.7.html)
- [select(2)](https://man7.org/linux/man-pages/man2/select.2.html)
- [poll(2)](https://man7.org/linux/man-pages/man2/poll.2.html)
- [Linux `io_uring(7)`](https://man7.org/linux/man-pages/man7/io_uring.7.html)
- [Linux NAPI 文档](https://docs.kernel.org/networking/napi.html)

提交队列、完成队列和多次完成操作见 [io_uring](./io_uring.md)。

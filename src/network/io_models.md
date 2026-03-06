# I/O 模型演进 (Evolution of I/O Models)

在深入研究 io_uring 和 Kernel Bypass 之前，我们需要先理解操作系统是如何处理网络 I/O 的。为什么我们需要 `epoll`？为什么 `select` 在连接数多的时候会变慢？

这一切都始于一个基本概念：**文件描述符 (File Descriptor, FD)**。在 Linux 中，一切皆文件，网络套接字 (Socket) 也不例外。

## 1. 基础概念：用户态与内核态

为了安全，操作系统将内存划分为 **用户空间 (User Space)** 和 **内核空间 (Kernel Space)**。
- 你的应用程序运行在用户空间。
- 网卡驱动和协议栈 (TCP/IP) 运行在内核空间。

当网卡收到数据包时：
1.  网卡通过 DMA 将数据写入内核缓冲区 (Kernel Buffer)。
2.  网卡向 CPU 发送中断。
3.  内核处理中断，将数据包放入 Socket 的接收队列。
4.  **用户程序发起系统调用 (read/recv)**，CPU 将数据从内核缓冲区 **复制 (Copy)** 到用户缓冲区。

这个“复制”过程，以及伴随的系统调用 (System Call) 开销，是高性能网络编程需要解决的核心问题。

## 2. 阻塞 I/O (Blocking I/O)

最原始的模型。当你调用 `read()` 时，如果内核缓冲区没有数据，你的线程就会被挂起 (Sleep)，直到数据到达。

```rust
// 伪代码
let mut buf = [0u8; 1024];
// 线程在此处阻塞，直到有数据
let n = socket.read(&mut buf).unwrap(); 
process(&buf[..n]);
```

- **优点**：编程简单，数据来了就处理。
- **缺点**：无法处理并发。如果要处理 10000 个连接，就需要 10000 个线程。线程切换开销巨大。

## 3. 非阻塞 I/O (Non-blocking I/O)

我们可以将 Socket 设置为非阻塞模式 (`O_NONBLOCK`)。此时调用 `read()`，如果没数据，内核会立即返回 `EWOULDBLOCK` 错误，而不是挂起线程。

```rust
socket.set_nonblocking(true).unwrap();

loop {
    match socket.read(&mut buf) {
        Ok(n) => process(&buf[..n]),
        Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
            // 没数据，稍后再试
            std::thread::yield_now(); 
        }
        Err(e) => panic!("IO Error: {}", e),
    }
}
```

- **优点**：单线程可以管理多个连接（轮询）。
- **缺点**：**忙轮询 (Busy Polling)** 会导致 CPU 空转率 100%。如果要把 CPU 让给别人 (`yield` 或 `sleep`)，又会引入延迟。

我们需要一种机制，让内核告诉我们：“哪些 Socket 有数据了？”

## 4. I/O 多路复用 (I/O Multiplexing)

这是现代网络服务的基石。我们把一组 FD 交给内核，让内核帮我们要么挂起，要么告诉我们要读哪个。

### 4.1 `select` (1983)

最古老的接口。

- **工作原理**：你传给内核一个 `fd_set` (位图)，内核遍历检查这些 FD 的状态。如果有就绪的，内核修改位图返回。
- **致命缺陷**：
    1.  **数量限制**：默认只能监控 1024 个 FD (`FD_SETSIZE`)。
    2.  **O(N) 开销**：每次调用 `select`，都需要把整个 FD 集合从用户态拷贝到内核态。内核需要遍历所有 FD。即使只有一个 FD 就绪，你也得遍历整个集合才知道是哪个。

### 4.2 `poll` (1997)

改进了 `select`。

- **改进**：使用链表/数组存储 FD，消除了 1024 的数量限制。
- **遗留问题**：依然是 **O(N)** 的。如果有 10 万个连接，只有 1 个活跃，`poll` 依然要扫描这 10 万个项。

### 4.3 `epoll` (2002)

Linux 2.6 引入的革命性技术。它是 **O(1)** 的。

**核心机制**：
1.  **`epoll_create`**: 在内核创建一个 `eventpoll` 对象。
2.  **`epoll_ctl`**: 添加/删除/修改要监控的 FD。内核使用 **红黑树 (Red-Black Tree)** 来管理这些 FD，增删查效率为 O(log N)。
3.  **回调机制**: 当网卡收到数据，中断处理程序会查找红黑树，找到对应的 FD，并将其加入到一个 **就绪链表 (Ready List)** 中。
4.  **`epoll_wait`**: 用户调用此函数，内核只需检查“就绪链表”是否为空。如果不为空，直接返回链表中的项。

**为什么 epoll 快？**
- 不需要每次都把所有 FD 传给内核（`epoll_ctl` 只需要调用一次）。
- 不需要遍历所有 FD，只处理活跃的 (Ready List)。
- 哪怕你监控 100 万个连接，只要同一时刻只有 10 个活跃，`epoll_wait` 就只返回这 10 个，效率与总连接数无关。

### 4.4 触发模式：LT vs ET

`epoll` 有两种工作模式：

1.  **水平触发 (Level Triggered, LT)** - 默认模式
    - 只要缓冲区里还有数据，每次调用 `epoll_wait` 都会通知你。
    - 类似于 `select`/`poll` 的行为。
    - **安全，不易丢数据**。

2.  **边缘触发 (Edge Triggered, ET)** - 高速模式
    - 只有数据**从无到有**（或状态变化）的那一瞬间，才会通知你一次。
    - 如果你收到通知后没把缓冲区读空，下次 `epoll_wait` **不会**再通知你，剩下的数据就“死”在缓冲区里了，直到新数据到达触发下一次边缘。
    - **高效**：减少了系统调用次数。
    - **危险**：必须配合非阻塞 I/O 循环读取，直到 `EWOULDBLOCK`。

## 5. 模型对比与优劣分析 (Comparison & Trade-offs)

我们将从机制、开销和适用场景三个维度，对比这几种主流 I/O 模型。

| 特性 | Blocking I/O | Non-blocking I/O | I/O Multiplexing (Epoll) | Asynchronous I/O (io_uring) | Kernel Bypass (DPDK) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **系统调用 (Syscall)** | 每次读写 1 次 (阻塞) | 每次读写 1 次 (可能空转) | `epoll_wait` + `read/write` (至少 2 次) | **0 次** (SQPOLL模式) 或 1 次 (Batch) | **0 次** (完全接管网卡) |
| **数据拷贝** | 内核 -> 用户 (1次) | 内核 -> 用户 (1次) | 内核 -> 用户 (1次) | 内核 -> 用户 (1次, 异步) 或 **0次** (Zero-Copy) | **0 次** (DMA 直接到用户空间) |
| **CPU 开销** | 线程挂起/唤醒 (高) | 忙轮询 (极高) | 中等 (红黑树维护 +就绪链表) | **极低** (共享内存 + 内核线程轮询) | **独占核心** (Spin 100%) |
| **编程复杂度** | 低 (同步代码) | 中 (需处理 `EWOULDBLOCK`) | 高 (Reactor 模式, 回调) | **极高** (Proactor 模式, 内存安全挑战) | **地狱级** (驱动管理, 协议栈自研) |
| **适用场景** | 简单客户端, 低并发 | 极低延迟单连接 (Spin) | **高并发通用网关 (Nginx, Redis)** | **超高并发 / 磁盘 I/O / HFT 日志** | **极致低延迟 (HFT 核心网关)** |

### 5.1 为什么 Epoll 是当前主流？
`epoll` (Reactor 模型) 统治了过去 20 年的高性能网络编程。
- **成熟稳定**: 经过了无数生产环境验证 (Linux Kernel 2.6+)。
- **兼容性好**: 几乎所有语言的标准库都封装了它 (Rust `mio`, Go Netpoller, Java NIO)。
- **性能足够**: 对于 99% 的应用（Web Server, Database），`epoll` 的开销完全可以接受。

### 5.2 为什么 HFT 需要超越 Epoll？
但在微秒级竞争中，`epoll` 仍有瓶颈：
1.  **系统调用开销**: `epoll_wait` 是系统调用。从用户态切换到内核态，再切换回来，至少需要几百纳秒。如果每秒处理 100 万个包，光是系统调用的开销就占满了 CPU。
2.  **双次调用**: 必须先 `wait` (通知) 再 `read` (数据搬运)。这导致了**两次**用户态/内核态切换。
3.  **内存拷贝**: 数据依然需要从内核缓冲区 `copy` 到用户缓冲区。

### 5.3 下一代：io_uring 与 Kernel Bypass
为了解决这些问题，我们引入了两种技术路线：
1.  **io_uring (Proactor)**: 
    - **合并调用**: `wait` 和 `read` 合并为一步（提交请求 -> 内核完成后通知）。
    - **共享内存**: 通过 SQ/CQ 环形队列，实现用户态和内核态的零拷贝通信。
    - **Polling**: 内核线程主动轮询，消灭系统调用。
2.  **Kernel Bypass (DPDK/OpenOnload)**: 
    - **完全绕过内核**: 用户态程序直接接管网卡，实现真正的零拷贝和零中断。
    - **极致低延迟**: 但开发难度极大，且不仅限于 Linux 兼容性。

### 5.4 Rust 生态现状 (Ecosystem Status)

知道原理后，我们来看看在 Rust 中可以直接使用哪些库。

#### 1. Epoll (Reactor)
- **[mio](https://github.com/tokio-rs/mio)**: Rust 异步生态的基石。它是一个轻量级的系统调用封装，统一了 Linux (epoll), macOS (kqueue), Windows (IOCP)。几乎所有上层 Runtime (Tokio, async-std) 都基于它。
- **[tokio](https://github.com/tokio-rs/tokio)**: 工业级标准。基于 `mio`，提供了 Work-stealing 调度器。
  - **评价**: 极其稳定，生态最丰富。但在超高并发下，Work-stealing 带来的跨核通信开销可能会成为瓶颈（相比于 Thread-per-core）。

#### 2. io_uring (Proactor)
- **[io-uring](https://github.com/tokio-rs/io-uring)**: `tokio` 团队维护的底层 Bindings。
  - **评价**: 非常 Raw，全是 `unsafe`。它只提供了像 C 语言一样的基础接口（Submission Queue/Completion Queue 操作）。如果你要极致性能，就用这个自己造轮子。
- **[glommio](https://github.com/DataDog/glommio)**: DataDog 开源。基于 `io_uring` 的 Thread-per-core 架构（类似 C++ Seastar）。
  - **评价**: 专为 NVMe 磁盘 I/O 和高吞吐网络设计。没有跨核开销，但不仅限于较新的 Linux 内核。
- **[monoio](https://github.com/bytedance/monoio)**: 字节跳动开源。也是 Thread-per-core 设计。
  - **评价**: 性能通常优于 Tokio。支持 `io_uring` 和 `epoll` 双驱动切换。

#### 3. Kernel Bypass (DPDK / AF_XDP)
- **[dpdk-rs](https://crates.io/crates/dpdk-rs)**: 仅仅是 `bindgen` 生成的 C 接口绑定。
  - **评价**: **极难使用**。你必须写大量 `unsafe` 代码来管理 mbuf 内存池、PCIe 设备初始化。目前 Rust 社区缺乏像 C++ `SPDK` 那样成熟的高级封装。
- **AF_XDP (XDP Socket)**: Linux 内核提供的原生 Bypass 方案（比 DPDK 稍微慢一点点，但更安全）。
  - **库**: 通常结合 eBPF 库（如 **[aya](https://github.com/aya-rs/aya)**）使用。
  - **评价**: 这是 Rust 更有潜力的方向。不需要像 DPDK 那样接管整个网卡硬件，能与内核协议栈共存。

**HFT 选型建议**:
- **交易执行 (Execution)**: 流量不大但要求极低延迟 -> **io_uring (Raw)** 或 **AF_XDP**。
- **行情数据 (Market Data)**: 吞吐量巨大 -> **DPDK (C FFI)** 或 **io_uring (Multishot)**。
- **通用网关**: -> **Tokio** (不要过早优化)。

下一章，我们将深入探讨 **io_uring**。

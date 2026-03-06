# io_uring 深度解析

Linux 5.1 引入的 `io_uring` 是异步 I/O 的革命。在它之前，我们有 `epoll`。
虽然 `epoll` 解决了 C10K 问题，但它本质上还是**同步**的：你告诉内核你想读，内核告诉你“可以读了”，然后你再发起 `read` 系统调用——这里仍然涉及系统调用开销和数据拷贝。

`io_uring` 旨在通过**提交队列 (SQ)** 和 **完成队列 (CQ)** 两个环形缓冲区，实现真正的**异步**和**零系统调用**（在理想情况下）。

## 1. 原理：环形缓冲区 (Ring Buffers)

`io_uring` 的核心是两个共享内存的 Ring Buffer：

```mermaid
graph TD
    subgraph UserSpace
        App[Application]
        SQ[Submission Queue (SQ)]
        CQ[Completion Queue (CQ)]
    end
    subgraph KernelSpace
        Kernel[Kernel Thread]
        Device[Hardware / Driver]
    end

    App -- "1. Push SQE" --> SQ
    SQ -- "2. Read SQE (No Syscall)" --> Kernel
    Kernel -- "3. Execute I/O" --> Device
    Device -- "4. Interrupt/Poll" --> Kernel
    Kernel -- "5. Push CQE" --> CQ
    CQ -- "6. Poll/Read CQE" --> App

    style SQ fill:#dfd,stroke:#333
    style CQ fill:#fdd,stroke:#333
    style Kernel fill:#f96,stroke:#333
```

1.  **Submission Queue (SQ)**: 用户进程将 I/O 请求（SQE, Submission Queue Entry）写入此队列。
2.  **Completion Queue (CQ)**: 内核完成 I/O 后，将结果（CQE, Completion Queue Entry）写入此队列。

### 1.1 零系统调用 (Zero Syscall)
在 `IORING_SETUP_SQPOLL` 模式下，内核会启动一个内核线程 (Kernel Thread) 专门轮询 SQ。
这意味着：
1. 用户进程把请求写入 SQ。
2. 更新 SQ 尾指针。
3. **无需任何系统调用**，内核线程就会看到新请求并处理。
4. 用户进程轮询 CQ 获取结果。

这对于高频交易中的**日志落盘**和**非关键路径网络 I/O** 具有极大的吸引力。

## 2. Rust 生态与网络编程实战

Rust 提供了低层级的 `io-uring` crate，以及基于它的异步运行时 `glommio` 和 `tokio-uring`。虽然 `io_uring` 最常被提及的是文件 I/O，但它在网络编程（特别是 TCP/UDP 处理）上同样强大。

### 2.1 基础用法示例：文件读取

```rust
use io_uring::{IoUring, opcode, types};
use std::os::unix::io::AsRawFd;

fn read_file_with_iouring(fd: i32, buf: &mut [u8]) -> std::io::Result<()> {
    let mut ring = IoUring::new(8)?; // 队列深度 8

    // 1. 准备 SQE (Read 请求)
    let read_e = opcode::Read::new(types::Fd(fd), buf.as_mut_ptr(), buf.len() as _)
        .build()
        .user_data(0x42); // 标记请求 ID

    // 2. 提交请求
    unsafe {
        ring.submission()
            .push(&read_e)
            .expect("submission queue is full");
    }

    // 3. 通知内核 (如果不使用 SQPOLL)
    ring.submit_and_wait(1)?;

    // 4. 处理 CQE
    let cqe = ring.completion().next().expect("completion queue is empty");
    assert_eq!(cqe.user_data(), 0x42);
    
    if cqe.result() < 0 {
        return Err(std::io::Error::from_raw_os_error(-cqe.result()));
    }

    Ok(())
}
```

### 2.2 网络 I/O 模型演进 (原理篇)

为了理解 `io_uring` 的革命性，我们需要先回顾它是如何解决 `epoll` 模型的固有缺陷的。

#### 阶段 1: Epoll + Non-blocking I/O (Reactor 模型)
这是大多数现代高性能网络库（如 Rust 的 `mio` / `tokio`, C++ 的 `libevent`）的工作方式。

1.  **注册**: 告诉 `epoll` 关注某个 socket 的 `EPOLLIN` (可读) 事件。
2.  **通知**: `epoll_wait` 返回，告诉用户“Socket A 有数据了”。
3.  **执行**: 用户发起 `recv(Socket A)` 系统调用。
    *   CPU 陷入内核。
    *   内核将数据从网卡/内核缓冲区**拷贝**到用户缓冲区。
    *   `recv` 返回。

**痛点**:
*   **割裂**: `epoll` 只管通知，不管数据搬运。真正的搬运工作（`recv`）仍然是**同步**的系统调用。
*   **系统调用开销**: 处理 N 个活跃连接，至少需要 N 次 `epoll_wait` (批量) + N 次 `recv`。如果是小包高频通信，syscall 开销巨大。

#### 阶段 2: io_uring (Proactor 模型)
`io_uring` 将“通知”和“执行”合二为一，实现了真正的**异步 I/O**。

1.  **提交**: 用户不仅告诉内核“我想读 Socket A”，还直接把**空缓冲区**交给内核（写入 SQ）。
2.  **异步执行**: 用户无需等待，继续处理其他逻辑。内核在后台自动等待数据到达，并直接将数据**拷贝**到用户提供的缓冲区中。
3.  **完成**: 内核通过 CQE 告诉用户“操作完成了，数据已经在你的 Buffer 里了”。

**为什么 io_uring 能做到“零系统调用”？**
你说得对，`epoll_wait` 是系统调用，传统的 `io_uring_enter` 也是系统调用。但 `io_uring` 有两个杀手锏是 `epoll` 做不到的：

1.  **共享内存 (Shared Memory Ring Buffers)**:
    SQ 和 CQ 位于内核与用户态共享的内存区域。用户写 SQE、内核写 CQE 都不需要进入内核。只有在**通知**内核处理时才需要系统调用。
2.  **SQPOLL 模式 (内核线程轮询)**:
    这是 `io_uring` 真正的绝招。你可以配置一个内核线程专门盯着 SQ。
    - 用户：写 SQE -> 更新 tail 指针（纯用户态内存操作）。
    - 内核线程：发现 tail 变了 -> 自动捡起请求执行。
    - **全程 0 系统调用**。相比之下，`epoll_wait` 永远无法摆脱系统调用，因为你必须通过它来向内核“索要”事件。

**对比**:
*   **Epoll**: "告诉我什么时候可以读" -> 用户发起 `epoll_wait` (Syscall) -> 内核返回 -> 用户发起 `recv` (Syscall) -> 内核拷贝。
*   **io_uring (SQPOLL)**: "帮我把数据读到这里" -> 用户写 SQ (0 Syscall) -> 内核线程搬运数据 -> 用户读 CQ (0 Syscall)。

### 2.3 实战：UDP 高效收发

在 HFT 中，行情数据通常通过 UDP 组播传输。使用 `io_uring` 处理 UDP 包可以显著减少系统调用开销。

#### 关键 Opcode: `RecvMsg` 与 `SendMsg`

```rust
use io_uring::{opcode, types, IoUring};
use std::os::unix::io::AsRawFd;
use std::net::UdpSocket;

fn receive_market_data(socket: &UdpSocket) -> std::io::Result<()> {
    let mut ring = IoUring::new(128)?;
    let fd = types::Fd(socket.as_raw_fd());

    // 准备接收缓冲区
    let mut buf = vec![0u8; 1500]; // 标准 MTU
    let mut iov = libc::iovec {
        iov_base: buf.as_mut_ptr() as *mut _,
        iov_len: buf.len(),
    };
    
    // 构造 msghdr 结构体 (用于 recvmsg)
    let mut msg_hdr: libc::msghdr = unsafe { std::mem::zeroed() };
    msg_hdr.msg_iov = &mut iov;
    msg_hdr.msg_iovlen = 1;

    // 1. 提交 RecvMsg 请求
    let recv_op = opcode::RecvMsg::new(fd, &mut msg_hdr)
        .build()
        .user_data(1001); // Tag

    unsafe {
        ring.submission().push(&recv_op).expect("SQ full");
    }
    
    // 2. 提交并等待
    ring.submit_and_wait(1)?;

    // 3. 处理完成事件
    if let Some(cqe) = ring.completion().next() {
        if cqe.result() > 0 {
            println!("Received {} bytes of market data", cqe.result());
            // 处理 buf 中的数据...
        }
    }
    
    Ok(())
}
```

#### 进阶：多路复用 (Multishot Recv)

Linux 5.19+ 引入了 `IORING_RECV_MULTISHOT`。这是一个杀手级特性，它解决了“请求补充速度赶不上发包速度”的问题。

**工作原理**:
1.  用户提交**一个**带有 `MULTISHOT` 标志的 `recv` 请求。
2.  该请求在内核中保持**激活状态 (Armed)**，不会因为接收到一个包就从 SQ 中移除。
3.  每当网卡有新数据到达，内核直接写入数据，并生成一个 CQE。
4.  这个过程一直持续，直到出错或被显式取消。

**对比**:
- **One-Shot**: 1 SQE -> 1 Packet -> 1 CQE. (瓶颈在 SQE 提交速度，如果应用处理慢了，SQ 空了，就会丢包)
- **Multi-Shot**: 1 SQE -> N Packets -> N CQEs. (瓶颈仅在处理 CQE 速度，内核自动驱动接收循环)

这完美匹配了 HFT 中的行情流特征：突发、高频、单向。

```rust
// 伪代码示例 (需较新内核与 crate 支持)
let multi_recv = opcode::RecvMsg::new(fd, &mut msg_hdr)
    .flags(libc::IORING_RECV_MULTISHOT) // 关键标志
    .build();
```

### 2.4 零拷贝网络 (Zero-Copy Networking)

Linux 6.0+ 引入了 `io_uring` 的 `send_zc` (Zero Copy Send)。

**原理**:
传统的 `send` 会将数据从用户态 Buffer `memcpy` 到内核态的 `sk_buff`。
`send_zc` 通过**页面锁定 (Page Pinning)** 技术，让网卡 DMA 直接读取用户态内存。
- **发送阶段**: 内核记录用户内存地址，直接通知网卡发送。
- **完成阶段**: 只有当网卡真正发送完毕（DMA 完成），内核才会生成 CQE。在此之前，用户**绝对不能**修改该 Buffer，否则会发送错误数据。

**HFT 意义**: 
对于发送大包（如回放历史行情）或高频发送小包（如订单指令），能显著降低 CPU 占用和内存带宽压力。但对于极小的包（< 1KB），页面锁定的开销可能超过拷贝数据的开销，需要 Benchmark 验证。

## 3. HFT 场景分析

### 3.1 适用场景
- **异步日志落盘**: 使用 `io_uring` 批量写入日志文件，完全不阻塞交易线程，且比后台线程 `write` 更高效。
- **行情记录 (Market Data Recording)**: 将海量 UDP 包直接 dump 到磁盘。
- **网关服务器**: 处理大量并发 TCP 连接（类似于 Nginx 的角色）。

### 3.2 不适用场景 (陷阱)
- **极低延迟交易**:
    虽然 `io_uring` 很快，但在**单次小包**的延迟上，它通常不如 **Busy Polling + Userspace Networking (DPDK/OpenOnload)**。
    因为 `io_uring` 仍然经过内核的文件系统层或网络栈层，路径比 Kernel Bypass 长。
    且 `SQPOLL` 线程引入了额外的调度不确定性。

## 4. 高级特性：Fixed Buffers & Files

为了进一步减少开销，`io_uring` 允许预先注册缓冲区和文件描述符。

- **Registered Buffers**: 预先将用户态内存映射到内核，避免每次 I/O 时的 `get_user_pages` 调用（锁住内存页）。
- **Registered Files**: 避免每次通过 fd 查找内核 file 结构体（原子引用计数开销）。

```rust
// 注册缓冲区示例
let mut buf = vec![0u8; 4096];
let iovec = libc::iovec {
    iov_base: buf.as_mut_ptr() as *mut _,
    iov_len: buf.len(),
};

// 这是一个系统调用，但在初始化阶段做一次即可
ring.submitter().register_buffers(&[iovec])?;

// 之后使用 opcode::ReadFixed 代替 Read
```

## 5. 总结

`io_uring` 是 Linux I/O 的未来。
在 HFT 系统中，它可能不会直接用于**核心策略逻辑**（那里我们用自旋锁和共享内存），但在**数据持久化**、**历史回放**和**非核心网关**中，它是无与伦比的利器。

---
下一章：[第四部分：市场连接 (Market Connectivity)](../connectivity/protocols.md)

# io_uring 深度解析

Linux 5.1 引入的 `io_uring` 是异步 I/O 的革命。在它之前，我们有 `epoll`。
虽然 `epoll` 解决了 C10K 问题，但它本质上还是**同步**的：你告诉内核你想读，内核告诉你“可以读了”，然后你再发起 `read` 系统调用——这里仍然涉及系统调用开销和数据拷贝。

`io_uring` 旨在通过**提交队列 (SQ)** 和 **完成队列 (CQ)** 两个环形缓冲区，实现真正的**异步**和**零系统调用**（在理想情况下）。

## 1. 原理：环形缓冲区 (Ring Buffers)

`io_uring` 的核心是两个共享内存的 Ring Buffer：

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

## 2. Rust 生态：io-uring crate

Rust 提供了低层级的 `io-uring` crate，以及基于它的异步运行时 `glommio` 和 `tokio-uring`。

### 2.1 基础用法示例

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

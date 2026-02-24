# TCP 协议优化 (TCP Optimization)

并不是所有环境都能部署 Kernel Bypass（比如你只能用 AWS 虚拟机，或者交易所强制要求 VPN）。在标准 Linux 内核栈上，我们依然可以压榨出最后一滴性能。

本章将介绍如何通过 Socket 选项调优，将 TCP 延迟降低 50% 以上。

## 1. 核心选项：TCP_NODELAY

### 1.1 Nagle 算法的诅咒
Nagle 算法诞生于 Telnet 时代，为了防止网络上充斥着只有 1 字节负载的小包。它规定：如果还有未被 ACK 的数据，且发送缓冲区未满，就先攒着不发。

这对于 HFT 是灾难性的。你的下单指令可能只有 64 字节，会被 Nagle 算法强行扣留几十毫秒，直到攒够一个 MSS（通常 1460 字节）或者收到上一个包的 ACK。

### 1.2 解决方案
**必须** 在所有 TCP 连接上禁用 Nagle 算法。

```rust
use std::net::TcpStream;

fn configure_socket(stream: &TcpStream) -> std::io::Result<()> {
    // 禁用 Nagle 算法，有数据立刻发
    stream.set_nodelay(true)?;
    Ok(())
}
```

## 2. 延迟确认 (Delayed ACK)

接收端也有一个类似的机制：Delayed ACK。它为了减少纯 ACK 包的数量，会等待 ~40ms 看看有没有数据要回传（Piggyback）。
**Nagle + Delayed ACK = 死锁**。
发送端在等 ACK 才发包（Nagle），接收端在等数据包才回 ACK（Delayed ACK）。两者互等，导致至少 40ms 的延迟。

**优化**: 虽然 Linux 提供了 `TCP_QUICKACK`，但它不是永久生效的（每次 recv 后都会重置）。
最好的办法是：**确保发送端开启 `TCP_NODELAY`**。

## 3. 缓冲区调优

### 3.1 发送/接收缓冲区
默认的缓冲区可能很大（几 MB），这有助于吞吐量，但不利于延迟（Bufferbloat）。
对于 HFT，我们希望缓冲区尽可能小，以减少排队延迟。但太小会导致丢包。

```rust
use std::os::unix::io::AsRawFd;

fn set_buffer_size(stream: &TcpStream) -> std::io::Result<()> {
    // 只要能容纳几个包即可，例如 32KB
    // 注意：内核会将其翻倍作为实际大小
    let size = 32 * 1024; 
    
    // Rust std 没直接暴露 setsockopt，需用 libc 或 socket2 crate
    // 这里用伪代码示意
    // setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &size);
    // setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &size);
    Ok(())
}
```

## 4. Busy Polling (忙轮询)

自 Linux 3.11 起，内核支持 `SO_BUSY_POLL`。
这允许内核在 `recv` 系统调用中进行短时间的死循环轮询，而不是立即挂起进程等待中断。
这在没有 Kernel Bypass 的情况下，模拟了类似 DPDK 的行为。

**效果**: 可以显著减少 Context Switch 和中断延迟。

```rust
// 伪代码，需使用 libc
const SO_BUSY_POLL: i32 = 46;

fn enable_busy_poll(stream: &TcpStream) {
    let fd = stream.as_raw_fd();
    // 轮询 50 微秒
    let usecs: i32 = 50; 
    unsafe {
        libc::setsockopt(
            fd, 
            libc::SOL_SOCKET, 
            SO_BUSY_POLL, 
            &usecs as *const i32 as *const libc::c_void, 
            std::mem::size_of::<i32>() as u32
        );
    }
}
```
**注意**: 全局还需要调整 sysctl: `sysctl -w net.core.busy_read=50`.

## 5. 读写模式：Blocking vs Non-Blocking vs Async

### 5.1 Async (Tokio)
- **优点**: 处理成千上万连接（C10K）。
- **缺点**: Runtime 调度有开销。Waker 机制涉及分配和原子操作。
- **HFT 适用性**: **不推荐用于核心交易路径**。可以用在网关前端或管理接口。

### 5.2 Blocking (阻塞)
- **优点**: 简单，直接。
- **缺点**: 一个连接需要一个线程。
- **HFT 适用性**: **推荐**。我们通常只有几个连接（交易所 A, B, C），Thread per Core 模型完美契合。

### 5.3 Non-Blocking (非阻塞) + Busy Loop
这是最极致的做法。

```rust
stream.set_nonblocking(true)?;

loop {
    match stream.read(&mut buf) {
        Ok(n) if n > 0 => process(&buf[..n]),
        Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
            // 没有数据，自旋！
            // 不要 yield，不要 sleep
            std::hint::spin_loop();
        }
        _ => break,
    }
}
```
这会占满 100% CPU，但能获得最低的 User-Space 延迟。

## 6. 常见陷阱

1.  **DNS 查询**:
    `TcpStream::connect("exchange.com:80")` 会触发 DNS 查询。这可能耗时几百毫秒！
    **解决**: 启动时解析好 IP，或者直接在 `/etc/hosts` 硬编码。运行时只连 IP。

2.  **Slow Start (慢启动)**:
    TCP 连接刚建立时，拥塞窗口 (cwnd) 很小。
    **解决**: 如果连接长时间空闲，TCP 可能会重置 cwnd。保持心跳（应用层心跳）不仅为了保活，也为了维持 TCP 窗口全开。

---
下一章：[UDP 多播处理 (UDP Multicast)](udp_multicast.md)

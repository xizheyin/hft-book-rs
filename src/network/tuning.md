# TCP/UDP 调优 (TCP/UDP Tuning)

在深入 Kernel Bypass 之前，我们首先要榨干标准内核协议栈的性能。很多时候，仅仅修改几行 `sysctl` 配置或 Socket 选项，就能带来显著的延迟降低。

## 1. 理论基础：TCP 的延迟杀手

TCP 协议设计之初是为了在不可靠的低速网络上提供可靠传输，而不是为了微秒级低延迟。因此，默认配置中包含了很多“延迟杀手”。

### 1.1 Nagle 算法 (Nagle's Algorithm)
- **目的**：减少小包数量，提高网络利用率。
- **机制**：如果发送的数据小于 MSS (Maximum Segment Size)，且之前发送的数据未被 ACK，则缓存该数据，直到凑满 MSS 或收到 ACK。
- **HFT 影响**：极度致命。如果你发送一个 50 字节的订单，Nagle 可能会让你等待 40ms（典型的 Delayed ACK 超时）才发出去。
- **解决**：必须禁用！设置 `TCP_NODELAY`。

### 1.2 延迟确认 (Delayed ACK)
- **目的**：减少 ACK 包的数量，减轻网络负载。
- **机制**：收到数据后不立即回复 ACK，而是等待几十毫秒，看是否有数据要发回（Piggybacking），或者等第二个数据包到达。
- **HFT 影响**：增加 RTT (Round Trip Time)。
- **解决**：在 Linux 上设置 `TCP_QUICKACK`（注意：每次 recv 后可能需要重新设置）。

### 1.3 慢启动 (Slow Start)
- **机制**：连接建立初期，拥塞窗口 (CWND) 很小，随着 ACK 逐渐增大。
- **HFT 影响**：对于长连接（如 FIX 会话），这不是大问题。但对于新建连接，前几个包可能被阻塞。
- **解决**：增大初始拥塞窗口 (`initcwnd`)。

## 2. 核心实现：Socket 选项调优

在 Rust 中，我们通常使用 `socket2` crate 来进行底层配置，或者直接在 `TcpStream` 上设置。

```rust
use std::net::TcpStream;
use std::os::unix::io::AsRawFd;

fn tune_socket(stream: &TcpStream) -> std::io::Result<()> {
    // 1. 禁用 Nagle 算法 (最重要!)
    stream.set_nodelay(true)?;

    // 2. 设置非阻塞模式
    stream.set_nonblocking(true)?;

    // 3. 增大缓冲区 (避免填满导致阻塞/丢包)
    // 注意：过大的缓冲区可能导致 Buffer Bloat (延迟增加)
    // 对于 HFT，通常设置适中即可，如 256KB - 1MB
    let buf_size = 1024 * 1024; 
    // stream.set_recv_buffer_size(buf_size)?;
    // stream.set_send_buffer_size(buf_size)?;
    
    // 4. 设置 QoS / TOS (Type of Service)
    // 告诉路由器：这个包优先级最高 (Low Delay)
    // 对应 IP 头部的 DSCP 字段
    // 需要 libc
    let fd = stream.as_raw_fd();
    unsafe {
        let iptos_lowdelay: i32 = 0x10;
        let res = libc::setsockopt(
            fd,
            libc::IPPROTO_IP,
            libc::IP_TOS,
            &iptos_lowdelay as *const _ as *const libc::c_void,
            std::mem::size_of_val(&iptos_lowdelay) as u32,
        );
        if res < 0 {
            // handle error
        }
        
        // 5. 启用 TCP_BUSY_POLL (Linux 3.11+)
        // 让内核在 recv 调用中忙轮询，而不是挂起等待中断
        // 这可以显著降低延迟 (Latency) 和 抖动 (Jitter)
        let busy_poll_us: i32 = 50; // 轮询 50us
        libc::setsockopt(
            fd,
            libc::SOL_SOCKET,
            libc::SO_BUSY_POLL,
            &busy_poll_us as *const _ as *const libc::c_void,
            std::mem::size_of_val(&busy_poll_us) as u32,
        );
    }

    Ok(())
}
```

## 3. 操作系统级调优 (Sysctl)

除了代码，还需要修改 `/etc/sysctl.conf`。

### 3.1 缓冲区与队列

```bash
# 增大读写缓冲区上限
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 16777216
net.core.wmem_default = 16777216

# 增大 backlog 队列 (防止 SYN Flood 攻击或瞬时高并发丢包)
net.core.netdev_max_backlog = 50000
net.ipv4.tcp_max_syn_backlog = 30000
```

### 3.2 TCP 行为

```bash
# 禁用慢启动重启 (Slow Start Restart)
# 如果连接空闲一段时间，TCP 默认会重置 CWND，导致再次发送数据时变慢
net.ipv4.tcp_slow_start_after_idle = 0

# 启用 BBR 拥塞控制算法 (Linux 4.9+)
# BBR 基于带宽和延迟探测，比传统的 CUBIC 更适合高吞吐低延迟网络
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# 快速回收 TIME_WAIT 连接 (仅在特定场景下开启，NAT 环境慎用)
net.ipv4.tcp_tw_reuse = 1
```

## 4. UDP 调优 (Market Data)

对于行情数据，我们通常使用 UDP (Multicast)。

### 4.1 接收缓冲区

UDP 没有流量控制。如果你的程序处理慢了，或者内核缓冲区满了，包就会被**直接丢弃**。
这是 HFT 中最常见的丢包原因。

**必须**将 UDP 接收缓冲区设置得足够大，以应对微突发 (Micro-bursts)。

```rust
use std::net::UdpSocket;

fn tune_udp(socket: &UdpSocket) {
    // 建议至少 8MB，甚至 32MB
    let buf_size = 32 * 1024 * 1024;
    // socket.set_recv_buffer_size(buf_size).expect("Failed to set recv buffer");
    
    // 实际上，setsockopt 设置的值会被内核加倍 (用于元数据)
    // 并且受限于 net.core.rmem_max
}
```

### 4.2 绑定特定网卡与 CPU

多播流量通常巨大。如果不绑定 CPU，软中断 (SoftIRQ) 可能会在不同核心间跳动，导致缓存失效和乱序。

- 使用 `taskset` 或 `numactl` 绑定进程。
- 配置网卡多队列 (RSS, Receive Side Scaling)，将流量哈希到特定队列，并绑定中断到特定 CPU。

## 5. 性能验证工具

### 5.1 `sockperf`

Google 开发的网络基准测试工具，专注于延迟。

```bash
# Server
sockperf server

# Client (测试 Ping-Pong 延迟)
sockperf ping-pong -i 192.168.1.10 -t 10 --tcp
```

### 5.2 `netstat` / `ss` / `ethtool`

监控丢包和错误：

```bash
# 查看 UDP 丢包 (RcvbufErrors)
cat /proc/net/snmp | grep Udp

# 查看网卡级丢包 (Ring buffer overflow)
ethtool -S eth0 | grep drop
```

如果 `RcvbufErrors` 增加，说明你的应用程序处理太慢（或者调度不及时），导致 Socket 缓冲区溢出。
如果 `rx_missed_errors` (网卡级) 增加，说明 PCIe 带宽不足或 CPU 根本来不及把包从网卡取走 -> 需要 Kernel Bypass (DPDK)。

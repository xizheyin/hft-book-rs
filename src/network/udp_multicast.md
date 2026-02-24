# UDP 多播处理 (UDP Multicast)

在交易所的世界里，市场数据 (Market Data) 是生命之源。为了将海量的订单簿更新推送给所有参与者，交易所通常采用 **UDP 多播 (Multicast)**。
相比 TCP，UDP 没有握手、没有重传、没有拥塞控制，它是真正的“发射后不管 (Fire and Forget)”。

本章将介绍如何高效、可靠地处理这些高速数据流。

## 1. 基础配置

### 1.1 加入多播组
要接收多播数据，你需要加入特定的 IP 组（如 `239.0.0.1`）。

```rust
use socket2::{Socket, Domain, Type, Protocol};
use std::net::{Ipv4Addr, SocketAddrV4};

fn join_multicast(interface_ip: Ipv4Addr, multicast_ip: Ipv4Addr, port: u16) -> Socket {
    let socket = Socket::new(Domain::IPV4, Type::DGRAM, Some(Protocol::UDP)).unwrap();
    
    // 允许地址复用（允许多个进程监听同一端口）
    socket.set_reuse_address(true).unwrap();
    // socket.set_reuse_port(true).unwrap(); // Linux specific
    
    let addr = SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, port);
    socket.bind(&addr.into()).unwrap();
    
    // 关键一步：告诉内核我们要加入哪个组，并通过哪个网卡（interface）接收
    socket.join_multicast_v4(&multicast_ip, &interface_ip).unwrap();
    
    socket
}
```

### 1.2 SO_RCVBUF
UDP 缓冲区溢出是丢包的头号杀手。如果你的程序处理不过来，内核缓冲区满了，新来的包就会被静默丢弃。
**建议**: 设置为系统允许的最大值（如 16MB 或更大）。

```bash
# 系统层面
sysctl -w net.core.rmem_max=16777216
```

```rust
// 代码层面
socket.set_recv_buffer_size(16 * 1024 * 1024).unwrap();
```

## 2. 丢包检测与恢复 (Gap Detection & Recovery)

UDP 不保证可靠传输。在网络拥塞时，你可能会发现 Sequence Number 跳变：
`100, 101, 102, 104, 105` (丢了 103)。

### 2.1 序列号检查
交易所的协议（如 ITCH, SBE）通常会在包头包含一个 `Sequence Number`。

```rust
struct GapDetector {
    next_seq: u64,
}

impl GapDetector {
    fn on_packet(&mut self, seq: u64, count: u64) {
        if seq > self.next_seq {
            println!("GAP DETECTED! Expected {}, got {}", self.next_seq, seq);
            // 触发重传逻辑
        } else if seq < self.next_seq {
            // 可能是乱序包，或者是 A/B 通道的重复包
        }
        
        self.next_seq = seq + count;
    }
}
```

### 2.2 恢复策略
1.  **Snapshot (快照)**: 如果丢包严重，直接请求最新的全量快照（如 TCP 连接）。
2.  **Retransmission (重传)**: 向交易所的 TCP 重传服务器请求特定的 Seq 范围（如 "Give me 103"）。
3.  **Ignore (忽略)**: 如果只是 Level 2 的某个价格更新丢了，且后续包覆盖了该价格，可能可以忽略。

## 3. A/B 通道仲裁 (Arbitration)

为了提高可靠性，交易所通常提供两条完全独立的物理线路（Line A 和 Line B），发送完全相同的数据。

**目标**: 无论 A 还是 B，谁先到就用谁。如果 A 丢包了，B 补上。

### 3.1 实现思路
- **单线程轮询**: 在一个线程中轮询 socket A 和 socket B。
- **序列号去重**: 维护一个 `max_seq_processed`。如果收到一个 seq <= max，说明是重复包，直接丢弃。

```rust
loop {
    // 非阻塞读取 A
    if let Ok((size, _)) = socket_a.recv_from(&mut buf) {
        process(buf, &mut state);
    }
    // 非阻塞读取 B
    if let Ok((size, _)) = socket_b.recv_from(&mut buf) {
        process(buf, &mut state);
    }
}
```

## 4. 常见陷阱

1.  **多网卡困境**:
    如果你的机器有多个网卡（eth0, eth1），且它们都能收到多播流量。如果不指定 Interface，内核可能会走默认路由，导致你收不到数据，或者从错误的网卡收数据。
    **解决**: 始终显式指定 `join_multicast_v4` 的 `interface` 参数。

2.  **IGMP Snooping**:
    交换机通常会开启 IGMP Snooping。如果你不发送 IGMP Join 报文，交换机不会把多播包转发给你。确保你的程序正确调用了 `join_multicast`。

3.  **大包分片 (Fragmentation)**:
    尽量避免 IP 分片。如果 UDP 包超过 MTU (1500)，会被分片。只要其中一个分片丢了，整个 UDP 包就废了。

---
下一章：[协议解析 (Protocols)](../protocols/README.md) - 我们将学习如何解析 ITCH, SBE, FIX 等二进制协议。

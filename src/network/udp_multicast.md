# UDP 多播处理 (UDP Multicast)

在交易所的世界里，市场数据 (Market Data) 是生命之源。为了将海量的订单簿更新推送给所有参与者，交易所通常采用 **UDP 多播 (Multicast)**。
相比 TCP，UDP 没有握手、没有重传、没有拥塞控制，它是真正的“发射后不管 (Fire and Forget)”。

本章将介绍如何高效、可靠地处理这些高速数据流。

## 1. 基础配置

### 1.1 加入多播组
要接收多播数据，你需要加入特定的 IP 组（如 `239.0.0.1`）。

下面使用第三方 `socket2`，因为它能暴露地址复用和接收缓冲等底层选项。代码依赖真实网卡、路由与组播环境，所以标为 `ignore`；验证时在独立 Cargo 项目执行 `cargo add socket2`、`cargo check`，再在隔离 network namespace/VLAN 中用发送端与抓包/计数器做集成测试。

```rust,ignore
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
Socket 缓冲区溢出是常见丢包原因之一；包也可能丢在交换机、NIC ring 或内核 backlog。接收缓冲要能吸收实测 microburst，但不是无脑设为系统最大值：过大的队列会积压过期行情并掩盖应用长期处理不过来的事实。

```bash
# 系统层面
sysctl -w net.core.rmem_max=16777216
```

下面一行延续上一段的 `socket2::Socket`，不是独立程序；系统还可能把请求值翻倍或受 `rmem_max` 限制，因此启动时应读回实际值并记录。

```rust,ignore
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
3.  **按协议降级或跳过**: 只有 feed 规范明确说明后续消息能完整覆盖缺失状态时才可跳过。维护订单簿的增量消息通常不能随意忽略，否则本地状态会永久错误。

## 3. A/B 通道仲裁 (Arbitration)

为了提高可靠性，交易所通常提供两条完全独立的物理线路（Line A 和 Line B），发送完全相同的数据。

**目标**: 无论 A 还是 B，谁先到就用谁。如果 A 丢包了，B 补上。

### 3.1 实现思路
- **单线程轮询**: 在一个线程中轮询 socket A 和 socket B。
- **序列号仲裁**: 按协议的 packet sequence 与 message count 维护下一个期望范围。不能只用 `max_seq_processed`：一包可能包含多条消息，A/B 还可能乱序，必须保留有限窗口并在确认两路都缺失后触发恢复。

下面是**教学骨架**：`socket_a/socket_b`、buffer、频道枚举和仲裁状态由完整应用提供。它只表达“两路都要轮询”，不能直接用于生产；验证应注入重复、乱序、单路/双路丢包和 sequence wrap，并检查只应用一次且能进入恢复状态。

```rust,ignore
loop {
    // 非阻塞读取 A
    if let Ok((size, _)) = socket_a.recv_from(&mut buf_a) {
        process(&buf_a[..size], Channel::A, &mut state);
    }
    // 非阻塞读取 B
    if let Ok((size, _)) = socket_b.recv_from(&mut buf_b) {
        process(&buf_b[..size], Channel::B, &mut state);
    }
}
```

## 4. 常见陷阱

1.  **多网卡困境**:
    如果你的机器有多个网卡（eth0, eth1），且它们都能收到多播流量。如果不指定 Interface，内核可能会走默认路由，导致你收不到数据，或者从错误的网卡收数据。
    **解决**: 始终显式指定 `join_multicast_v4` 的 `interface` 参数。

2.  **IGMP Snooping**:
    程序加入组后由内核发送 IGMP membership report，交换机可以通过 snooping 学习成员端口。还要检查 VLAN、querier、组播路由和 membership 是否过期，不能只确认 `join_multicast` 返回成功。

3.  **大包分片 (Fragmentation)**:
    尽量避免 IP 分片。如果 UDP 包超过 MTU (1500)，会被分片。只要其中一个分片丢了，整个 UDP 包就废了。

---
下一章：[交易所协议详解](../connectivity/protocols.md) —— 继续学习 FIX、ITCH、SBE、OUCH 等文本或二进制协议如何编码与解析。

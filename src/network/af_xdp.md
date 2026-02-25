# AF_XDP 实战 (AF_XDP in Action)

AF_XDP (Address Family eXpress Data Path) 是 Linux 内核 4.18 引入的一种高性能网络套接字。它旨在在不牺牲 Linux 内核网络栈灵活性的前提下，提供媲美 DPDK 的性能。

对于 Rust 开发者来说，AF_XDP 是一个比 DPDK 更“亲民”的选择，因为它不需要接管整个网卡，可以与现有的内核工具（如 `ethtool`, `tcpdump`）共存。

## 1. 核心架构：UMEM 与 Ring Buffers

AF_XDP 的核心思想是**零拷贝**。它通过共享内存（UMEM）在内核和用户态之间传递数据包，避免了传统 Socket 的 `sk_buff` 分配和内存拷贝。

AF_XDP 使用四个 Ring Buffer 进行通信：

1.  **Fill Ring**: 用户态 -> 内核。用户态将空闲的 UMEM 帧地址放入此环，供内核接收数据包使用。
2.  **RX Ring**: 内核 -> 用户态。内核将接收到的数据包描述符（地址、长度）放入此环。
3.  **TX Ring**: 用户态 -> 内核。用户态将要发送的数据包描述符放入此环。
4.  **Completion Ring**: 内核 -> 用户态。内核通知用户态哪些发送缓冲区已经发送完毕，可以回收。

## 2. Rust 生态支持

目前 Rust 对 AF_XDP 的支持主要通过以下库：
*   **aya**: 专注于 eBPF 开发的 Rust 库，支持加载 XDP 程序。
*   **libbpf-sys**: libbpf 的 FFI 绑定。
*   **af-xdp**: 一个封装良好的 Rust crate（推荐）。

## 3. 实现步骤

### 3.1 创建 UMEM

首先，我们需要分配一块大内存区域作为 UMEM，并将其注册到 Socket。

```rust
use std::os::unix::io::AsRawFd;

// 伪代码示例
struct Umem {
    data: Vec<u8>,
    // ...
}

impl Umem {
    pub fn new(config: UmemConfig) -> Self {
        // 使用 mmap 分配对齐的内存
        let layout = Layout::from_size_align(config.frame_size * config.num_frames, 4096).unwrap();
        let data = unsafe { alloc_zeroed(layout) };
        // 调用 setsockopt 注册 UMEM
    }
}
```

### 3.2 绑定 Socket (XSK)

创建 `AF_XDP` 类型的 Socket，并绑定到特定的网卡队列。

```rust
pub fn create_socket(if_name: &str, queue_id: u32, umem: &Umem) -> Result<Socket> {
    // 1. 加载 XDP BPF 程序到网卡
    // 2. 创建 Socket: socket(AF_XDP, SOCK_RAW, 0)
    // 3. 绑定: bind(fd, sockaddr_xdp)
    // 4. 关键：启用 Zero Copy 模式
    // let bind_flags = XDP_ZEROCOPY | XDP_COPY; 
}
```

### 3.3 轮询循环 (Busy Loop)

与 DPDK 类似，AF_XDP 也需要一个死循环来处理收发包。

```rust
pub fn run_loop(mut socket: Socket, mut umem: Umem) {
    let mut rx_descs = [0u64; 32];
    
    loop {
        // 1. 填充 Fill Ring (告诉内核哪里有空闲内存收包)
        let n_free = umem.fill_ring.produce(32);
        
        // 2. 接收数据包 (消费 RX Ring)
        let n_recv = socket.rx_ring.consume(&mut rx_descs);
        
        for i in 0..n_recv {
            let desc = rx_descs[i];
            let pkt_data = umem.get_frame(desc.addr, desc.len);
            
            // 处理数据包...
            process_packet(pkt_data);
            
            // 处理完后，将 frame 地址放回 Fill Ring
        }
        
        // 3. 触发内核收包 (如果 RX Ring 为空，可能需要 syscall 唤醒)
        if n_recv == 0 {
             // 只有在非 busy-poll 模式下才需要这个 syscall
             // libc::recvfrom(socket.fd, ...);
        }
    }
}
```

## 4. 关键优化：Busy Polling

默认情况下，AF_XDP 在 RX Ring 为空时会阻塞。为了获得最低延迟，我们需要启用 **Busy Polling**。

在 Linux 5.11+，推荐使用 `SO_PREFER_BUSY_POLL` 和 `SO_BUSY_POLL` 选项。

```rust
// 设置 Socket 选项
let val: u32 = 1;
setsockopt(fd, SOL_SOCKET, SO_PREFER_BUSY_POLL, &val, ...);
let time_us: u32 = 0; // 0 表示一直轮询
setsockopt(fd, SOL_SOCKET, SO_BUSY_POLL, &time_us, ...);
```

启用后，内核会不断轮询网卡队列，一旦有包到达立即放入 RX Ring，无需中断唤醒。

## 5. AF_XDP vs DPDK

| 特性 | AF_XDP | DPDK |
| :--- | :--- | :--- |
| **内核旁路** | 部分旁路 (保留内核控制面) | 完全旁路 |
| **驱动依赖** | 通用 (只要网卡支持 XDP) | 特定 PMD 驱动 |
| **工具兼容性** | 完美 (tcpdump, iptables 可用) | 不兼容 (网卡对 OS 消失) |
| **性能** | 极高 (单核 10Mpps+) | 极致 (单核 14Mpps+) |
| **开发难度** | 中等 | 高 |

## 6. 总结

对于大多数不想维护复杂的 DPDK 依赖栈的 Rust HFT 项目，**AF_XDP 是最佳的平衡点**。它提供了接近 DPDK 的性能，同时保留了 Linux 强大的网络管理功能。

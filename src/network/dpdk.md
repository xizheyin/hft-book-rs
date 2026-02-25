# DPDK 集成 (DPDK Integration)

DPDK (Data Plane Development Kit) 是高性能网络应用的“核武器”。它通过绕过操作系统内核（Kernel Bypass），让用户态程序直接接管网卡，从而实现极高的吞吐量（单核 10Gbps+）和极低的延迟（< 10µs）。

对于 Rust HFT 系统来说，集成 DPDK 是通往极致性能的必经之路，但也是最具挑战性的一环。

## 1. 为什么选择 DPDK？

传统 Socket API 的瓶颈在于：
1.  **系统调用开销**: `recv/send` 需要上下文切换。
2.  **内存拷贝**: 网卡 -> 内核缓冲区 -> 用户缓冲区。
3.  **中断风暴**: 高负载下，频繁的硬中断会打断 CPU 流水线。

DPDK 通过以下技术解决这些问题：
1.  **UIO / VFIO**: 将网卡寄存器映射到用户空间。
2.  **Hugepages**: 使用大页内存（2MB/1GB）减少 TLB Miss。
3.  **PMD (Poll Mode Driver)**: 轮询模式驱动，100% 占用 CPU 核心，完全消除中断。
4.  **Zero Copy**: 数据包直接写入用户态内存池（Mempool）。

## 2. Rust 与 DPDK 的集成挑战

DPDK 是用 C 语言编写的，且严重依赖宏和内联函数。在 Rust 中使用 DPDK 主要面临两个挑战：
1.  **FFI 复杂性**: `bindgen` 生成的绑定非常庞大且不安全。
2.  **所有权模型冲突**: DPDK 的 `rte_mbuf` 管理（引用计数、内存池）需要小心映射到 Rust 的生命周期。

### 2.1 现有方案
*   **dpdk-rs**: 原始的 bindgen 绑定。
*   **capsule**: 一个未维护但设计优秀的 Rust DPDK 框架。
*   **手动绑定**: 对于 HFT，我们通常只用到 DPDK 的一小部分功能（EAL, Ethdev, Ring），因此推荐**手动维护最小化绑定**或基于 bindgen 进行封装。

## 3. 核心组件架构

### 3.1 EAL (Environment Abstraction Layer)
EAL 负责初始化硬件、内存和 CPU 核心。

```rust
use std::ffi::CString;
use std::os::raw::{c_char, c_int};

// 链接 DPDK 库
#[link(name = "dpdk")]
extern "C" {
    fn rte_eal_init(argc: c_int, argv: *mut *mut c_char) -> c_int;
}

pub fn init_eal() {
    let args = vec![
        "hft_engine",
        "-l", "1",       // 使用 Core 1
        "--proc-type", "auto",
    ];
    
    // 将 Rust 字符串转换为 C 风格参数...
    // unsafe { rte_eal_init(...) };
}
```

### 3.2 Mempool 与 Mbuf
这是 DPDK 的核心。`rte_mbuf` 是存放数据包的结构体。我们需要在启动时预分配一个巨大的内存池。

```rust
struct MbufPool {
    ptr: *mut rte_mempool,
}

impl MbufPool {
    pub fn new(name: &str, n: u32) -> Self {
        // rte_pktmbuf_pool_create(...)
    }
    
    pub fn alloc(&self) -> Option<Mbuf> {
        // rte_pktmbuf_alloc(...)
    }
}
```

### 3.3 PMD 轮询循环
这是 HFT 引擎的主循环。

```rust
pub fn run_loop(port_id: u16, queue_id: u16) {
    let mut pkts: [*mut rte_mbuf; 32] = [std::ptr::null_mut(); 32];
    
    loop {
        // 1. 批量接收数据包 (RX Burst)
        let nb_rx = unsafe {
            rte_eth_rx_burst(port_id, queue_id, pkts.as_mut_ptr(), 32)
        };

        if nb_rx > 0 {
            for i in 0..nb_rx {
                let mbuf = pkts[i as usize];
                process_packet(mbuf);
                
                // 处理完必须释放，除非将其发送出去
                // rte_pktmbuf_free(mbuf);
            }
        }
        
        // 2. 发送逻辑 (TX)
        // ...
        
        // 3. 其它周期性任务
    }
}
```

## 4. 零拷贝数据包解析

在收到 `rte_mbuf` 后，我们可以直接将其数据段转换为 Rust 的 Slice，通过 `nom` 或手动解析。

```rust
struct PacketView<'a> {
    data: &'a [u8],
}

impl<'a> PacketView<'a> {
    fn from_mbuf(mbuf: *mut rte_mbuf) -> Self {
        unsafe {
            let data_ptr = rte_pktmbuf_mtod(mbuf, *mut u8);
            let data_len = rte_pktmbuf_data_len(mbuf);
            Self {
                data: std::slice::from_raw_parts(data_ptr, data_len as usize),
            }
        }
    }
    
    fn parse_udp(&self) -> Option<UdpPayload> {
        // 解析 Ethernet -> IP -> UDP 头
        // 返回 payload 的切片，零拷贝
    }
}
```

## 5. 性能优化 Checklist

1.  **Batch Size**: `rx_burst` 的大小通常设为 32。太小会导致函数调用开销过大，太大会增加延迟。
2.  **Hugepages**: 确保系统预留了足够的 1GB 大页。
3.  **Core Isolation**: 在 Linux 启动参数中添加 `isolcpus=1`，并将 DPDK 线程绑定到 Core 1，防止内核任务抢占。
4.  **DDIO (Data Direct I/O)**: 确保网卡直接将数据包写入 L3 缓存（Intel CPU 特性），避免内存读写。
5.  **Prefetch**: 在处理当前包时，预取下一个包的 header 到 L1 缓存。

```rust
// 软件预取示例
if i + 1 < nb_rx {
    let next_mbuf = pkts[i + 1];
    rte_prefetch0(rte_pktmbuf_mtod(next_mbuf, *const c_void));
}
```

## 6. 总结

DPDK 是 Rust HFT 系统的终极优化手段。虽然它引入了大量的 `unsafe` 代码和复杂的构建流程，但它带来的微秒级延迟收益是巨大的。

对于初学者，建议先使用 `AF_XDP`（下一章介绍），因为它更符合 Linux 哲学且安全性更好。但对于顶级的 HFT 策略，DPDK 仍然是不可替代的王者。

# 内核旁路技术 (Kernel Bypass)

在标准网络编程中，我们使用 `socket` API (如 `TcpStream::connect`)。这背后发生了什么？
1.  **Syscall**: 你的程序发起系统调用，陷入内核态 (Context Switch)。
2.  **Copy**: 内核将数据从用户空间拷贝到内核缓冲区 (sk_buff)。
3.  **Protocol Stack**: 内核执行 TCP/IP 协议栈逻辑（校验和、路由、防火墙 iptables）。
4.  **Driver**: 驱动程序将数据放入网卡队列。
5.  **Interrupt**: 网卡发送完成后中断 CPU。

这一套流程在 Web 服务器上工作得很好，但在 HFT 中，这些都是**不可接受的开销**。

**Kernel Bypass (内核旁路)** 的核心思想是：**让用户态程序直接控制网卡**，完全跳过操作系统内核。

## 1. 主流技术方案

### 1.1 对比：内核栈 vs 旁路

```mermaid
graph TD
    subgraph Kernel Stack
        App1[Application] -->|Syscall| Socket[BSD Socket]
        Socket -->|Copy| KBuf[Kernel Buffer (sk_buff)]
        KBuf -->|TCP/IP| Stack[Protocol Stack]
        Stack -->|Driver| NIC1[NIC Driver]
        NIC1 -->|Interrupt| HW1[Hardware NIC]
    end
    
    subgraph Kernel Bypass
        App2[Application] -->|DMA / Zero Copy| Ring[Userspace Ring]
        Ring -->|Poll Mode| PMD[PMD Driver]
        PMD -->|PCIe| HW2[Hardware NIC]
    end
    
    style App2 fill:#dfd,stroke:#333
    style Ring fill:#dfd,stroke:#333
    style PMD fill:#f96,stroke:#333
    style KBuf fill:#f99,stroke:#333
    style Stack fill:#f99,stroke:#333
```

### 1.2 DPDK (Data Plane Development Kit)
Intel 推出的开源框架，是目前最通用的方案。
- **原理**: 使用 UIO (Userspace I/O) 或 VFIO 驱动，将网卡寄存器映射到用户空间。
- **特点**: 
    - **Poll Mode Driver (PMD)**: 不使用中断，而是死循环轮询网卡，消除了中断开销。
    - **Hugepages**: 使用大页内存，减少 TLB Miss。
    - **Zero Copy**: 数据直接写入 DMA 区域。
- **缺点**: 即使没有流量，也会占满 100% CPU。需要自己实现 TCP/IP 栈（或者使用 Seastar, F-Stack）。

### 1.2 Solarflare OpenOnload / TCPDirect
Solarflare (现属 AMD) 网卡的独门绝技。
- **OpenOnload**: 透明加速。不需要修改一行代码，只需 `LD_PRELOAD` 库，就能拦截 socket 调用并走旁路。延迟可降至 ~2µs。
- **TCPDirect (ef_vi)**: 更底层的 API，类似 DPDK，但提供了硬件级 TCP 卸载。延迟可降至 < 1µs。
- **优点**: 极低延迟，硬件级 TCP 协议栈（部分）。
- **缺点**: 绑定硬件厂商，闭源且昂贵。

## 2. Rust 与 Kernel Bypass

在 Rust 中使用 Kernel Bypass 通常涉及 FFI 调用 C 库。

### 2.1 DPDK Bindings
Rust 社区有 `dpdk-rs` 等库，但通常比较底层。

```rust
// 伪代码：DPDK 接收循环
pub fn run_dpdk_loop(port_id: u16, queue_id: u16) {
    let burst_size = 32;
    let mut mbufs:Vec<*mut rte_mbuf> = Vec::with_capacity(burst_size);

    loop {
        // 直接调用 C 函数轮询网卡
        let nb_rx = unsafe {
            rte_eth_rx_burst(port_id, queue_id, mbufs.as_mut_ptr(), burst_size)
        };

        if nb_rx > 0 {
            for i in 0..nb_rx {
                let mbuf = mbufs[i];
                process_packet(mbuf);
                // 处理完必须释放
                unsafe { rte_pktmbuf_free(mbuf); }
            }
        }
    }
}
```

### 2.2 Solarflare ef_vi (Rust 封装)
如果你有 Solarflare 网卡，可以使用 `solarflare-rs` (假设的库名，通常需要自己封装)。

```rust
// 伪代码：从 ef_vi 环中读取
fn poll_ef_vi(vi: &EfVi) {
    loop {
        // 检查 Event Queue
        if let Some(event) = vi.poll_event() {
            match event {
                EventType::Rx(pkt_id) => {
                    let payload = vi.get_packet(pkt_id);
                    // 零拷贝解析: 直接把 bytes 转为 struct
                    let market_data = unsafe { 
                        &*(payload.as_ptr() as *const MarketData) 
                    };
                    on_market_data(market_data);
                    
                    // 把 Buffer 还给网卡
                    vi.refill(pkt_id);
                }
                _ => {}
            }
        }
    }
}
```

## 3. 混合架构 (Hybrid Architecture)

完全重写 TCP 栈太痛苦且容易出错。HFT 系统通常采用**混合架构**：

- **Control Path (控制流)**: 使用标准 `std::net::TcpStream`。负责登录、心跳、非关键查询。走内核栈。
- **Data Path (数据流)**: 使用 Kernel Bypass。
    - **UDP Market Data**: 使用 DPDK/ef_vi 直接收包。
    - **TCP Order Entry**: 如果交易所支持，使用 TCPDirect；否则使用内核栈并开启 Busy Poll。

## 4. 常见陷阱

1.  **ARP 处理**: 
    绕过内核后，网卡不会自动回复 ARP 请求。你的程序必须自己解析 ARP 包并回复，否则交换机会“忘记”你的 MAC 地址，导致断网。
    
2.  **隔离 CPU**:
    运行 DPDK 的核心必须在启动参数中隔离 (`isolcpus`)，否则内核任务调度会打断轮询，造成数十微秒的延迟尖峰。

3.  **调试困难**:
    `tcpdump` 抓不到包了！因为包没过内核。
    **解决**: 使用网卡的 Port Mirroring，或者在代码里加采样日志。

## 5. 延伸阅读

- [Intel DPDK Documentation](https://doc.dpdk.org/guides/)
- [OpenOnload User Guide](https://support.solarflare.com/)
- [Smoltcp](https://github.com/smoltcp-rs/smoltcp) - 一个纯 Rust 编写的嵌入式 TCP/IP 栈，常用于配合 DPDK。

---
下一章：[TCP 协议优化 (TCP Optimization)](tcp_optimization.md)

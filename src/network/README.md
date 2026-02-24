# 网络篇 (Network)

在 HFT 系统中，网络不仅仅是传输数据的管道，它是战场的最前线。
当你在交易所的撮合引擎收到成交确认时，实际上你已经比竞争对手慢了几微秒。真正的竞争发生在你按下“发送”按钮的那一刻，甚至更早——发生在你的网卡收到行情数据的那一纳秒。

本章将带你深入 Linux 网络栈的深渊，并教你如何绕过它。

## 章节概览

1.  **[内核旁路技术 (Kernel Bypass)](kernel_bypass.md)**
    *   为什么 `epoll` 还不够快？
    *   用户态网络栈原理 (DPDK, Solarflare OpenOnload)。
    *   如何让 Rust 代码直接与网卡对话。

2.  **[TCP 协议优化 (TCP Optimization)](tcp_optimization.md)**
    *   Nagle 算法与 Delayed ACK 的致命组合。
    *   Socket 缓冲区调优。
    *   Busy Polling 与低延迟读写。

3.  **[UDP 多播处理 (UDP Multicast)](udp_multicast.md)**
    *   处理交易所的高速行情数据流 (Market Data Feed)。
    *   多播组管理与 IGMP。
    *   丢包检测与 A/B 通道仲裁。

4.  **[FPGA 互联 (FPGA Interconnect)](fpga.md)**
    *   (高级话题) 当软件已经达到物理极限，如何与 FPGA 协同工作。

## 关键指标

在网络编程中，我们关注两个核心指标：

- **RTT (Round Trip Time)**: 往返时延。对于同城交易所，这通常在 100µs - 2ms 之间。
- **Jitter (抖动)**: 延迟的标准差。在 HFT 中，抖动比平均延迟更可怕。我们追求的是**确定性的低延迟**。

准备好抛弃 `std::net::TcpStream` 了吗？让我们开始吧。

# HFT 生态概览 (Ecosystem)

Rust 的高性能生态正在飞速发展。虽然不如 C++ 成熟，但在某些细分领域（如安全性、构建工具、包管理）已经超越了 C++。

以下是构建 HFT 系统时不可或缺的 Rust 库（Crates）：

## 1. 并发与底层优化
*   **[crossbeam](https://github.com/crossbeam-rs/crossbeam)**: 提供了无锁队列（ArrayQueue, SegQueue）、Epoch-based 内存回收、Cache-padded 原子类型等。这是 HFT 的基石。
*   **[parking_lot](https://github.com/Amanieu/parking_lot)**: 比标准库更小、更快、更灵活的 Mutex 和 RwLock。
*   **[memmap2](https://github.com/RazrFalcon/memmap2)**: 内存映射文件（mmap）的安全封装，用于读取历史数据或共享内存 IPC。
*   **[ahash](https://github.com/tkaitchuck/aHash)**: 极速非加密 Hash 算法，专门利用 AES 指令集加速，比标准库的 SipHash 快数倍。

## 2. 网络与异步运行时
*   **[mio](https://github.com/tokio-rs/mio)**: 轻量级非阻塞 I/O 库（epoll/kqueue 封装），构建 Event Loop 的基础。
*   **[socket2](https://github.com/rust-lang/socket2)**: 提供了比标准库更底层的 Socket 配置能力（如 `SO_BUSY_POLL`, `SO_REUSEPORT`）。
*   **[glommio](https://github.com/DataDog/glommio)**: 基于 `io_uring` 和 Thread-per-Core 模型的异步运行时，比 tokio 更适合磁盘 I/O 密集型任务。
*   **[bytes](https://github.com/tokio-rs/bytes)**: 高效的字节缓冲区管理，支持零拷贝切片。

## 3. 序列化与数据处理
*   **[serde](https://github.com/serde-rs/serde)**: 序列化框架的标准。
*   **[bincode](https://github.com/bincode-org/bincode)**: 极速二进制序列化格式。
*   **[rkyv](https://github.com/rkyv/rkyv)**: **零拷贝反序列化**框架。它保证序列化后的字节布局与内存中的结构体一致，直接强转指针即可使用，无需 parsing。这对 HFT 极其重要。
*   **[simd-json](https://github.com/simd-lite/simd-json)**: 利用 SIMD 指令加速 JSON 解析（虽然 HFT 尽量不用 JSON，但某些交易所配置接口还是需要的）。

## 4. 监控与分析
*   **[hdrhistogram](https://github.com/HdrHistogram/HdrHistogram_rust)**: 高动态范围直方图，记录延迟分布的神器。
*   **[criterion](https://github.com/bheisler/criterion.rs)**: 统计学严谨的基准测试（Benchmark）框架。
*   **[iai](https://github.com/bheisler/iai)**: 基于 Cachegrind 的一次性基准测试，结果更稳定，不受机器负载影响。

## 5. FFI 与 硬件交互
*   **[bindgen](https://github.com/rust-lang/rust-bindgen)**: 自动生成 C 库的 Rust 绑定（如 DPDK, Onload）。
*   **[core_affinity](https://github.com/Elzair/core_affinity_rs)**: 用于将线程绑定到特定的 CPU 核心。

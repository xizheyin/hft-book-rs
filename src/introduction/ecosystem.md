# 低延迟系统 Rust 生态概览 (Ecosystem)

Rust 的高性能生态正在持续成熟。虽然它在某些传统系统软件领域仍不如 C++ 积累深厚，但在安全性、构建工具、依赖管理与库设计一致性方面，已经形成了鲜明优势。

以下是构建低延迟系统时经常会接触到的一组 Rust 库（Crates）：

## 1. 并发与底层优化
*   **[crossbeam](https://github.com/crossbeam-rs/crossbeam)**: 提供无锁队列、Epoch-based 内存回收和并发工具。它常用于高性能系统，但具体队列是否适合热路径仍要按生产者/消费者数量和背压要求选择。
*   **[parking_lot](https://github.com/Amanieu/parking_lot)**: 提供紧凑且功能丰富的 Mutex 和 RwLock。它在许多负载下表现很好，但“比标准库快”不是无条件结论，应对目标竞争模式做基准。
*   **[memmap2](https://github.com/RazrFalcon/memmap2)**: 内存映射文件（mmap）的安全封装，用于读取历史数据或共享内存 IPC。
*   **[ahash](https://github.com/tkaitchuck/aHash)**: 面向性能的非加密哈希实现，可在支持的硬件上利用 AES 指令。使用前要评估输入是否可能由攻击者控制，并在目标数据分布上测量，而不是套用固定倍数。

## 2. 网络与异步运行时
*   **[mio](https://github.com/tokio-rs/mio)**: 轻量级非阻塞 I/O 库（epoll/kqueue 封装），构建 Event Loop 的基础。
*   **[socket2](https://github.com/rust-lang/socket2)**: 提供了比标准库更底层的 Socket 配置能力（如 `SO_BUSY_POLL`, `SO_REUSEPORT`）。
*   **[glommio](https://github.com/DataDog/glommio)**: 基于 `io_uring` 与 thread-per-core 思路的运行时，适合研究单核执行器和分片 I/O；是否优于 Tokio 取决于 I/O 类型、生态需求和部署内核。
*   **[bytes](https://github.com/tokio-rs/bytes)**: 高效的字节缓冲区管理，支持零拷贝切片。

## 3. 序列化与数据处理
*   **[serde](https://github.com/serde-rs/serde)**: 序列化框架的标准。
*   **[bincode](https://github.com/bincode-org/bincode)**: 极速二进制序列化格式。
*   **[rkyv](https://github.com/rkyv/rkyv)**: 面向归档数据的零拷贝反序列化框架，可直接访问归档表示中的字段。外部字节仍需考虑校验、对齐、版本兼容和不受信输入，不能把任意数据直接强转为可信结构体。
*   **[simd-json](https://github.com/simd-lite/simd-json)**: 利用 SIMD 指令加速 JSON 解析（虽然 HFT 尽量不用 JSON，但某些交易所配置接口还是需要的）。

## 4. 监控与分析
*   **[hdrhistogram](https://github.com/HdrHistogram/HdrHistogram_rust)**: 高动态范围直方图，可在较大数值范围内记录延迟分布；配置精度、范围和 coordinated omission（协调遗漏）处理方式会影响结论。
*   **[criterion](https://github.com/bheisler/criterion.rs)**: 统计学严谨的基准测试（Benchmark）框架。
*   **[iai-callgrind](https://github.com/iai-callgrind/iai-callgrind)**: 基于 Valgrind/Callgrind 统计指令和缓存相关事件，适合做确定性更强的成本对比；它是模拟/插桩结果，不能替代真实机器上的端到端延迟测试。

## 5. FFI 与 硬件交互
*   **[bindgen](https://github.com/rust-lang/rust-bindgen)**: 自动生成 C 库的 Rust 绑定（如 DPDK, Onload）。
*   **[core_affinity](https://github.com/Elzair/core_affinity_rs)**: 用于将线程绑定到特定的 CPU 核心。

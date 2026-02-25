# 开源项目资源 (Resources)

虽然顶级的 HFT 系统都是闭源的，但我们可以从以下开源项目中汲取灵感。

## 1. 交易系统与回测框架
*   **[Nautilus Trader](https://github.com/nautechsystems/nautilus_trader)**
    *   基于 Rust (核心) 和 Python (Cython) 的高性能回测与实盘交易平台。它是目前开源界架构最接近专业水准的 Rust 交易系统。
*   **[Barter-rs](https://github.com/barter-rs/barter)**
    *   一套模块化的 Rust 交易库，包含数据流（Data）、执行（Execution）和集成（Integration）。

## 2. 网络与底层库
*   **[Smoltcp](https://github.com/smoltcp-rs/smoltcp)**
    *   一个独立的、事件驱动的 TCP/IP 栈，专为裸机（Bare-metal）实时系统设计。对于想要自己实现 TCP 协议栈的同学很有参考价值。
*   **[Glommio](https://github.com/DataDog/glommio)**
    *   Datadog 开源的 Thread-per-Core 运行时，展示了如何利用 `io_uring` 和 CPU 亲和性。

## 3. 市场数据工具
*   **[Databento](https://databento.com/)**
    *   虽然是商业公司，但他们开源了一些高性能的 Python/Rust 客户端和数据格式标准（DBN），其设计非常优秀。

## 4. 有用的工具集
*   **[FlameGraph](https://github.com/brendangregg/FlameGraph)**
    *   性能分析可视化工具。
*   **[Hotspot](https://github.com/KDAB/hotspot)**
    *   Linux perf GUI 查看器。

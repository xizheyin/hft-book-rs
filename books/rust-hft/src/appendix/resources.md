# 开源项目资源 (Resources)

真实交易系统通常包含大量专有组件，但开源项目仍适合学习模块边界、API 设计和测试方法。它们不是生产能力或收益的保证；阅读时要核对版本、维护状态、许可证和适用市场。

## 1. 交易系统与回测框架
*   **[Nautilus Trader](https://github.com/nautechsystems/nautilus_trader)**
    *   使用 Rust 与 Python 的回测/实盘交易平台，可用于观察事件模型、订单状态和适配器边界。不要把其抽象直接等同于交易所共址热路径。
*   **[Barter-rs](https://github.com/barter-rs/barter)**
    *   一套模块化的 Rust 交易库，包含数据流（Data）、执行（Execution）和集成（Integration）。

## 2. 网络与底层库
*   **[Smoltcp](https://github.com/smoltcp-rs/smoltcp)**
    *   面向资源受限或裸机等环境的独立 TCP/IP 栈。它适合学习协议栈结构；自行维护网络栈的正确性、安全性和运维成本很高。
*   **[Glommio](https://github.com/DataDog/glommio)**
    *   Datadog 开源的 Thread-per-Core 运行时，展示了如何利用 `io_uring` 和 CPU 亲和性。

## 3. 市场数据工具
*   **[Databento](https://databento.com/)**
    *   商业数据服务及其开源客户端/DBN 格式实现，可用于研究二进制数据、schema 和多语言接口。数据许可与目标交易所协议需要分别确认。

## 4. 有用的工具集
*   **[FlameGraph](https://github.com/brendangregg/FlameGraph)**
    *   性能分析可视化工具。
*   **[Hotspot](https://github.com/KDAB/hotspot)**
    *   Linux perf GUI 查看器。

# 开源项目资源 (Resources)

真实交易系统通常包含大量专有组件，但开源项目仍适合学习模块边界、API 设计和测试方法。它们不是生产能力或收益的保证；阅读时要核对版本、维护状态、许可证和适用市场。

不要把“跑起来”当作读懂。每次只选一个与你当前章节对应的项目，先画出输入、核心状态、输出和失败路径，再追一条最小调用链并运行相关测试。没有明确学习问题时可以跳过整页；项目数量不是面试指标。

## 1. 交易系统与回测框架
*   **[Nautilus Trader](https://github.com/nautechsystems/nautilus_trader)**
    *   使用 Rust 与 Python 的回测/实盘交易平台，可用于观察事件模型、订单状态和适配器边界。不要把其抽象直接等同于交易所共址热路径。
*   **[Barter-rs](https://github.com/barter-rs/barter)**
    *   一套模块化的 Rust 交易库，包含数据流（Data）、执行（Execution）和集成（Integration）。

## 2. 网络与底层库
*   **[Smoltcp](https://github.com/smoltcp-rs/smoltcp)**
    *   面向资源受限或裸机等环境的独立 TCP/IP 栈。它适合学习协议栈结构；自行维护网络栈的正确性、安全性和运维成本很高。
*   **[Glommio](https://github.com/DataDog/glommio)**
    *   Datadog 开源的 Thread-per-Core（每个核心运行一个主要事件循环）运行时，展示了如何利用 `io_uring` 和 CPU 亲和性。

## 3. 市场数据工具
*   **[Databento](https://databento.com/)**
    *   商业数据服务及其开源客户端/DBN 二进制格式实现，可用于研究市场数据的二进制布局和多语言接口。数据许可与目标交易所协议需要分别确认。

## 4. 有用的工具集
*   **[FlameGraph](https://github.com/brendangregg/FlameGraph)**
    *   性能分析可视化工具。
*   **[Hotspot](https://github.com/KDAB/hotspot)**
    *   用图形界面查看 Linux `perf` CPU 剖析数据的工具。

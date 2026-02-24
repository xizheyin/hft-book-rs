# 交易所协议详解 (Exchange Protocols)

当你解决了网络层的延迟问题，数据包终于抵达了你的内存。现在的挑战是：如何以最快速度理解这些字节的含义？

在 HFT 中，协议解析 (Parsing) 往往是 CPU 消耗的大户。如果解析一个订单簿更新需要 500ns，而你每秒收到 100 万个更新，你就用掉了半个核心。更重要的是，解析延迟直接计入 Tick-to-Trade 延迟。

本章将探讨如何使用 Rust 的**零拷贝 (Zero-copy)** 特性和现代 CPU 指令集来极速解析交易所协议。

## 协议分类

交易所协议主要分为两大类：

### 1. 文本协议 (Text-based)
最典型的是 **FIX (Financial Information eXchange)**。
- **特点**: Key=Value 格式，如 `8=FIX.4.2^9=128^35=D^...`。
- **优点**: 人类可读，兼容性好。
- **缺点**: 解析慢（需要扫描分隔符、转换 ASCII 到整数/浮点数），体积大。
- **现状**: 主要用于**下单 (Order Entry)** 和盘后结算，因为其低频特性和灵活性。

### 2. 二进制协议 (Binary)
如 **NASDAQ ITCH**, **CME SBE (Simple Binary Encoding)**, **Eurex ETI**。
- **特点**: 固定偏移量，紧凑结构。
- **优点**: 极致速度，极小体积。直接映射为 C/Rust 结构体。
- **缺点**: 人类不可读，版本升级可能破坏兼容性。
- **现状**: 绝对统治**行情数据 (Market Data)** 传输，越来越多地用于高性能下单接口 (如 OUCH)。

## Rust 的优势

Rust 在协议解析上具有天然优势：

1.  **Memory Layout Control**: `#[repr(C, packed)]` 让我们能定义与线路协议完全一致的内存结构。
2.  **Zero-copy Parsing**: 直接将网络缓冲区的指针强转为结构体引用，解析耗时接近于 0。
3.  **Nom**: 强大的解析组合子库，在处理变长或复杂协议时，性能依然接近手写 C++。

## 章节概览

1.  **[FIX 协议解析 (Nom & Zero-copy)](fix.md)**
    *   如何手写一个零分配 (Zero-allocation) 的 FIX 解析器。
    *   避免 `String`，全部使用 `&[u8]` 切片。

2.  **[二进制协议 (SBE, ITCH, OUCH)](binary_protocols.md)**
    *   使用 `unsafe` 和 `transmute` 进行直接内存映射。
    *   处理字节序 (Endianness) 的最佳实践。
    *   SBE 的模板与 Schema 处理。

准备好你的十六进制编辑器，我们要深入字节流了。

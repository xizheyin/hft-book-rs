# 二进制协议解析 (Binary Protocols)

在 HFT 中，"Parsing" 这个词通常意味着“什么都不做”。
最快的解析就是不解析。如果内存中的字节布局和网络包的布局完全一致，我们只需要一个 `reinterpret_cast` (C++) 或 `transmute` (Rust)。

## 1. 案例：NASDAQ ITCH 5.0

ITCH 是全球最流行的行情数据协议之一。它非常简单：每个消息都以一个字节的 `Msg Type` 开始。

### 1.1 消息结构定义
关键在于 `#[repr(C, packed)]`。这告诉 Rust 编译器：不要为了对齐而填充字节，严格按照我定义的顺序排列。

```rust
use std::mem;

// Add Order Message (Type 'A')
#[repr(C, packed)]
#[derive(Debug, Clone, Copy)]
pub struct AddOrderMessage {
    pub message_type: u8,       // 'A'
    pub stock_locate: u16,      // Stock Locate
    pub tracking_number: u16,   // Tracking Number
    pub timestamp: u64,         // Nanoseconds from midnight (48 bits in protocol, need handling)
    pub order_reference: u64,   // Order Reference Number
    pub buy_sell_indicator: u8, // 'B' or 'S'
    pub shares: u32,            // Integer number of shares
    pub stock: [u8; 8],         // Stock Symbol (ASCII)
    pub price: u32,             // 4 decimal digits
}

// 确保编译器没有偷偷加 Padding
const _: () = assert!(mem::size_of::<AddOrderMessage>() == 36);
```

**注意**: ITCH 协议中的 Timestamp 是 48-bit (6字节)，而 Rust 没有 `u48`。直接映射 `u64` 会错位。
**正确做法**: 定义为 `[u8; 6]`，并在 Getter 方法中转换。

```rust
#[repr(C, packed)]
pub struct AddOrderMessageCorrect {
    // ... 前面的字段
    pub timestamp_bytes: [u8; 6],
    // ... 后面的字段
}

impl AddOrderMessageCorrect {
    #[inline(always)]
    pub fn timestamp(&self) -> u64 {
        // 大端序处理
        let b = self.timestamp_bytes;
        ((b[0] as u64) << 40) | ((b[1] as u64) << 32) |
        ((b[2] as u64) << 24) | ((b[3] as u64) << 16) |
        ((b[4] as u64) << 8)  | (b[5] as u64)
    }
}
```

### 1.2 零拷贝解析

```rust
pub fn handle_packet(buffer: &[u8]) {
    // 假设 buffer[0] 是 'A'
    if buffer[0] == b'A' {
        let msg = unsafe {
            // SAFETY: 
            // 1. 确保 buffer 长度足够
            // 2. 确保指针按照 align_of::<AddOrderMessage>() 对齐 (packed 为 1，所以总是对齐)
            &*(buffer.as_ptr() as *const AddOrderMessageCorrect)
        };
        
        process_order(msg);
    }
}
```

## 2. 字节序 (Endianness)

网络协议通常是大端序 (Big Endian)，而 x86 CPU 是小端序 (Little Endian)。
这意味着 `u32` 不能直接读，必须 `u32::from_be()`。

```rust
impl AddOrderMessageCorrect {
    #[inline(always)]
    pub fn price(&self) -> u32 {
        // 读取未对齐的字段 (packed struct 的字段通常是未对齐的)
        let val = unsafe { std::ptr::read_unaligned(&self.price_raw) };
        u32::from_be(val)
    }
}
```
**性能提示**: 现代 x86 CPU 的 `BSWAP` 指令非常快（1个周期）。不用担心字节序转换的开销。

## 3. SBE (Simple Binary Encoding)

SBE 是 FIX Trading Community 推出的二进制标准，旨在取代 FIX。它比 ITCH 复杂，因为它支持 Schema 和 Template。

### 3.1 核心概念
- **Schema**: XML 文件，定义消息结构。
- **Block**: 固定长度的根部分。
- **Repeating Groups**: 重复组（如行情快照中的多个档位）。
- **Var Data**: 变长字符串（放在最后）。

### 3.2 解析策略
对于 SBE，手写 struct 太繁琐且容易出错。通常使用代码生成器 (Code Generator)。
Rust 生态中有 `sbe-tool` 类似的库，或者你可以写一个简单的 Python 脚本，将 XML Schema 转换为 Rust `struct`。

```rust
// 生成的代码示例
#[repr(C, packed)]
pub struct MarketDataSnapshotFullRefresh {
    pub header: MessageHeader,
    pub security_id: u64,
    pub no_md_entries: u8, // Repeating Group Count
    // Group 的内容紧跟其后，但无法在 struct 中直接定义，因为长度可变
}

// 访问 Repeating Group 需要指针偏移
impl MarketDataSnapshotFullRefresh {
    pub fn entries(&self) -> MdEntryIterator {
        let ptr = (self as *const Self as usize + mem::size_of::<Self>()) as *const u8;
        MdEntryIterator::new(ptr, self.no_md_entries)
    }
}
```

## 4. 常见陷阱

1.  **Unaligned Access (未对齐访问)**:
    在 `#[repr(packed)]` 结构体中引用字段（如 `&msg.price`）是未定义行为 (UB)，甚至在某些架构上会导致 CPU 异常 (Bus Error)。
    **必须** 使用值拷贝 (`msg.price`) 或者 `std::ptr::read_unaligned`。

2.  **Bounds Checking (边界检查)**:
    `unsafe` 指针转换是最快的，也是最危险的。如果你收到了一个只有 10 字节的包，却强转为 36 字节的结构体，你会读取到越界内存（Segfault 或数据污染）。
    **必须** 在 `unsafe` 块之前检查 `buffer.len() >= size_of::<T>()`。

---
下一章：[FIX 协议解析 (FIX Protocol)](fix.md)

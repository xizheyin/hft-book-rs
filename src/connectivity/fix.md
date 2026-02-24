# FIX 协议解析 (FIX Protocol)

FIX (Financial Information eXchange) 是金融界的“通用语言”。尽管它很老（1992年诞生）、很冗余、解析很慢，但它无处不在。
对于 HFT 而言，FIX 主要用于**Session 管理**（登录、心跳）和**私有下单接口**。即使你有 OUCH 这样的二进制下单口，通常也需要 FIX 来进行盘后对账或处理 Drop Copy。

本章的目标是：写一个比开源库快 10 倍的 FIX 解析器。

## 1. 为什么标准库慢？

标准的 FIX 解析器（如 QuickFIX）通常这样做：
1.  读取 Socket 到 `String`。
2.  用 `split('\x01')` 切割成 `Vec<String>`。
3.  用 `split('=')` 切割成 Key-Value 对。
4.  把 Value 解析为 `int` 或 `double`。
5.  放到 `HashMap<String, String>` 中。

这里充满了**内存分配 (Allocation)** 和 **数据拷贝 (Copy)**。在 Rust 中，这简直是犯罪。

## 2. 零分配解析 (Zero-Allocation Parsing)

我们的原则是：
- **In-place Parsing**: 直接在接收缓冲区上操作。
- **No Strings**: 使用 `&[u8]` 切片代替 `String`。
- **No HashMap**: 对于已知字段（如 Tag 35 MsgType），直接用 `match` 或数组索引。

### 2.1 核心数据结构

我们不需要把整个 FIX 消息解析成一个通用的 Map。我们只需要提取我们关心的字段。

```rust
use nom::{
    bytes::complete::{tag, take_until},
    character::complete::{char, u32 as parse_u32},
    sequence::{preceded, separated_pair},
    IResult,
};

#[derive(Debug)]
struct FixHeader<'a> {
    begin_string: &'a [u8], // Tag 8
    body_length: u32,       // Tag 9
    msg_type: &'a [u8],     // Tag 35
}

// 示例消息: 8=FIX.4.2^9=12^35=D^...
```

### 2.2 使用 Nom 解析

`nom` 是 Rust 中强大的 Parser Combinator 库。虽然它主要用于功能性，但如果用得好，性能也非常强劲。

```rust
const SOH: u8 = 0x01; // Start of Header

fn parse_tag_value(input: &[u8]) -> IResult<&[u8], (u32, &[u8])> {
    let (input, (tag_id, value)) = separated_pair(
        parse_u32,      // 解析 Tag ID (如 35)
        char('='),      // 分隔符
        take_until("\x01") // 读取直到 SOH
    )(input)?;

    // 跳过 SOH
    let (input, _) = char(SOH as char)(input)?;
    
    Ok((input, (tag_id, value)))
}
```

### 2.3 状态机解析 (State Machine)

对于极致性能，手写状态机通常比组合子更快。我们可以遍历字节流，寻找 `=` 和 `\x01`。

```rust
pub struct FastFixParser<'a> {
    buffer: &'a [u8],
}

impl<'a> FastFixParser<'a> {
    pub fn new(buffer: &'a [u8]) -> Self {
        Self { buffer }
    }

    // 迭代器风格，零分配
    pub fn next_field(&mut self) -> Option<(u32, &'a [u8])> {
        if self.buffer.is_empty() {
            return None;
        }

        // 查找 '='
        let eq_pos = self.buffer.iter().position(|&b| b == b'=')?;
        // 解析 Tag (简单 atoi)
        let tag_bytes = &self.buffer[..eq_pos];
        let tag_id = atoi_simd(tag_bytes); // 假设有个 SIMD 优化的 atoi

        // 查找 SOH
        let value_start = eq_pos + 1;
        let soh_pos = self.buffer[value_start..].iter().position(|&b| b == SOH)?;
        let value = &self.buffer[value_start..value_start + soh_pos];

        // 推进 buffer 指针
        self.buffer = &self.buffer[value_start + soh_pos + 1..];

        Some((tag_id, value))
    }
}
```

## 3. 数值转换优化

FIX 协议中大量的 CPU 时间花在 `atoi` (ASCII to Integer) 和 `ftoa` (Float to ASCII) 上。
标准库的 `parse()` 很安全，但对于 HFT 来说太慢了。

### 3.1 整数解析 (SIMD)
对于 Tag ID (如 "35") 和整数数量 (Tag 38)，我们可以用简单的循环展开或 SIMD。

```rust
#[inline(always)]
fn parse_u32_fast(bytes: &[u8]) -> u32 {
    let mut result = 0;
    for &b in bytes {
        result = result * 10 + (b - b'0') as u32;
    }
    result
}
```

### 3.2 浮点数陷阱
FIX 中的价格 (Tag 44) 是文本浮点数（如 "100.50"）。
**永远不要用 `f64` 存储价格**。因为 `0.1 + 0.2 != 0.3`。
在 HFT 中，我们通常使用**定点数 (Fixed Point)**，即 `price * 10^8` 存为 `i64`。

```rust
#[inline(always)]
fn parse_price_to_i64(bytes: &[u8]) -> i64 {
    // 手写解析逻辑：
    // 1. 找到小数点位置
    // 2. 解析整数部分
    // 3. 解析小数部分并补齐 0
    // ...
}
```

## 4. 常见陷阱

1.  **校验和 (Checksum)**:
    Tag 10 (Checksum) 是最后一个字段。验证它需要遍历整个消息计算 sum % 256。
    **优化**: 在收到包的同时（网卡 DMA 到内存后），如果可能，利用 SIMD 并行计算。或者，如果在可信内网，可以**跳过校验**（风险自负）。

2.  **粘包与拆包**:
    TCP 是流式协议。你可能会一次 `recv` 收到半个 FIX 消息，或者 2.5 个消息。
    **必须** 维护一个 Ring Buffer，处理跨包边界的情况。先解析 Tag 9 (BodyLength)，确定完整消息长度。

3.  **GC 暂停**:
    虽然 Rust 没有 GC，但如果你在热路径上频繁 `Vec::push` 导致扩容 (realloc)，效果和 GC 暂停一样糟糕。**预分配**所有容器。

---
下一章：[市场数据处理 (Market Data)](../connectivity/market_data.md)

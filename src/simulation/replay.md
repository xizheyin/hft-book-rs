# 历史数据回放 (Data Replay)

对于 HFT 而言，历史数据（Historical Data）就是金矿。高质量的 Tick 级数据（甚至 PCAP 级数据）是策略研发的基础。

本章将讨论如何高效地存储、读取和回放海量的市场数据。

## 1. 数据格式选择

在存储数百 TB 的行情数据时，CSV 绝对不是一个好选择。我们需要更紧凑、解析更快的二进制格式。

### 1.1 常见格式对比

| 格式 | 优点 | 缺点 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **CSV** | 人类可读，通用性强 | 体积大，解析慢，精度丢失 | 少量数据的快速验证 |
| **HDF5** | 支持层级结构，压缩率高，Pandas 友好 | 并发写入支持差，Rust 生态一般 | 每日收盘后的数据归档 |
| **Parquet** | 列式存储，压缩率极高，查询快 | 写入开销大，不适合流式追加 | 大规模离线分析 (Spark/Presto) |
| **Raw Binary** | **读写最快**，体积最小 | 缺乏元数据，跨平台兼容性差 | **HFT 回测与实盘记录** |

对于 HFT 回测，我们通常选择 **Raw Binary**（直接将 Rust 结构体 `这种` 到磁盘）或 **PCAP**（原始网络包）。

### 1.2 自定义二进制格式设计

```rust
#[repr(C, packed)]
struct TickHeader {
    magic: u32,      // 魔数，用于校验
    version: u16,    // 版本号
    symbol_id: u16,  // 标的 ID
    timestamp: u64,  // 纳秒级时间戳
}

#[repr(C, packed)]
struct TickData {
    price: i64,      // 价格 (定点数)
    qty: u32,        // 数量
    flags: u8,       // 买卖方向等标志位
}
```

使用 `#[repr(C, packed)]` 可以确保内存布局紧凑且与 C 语言兼容，允许我们直接通过 `mmap` 读取文件。

## 2. 高性能数据读取：Memory Mapping (mmap)

当数据文件达到几十 GB 时，普通的文件 I/O (`read`) 会产生大量的系统调用和内存拷贝。

`mmap` 允许我们将文件直接映射到进程的虚拟内存空间。操作系统会负责按需加载（Page Fault）和页面缓存（Page Cache）。

### 2.1 Rust 中使用 memmap2

```rust
use memmap2::MmapOptions;
use std::fs::File;
use std::slice;

struct MmapReader {
    mmap: memmap2::Mmap,
    cursor: usize,
}

impl MmapReader {
    fn new(path: &str) -> std::io::Result<Self> {
        let file = File::open(path)?;
        let mmap = unsafe { MmapOptions::new().map(&file)? };
        Ok(Self { mmap, cursor: 0 })
    }

    fn next_tick(&mut self) -> Option<&TickData> {
        if self.cursor + std::mem::size_of::<TickData>() > self.mmap.len() {
            return None;
        }

        let tick = unsafe {
            let ptr = self.mmap.as_ptr().add(self.cursor) as *const TickData;
            &*ptr
        };
        
        self.cursor += std::mem::size_of::<TickData>();
        Some(tick)
    }
}
```

**性能优势**:
1.  **零拷贝**: 数据直接从磁盘缓存映射到用户空间，无需内核到用户的拷贝。
2.  **减少系统调用**: 无需频繁调用 `read`。
3.  **操作系统优化**: OS 会利用空闲内存自动预读（Read-ahead）。

## 3. PCAP 回放 (Packet Capture Replay)

最硬核的回测方式是直接回放抓包文件（PCAP）。这能还原最真实的网络环境，包括 TCP 握手、丢包重传、多播乱序等。

### 3.1 为什么需要 PCAP 回放？

- **验证解析器**: 确保你的解析逻辑能处理所有边缘情况。
- **还原微观结构**: 交易所的消息往往是打包发送的（一个 UDP 包包含多个 Update）。PCAP 能还原这种打包结构。
- **时序精确**: PCAP 包含硬件打的时间戳（Hardware Timestamping），精度可达纳秒级。

### 3.2 Rust 实现

我们可以使用 `pcap` crate，或者手写解析器（推荐，为了性能）。

```rust
// PCAP Global Header (24 bytes)
struct PcapHeader {
    magic_number: u32,
    version_major: u16,
    version_minor: u16,
    thiszone: i32,
    sigfigs: u32,
    snaplen: u32,
    network: u32,
}

// PCAP Packet Header (16 bytes)
struct PacketHeader {
    ts_sec: u32,
    ts_usec: u32,
    incl_len: u32, // 保存的长度
    orig_len: u32, // 原始长度
}
```

## 4. 甚至... FPGA 硬件回放？

顶级 HFT 团队会使用 FPGA 卡（如 Solarflare 或 ExaNIC）进行硬件级回放。
将 PCAP 文件加载到 FPGA 的大容量内存（或 NVMe SSD）中，然后让 FPGA 按照原始时间间隔将包发送到交易服务器的网卡上。

这允许我们在不修改任何生产代码的情况下，对整个交易系统进行压力测试。

## 5. 常见陷阱

1.  **字节序 (Endianness)**:
    x86 是小端序 (Little Endian)，而网络协议通常是大端序 (Big Endian)。直接 `transmute` 结构体时必须小心。
    **解决**: 在文件头写入魔数（Magic Number）来检测字节序，或者强制使用 Little Endian 存储。

2.  **磁盘 IO 瓶颈**:
    即使是 NVMe SSD，读取速度也有上限（约 3-5 GB/s）。如果回测引擎处理速度超过磁盘，CPU 就会空转。
    **解决**: 使用压缩（如 Zstd）以 CPU 换 IO，或者构建多磁盘 RAID 0 阵列。

3.  **时间旅行 (Look-ahead)**:
    在使用 `mmap` 时，很容易不小心读取了 `cursor` 之后的数据。
    **解决**: 封装严格的迭代器接口，禁止随机访问。

## 6. 延伸阅读

- [KDB+ / q](https://kx.com/) - 华尔街标准的时序数据库，了解其设计理念非常有益。
- [Apache Arrow](https://arrow.apache.org/) - 现代列式内存格式标准，Rust 实现非常高效。

---
下一章：我们将讨论如何模拟高精度的时钟与定时器 —— [高精度时钟模拟 (Clock Simulation)](clock.md)。

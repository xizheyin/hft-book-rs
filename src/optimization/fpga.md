# FPGA 交互 (Rust Bindings)

在极致的 HFT 军备竞赛中，通用 CPU (x86) 即使经过所有优化，也面临物理瓶颈（PCIe 往返延迟、OS 调度、缓存未命中）。当软件优化达到极限（~2-5µs Tick-to-Trade），下一步就是硬件加速。

现场可编程门阵列 (FPGA) 允许我们将网络协议解析、预交易风控甚至核心执行逻辑“烧录”到硬件电路中，实现 **< 1µs** 甚至 **< 200ns** 的线速延迟。

本章不讨论 Verilog/VHDL 编写，而是聚焦于 **Rust 如何高效地与 FPGA 交互**。

## 理论架构：混合系统 (Hybrid Architecture)

通常我们不会把所有逻辑都放入 FPGA（开发成本过高），而是采用混合架构：

1.  **Fast Path (FPGA)**:
    - 处理 L1 市场数据（过滤、归一化）。
    - 简单的触发策略（如 Sniper, Pegging）。
    - 预交易风控（硬性限额）。
    - 订单发送（FIX/Binary 编码）。
2.  **Slow Path (Rust/CPU)**:
    - 复杂策略计算（机器学习推理、多市场套利）。
    - 仓位管理与对账。
    - 异常处理。
    - 配置更新。

Rust 与 FPGA 的通信通常通过 **PCIe** 总线，涉及两种主要机制：
- **MMIO (Memory Mapped I/O)**: 用于控制寄存器（配置、状态读取）。
- **DMA (Direct Memory Access)**: 用于大批量数据传输（行情流、订单流）。

## 核心实现：用户态驱动 (Userspace Driver)

为了避免内核系统调用的开销，我们通常使用 UIO (Userspace I/O) 或 VFIO 技术，将 FPGA 的 PCIe BAR 空间直接映射到用户态进程的虚拟内存中。

### 1. MMIO：像访问内存一样访问硬件

假设 FPGA 暴露了一个控制寄存器（Bar 0, Offset 0x100），写入 1 表示启动，写入 0 表示停止。

```rust
use std::fs::OpenOptions;
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::io::AsRawFd;
use memmap2::{MmapOptions, MmapMut};

pub struct FpgaDevice {
    bar0: MmapMut,
}

impl FpgaDevice {
    pub fn new(uio_path: &str) -> Self {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(libc::O_SYNC) // 确保写入不被 CPU 缓存
            .open(uio_path)
            .expect("Failed to open UIO device");

        let mmap = unsafe {
            MmapOptions::new()
                .len(4096) // 假设 BAR0 大小
                .map_mut(&file)
                .expect("Failed to mmap BAR0")
        };

        Self { bar0: mmap }
    }

    /// 写入 32 位寄存器
    /// offset 必须是 4 的倍数
    #[inline(always)]
    pub unsafe fn write_reg(&mut self, offset: usize, value: u32) {
        let ptr = self.bar0.as_mut_ptr().add(offset) as *mut u32;
        // 使用 volatile 写入，防止编译器优化
        std::ptr::write_volatile(ptr, value);
    }

    /// 读取 32 位寄存器
    #[inline(always)]
    pub fn read_reg(&self, offset: usize) -> u32 {
        let ptr = self.bar0.as_ptr() as *const u8;
        unsafe {
            let reg_ptr = ptr.add(offset) as *const u32;
            std::ptr::read_volatile(reg_ptr)
        }
    }
}
```

### 2. 零拷贝 DMA 环形缓冲区

对于高吞吐量的行情数据，FPGA 会通过 DMA 直接将数据写入主机的 RAM。我们需要在 Rust 中分配一块对齐的内存，并将其物理地址告诉 FPGA。

```rust
#[repr(C, align(64))] // 缓存行对齐
struct DmaDescriptor {
    // 硬件定义的描述符格式
    addr: u64,
    len: u32,
    flags: u32,
}

struct RingBuffer {
    buffer: Vec<u8>,
    descriptors: Vec<DmaDescriptor>,
}

impl RingBuffer {
    pub fn new(size: usize) -> Self {
        // 在生产环境中，这里需要使用 hugepages (大页内存)
        // 并通过 /proc/self/pagemap 获取物理地址
        let buffer = vec![0u8; size]; 
        
        // ... 初始化逻辑
        Self { buffer, descriptors: vec![] }
    }
    
    // 轮询是否有新数据
    pub fn poll(&self) -> Option<&[u8]> {
        // 检查描述符状态位 (Owned by Host?)
        // ...
        None
    }
}
```

## 实战案例：FPGA 辅助的订单发送

在这个场景中，Rust 策略决定下单，但为了节省 PCI 往返时间，我们只发送核心参数（Price, Qty, Side），由 FPGA 填充协议头（FIX/OUCH）并计算校验和。

```rust
#[repr(C, packed)]
struct FastOrderCmd {
    symbol_index: u16,
    side: u8, // 'B' or 'S'
    padding: u8,
    price: u64, // 定点数
    qty: u32,
}

impl FpgaDevice {
    pub fn send_order(&mut self, cmd: FastOrderCmd) {
        // 将命令直接写入 FPGA 的命令队列寄存器 (Doorbell)
        // 这通常比通过网卡发包快得多
        unsafe {
            let cmd_ptr = &cmd as *const _ as *const u64;
            // 假设命令队列位于 BAR0 偏移 0x2000，且支持 64 位原子写入
            self.write_reg64(0x2000, *cmd_ptr); 
            self.write_reg64(0x2008, *cmd_ptr.add(1));
        }
    }
}
```

## 常见陷阱

1.  **内存序 (Memory Ordering)**: CPU 和 FPGA 之间的内存交互必须小心处理内存屏障 (`std::sync::atomic::fence`)。
2.  **缓存一致性 (Cache Coherency)**: DMA 写入通常是 coherent 的，但如果不小心，CPU 可能会读取到 L3 缓存中的旧数据。
3.  **对齐 (Alignment)**: PCIe 传输通常要求 64 字节甚至 4KB 对齐。

## 现有生态

- **Xilinx XDMA / QDMA**: 官方提供了 Linux 驱动，Rust 可以通过 `ioctl` 与之交互。
- **ExaSock / Solarflare**: 提供了基于 Socket API 的透明加速，但如果需要更细粒度的控制，仍需直接操作硬件。

FPGA 开发周期长且昂贵，但在某些 winner-takes-all 的策略中，它是唯一的生存方式。
